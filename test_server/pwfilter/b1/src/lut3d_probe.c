/* ============================================================
 * lut3d_probe.c —— NX500 ISP 3D LUT / NOG 控制链探针
 *
 * 目标：验证 libudd5.so 里的 _udd_ep_* / d5_ep_* 纯用户态函数
 *       能否在独立进程里驱动 3D LUT。
 *
 * 已确认的关键符号（libudd5.so 符号表未剥离）：
 *   d5_ep_3dl_load_lut         0x13d10  ★★ 加载 LUT
 *   d5_ep_3dl_save_lut         0x13e14  ★  保存 LUT
 *   d5_ep_3dlut_op_init        0x13c2c  ★  初始化
 *   _udd_ep_3dl_reg_SetReg     0x17530  直接写寄存器
 *   _udd_ep_3dl_reg_SetAddress 0x1798c  设置地址
 *   _udd_ep_3dl_reg_rw_Start   0x17884  开始读写
 *   _udd_ep_3dl_reg_SelLUT     0x17668  选表
 *   _udd_ep_3dl_reg_SelCbCr_ch 0x175e4  选 Cb/Cr 通道
 *   _udd_ep_nog_reg_struct_init 0x20070  ★ NOG 初始化
 *   _udd_ep_nog_set_std_sigma  0x203b0  颗粒强度
 *   _udd_ep_nog_set_gamma      0x20560  颗粒分布
 *   _udd_ep_nog_select_rv_type 0x20300  颗粒类型
 *   d5_ep_open                 0x1bcc0  ★ EP 打开（可能分配 reg_base）
 *   d5_udd_open                0x45834
 *   ipcc_open/read/write_pkt   0x45e3c / 0x46168 / 0x461d0
 *
 * 编译铁律：-O0（-O1+ 实测段错误）+ -ldl
 * 输出：自己 write 到 /mnt/mmc/_fl2/lut3d.log（崩溃也留痕）
 * ============================================================ */

#include <dlfcn.h>
#include <fcntl.h>
#include <signal.h>
#include <stddef.h>
#include <stdlib.h>
#include <unistd.h>

/* ---- 日志 fd：直接 write，不依赖 stdio 缓冲 ---- */
static int G = -1;

static void ws(const char *s)
{
    int n = 0;
    while (s[n]) n++;
    if (G >= 0) (void)!write(G, s, (size_t)n);
}

static char gbuf[64];

static void puthex(unsigned int v, int digits)
{
    static const char *H = "0123456789abcdef";
    int i;
    ws("0x");
    for (i = digits - 1; i >= 0; i--) {
        gbuf[0] = H[(v >> (i * 4)) & 0xF];
        gbuf[1] = 0;
        ws(gbuf);
    }
}

static void putdec(unsigned int v)
{
    char t[12];
    int i = 0;
    if (v == 0) { ws("0"); return; }
    while (v) { t[i++] = (char)('0' + (v % 10)); v /= 10; }
    while (i > 0) { gbuf[0] = t[--i]; gbuf[1] = 0; }
    while (i > 0) { gbuf[0] = t[--i]; gbuf[1] = 0; ws(gbuf); }
}

static void nl(void) { ws("\n"); }

static void kv(const char *k, unsigned int v)
{
    ws("  "); ws(k); ws(" = "); puthex(v, 8); ws("  ("); putdec(v); ws(")"); nl();
}

static void onsegv(int sig)
{
    ws("\n*** SIGNAL ");
    putdec((unsigned int)sig);
    ws("  (4=SIGILL 6=SIGABRT 7=SIGBUS 11=SIGSEGV) ***\n");
    ws("PROBE_DIED\n");
    _exit(99);
}

/* ================= 目标符号 ================= */
static const char *WANT[] = {
    "d5_ep_3dlut_op_init",
    "d5_ep_3dl_load_lut",
    "d5_ep_3dl_save_lut",
    "_udd_ep_3dl_reg_GetReg",
    "_udd_ep_3dl_reg_SetReg",
    "_udd_ep_3dl_reg_OnOff",
    "_udd_ep_3dl_reg_SelCbCr_ch",
    "_udd_ep_3dl_reg_SelLUT",
    "_udd_ep_3dl_reg_SetColorFormat_LUT0",
    "_udd_ep_3dl_reg_SetColorFormat_LUT1",
    "_udd_ep_3dl_reg_Acc_OnOff",
    "_udd_ep_3dl_reg_rw_Start",
    "_udd_ep_3dl_reg_SetAddress",
    "_udd_ep_3dl_ctrl_ConfigBypassMode",
    "_udd_ep_3dl_ctrl_ConfigAccessMode",
    "_udd_ep_3dl_ctrl_ConfigProcessMode",
    "_udd_ep_nog_reg_struct_init",
    "_udd_ep_nog_set_random_seed",
    "_udd_ep_nog_seed_load_switch",
    "_udd_ep_nog_select_rv_type",
    "_udd_ep_nog_set_std_sigma",
    "_udd_ep_nog_set_gamma",
    "_udd_ep_nog_set_bypass",
    "d5_ep_nog_set_noisegen",
    "d5_ep_nog_set_bypass",
    "d5_ep_open",
    "d5_ep_close",
    "d5_udd_open",
    "d5_udd_close",
    "d5_ep_top_udd_open",
    "d5_ep_top_clock_onoff",
    "d5_ep_top_sw_reset",
    "get_virtual_address",
    "d5_ep_sma_virt_to_phys",
    "d5_ep_mc_set_custom_param_yccmixer",
    "ipcc_open",
    "ipcc_close",
    "ipcc_read_pkt",
    "ipcc_write_pkt",
    0
};

