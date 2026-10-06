/* eplut10.c — NX-KS2 步骤 10：完整复刻 p7 固件的 6 步写入序列
 *
 * ★★★★ 这是唯一"逐行对照 p7 反编译"写的版本，不是猜的。
 *
 * p7 权威来源：raw8/p7/ghidra/53_all_pseudocode.c:617685  FUN_004a5e30
 *   if (*(char*)(param_1+1) == 1) {
 *       FUN_004cf3d4(1);              // ① OnOff
 *       FUN_004cf45c(0);              // ② ★★ 脉冲位先清 0
 *       FUN_004cf45c(1);              // ③ ★★ 再置 1← 启动
 *       switch (*(char*)(param_1+0xc)) { ... SetAddress ... }
 *       FUN_004cf414(ch);              // ④ 通道选择（bit[5:4]）
 *       FUN_004cf484(1);              // ⑤ ★★★ 读侧清理（mode1 → &=~0x100）
 *   }
 *
 * ★★★ 我之前漏了 ② 和 ⑤ —— 这就是"写了但画面不变"的原因。
 *
 * 寄存器定义（同文件641680+）：
 *   +0x000 OnOff   bit0        FUN_004cf3d4
 *   +0x004 bits[1:0] SelCbCr   FUN_004cf3fc
 *   +0x004 bits[5:4] SelLUTch  FUN_004cf414
 *   +0x004 bit8LUT0 src   FUN_004cf42c
 *   +0x004 bit12   LUT1 src   FUN_004cf444
 *   +0x008 bit0    写脉冲      FUN_004cf45c
 *   +0x008 bit8/bit4 读标志   FUN_004cf484
 *   +0x00c LUT0 数据地址ch=1   FUN_004cf4b4
 *   +0x010 LUT1 数据地址       FUN_004cf4b4
 *
 * 用法:
 *   eplut10 full <phys> <mode>   执行 6 步（mode: 0=恒等 1=偏红 2=偏蓝）
 *   eplut10 restore              恢复基线
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

#define R_ONOFF     0x000
#define R_CFG       0x004
#define R_PULSE     0x008
#define R_LUT0      0x00c

#define BASE_ONOFF  0x00000001UL
#define BASE_CFG    0x00000100UL
#define BASE_LUT    0x81115200UL

static struct ep_reg_phys_info *blk(struct ep_reg_info *p, int i)
{
    return (struct ep_reg_phys_info *)((char *)p + i * sizeof(struct ep_reg_phys_info));
}

static void gen_lut(unsigned char *buf, int mode)
{
    int i;
    memset(buf, 0, 32);                 /* ★ 铁律 51：只填 32 字节 */
    for (i = 0; i < 11; i++) {
        unsigned char v = (unsigned char)(i * 8);
        switch (mode) {
        case 0: buf[i*3+0]=v; buf[i*3+1]=v; buf[i*3+2]=v; break;
        case 1: buf[i*3+0]=(v>20?v-20:0); buf[i*3+1]=v; buf[i*3+2]=v; break; /* 压红 */
        case 2: buf[i*3+0]=v; buf[i*3+1]=v; buf[i*3+2]=(v>20?v-20:0); break; /* 压蓝 */
        default: buf[i*3+0]=v; buf[i*3+1]=v; buf[i*3+2]=v; break;
        }
    }
}

