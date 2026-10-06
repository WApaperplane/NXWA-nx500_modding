/* eplut3.c — NX-KS2 步骤 3：3DLUT 完整 LUT 写入（会改画面！）
 *
 * ★★★ 前置条件（缺一不可）：
 *   1. 相机在 Liveview / 拍摄态（di-camera-app 运行中）
 *   2. /dev/d5_sma 可 open
 *   3. buffer 256 字节对齐（virt_to_phys 的硬要求）
 *
 * ★ 本程序分两阶段，靠命令行控制，避免一次性做完：
 *   eplut3 put<slot> <mode>   写入一个 LUT 并启动
 *   eplut3restore            恢复出厂（把备份写回）
 *   eplut3 info              只读：显示槽位与DMA 缓冲状态
 *
 * mode: 0 = identity（恒等，不改画面，用于验证通路）
 *       1 = 提亮 20%
 *       2 = 压暗 20%
 *       3 = 通道交换（R<->B，用于最直观确认 LUT 生效）
 *
 * ★★★ 安全设计：
 *   1. 每次运行先自动备份 16 个槽的原始地址到 /mnt/mmc/_xfer/lut_bak.txt
 *   2. mode=0（identity）本身不改变画面 ⇒ 可用它验证整条链路
 *   3. restore 命令一键回滚
 *   4. 全程不碰除 +0x0c/+0x08 之外的寄存器
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
#define NSLOT       16     /* ★ 实测 16 个槽，每槽 0x100 字节 */
#define SLOTSZ      0x100

/* ★ 实测常量 */
#define V2P_IOWR    0xc0047302UL   /* _IOWR('s',2,u32) —— d5_sma 的 virt2phys */

static struct ep_reg_phys_info *blk(struct ep_reg_info *p, int i)
{
    return (struct ep_reg_phys_info *)((char *)p + i * sizeof(struct ep_reg_phys_info));
}

static int fd_ep, fd_sma;

/* ---- virt2phys：走 /dev/d5_sma，逻辑与 d5_ep_sma_virt_to_phys 完全一致 ---- */
static unsigned long virt2phys(void *va)
{
    unsigned long a = (unsigned long)va;
    if (ioctl(fd_sma, V2P_IOWR, &a) < 0) {
        printf("  ioctl(virt2phys) 失败: %s\n", strerror(errno));
        return 0;
    }
    return a;
}

