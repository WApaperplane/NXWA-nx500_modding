/* eplut5.c — NX-KS2 步骤 5：直接用 CMA 区物理内存做 3DLUT 缓冲
 *
 * ★★★ 这是绕过 SMA 驱动未probe 问题的方案。
 *   SMA_ALLOC 走内核 cma_alloc，而 sma_dev 为 NULL（驱动没 probe）。
 *   但 CMA 区本身是内核声明过的合法内存（0x94000000..0x9d000000），
 *   且实测 98.6% 空闲 ⇒ 可以直接用 /dev/mem 借用。
 *
 * ★ 三阶段安全设计：
 *   check <addr>   只读 dump，确认该地址全零（零风险）
 *   put<addr> <mode>  写入 LUT + 挂到 3DLUT + 脉冲（会改画面）
 *   restore            把 +0x0c 恢复成 0x81115200
 *
 * 用法:
 *   eplut5 check 0x9a00000     只读检查
 *   eplut5 put   0x9a00000 0   identity（最安全）
 *   eplut5 put   0x9a00000 3   R/G 反相（效果最明显）
 *   eplut5 restore
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <errno.h>

#include <media/drime5/ep/d5_ep_ioctl.h>

#define R_START     0x08
#define R_LUT0_ADDR 0x0c
#define NSLOT       16
#define SLOTSZ      0x100
#define ORIG_LUT    0x81115200UL      /* ★ 实测的原始值 */

static struct ep_reg_phys_info *blk(struct ep_reg_info *p, int i)
{
    return (struct ep_reg_phys_info *)((char *)p + i * sizeof(struct ep_reg_phys_info));
}

static void gen_lut(unsigned char *buf, int mode)
{
    int i;
    memset(buf, 0, SLOTSZ);
    for (i = 0; i < 256; i++) {
        unsigned char r, g, bl;
        switch (mode) {
        case 0:  r = g = bl = (unsigned char)i; break;
        case 1:  r = g = bl = (unsigned char)(i + 51); break;
        case 2:  r = g = bl = (unsigned char)(i > 51 ? i - 51 : 0); break;
        case 3:  r = (unsigned char)i; g = (unsigned char)(255 - i); bl = 0; break;
        case 4:  { int y = (i * 77) / 255; r = g = bl = (unsigned char)y; } break;
        default: r = g = bl = (unsigned char)i; break;
        }
        buf[i * 3 + 0] = r;
        buf[i * 3 + 1] = g;
        buf[i * 3 + 2] = bl;
    }
}

