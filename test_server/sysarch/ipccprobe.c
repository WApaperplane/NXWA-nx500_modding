/*★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
 * ipccprobe.c —— p7↔Linux IPCC 通道探测器（★ 零风险：只读，不发任何包）
 *
 * ★★★ 背景（2026-10-07）
 *   "数据口袋"= p7 侧 CLiveviewFactory::GetDataPocket()
 *   p7 侧日志有 "lv1/lv2/lv3/4k1/4k2/ud2/burst data size = %d, lut size = %d"
 *   ⇒ p7【自己知道表长】，走它的官方通路就不需要逆硬件格式
 *
 *   /proc/net 无对应 socket 端口⇒ 推测是共享内存/IPCC，而非socket
 *   相机端确认：/dev/d5_ipcc（10,111），头文件在 NX1 GPL 源码里
 *
 * ★★★ 官方 API（ipcc.h:28-37，libudd5 全部 STB_GLOBAL）
 *   intipcc_open(void);
 *   void     ipcc_close(void);
 *   unsigned int ipcc_get_write_available(int core_id);
 *   unsigned int ipcc_get_read_available(int core_id);
 *   unsigned int ipcc_get_read_pkt_lenth(int core_id);
 *   unsigned int ipcc_read_pkt (unsigned char *buf, int core_id, unsigned len);
 *   unsigned int ipcc_write_pkt(unsigned char *buf, int core_id, unsigned len);
 *   unsigned int ipcc_raw_send_interrupt(enum d5_intr_type intr_type);
 *
 * ★★★ 中断枚举（d5_lib.h）⇒ 双核结构
 *   INT_IPCC_CA7_1=0, CA7_2, CA9_1=2, CA9_2, CM4_1=4, CM4_2, CM4_3, SRP, MAX=8
 *   ★ CA9 = p7（Cortex-A9），CA7 = Linux 主控
 *
 * ★★★ 本工具【只做只读查询】
 *   ① ipcc_open()                       —— 打开设备
 *   ② ipcc_get_write/read_available(0..15) —— 逐 core 查收发空间
 *   ③ ipcc_get_read_pkt_lenth(0..15)      —— 查待收包长度
 *   ★★ 绝不调用 ipcc_write_pkt / raw_send_interrupt
 *
 * 用法：
 *   ipccprobe.scan     扫所有 core（0..15）的收发能力
 *   ipccprobe.info     只解析符号地址
 * ================================================================*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dlfcn.h>
#include <unistd.h>

/* ── IPCC API 原型 ─────────────────────────────────────────── */
typedef int      (*fn_open)(void);
typedef void     (*fn_close)(void);
typedef unsigned int (*fn_avail)(int);
typedef unsigned int (*fn_pktlen)(int);
typedef unsigned int (*fn_readpkt)(unsigned char *, int, unsigned int);
typedef unsigned int (*fn_writepkt)(unsigned char *, int, unsigned int);
typedef unsigned int (*fn_sendintr)(int);

/* ── 中断类型（d5_lib.h:15-24）───────────────────────────────── */
static const char *INTR_NAME[] = {
    "CA7_1 (Linux)", "CA7_2 raw", "CA9_1 (p7)", "CA9_2 raw",
    "CM4_1", "CM4_2", "CM4_3", "SRP", "MAX"
};
#define N_INTR ((int)(sizeof(INTR_NAME)/sizeof(INTR_NAME[0])))

/* core_id 候选：IPCC 通道号，0..15 全部扫一遍（★ 只读，无副作用）*/
#define CORE_MAX 16

static fn_open       p_open;
static fn_close      p_close;
static fn_avail      p_wavail;
static fn_avail      p_ravail;
static fn_pktlen     p_pktlen;
static fn_readpkt    p_readpkt;
static fn_writepkt   p_writepkt;
static fn_sendintr   p_sendintr;

static const char *SYMS[] = {
    "ipcc_open", "ipcc_close",
    "ipcc_get_write_available", "ipcc_get_read_available",
    "ipcc_get_read_pkt_lenth", "ipcc_read_pkt", "ipcc_write_pkt",
    "ipcc_raw_send_interrupt", "ipcc_lock_open", "ipcc_lock_close",
    "ipcc_lock", "ipcc_unlock"
};