/* ================= 寄存器组基址全局（静态偏移） ================= */
static const struct { const char *name; unsigned int off; } GLOBALS[] = {
    { "ep_top_reg_base",     0x57720 },
    { "ep_nog_reg_base",     0x57724 },
    { "ep_ldc_reg_base",     0x57728 },
    { "ep_bblt_reg_base",    0x5772c },
    { "ep_3dlut_reg_base",   0x57730 },
    { "ep_fd_reg_base",      0x57734 },
    { "ep_jpeg_reg_base",    0x57738 },
    { "ep_rsz_reg_base",     0x5773c },
    { "ep_mc_reg_base",      0x57740 },
    { "ep_lvr_reg_base",     0x57744 },
    { 0, 0 }
};

static void dump_globals(unsigned int base, const char *title)
{
    int i;
    ws(title); nl();
    for (i = 0; GLOBALS[i].name; i++) {
        unsigned int *p = (unsigned int *)(base + GLOBALS[i].off);
        unsigned int v = *p;
        ws("  "); ws(GLOBALS[i].name); ws(" @"); puthex(base + GLOBALS[i].off, 8);
        ws(" = "); puthex(v, 8);
        if (v == 0) ws("     ← 0 未初始化");
        else if (v == 0xffffffffu) ws("     ← 0xffffffff");
        nl();
    }
    nl();
}

