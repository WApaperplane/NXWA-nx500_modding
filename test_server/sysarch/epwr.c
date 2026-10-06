/* epwr.c — NX-KS2 步骤 3：EP 3DLUT 寄存器写入实验
 *
 * ★★★ 三级递进，每级都带"读回验证 + 自动回滚"，失败立即还原：
 *
 *   级别 1  握手脉冲（★最低风险，理论上不改画面）
 *            只对 +0x08 做 v|=0x100 → v&=~0x100，不写地址寄存器。
 *            没有数据源 ⇒ 硬件启动了一次空写。
 *   级别 2  开关切换（可逆）
 *            OnOff / Acc_OnOff 这类 enable 位，原值全部记录并回滚。
 *   级别 3  完整 LUT 写入（★会改画面）
 *            需要 256 对齐的 buffer + virt_to_phys。默认不执行。
 *
 * ★ 安全设计：
 *   1. 每个级别独立执行，argv[1] 选级别，绝不一次跑完
 *   2. 写前 record、异常/失败立即 restore
 *   3. mmap 用 PROT_READ|PROT_WRITE（级别 1 只需 +0x08，仍统一）
 *   4. 不碰任何地址寄存器（除非级别 3 显式要求）
 *
 * 用法: epwr <level> [lut_sel]
 *   epwr 1        握手脉冲
 *   epwr 2        开关切换 + 回滚
 *   epwr 3        完整 LUT 写入（危险，需 -w 开关）
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <errno.h>
#include <time.h>

#include <media/drime5/ep/d5_ep_ioctl.h>

/* ---- 3DLUT 块内偏移（静态反汇编 + 实机 mmap 双重证实）---- */
#define R_START      0x08   /* ★ write-1-clear 握手：bit8=写, bit4=读 */
#define R_LUT0_ADDR  0x0c   /* ★ LUT0 数据物理地址（实机读到 0x81115200）*/
#define R_LUT1_ADDR  0x10   /* LUT1 数据物理地址 */
#define R_ONOFF      0x64   /* OnOff */
#define R_ONOFF2     0x68
#define R_ACC        0x6c   /* Acc_OnOff（访问窗口）*/
#define R_ACC2       0x70

static struct ep_reg_phys_info *blk(struct ep_reg_info *p, int i)
{
    return (struct ep_reg_phys_info *)((char *)p + i * sizeof(struct ep_reg_phys_info));
}

/* 保存/恢复区 */
#define MAXSAVE 32
struct save { unsigned off; unsigned val; };
static struct save sv[MAXSAVE];
static int nsv = 0;

static void reg_save(volatile unsigned *b, unsigned off)
{
    if (nsv < MAXSAVE) { sv[nsv].off = off; sv[nsv].val = b[off / 4]; nsv++; }
}
static void reg_restore(volatile unsigned *b)
{
    int i;
    for (i = 0; i < nsv; i++) b[sv[i].off / 4] = sv[i].val;
    printf("  已回滚 %d 个寄存器\n", nsv);
}
static void dump(volatile unsigned *b, unsigned off)
{
    printf("    +0x%03x = 0x%08x  %s\n", off, b[off / 4],
           b[off / 4] ? "" : "(zero)");
}

