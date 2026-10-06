/* eplut6.c — NX-KS2 步骤 6：通过 /dev/d5_sma 的 mmap 拿可写 CMA 内存
 *
 * ★★★★ 这是绕过两条死路的正解：
 *   死路 1  /dev/mem 写 CMA      → STRICT_DEVMEM ⇒ SIGSEGV
 *   死路 2  SMA_ALLOC 分配      → sma_dev==NULL（驱动 probe 分配失败）
 *
 * ★★ 正解：drivers/media/video/drime5/sma/d5_sma_ioctl.c:240
 *      int sma_mmap(struct file *file, struct vm_area_struct *vma) {
 *          offset = vma->vm_pgoff << PAGE_SHIFT;   ← ★ 直接把 mmap offset
 *                                                       当物理地址用！
 *          offset = __phys_to_pfn(offset);
 *          remap_pfn_range(vma, vm_start, offset, size, ...);
 *      }
 *   ★ 它【不检查 sma_dev、不验证地址范围】⇒ 可以 mmap 任意物理地址。
 *   ★ 走的是设备 fd 的 mmap，不是 /dev/mem ⇒ 不受 STRICT_DEVMEM 限制。
 *
 * ★ 与 EP 块同一个道理：EP 块能写是因为走 d5_ep_mmap 的 remap_pfn_range。
 *
 * 用法:
 *   eplut6 check <phys>            只读检查
 *   eplut6 put<phys> <mode>        写入 LUT（会改画面）
 *   eplut6 restore                 恢复 +0x0c
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
#define ORIG_LUT    0x81115200UL

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
    int fd_sma, fd_ep, i, nz;
    const char *cmd;
    volatile unsigned char *lp;

    if (argc < 3) {
        printf("用法: %s check <phys> | put <phys> <mode> | restore\n", argv[0]);
        return 1;
    }
    cmd = argv[1];
    target = strtoul(argv[2], NULL, 0);

    fd_sma = open("/dev/d5_sma", O_RDWR);
    if (fd_sma < 0) { printf("open /dev/d5_sma: %s\n", strerror(errno)); return 2; }
    printf("open(/dev/d5_sma, O_RDWR) = %d ★\n", fd_sma);

    /* ============ check：只读 ============ */
    if (strcmp(cmd, "check") == 0) {
        nz = 0;
        /*★★ 关键：offset 传【物理地址原值】，内核会自己 >>PAGE_SHIFT */
        lp = mmap(NULL, 4096, PROT_READ, MAP_SHARED, fd_sma, (off_t)target);
        if (lp == MAP_FAILED) {
            printf("mmap(phys=0x%08lx) 失败: %s\n", target, strerror(errno));
            return 3;
        }
        printf("\n--- 只读 dump 0x%08lx ---\n", target);
        for (i = 0; i < 16; i++) {
            unsigned v = lp[i];
            printf("  +0x%03x  0x%08x  %s\n", i * 4, v, v ? "★非零" : "");
            if (v) nz++;
        }
        munmap((void *)lp, 4096);
        printf("\n非零 word = %d/16 ⇒ %s\n", nz,
               nz ? "有数据，换地址" : "★ 全零，可借用");
        close(fd_sma);
        return 0;
    }

    /* ============ 打开 EP ============ */
    fd_ep = open("/dev/drime5_ep", O_RDWR);
    if (fd_ep < 0) { printf("open EP: %s\n", strerror(errno)); return 4; }
    if (ioctl(fd_ep, EP_IOCTL_GET_PHYS_REG_INFO, &info) < 0) {
        printf("ioctl: %s\n", strerror(errno)); return 5;
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
        goto out;
    }

    /* ============ put ============ */
    if (strcmp(cmd, "put") == 0) {
        int mode = (argc > 3) ? atoi(argv[3]) : 0;
        unsigned char tmp[SLOTSZ];

        /* 步骤 1：只读确认全零 */
        printf("\n--- 1. 只读确认 0x%08lx 全零 ---\n", target);
        lp = mmap(NULL, 4096, PROT_READ, MAP_SHARED, fd_sma, (off_t)target);
        if (lp == MAP_FAILED) { printf("mmap 失败: %s\n", strerror(errno)); goto out; }
        nz = 0;
        for (i = 0; i < 16; i++) if (lp[i]) nz++;
        printf("  非零 %d/16 %s\n", nz, nz ? "⚠ 中止" : "★ 全零，可用");
        munmap((void *)lp, 4096);
        if (nz) goto out;

        /* 步骤 2：可写映射 + 写 LUT */
        printf("\n--- 2. 映射为可写并写入 LUT（mode=%d）---\n", mode);
        lp = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, fd_sma, (off_t)target);
        if (lp == MAP_FAILED) {
            printf("  ★ mmap(PROT_WRITE) 失败: %s\n", strerror(errno));
            printf("  ⇒ 该设备可能只允许只读映射\n");
            goto out;
        }
        printf("  ★ mmap(PROT_WRITE) 成功 = %p\n", (void *)lp);
        gen_lut(tmp, mode);
        memcpy((void *)lp, tmp, SLOTSZ);
        printf("  已写入 256 字节，读回校验 %s\n",
               memcmp((void *)lp, tmp, SLOTSZ) ? "★不一致" : "一致 ✓");
        printf("  前 16 字节: ");
        for (i = 0; i < 16; i++) printf("%02x ", lp[i]);
        printf("\n");
        munmap((void *)lp, 4096);

        /* 步骤 3：挂到 3DLUT */
        printf("\n--- 3. 16 槽 +0x0c<- 0x%08lx ---\n", target);
        for (i = 0; i < NSLOT; i++)
            b[(i * SLOTSZ + R_LUT0_ADDR) / 4] = (unsigned)target;
        printf("  读回 slot0 = 0x%08x\n", b[R_LUT0_ADDR / 4]);

        /* 步骤 4：脉冲 */
        printf("\n--- 4. 启动脉冲 ---\n");
        b[R_START / 4] = 0x100;
        usleep(3000);
        printf("  +0x08 = 0x%08x\n", b[R_START / 4]);

        printf("\n★★★ 请看取景器（mode=%d，0=恒等 1=亮 2=暗 3=R/G反相 4=灰阶）\n", mode);
        printf("    恢复：%s restore 0x81115200\n", argv[0]);
    }

out:
    munmap(mb, map_len);
    close(fd_ep);
    close(fd_sma);
    return 0;
}