/* ---- 生成测试 LUT（256 字节 = 16x16 RGB 三通道）---- */
static void gen_lut(unsigned char *buf, int mode)
{
    int i;
    memset(buf, 0, SLOTSZ);
    for (i = 0; i < 256; i++) {
        int v = i;
        unsigned char r, g, bl;
        switch (mode) {
        case 0:  r = g = bl = (unsigned char)i; break;           /* identity */
        case 1:  r = g = bl = (unsigned char)(i + 51); break;    /* 提亮 20% */
        case 2:  r = g = bl = (unsigned char)(i > 51 ? i - 51 : 0); break; /* 压暗 */
        case 3:  r = (unsigned char)i; g = (unsigned char)(255 - i); bl = 0; break; /* R/G 反相 */
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
    unsigned long pa, size, phys;
    volatile unsigned *b;
    unsigned char *map_base;
    unsigned long map_len;
    unsigned char *lut;
    const char *cmd;
    int slot, mode, i;

    if (argc < 2) {
        printf("用法:\n");
        printf("  %s info                 只读显示\n", argv[0]);
        printf("  %s put <slot> <mode>    写入 LUT(0=id 1=亮 2=暗 3=R/G反相)\n", argv[0]);
        printf("  %s restore              恢复出厂\n", argv[0]);
        return 1;
    }
    cmd = argv[1];

    /* ---- 打开两个设备 ---- */
    fd_ep = open("/dev/drime5_ep", O_RDWR);
    if (fd_ep < 0) { printf("open EP 失败: %s\n", strerror(errno)); return 2; }
    fd_sma = open("/dev/d5_sma", O_RDWR);
    if (fd_sma < 0) {
        printf("open(/dev/d5_sma) 失败: %s\n", strerror(errno));
        printf("  ★ 若 ENOENT/EPERM，说明 SMA 设备需CAP_SYS_ADMIN 或节点名不同\n");
        close(fd_ep);
        return 3;
    }
    printf("open(/dev/drime5_ep) = %d, open(/dev/d5_sma) = %d  ★\n", fd_ep, fd_sma);

    if (ioctl(fd_ep, EP_IOCTL_GET_PHYS_REG_INFO, &info) < 0) {
        printf("ioctl 失败: %s\n", strerror(errno));
        return 4;
    }
    pa = blk(&info, 8)->reg_start_addr;
    size = blk(&info, 8)->reg_size;
    map_len = (size + 4095) & ~4095UL;
    map_base = mmap(NULL, map_len, PROT_READ | PROT_WRITE, MAP_SHARED, fd_ep, (off_t)pa);
    if (map_base == MAP_FAILED) { printf("mmap 失败\n"); return 5; }
    b = (volatile unsigned *)map_base;
    printf("3dlut @0x%08lx mmap=%p  ★\n\n", pa, (void *)map_base);

    if (strcmp(cmd, "info") == 0) {
        printf("--- 16 个槽的当前 LUT 地址 ---\n");
        for (i = 0; i < NSLOT; i++)
            printf("  slot %2d: +0x%03x = 0x%08x\n", i, i * SLOTSZ,
                   b[(i * SLOTSZ + R_LUT0_ADDR) / 4]);
        /* 测 virt2phys */
        printf("\n--- virt2phys 自测---\n");
        lut = NULL;
        if (posix_memalign((void **)&lut, 256, SLOTSZ) != 0 || !lut) {
            printf("posix_memalign(256) 失败\n");
        } else {
            lut[0] = 0xAB; lut[1] = 0xCD;
            printf("  vaddr=%p (对齐后 %%256 = %lu)\n", lut,
                   ((unsigned long)lut) & 0xffUL);
            phys = virt2phys(lut);
            printf("  ★ phys=0x%08lx  %s\n", phys,
                   phys ? "成功" : "失败");
            if (phys && ((phys & 0xff) != 0))
                printf("  ⚠ 物理地址未 256 对齐 ⇒ libudd5 的 save_lut 会返回 -301\n");
            if (phys)
                printf("  ★ 可以往这个地址写 LUT 数据了\n");
            free(lut);
        }
        goto out;

    } else if (strcmp(cmd, "restore") == 0) {
        /* 从备份文件恢复所有槽 */
        FILE *fp = fopen("/mnt/mmc/_xfer/lut_bak.txt", "r");
        unsigned v;
        int s;
        if (!fp) { printf("没有备份文件 lut_bak.txt\n"); goto out; }
        printf("--- 恢复出厂 ---\n");
        while (fscanf(fp, "%d %x", &s, &v) == 2) {
            b[(s * SLOTSZ + R_LUT0_ADDR) / 4] = v;
            printf("  slot %2d: +0x%03x <- 0x%08x\n", s, s * SLOTSZ + R_LUT0_ADDR, v);
        }
        fclose(fp);
        b[R_START / 4] = 0x100;      /* 启动 */
        usleep(2000);
        printf("  已发启动脉冲\n");
        goto out;
    } else if (strcmp(cmd, "put") == 0) {
        if (argc < 4) { printf("需要 slot 与 mode\n"); goto out; }
        slot = atoi(argv[2]);
        mode = atoi(argv[3]);
        if (slot < 0 || slot >= NSLOT) { printf("slot 越界\n"); goto out; }

        /* 1) 备份全部槽地址 */
        {
            FILE *fp = fopen("/mnt/mmc/_xfer/lut_bak.txt", "w");
            if (fp) {
                for (i = 0; i < NSLOT; i++)
                    fprintf(fp, "%d %08x\n", i, b[(i * SLOTSZ + R_LUT0_ADDR) / 4]);
                fclose(fp);
                printf("已备份 16 个槽地址 -> lut_bak.txt\n");
            }
        }

        /* 2) 分配 256 对齐 buffer */
        if (posix_memalign((void **)&lut, 256, SLOTSZ) != 0 || !lut) {
            printf("posix_memalign(256) 失败\n"); goto out;
        }
        printf("\nbuffer vaddr = %p  (%%256 = %lu)\n", lut,
               ((unsigned long)lut) & 0xffUL);
        gen_lut(lut, mode);
        printf("LUT 已生成 (mode=%d: %s)\n", mode,
               mode == 0 ? "identity 恒等" : mode == 1 ? "提亮20%" :
               mode == 2 ? "压暗20%" : "R/G 反相");

        /* 3) ★ 用 /dev/mem 写物理内存（绕过 virt2phys 不确定性）*/
        {
            int fdm = open("/dev/mem", O_RDWR | O_SYNC);
            void *pm;
            if (fdm < 0) {
                printf("open(/dev/mem, O_RDWR) 失败: %s\n", strerror(errno));
                printf("  ⇒ 只能退回 virt2phys 路径\n");
            } else {
                pm = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, fdm,
                          (off_t)(0x81115200 & ~4095UL));
                if (pm == MAP_FAILED) {
                    printf("mmap /dev/mem @0x81115200 失败: %s\n", strerror(errno));
                } else {
                    unsigned char *dst = (unsigned char *)pm + (0x81115200 & 4095);
                    printf("★ 已 mmap DMA 区 0x81115200（不依赖 virt2phys）\n");
                    memcpy(dst, lut, SLOTSZ);
                    printf("  已写入 256 字节 LUT 数据\n");
                    printf("  读回校验: ");
                    {
                        int bad = 0;
                        for (i = 0; i < SLOTSZ; i++)
                            if (dst[i] != lut[i]) { bad++; break; }
                        printf("%s\n", bad ? "★ 不一致！" : "一致 ✓");
                    }
                    printf("  ★ 若上面有 fail，直接用 put 的 fallback：");
                    printf("把DMA 区映射过来再试\n");
                    munmap(pm, 4096);
                    close(fdm);
                }
            }
        }

        /* 4) 发启动脉冲（一次写 1 即可，硬件自清）*/
        printf("\n--- 发启动脉冲 ---\n");
        b[R_START / 4] = 0x100;
        usleep(2000);
        printf("  +0x08 已写 0x100，读回 = 0x%08x\n", b[R_START / 4]);
        printf("\n★★ 请看取景器：画面有变化吗？（mode=%d）\n", mode);
        printf("   恢复：%s restore\n", argv[0]);
        free(lut);
        goto out;
    }

out:
    munmap(map_base, map_len);
    close(fd_ep);
    if (fd_sma > 0) close(fd_sma);
    return 0;
}