int main(int argc, char **argv)
{
    void *h;
    int i;
    int mode = 1;
    unsigned int base = 0;
    void *f;

    G = open("/mnt/mmc/_fl2/lut3d.log", O_WRONLY | O_CREAT | O_TRUNC, 0666);
    if (G < 0) G = 1;

    signal(SIGSEGV, onsegv);
    signal(SIGABRT, onsegv);
    signal(SIGBUS, onsegv);
    signal(SIGILL, onsegv);

    if (argc > 1) mode = atoi(argv[1]);

    ws("=== NX500 3D LUT / NOG 控制链探针 ===\n");
    ws("mode="); putdec((unsigned int)mode); nl(); nl();

    /* ---------- 1. dlopen ---------- */
    h = dlopen("/usr/lib/libudd5.so", RTLD_NOW | RTLD_GLOBAL);
    if (!h) {
        ws("[1] dlopen /usr/lib/libudd5.so 失败: "); ws(dlerror()); nl();
        h = dlopen("libudd5.so", RTLD_NOW | RTLD_GLOBAL);
        if (!h) { ws("    短名也失败\nPROBE_DIED\n"); return 1; }
        ws("    短名成功\n");
    }
    ws("[1] dlopen OK\n\n");

    /* ---------- 2. 库基址 ---------- */
    f = dlsym(h, "d5_ep_3dlut_op_init");
    if (f) base = (unsigned int)(unsigned long)f - 0x13c2c;
    ws("[2] 库基址 = "); puthex(base, 8);
    ws("   (d5_ep_3dlut_op_init 反推 0x13c2c)\n\n");

    /* ---------- 3. dlsym 全部 ---------- */
    ws("[3] 符号解析\n");
    for (i = 0; WANT[i]; i++) {
        void *s = dlsym(h, WANT[i]);
        ws("  "); ws(WANT[i]); ws(" = ");
        if (s) puthex((unsigned int)(unsigned long)s, 8);
        else ws("(null)");
        nl();
    }
    nl();

    /* ---------- 4. reg_base（本进程副本）---------- */
    dump_globals(base, "[4] 寄存器组基址 —— 探针进程自己这份.libudd5 .bss");

    /* ---------- 5. 其他全局 ---------- */
    ws("[5] 其他全局控制变量\n");
    kv("g_dev_id", *(unsigned int *)(base + 0x57524));
    kv("g_d5_dev_ctx", *(unsigned int *)(base + 0x57528));
    kv("g_nCoreIntrWaitTimeout", *(unsigned int *)(base + 0x55570));
    kv("fd_ep", *(unsigned int *)(base + 0x5556c));
    nl();

    if (mode < 2) {
        ws("[mode=1] 只解析符号 + 读全局，未调用任何函数\n");
        ws("PROBE_OK\n");
        return 0;
    }

    /* ---------- 6. mode=2：试 d5_ep_open ---------- */
    if (mode >= 2) {
        ws("[6] ★ 调 d5_ep_open() —— 看能否让本进程分配 reg_base\n");
        f = dlsym(h, "d5_ep_open");
        if (f) {
            int (*fn)(void) = (int (*)(void))f;
            int r;
            ws("  calling... "); ws("\n");
            r = fn();
            ws("  返回 = "); putdec((unsigned int)r); nl();
        } else {
            ws("  (符号未找到，跳过)\n");
        }
        dump_globals(base, "[6b] d5_ep_open 之后的 reg_base");
    }

    /* ---------- 7. mode=3：试 NOG 初始化 ---------- */
    if (mode >= 3) {
        ws("[7] ★ 调 _udd_ep_nog_reg_struct_init()\n");
        f = dlsym(h, "_udd_ep_nog_reg_struct_init");
        if (f) {
            void (*fn)(void) = (void (*)(void))f;
            ws("  calling... "); ws("\n");
            fn();
            ws("  返回\n");
        } else {
            ws("  (未找到)\n");
        }
        dump_globals(base, "[7b] NOG init 之后的 reg_base");
    }

    /* ---------- 8. mode=4：试 d5_ep_3dlut_op_init ---------- */
    if (mode >= 4) {
        ws("[8] ★ 调 d5_ep_3dlut_op_init()\n");
        f = dlsym(h, "d5_ep_3dlut_op_init");
        if (f) {
            void (*fn)(void) = (void (*)(void))f;
            ws("  calling... "); ws("\n");
            fn();
            ws("  返回\n");
        } else {
            ws("  (未找到)\n");
        }
        dump_globals(base, "[8b] 3dlut op_init 之后的 reg_base");
    }

    /* ---------- 9. mode=5：★★ 直接读 3D LUT 寄存器窗口 ---------- */
    if (mode >= 5) {
        unsigned int lutbase = *(unsigned int *)(base + 0x57730);
        unsigned int *p;
        int n;
        ws("[9] ★★★ 直接读 3D LUT 寄存器窗口\n");
        ws("  ep_3dlut_reg_base = ");
        puthex(lutbase, 8);
        ws("\n");
        if (lutbase == 0 || lutbase == 0xffffffffu) {
            ws("  ★ 无效地址，跳过（不读，避免崩）\n");
        } else {
            /* 只读前 256 字节（64 个32 位）—— 纯读，无副作用 */
            p = (unsigned int *)lutbase;
            ws("  --- 前 64 个 32 位寄存器值 ---\n");
            for (n = 0; n < 64; n++) {
                ws("   +0x");
                puthex((unsigned int)(n * 4), 3);
                ws(" = ");
                puthex(p[n], 8);
                ws("  (");
                putdec(p[n]);
                ws(")\n");
            }
            /* 统计非零 */
            {
                int nz = 0;
                for (n = 0; n < 64; n++) if (p[n]) nz++;
                ws("  非零个数 = ");
                putdec((unsigned int)nz);
                ws(" / 64\n");
            }
            /* 再往后看 4096 字节的分布（每 256 字节统计非零率） */
            ws("  --- 每 256 字节的非零率（探测 LUT 数据区大小）---\n");
            for (n = 0; n < 16; n++) {
                unsigned int *q = p + n * 64;
                int k, c = 0;
                for (k = 0; k < 64; k++) if (q[k]) c++;
                ws("   +0x");
                puthex((unsigned int)(n * 256), 5);
                ws(" :非零 ");
                putdec((unsigned int)c);
                ws("/64\n");
            }
        }
        ws("\n");
    }

    /* ---------- 10. mode=6：读NOG 窗口 ---------- */
    if (mode >= 6) {
        unsigned int nogbase = *(unsigned int *)(base + 0x57724);
        unsigned int *p;
        int n;
        ws("[10] ★ 读 NOG（硬件颗粒）寄存器窗口\n");
        ws("  ep_nog_reg_base = ");
        puthex(nogbase, 8);
        ws("\n");
        if (nogbase == 0 || nogbase == 0xffffffffu) {
            ws("  ★ 无效地址（0 / 0xffffffff），跳过\n");
            ws("  → NOG 未被 d5_ep_open 分配，需另找初始化路径\n");
        } else {
            p = (unsigned int *)nogbase;
            for (n = 0; n < 32; n++) {
                ws("   +0x");
                puthex((unsigned int)(n * 4), 3);
                ws(" = ");
                puthex(p[n], 8);
                ws("\n");
            }
        }
        ws("\n");
    }

    ws("PROBE_OK\n");
    return 0;
}