int main(int argc, char **argv)
{
    struct ep_reg_info info;
    unsigned long pa, size, map_len, target;
    volatile unsigned *b;
    unsigned char *mb;
    int fd_ep, i;
    unsigned v;

    if (argc < 3) {
        printf("用法: %s full <phys> <mode> | restore\n", argv[0]);
        return 1;
    }
    fd_ep = open("/dev/drime5_ep", O_RDWR);
    if (fd_ep < 0) { printf("open EP: %s\n", strerror(errno)); return 2; }
    if (ioctl(fd_ep, EP_IOCTL_GET_PHYS_REG_INFO, &info) < 0) {
        printf("ioctl: %s\n", strerror(errno)); return 3;
    }
    pa = blk(&info, 8)->reg_start_addr;
    size = blk(&info, 8)->reg_size;
    map_len = (size + 4095) & ~4095UL;
    mb = mmap(NULL, map_len, PROT_READ | PROT_WRITE, MAP_SHARED, fd_ep, (off_t)pa);
    if (mb == MAP_FAILED) { printf("mmap EP fail\n"); return 4; }
    b = (volatile unsigned *)mb;
    target = strtoul(argv[2], NULL, 0);

    printf("3dlut @0x%08lx = %p\n", pa, (void *)mb);
    printf("\n--- 写入前 ---\n");
    printf("  +0x000 = 0x%08x\n", b[R_ONOFF / 4]);
    printf("  +0x004 = 0x%08x\n", b[R_CFG / 4]);
    printf("  +0x008 = 0x%08x\n", b[R_PULSE / 4]);
    printf("  +0x00c = 0x%08x\n", b[R_LUT0 / 4]);

    if (strcmp(argv[1], "restore") == 0) {
        printf("\n=== 恢复基线 ===\n");
        b[R_ONOFF / 4] = (unsigned)BASE_ONOFF;
        b[R_CFG / 4]   = (unsigned)BASE_CFG;
        b[R_LUT0 / 4]  = (unsigned)BASE_LUT;
        b[R_PULSE / 4] &= ~1UL;
        b[R_PULSE / 4] |= 1UL;
        b[R_PULSE / 4] &= ~0x100UL;      /* ★ mode1 读侧清理 */
        usleep(3000);
        printf("  +0x000 = 0x%08x\n", b[R_ONOFF / 4]);
        printf("  +0x004 = 0x%08x\n", b[R_CFG / 4]);
        printf("  +0x008 = 0x%08x\n", b[R_PULSE / 4]);
        printf("  +0x00c = 0x%08x\n", b[R_LUT0 / 4]);
        goto out;
    }

    if (strcmp(argv[1], "full") == 0) {
        int mode = (argc > 3) ? atoi(argv[3]) : 0;

        /* ---- 步骤 0：LUT 数据写入 CMA ---- */
        printf("\n=== 步骤 0：LUT 数据 -> CMA 0x%08lx (mode=%d) ===\n", target, mode);
        {
            int fds = open("/dev/d5_sma", O_RDWR);
            unsigned char tmp[32];
            unsigned char *lp;
            if (fds < 0) { printf("open d5_sma: %s\n", strerror(errno)); goto out; }
            lp = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, fds, (off_t)target);
            if (lp == MAP_FAILED) { printf("mmap: %s\n", strerror(errno)); close(fds); goto out; }
            gen_lut(tmp, mode);
            memcpy(lp, tmp, 32);
            printf("  写入 32 字节，校验 %s\n", memcmp(lp, tmp, 32) ? "★不一致" : "一致 ✔");
            printf("  前 16: ");
            for (i = 0; i < 16; i++) printf("%02x ", lp[i]);
            printf("\n");
            munmap(lp, 4096);
            close(fds);
        }

        /* ---- 步骤 ① OnOff (FUN_004cf3d4(1)) ---- */
        printf("\n=== ① FUN_004cf3d4(1)  OnOff ===\n");
        b[R_ONOFF / 4] = b[R_ONOFF / 4] | 1UL;
        printf("  +0x000 = 0x%08x\n", b[R_ONOFF / 4]);

        /* ---- 步骤 ② 脉冲位先清 0（FUN_004cf45c(0))★ 之前漏了这步 ---- */
        printf("\n=== ② FUN_004cf45c(0)  脉冲位清零 ★之前漏了 ===\n");
        b[R_PULSE / 4] = b[R_PULSE / 4] & ~1UL;
        printf("  +0x008 = 0x%08x\n", b[R_PULSE / 4]);

        /* ---- 步骤 ③ 置位启动（FUN_004cf45c(1))---- */
        printf("\n=== ③ FUN_004cf45c(1)  置位启动 ===\n");
        b[R_PULSE / 4] = b[R_PULSE / 4] | 1UL;
        usleep(2000);
        printf("  +0x008 = 0x%08x %s\n", b[R_PULSE / 4],
               b[R_PULSE / 4] == 0 ? "(硬件自清)" : "(保持)");

        /* ---- 步骤 ④ SetAddress (FUN_004cf4b4, ch=1 → +0x0c) ---- */
        printf("\n=== ④ FUN_004cf4b4 SetAddress -> +0x00c ===\n");
        b[R_LUT0 / 4] = (unsigned)target;
        usleep(2000);
        printf("  +0x00c = 0x%08x %s\n", b[R_LUT0 / 4],
               b[R_LUT0 / 4] == (unsigned)target ? "✔" : "★不一致");

        /* ---- 步骤 ⑤ 通道选择 (FUN_004cf414, bit[5:4]=0) ---- */
        printf("\n=== ⑤ FUN_004cf414 通道选择 ===\n");
        v = b[R_CFG / 4];
        v = (v & 0xffffffcfUL) | 0UL;    /* ch=0 → bit[5:4]=0 */
        b[R_CFG / 4] = v;
        printf("  +0x004 = 0x%08x\n", b[R_CFG / 4]);

        /* ---- 步骤 ⑥ ★★★ 读侧清理（FUN_004cf484(1) → &=~0x100）★ 之前漏了 ---- */
        printf("\n=== ⑥ FUN_004cf484(1)  读侧清理 ★★之前漏了这步 ===\n");
        b[R_PULSE / 4] = b[R_PULSE / 4] & ~0x100UL;
        usleep(3000);
        printf("  +0x008 = 0x%08x\n", b[R_PULSE / 4]);

        printf("\n--- 最终寄存器---\n");
        printf("  +0x000 = 0x%08x\n", b[R_ONOFF / 4]);
        printf("  +0x004 = 0x%08x\n", b[R_CFG / 4]);
        printf("  +0x008 = 0x%08x\n", b[R_PULSE / 4]);
        printf("  +0x00c = 0x%08x\n", b[R_LUT0 / 4]);

        printf("\n★★★ 请看取景器（mode=%d，0=恒等 1=压红 2=压蓝）！\n", mode);
        printf("    恢复：%s restore 0\n", argv[0]);
    }

out:
    munmap(mb, map_len);
    close(fd_ep);
    return 0;
}