int main(int argc, char **argv)
{
    struct ep_reg_info info;
    unsigned long pa, size, map_len, target;
    volatile unsigned *b;
    unsigned char *mb;
    int fd_mem, fd_ep, i;
    const char *cmd;

    if (argc < 3) {
        printf("用法:\n");
        printf("  %s check <addr>          只读检查该 CMA 地址\n", argv[0]);
        printf("  %s put<addr> <mode>      写入 LUT（0=id 1=亮 2=暗 3=R/G反相 4=灰阶）\n", argv[0]);
        printf("  %s restore               恢复原值\n", argv[0]);
        return 1;
    }
    cmd = argv[1];
    target = strtoul(argv[2], NULL, 0);

    fd_mem = open("/dev/mem", O_RDWR | O_SYNC);
    if (fd_mem < 0) { printf("open /dev/mem: %s\n", strerror(errno)); return 2; }
    printf("open(/dev/mem, O_RDWR) = %d ★\n", fd_mem);

    /* ---------- check：只读 ---------- */
    if (strcmp(cmd, "check") == 0) {
        volatile unsigned *p;
        int nz = 0;
        p = mmap(NULL, 4096, PROT_READ, MAP_SHARED, fd_mem, (off_t)(target & ~4095UL));
        if (p == MAP_FAILED) { printf("mmap 失败: %s\n", strerror(errno)); return 3; }
        printf("\n--- 只读 dump 0x%08lx（页内偏移 0x%lx）---\n", target,
               target & 4095UL);
        for (i = 0; i < 16; i++) {
            unsigned v = p[((target & 4095UL) / 4) + i];
            printf("  +0x%03x  0x%08x  %s\n", i * 4, v, v ? "★非零" : "");
            if (v) nz++;
        }
        munmap((void *)p, 4096);
        printf("\n非零 word = %d/16\n", nz);
        printf(nz == 0 ? "★ 全零 —— 可以安全借用\n" : "⚠ 有非零 —— 换地址\n");
        close(fd_mem);
        return 0;
    }

    /* ---------- 打开 EP ---------- */
    fd_ep = open("/dev/drime5_ep", O_RDWR);
    if (fd_ep < 0) { printf("open EP: %s\n", strerror(errno)); return 4; }
    if (ioctl(fd_ep, EP_IOCTL_GET_PHYS_REG_INFO, &info) < 0) {
        printf("ioctl: %s\n", strerror(errno));
        return 5;
    }
    pa = blk(&info, 8)->reg_start_addr;
    size = blk(&info, 8)->reg_size;
    map_len = (size + 4095) & ~4095UL;
    mb = mmap(NULL, map_len, PROT_READ | PROT_WRITE, MAP_SHARED, fd_ep, (off_t)pa);
    if (mb == MAP_FAILED) { printf("mmap EP 失败\n"); return 6; }
    b = (volatile unsigned *)mb;
    printf("3dlut @0x%08lx = %p\n", pa, (void *)mb);

    if (strcmp(cmd, "restore") == 0) {
        printf("\n恢复 16 槽 +0x0c <- 0x%08lx\n", ORIG_LUT);
        for (i = 0; i < NSLOT; i++)
            b[(i * SLOTSZ + R_LUT0_ADDR) / 4] = (unsigned)ORIG_LUT;
        b[R_START / 4] = 0x100;
        usleep(2000);
        printf("读回 slot0 = 0x%08x\n", b[R_LUT0_ADDR / 4]);
        printf("已恢复并发脉冲\n");
        goto out;
    }

    /* ---------- put ---------- */
    if (strcmp(cmd, "put") == 0) {
        int mode = (argc > 3) ? atoi(argv[3]) : 0;
        unsigned long mbase = target & ~4095UL;
        volatile unsigned char *lp;
        int nz = 0, bad;

        printf("\n--- 步骤 1：只读确认目标区全零 ---\n");
        lp = mmap(NULL, 4096, PROT_READ, MAP_SHARED, fd_mem, (off_t)mbase);
        if (lp == MAP_FAILED) { printf("mmap 失败: %s\n", strerror(errno)); goto out; }
        for (i = 0; i < 16; i++)
            if (lp[((target & 4095UL) / 4) + i]) nz++;
        printf("  0x%08lx 非零 word = %d/16 %s\n", target, nz,
               nz ? "⚠ 有数据，换地址" : "★ 全零，可用");
        munmap((void *)lp, 4096);
        if (nz) {
            printf("  ⇒ 中止（不写非空闲区）\n");
            goto out;
        }

        printf("\n--- 步骤 2：生成并写入 LUT（mode=%d）---\n", mode);
        lp = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, fd_mem, (off_t)mbase);
        if (lp == MAP_FAILED) { printf("mmap RW 失败: %s\n", strerror(errno)); goto out; }
        {
            unsigned char *dst = (unsigned char *)lp + (target & 4095UL);
            unsigned char tmp[SLOTSZ];
            gen_lut(tmp, mode);
            memcpy(dst, tmp, SLOTSZ);
            bad = 0;
            for (i = 0; i < SLOTSZ; i++)
                if (dst[i] != tmp[i]) { bad = 1; break; }
            printf("  已写入 256 字节，读回校验 %s\n", bad ? "★不一致" : "一致 ✓");
            printf("  前 16 字节: ");
            for (i = 0; i < 16; i++) printf("%02x ", dst[i]);
            printf("\n");
            /* 恢复权限为只读语义上不重要（映射已建立），直接解除 */
            munmap((void *)lp, 4096);
        }

        printf("\n--- 步骤 3：挂到 3DLUT 16 槽 +0x0c = 0x%08lx ---\n", target);
        for (i = 0; i < NSLOT; i++)
            b[(i * SLOTSZ + R_LUT0_ADDR) / 4] = (unsigned)target;
        printf("  读回 slot0 = 0x%08x\n", b[R_LUT0_ADDR / 4]);

        printf("\n--- 步骤 4：启动脉冲 ---\n");
        b[R_START / 4] = 0x100;
        usleep(3000);
        printf("  +0x08 = 0x%08x %s\n", b[R_START / 4],
               b[R_START / 4] == 0 ? "(硬件自清)" : "(待清)");

        printf("\n★★★ 请看取景器（mode=%d）：画面有变化吗？\n", mode);
        printf("    mode: 0=恒等 1=提亮20%% 2=压暗 3=R/G反相 4=灰阶\n", mode);
        printf("    恢复：%s restore 0x81115200\n", argv[0]);
    }

out:
    munmap(mb, map_len);
    close(fd_ep);
    close(fd_mem);
    return 0;
}