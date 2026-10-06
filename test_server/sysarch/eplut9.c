/* eplut9.c — NX-KS2 步骤 9：按 p7 固件的权威序列写 3DLUT
 *
 * ★★★★ 这是唯一有"权威配方"的版本 —— 所有寄存器定义来自 p7 固件反编译：
 *   raw8/p7/ghidra/53_all_pseudocode.c:641680+
 *
 *   FUN_004cf3d4(on)   _DAT_2082b000 = on==1 ? (x|1) : (x&~1)   ★ OnOff 总开关
 *   FUN_004cf3fc(ch)   _DAT_2082b004 bits[1:0]  = ch & 3
 *   FUN_004cf414(ch)   _DAT_2082b004 bits[5:4]  = ch & 3
 *   FUN_004cf42c(v)    _DAT_2082b004 bit8       = v & 1
 *   FUN_004cf444(v)    _DAT_2082b004 bit12      = v & 1
 *   FUN_004cf45c(v)    _DAT_2082b008 bit0       = v        ★★★ 写脉冲是 bit0！
 *   FUN_004cf484(v)    _DAT_2082b008 bit8/bit4  = 0        ★ 读侧清理
 *   FUN_004cf4b4(p1,p2,ch)  ch==1 → _DAT_2082b00c = p1      ★ SetAddress
 *                          ch==2 → _DAT_2082b010 = p2
 *
 * ★★★ 我之前犯的关键错误（已修正）：
 *   1. 脉冲用了 bit8(0x100)，实际应该是 **bit0(0x1)**
 *   2. 没写 OnOff 总开关（+0x00），实测它已是 1
 *   3. 没配 +0x004 的配置 bits（实测 bit8=1）
 *
 * ★ 实测基线（与 p7 定义4/4 吻合）：
 *   +0x00=0x01(开) +0x04=0x100(bit8) +0x08=0(脉冲已清) +0x0c=0x81115200
 *
 * 用法:
 *   eplut9 full <phys> <mode>    完整序列（开/配/地址/bit0 脉冲）
 *   eplut9 restore                恢复基线
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
#define R_LUT1      0x010
#define NSLOT16
#define SLOTSZ      0x100

/* ★ 实测基线值 */
#define BASE_ONOFF  0x00000001UL
#define BASE_CFG    0x00000100UL
#define BASE_LUT    0x81115200UL

static struct ep_reg_phys_info *blk(struct ep_reg_info *p, int i)
{
    return (struct ep_reg_phys_info *)((char *)p + i * sizeof(struct ep_reg_phys_info));
}

/* ★★★ 完全照抄 p7 的 LUT 生成格式未知 ⇒ 这里用最简单的 identity ramp。
 *   若 p7 用的是 17x17x17 或带索引的格式，identity 仍应"无变化"，
 *   但能验证"通路是否被真正触发"（若画面变了反而说明格式理解错）。 */