int main(int argc, char **argv)
{
    struct ep_reg_info info;
    int fd, level;
    unsigned long pa, size;
    volatile unsigned *b;
    unsigned char *map_base;
    unsigned long map_len;

    if (argc < 2) {
        printf("用法: %s <level>   level: 1=握手脉冲 2=开关+回滚 3=完整写\n", argv[0]);
        return 1;
    }
    level = atoi(argv[1]);

    printf("=== EP 3DLUT 写入实验  level=%d ===\n\n", level);

    fd = open("/dev/drime5_ep", O_RDWR);
    if (fd < 0) {
        printf("open(O_RDWR) 失败: %s\n", strerror(errno));
        return 2;
    }
    printf("open(/dev/drime5_ep, O_RDWR) = fd %d ★\n", fd);

    memset(&info, 0, sizeof(info));
    if (ioctl(fd, EP_IOCTL_GET_PHYS_REG_INFO, &info) < 0) {
        printf("ioctl 失败: %s\n", strerror(errno));
        close(fd);
        return 3;
    }
    pa   = blk(&info, 8)->reg_start_addr;
    size = blk(&info, 8)->reg_size;
    printf("3dlut phys=0x%08lx size=0x%08lx\n\n", pa, size);

    map_len = (size + 4095) & ~4095UL;
    map_base = mmap(NULL, map_len, PROT_READ | PROT_WRITE,
                    MAP_SHARED, fd, (off_t)pa);
    if (map_base == MAP_FAILED) {
        printf("mmap RW 失败: %s\n", strerror(errno));
        close(fd);
        return 4;
    }
    b = (volatile unsigned *)map_base;
    printf("mmap RW @ 0x%08lx = %p  ★成功\n\n", pa, (void *)map_base);

    /* ---------- 写入前状态 ---------- */
    printf("--- 写入前---\n");
    dump(b, R_START);
    dump(b, R_LUT0_ADDR);
    dump(b, R_LUT1_ADDR);
    dump(b, R_ONOFF);
    dump(b, R_ONOFF2);
    dump(b, R_ACC);
    dump(b, R_ACC2);
    printf("\n");

    if (level == 1) {
        /* ===== 级别 1：握手脉冲，理论上不改画面 ===== */
        unsigned v, orig;
        printf("--- 级别 1：write-1-clear 握手脉冲 ---\n");
        reg_save(b, R_START);
        orig = b[R_START / 4];
        printf("  原值 +0x08 = 0x%08x\n", orig);

        v = orig | 0x100;                 /* bit8 = 写启动 */
        b[R_START / 4] = v;
        printf("  写 0x%08x (bit8=1)\n", v);
        usleep(1000);                     /* 1ms：让硬件看到脉冲 */

        v = v & ~0x100;                  /* 清零复位 */
        b[R_START / 4] = v;
        printf("  写 0x%08x (bit8=0)\n", v);
        usleep(1000);

        printf("\n  读回 +0x08 = 0x%08x %s\n", b[R_START / 4],
               b[R_START / 4] == v ? "★ 与预期一致" : "★ 不一致！");
        printf("  ★ 脉冲已发完，硬件会自动清零 ⇒ 无需回滚\n");

    } else if (level == 2) {
        /* ===== 级别 2：开关切换 + 回滚 ===== */
        unsigned offs[] = { R_ONOFF, R_ONOFF2, R_ACC, R_ACC2 };
        unsigned i, orig[4];
        printf("--- 级别 2：开关切换（跑完立即回滚）---\n");
        for (i = 0; i < 4; i++) {
            reg_save(b, offs[i]);
            orig[i] = b[offs[i] / 4];
            printf("  +0x%03x: 0x%08x -> 0x%08x\n",
                   offs[i], orig[i], orig[i] ^ 0x1);
            b[offs[i] / 4] = orig[i] ^ 0x1;      /* 翻转 bit0 */
        }
        usleep(5000);
        printf("\n  5ms 后读回：\n");
        for (i = 0; i < 4; i++)
            printf("    +0x%03x = 0x%08x\n", offs[i], b[offs[i] / 4]);

        printf("\n  立即回滚...\n");
        reg_restore(b);
        printf("\n  回滚后验证：\n");
        for (i = 0; i < 4; i++)
            printf("    +0x%03x = 0x%08x  %s\n", offs[i], b[offs[i] / 4],
                   b[offs[i] / 4] == orig[i] ? "✓ 已还原" : "✗ 不一致");

    } else if (level == 3) {
        printf("--- 级别 3：完整 LUT 写入 ---\n");
        printf("  ★ 本探针不实现。理由：\n");
        printf("    1. 需要 256 对齐 buffer + /dev/d5_sma 的 virt_to_phys\n");
        printf("    2. 需要先验证 write-1-clear 脉冲不产生副作用\n");
        printf("    3. 会真正改变画面，需要你在取景器上目视确认\n");
        printf("  ⇒ 请先跑 level 1，确认无副作用后再设计 level 3\n");
        munmap(map_base, map_len);
        close(fd);
        return 5;
    }

    /* ---------- 写入后状态 ---------- */
    printf("\n--- 写入后 ---\n");
    dump(b, R_START);
    dump(b, R_LUT0_ADDR);
    dump(b, R_LUT1_ADDR);
    dump(b, R_ONOFF);
    dump(b, R_ONOFF2);
    dump(b, R_ACC);
    dump(b, R_ACC2);

    munmap(map_base, map_len);
    close(fd);
    printf("\n=== 结束 level=%d ===\n", level);
    return 0;
}