static void *g_h;

static int load_syms(void)
{
    int i, ok = 0, miss = 0;
    p_open     = (fn_open)      dlsym(g_h, "ipcc_open");
    p_close    = (fn_close)     dlsym(g_h, "ipcc_close");
    p_wavail   = (fn_avail)     dlsym(g_h, "ipcc_get_write_available");
    p_ravail   = (fn_avail)     dlsym(g_h, "ipcc_get_read_available");
    p_pktlen   = (fn_pktlen)    dlsym(g_h, "ipcc_get_read_pkt_lenth");
    p_readpkt  = (fn_readpkt)   dlsym(g_h, "ipcc_read_pkt");
    p_writepkt = (fn_writepkt)  dlsym(g_h, "ipcc_write_pkt");
    p_sendintr = (fn_sendintr)  dlsym(g_h, "ipcc_raw_send_interrupt");

    printf("=== IPCC 符号解析 ===\n");
    for (i = 0; i < (int)(sizeof(SYMS)/sizeof(SYMS[0])); i++) {
        void *a = dlsym(g_h, SYMS[i]);
        if (a) { printf("  %-34s %p  OK\n", SYMS[i], a); ok++; }
        else   { printf("  %-34s <无>\n", SYMS[i]);          miss++; }
    }
    printf("  => %d 个可用，%d 个缺失\n\n", ok, miss);

    if (!p_open || !p_wavail || !p_ravail) {
        printf("★ 核心符号缺失，探测中止\n");
        return 0;
    }
    return 1;
}

static int cmd_info(void)
{
    load_syms();
    return 0;
}

static int cmd_scan(void)
{
    int rc, core, any = 0;
    unsigned int w, r, l;

    printf("\n=== IPCC 只读扫描（★ 不发任何包）===\n");

    rc = p_open();
    printf("  ipcc_open() => %d  %s\n", rc,
           rc == 0 ? "OK" : (rc > 0 ? "已打开(引用++)" : "★ 失败"));
    if (rc < 0) {
        printf("  ⇒ 无法打开 /dev/d5_ipcc\n");
        printf("  ★ 相机主程序可能已独占（内核对象计数限制）\n");
        return 1;
    }

    printf("\n--- 逐 core 查询 ---\n");
    printf("  core |write_avail| read_avail | pkt_len | 备注\n");
    printf("  -----+-----------+------------+---------+------\n");
    for (core = 0; core < CORE_MAX; core++) {
        w = p_wavail(core);
        r = p_ravail(core);
        l = p_pktlen ? p_pktlen(core) : 0xFFFFFFFFu;
        printf("  %4d | %9u | %10u | %7u | %s\n",
               core, w, r, l,
               (w || r) ? "★ 有数据通路" : "");
        if (w || r) any = 1;
    }

    printf("\n--- 中断类型编号（发包时才需要）---\n");
    for (core = 0; core < N_INTR; core++)
        printf("  INT_IPCC[%d] = %-14s\n", core, INTR_NAME[core]);

    if (p_close) p_close();
    printf("\n%s\n", any
        ? "★ 找到有数据的 core ⇒ 下一步可用 ipcc_write_pkt 发探测包"
        : "★ 所有 core 都是空的⇒ 可能 core_id 编号不是 0..15，或需先注册回调");
    printf("★ 本工具【没有调用 write_pkt / send_interrupt】，全程零副作用\n");
    return 0;
}

int main(int argc, char **argv)
{
    const char *cmd = argc > 1 ? argv[1] : "scan";

    printf("=== NX500 ipccprobe：p7↔Linux IPCC 通道探测（只读）===\n");
    g_h = dlopen("libudd5.so", RTLD_LAZY | RTLD_GLOBAL);
    if (!g_h) {
        printf("  dlopen(libudd5.so) 失败: %s\n", dlerror());
        return 1;
    }
    printf("  dlopen ok\n");

    if      (strcmp(cmd, "info") == 0) return cmd_info();
    else if (strcmp(cmd, "scan") == 0) return cmd_scan();
    else {
        printf("用法: %s [scan|info]\n", argv[0]);
        printf("  scan  扫所有 core 的收发能力（★ 只读，默认）\n");
        printf("  info  只解析符号\n");
        return 1;
    }
}