static void gen_lut(unsigned char *buf, int mode)
{
    int i;
    /* ★ 只填前 32 字节：memset 256 在 -O0 下会 SIGSEGV（铁律 51） */
    memset(buf, 0, 32);
    for (i = 0; i < 11; i++) {
        unsigned char v = (unsigned char)i;
        switch (mode) {
        case 0: buf[i*3+0]=v; buf[i*3+1]=v; buf[i*3+2]=v; break;
        case 1: buf[i*3+0]=v+40; buf[i*3+1]=v; buf[i*3+2]=v; break; /* 偏红 */
        case 2: buf[i*3+0]=v; buf[i*3+1]=v; buf[i*3+2]=v+40; break; /* 偏蓝 */
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
    printf("\n--- 当前寄存器 ---\n");
    printf("  +0x000 OnOff = 0x%08x\n", b[R_ONOFF / 4]);
    printf("  +0x004 Cfg   = 0x%08x\n", b[R_CFG / 4]);
    printf("  +0x008 Pulse = 0x%08x\n", b[R_PULSE / 4]);
    printf("  +0x00c LUT0  = 0x%08x\n", b[R_LUT0 / 4]);

    if (strcmp(argv[1], "restore") == 0) {
        printf("\n--- 恢复基线 ---\n");
        b[R_ONOFF / 4] = (unsigned)BASE_ONOFF;
        b[R_CFG / 4]   = (unsigned)BASE_CFG;
        b[R_LUT0 / 4]  = (unsigned)BASE_LUT;
        b[R_PULSE / 4] |= 1;              /* ★ bit0 脉冲 */
        usleep(3000);
        printf("  +0x000 = 0x%08x\n", b[R_ONOFF / 4]);
        printf("  +0x004 = 0x%08x\n", b[R_CFG / 4]);
        printf("  +0x00c = 0x%08x\n", b[R_LUT0 / 4]);
        printf("  +0x008 = 0x%08x\n", b[R_PULSE / 4]);
        goto out;
    }

    if (strcmp(argv[1], "full") == 0) {
        int mode = (argc > 3) ? atoi(argv[3]) : 0;
        unsigned char *lp;

        /* 步骤 1：把 LUT 数据写进 CMA（用 d5_sma mmap，已验证可写）*/
        printf("\n=== 步骤 1：写 LUT 数据到 CMA 0x%08lx ===\n", target);
        {
            int fds = open("/dev/d5_sma", O_RDWR);
            unsigned char tmp[32];
            if (fds < 0) { printf("open d5_sma: %s\n", strerror(errno)); goto out; }
            lp = mmap(NULL, 4096, PROT_READ, MAP_SHARED, fds, (off_t)target);
            if (lp != MAP_FAILED)
                printf("  先读确认: %02x %02x %02x %02x\n", lp[0], lp[1], lp[2], lp[3]);
            if (lp != MAP_FAILED) munmap(lp, 4096);

            lp = mmap(NULL, 4096, PROT_READ | PROT_WRITE, MAP_SHARED, fds, (off_t)target);
            if (lp == MAP_FAILED) { printf("  mmap RW fail: %s\n", strerror(errno)); close(fds); goto out; }
            gen_lut(tmp, mode);
            memcpy(lp, tmp, 32);
            printf("  写入 32 字节 (mode=%d)，校验 %s\n", mode,
                   memcmp(lp, tmp, 32) ? "★不一致" : "一致 ✔");
            printf("  前 16 字节: ");
            for (i = 0; i < 16; i++) printf("%02x ", lp[i]);
            printf("\n");
            munmap(lp, 4096);
            close(fds);
        }

        /* 步骤 2：OnOff（照抄 FUN_004cf3d4 的读改写两段式）*/
        printf("\n=== 步骤 2：OnOff 总开关 (FUN_004cf3d4) ===\n");
        v = b[R_ONOFF / 4];
        printf("  原 +0x000 = 0x%08x\n", v);
        b[R_ONOFF / 4] = v & ~1UL;         /* 先关 */
        usleep(500);
        b[R_ONOFF / 4] = b[R_ONOFF / 4] | 1UL;  /* 再开 */
        usleep(500);
        printf("  现 +0x000 = 0x%08x\n", b[R_ONOFF / 4]);

        /* 步骤 3：配置 bits（照抄 4 个 FUN）*/
        printf("\n=== 步骤 3：配置 +0x004 ===\n");
        v = b[R_CFG / 4];
        printf("  原 +0x004 = 0x%08x\n", v);
        v = (v & 0xfffffffcUL) | 0UL;       /* FUN_004cf3fc: SelCbCr = 0 */
        v = (v & 0xffffffcfUL) | 0UL;       /* FUN_004cf414: ch2 group = 0 */
        v = (v & 0xfffffeffUL) | (1UL << 8);/* FUN_004cf42c: bit8 = 1 */
        v = (v & 0xffffefffUL) | (0UL << 12);/*FUN_004cf444: bit12 = 0 */
        b[R_CFG / 4] = v;
        usleep(500);
        printf("  现 +0x004 = 0x%08x\n", b[R_CFG / 4]);

        /* 步骤 4：SetAddress（照抄 FUN_004cf4b4，ch=1 → +0x0c）*/
        printf("\n=== 步骤 4：SetAddress ch=1 → +0x00c ===\n");
        b[R_LUT0 / 4] = (unsigned)target;
        usleep(500);
        printf("  现 +0x00c = 0x%08x  %s\n", b[R_LUT0 / 4],
               b[R_LUT0 / 4] == (unsigned)target ? "✔" : "★不一致");

        /* 步骤 5：★ 脉冲 bit0（不是 bit8！）*/
        printf("\n=== 步骤 5：启动脉冲 ★bit0（FUN_004cf45c）===\n");
        v = b[R_PULSE / 4];
        printf("  原 +0x008 = 0x%08x\n", v);
        b[R_PULSE / 4] = v | 1UL;          /* ★★★ 这一位才是写启动 */
        usleep(3000);
        printf("  写 0x%08x 后读回 0x%08x %s\n", v | 1UL, b[R_PULSE / 4],
               b[R_PULSE / 4] == 0 ? "(硬件自清 ✔)" : "");

        printf("\n★★★ 请看取景器（mode=%d，0=恒等 1=偏红 2=偏蓝）！\n", mode);
        printf("    恢复：%s restore 0\n", argv[0]);
    }

out:
    munmap(mb, map_len);
    close(fd_ep);
    return 0;
}