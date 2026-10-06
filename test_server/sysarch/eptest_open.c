/* eptest_open.c —— ★ 只测一件事：d5_ep_open() 在我们进程里能不能跑
 * =====================================================================
 *  【背景：2026-10-06 22:55 实测发现】
 *    libudd5 的 d5_ep_sma_virt_to_phys 反汇编：
 *
 *      unsigned int d5_ep_sma_virt_to_phys(unsigned int virt) {
 *          if (g_d5_dev_ctx < 0)  return 0;      ← ★ 未 open 直接返回 0
 *          if (virt == 0)         return 0;
 *          if (ioctl(g_d5_dev_ctx, 0xc0047302, &virt) < 0) return 0;
 *          return virt;
 *      }
 *
 *    ⇒ 它用的【就是同一个 ioctl 号 0xc0047302】，
 *      但要求进程内有一个有效的 g_d5_dev_ctx 句柄。
 *
 *    ⇒★ 实测对照（同一台相机、同一时刻）：
 *        v2p.arm 自己 open(/dev/drime5_ep) 后裸 ioctl
 *            → 0x99000000 ✔ 完全正常
 *        lutapi.arm 调 d5_ep_sma_virt_to_phys
 *            → 0x00000000 ✘（因为我们进程没 open）
 *
 *    ⇒★ 结论：官方 API 在我们进程里目前【完全不可用】，
 *      但根因只是"没 open"，不是 API 本身不对。
 *
 *  【本工具要回答的问题】
 *      相机主程序（di-camera-app 等）已持有 EP 时，
 *      我们再 d5_ep_open() 会怎样？
 *        A) 返回 2（= 已打开的计数）⇒ 安全，可继续
 *        B) 返回 1/0/负⇒ 被拒，但无害
 *        C) 抢锁阻塞 ⇒ 会卡住（危险，有超时保护）
 *
 *  【安全设计】
 *    - 每次动作前后都打印，绝不盲调
 *    - open 之后立刻 close，不长期持有
 *    - 全程有超时（由调用方的 timeout 控制）
 *    - 不碰任何 EP 寄存器（只 open/close + 读标量）
 *
 *  编译：
 *    zig cc -target arm-linux-gnueabi.2.15 -O0 -o eptest_open.arm eptest_open.c -ldl
 * =====================================================================
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <dlfcn.h>

typedef int  (*fn_open)(void);
typedef void (*fn_close)(void);
typedef unsigned int (*fn_v2p)(unsigned int);

#define BB "/opt/usr/nx-ks/busybox"

/* ★ d5_udd_open 的返回值语义（从 d5_ep_open 反汇编读出） */
static const char *open_rc_mean(int rc)
{
    switch (rc) {
    case  0: return "0= 首次打开成功（我们拿到了设备）";
    case  1: return "1 = 已是打开状态（可能未真正初始化）";
    case  2: return "2 = 引用计数++（设备已在用）★最理想";
    default: return "负值 = 错误（见 dmesg）";
    }
}

int main(void)
{
    void *h;
    fn_open  p_open;
    fn_close p_close;
    fn_v2p   p_v2p;
    unsigned *p_regbase;
    int rc, rc2;

    setvbuf(stdout, NULL, _IOLBF, 0);
    printf("=== eptest_open：只测 d5_ep_open 能否在我们进程工作 ===\n");

    printf("\n[1] 现状：先确认我们进程里【没有】设备句柄\n");
    h = dlopen("libudd5.so", RTLD_NOW);
    if (!h) h = dlopen("/usr/lib/libudd5.so", RTLD_NOW);
    if (!h) { printf("  dlopen 失败: %s\n", dlerror()); return 1; }
    printf("  dlopen ok\n");

    p_open  = (fn_open)  dlsym(h, "d5_ep_open");
    p_close = (fn_close) dlsym(h, "d5_ep_close");
    p_v2p   = (fn_v2p)   dlsym(h, "d5_ep_sma_virt_to_phys");
    p_regbase = (unsigned *)dlsym(h, "ep_3dlut_reg_base");
    printf("  d5_ep_open  = %p\n", (void*)p_open);
    printf("  d5_ep_close = %p\n", (void*)p_close);
    printf("  virt_to_phys= %p\n", (void*)p_v2p);
    if (!p_open || !p_close) { printf("  ★ 符号缺失，退出\n"); return 1; }

    if (p_regbase) {
        unsigned v = *p_regbase;
        printf("  ep_3dlut_reg_base = 0x%08x %s\n", v,
               v ? "(已初始化)" : "(未初始化)");
    }
    printf("  ⇒ 未 open 前 virt_to_phys 返回 %u\n",
           p_v2p ? p_v2p(0xb6f39000u) : 0);

    printf("\n[2] 调 d5_ep_open()\n");
    printf("  ★ 若相机主程序正在拍摄，可能阻塞；\n");
    printf("    若卡住请拔电池（不会损坏任何东西）。\n");
    fflush(stdout);
    rc = p_open();
    printf("  返回 = %d  %s\n", rc, open_rc_mean(rc));

    if (p_regbase) {
        unsigned v = *p_regbase;
        printf("  ep_3dlut_reg_base = 0x%08x  %s\n", v,
               v ? "★★ 已初始化 ⇒ 官方 API 现在可用" : "仍为 0 ⇒ 不可用");
    }
    if (p_v2p) {
        unsigned t = p_v2p(0xb6f39000u);
        printf("  virt_to_phys(0xb6f39000) = 0x%08x  %s\n", t,
               t ? "★★ 非零 ⇒ 通路已开" : "仍返回 0");
    }

    printf("\n[3] 立即 d5_ep_close()（不长期持有）\n");
    p_close();
    printf("  已 close\n");
    if (p_regbase)
        printf("  ep_3dlut_reg_base = 0x%08x\n", *p_regbase);

    printf("\n[4] dmesg 尾部（看驱动有没有报冲突）\n");
    fflush(stdout);
    if (system(BB " dmesg 2>/dev/null | tail -12") != 0)
        printf("  (dmesg 读不到，跳过)\n");

    printf("\n=== 结果判读 ===\n");
    printf("  返回 2 且 reg_base != 0  ⇒★★ 官方 API 可用，走 load 路线\n");
    printf("  返回 1 且 reg_base != 0  ⇒可用（设备已开，我们只是搭车）\n");
    printf("  返回 <=0 或 reg_base == 0 ⇒★ 官方 API 在我们进程不可用\n");
    printf("                            ⇒ 退回 lutload.arm 手写序列\n");
    printf("                            ⇒ 但必须先解决 virt_to_phys 的 ctx 问题\n");
    return 0;
}