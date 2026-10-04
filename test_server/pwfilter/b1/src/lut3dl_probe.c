/*
 * lut3dl-probe.c — 3D LUT dlopen/dlsym probe (stage 1: read-only, zero side effects)
 *
 * Goal: prove we can obtain libudd5's 3D LUT API pointers and the register
 * base from an ordinary user-space process. This stage performs NO writes:
 * no Set/Load/Config function is called, so ISP state is untouched.
 *
 * Protocol (from LUT_REGISTERS.md / LUT_REVERSE.md):
 *   d5_ep_3dlut_op_init(handle, ...)       top-level init
 *   d5_ep_3dl_load_lut(handle, idx, type, unused)
 *   _udd_ep_3dl_reg_GetReg(addr){ return *addr; }   raw read
 *   _udd_ep_3dl_reg_SetReg(addr, v)         { *addr = v; }       raw write
 *   ep_3dlut_reg_base                       OBJECT = register group base pointer
 *
 * Lessons honoured (from x11probe, 2026-10-03):
 *   1) Logging MUST use unbuffered open()+write(); stdio fprintf segfaulted (139).
 *   2) A va_arg-based hand-rolled formatter ALSO produced corrupted output
 *      (every char followed by 2 garbage bytes). So there is no formatter at
 *      all here: each line is built explicitly and written with one write().
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <stddef.h>
#include <unistd.h>

static int g_log = -1;

static void emit(const char *s, int n) {
    if (g_log >= 0 && n > 0) {
        ssize_t w = write(g_log, s, (size_t)n);
        (void)w;
    }
}
#define EMIT(s) emit((s), (int)(sizeof(s) - 1))

static const char HEXD[] = "0123456789abcdef";

static int put_hex(char *b, unsigned int v, int pad) {
    char t[8];
    int n = 0, i;
    if (v == 0) t[n++] = '0';
    while (v) { t[n++] = HEXD[v & 0xf]; v >>= 4; }
    while (n < pad) t[n++] = '0';
    for (i = 0; i < n; i++) b[i] = t[n - 1 - i];
    return n;
}
static int put_dec(char *b, unsigned int v) {
    char t[12];
    int n = 0, i;
    if (v == 0) t[n++] = '0';
    while (v) { t[n++] = (char)('0' + (v % 10)); v /= 10; }
    for (i = 0; i < n; i++) b[i] = t[n - 1 - i];
    return n;
}
static int put_str(char *b, const char *s) {
    int n = 0;
    while (s[n]) { b[n] = s[n]; n++; }
    return n;
}

/* 12-byte protocol struct used by load/save */
struct ep3dl_st {
    unsigned int f30;      /* [0x00] mode: 1=write 2=read */
    unsigned int f2c;      /* [0x04] */
    unsigned int f20;      /* [0x08] */
    unsigned int handle;   /* [0x0c] */
    unsigned int lut_type; /* [0x10] 0=LUT0 1=LUT1 */
    unsigned int index;    /* [0x14] */
};

static const char *SYMS[] = {
    "d5_ep_3dlut_op_init",
    "d5_ep_3dl_load_lut",
    "d5_ep_3dl_save_lut",
    "_udd_ep_3dl_reg_GetReg",
    "_udd_ep_3dl_reg_SetReg",
    "_udd_ep_3dl_reg_OnOff",
    "_udd_ep_3dl_reg_Acc_OnOff",
    "_udd_ep_3dl_reg_SelLUT",
    "_udd_ep_3dl_reg_SelCbCr_ch",
    "_udd_ep_3dl_reg_SetColorFormat_LUT0",
    "_udd_ep_3dl_reg_SetColorFormat_LUT1",
    "_udd_ep_3dl_reg_SetAddress",
    "_udd_ep_3dl_reg_rw_Start",
    "_udd_ep_3dl_ctrl_ConfigAccessMode",
    "_udd_ep_3dl_ctrl_ConfigBypassMode",
    "_udd_ep_3dl_ctrl_ConfigProcessMode",
    "_udd_ep_mux_3dlut_wdxi",
    "_udd_ep_demux_3dlut_wdxi",
    "_udd_ep_mux_3dlut_rdxi",
    "_udd_ep_demux_3dlut_rdxi",
    "_udd_ep_wdma_check_empty",
    "_udd_ep_mux_wdma",
    "d5_ep_sma_virt_to_phys",
    "ep_3dlut_reg_base",
    "ep_ldc_reg_base",
    "d5_ep_mc_set_custom_param_yccmixer",
    "nog_set_gamma",
    0,
};

int main(int argc, char **argv) {
    const char *path = (argc > 1) ? argv[1] : "/usr/lib/libudd5.so";
    char b[256];
    int n, i, k;

    g_log = open("/mnt/mmc/_pwtest/lut3dl.log", O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (g_log < 0) g_log = 1;

    EMIT("=== lut3dl probe v1 read-only ===\n");
    n = 0; n += put_str(b + n, "lib="); n += put_str(b + n, path); b[n++] = '\n';
    emit(b, n);

    void *h = dlopen(path, RTLD_NOW | RTLD_GLOBAL);
    if (!h) { EMIT("FAIL dlopen\n"); return 1; }
    EMIT("OK dlopen\n");

    int found = 0, miss = 0;
    for (i = 0; SYMS[i]; i++) {
        void *a = dlsym(h, SYMS[i]);
        if (a) found++; else miss++;
        n = 0;
        n += put_str(b + n, a ? "SYM  " : "MISS ");
        n += put_str(b + n, SYMS[i]);
        if (a) {
            b[n++] = '='; b[n++] = '0'; b[n++] = 'x';
            n += put_hex(b + n, (unsigned int)(unsigned long)a, 8);
        }
        b[n++] = '\n';
        emit(b, n);
    }
    n = 0;
    n += put_str(b + n, "-- found="); n += put_dec(b + n, (unsigned int)found);
    n += put_str(b + n, " miss=");    n += put_dec(b + n, (unsigned int)miss);
    b[n++] = '\n'; emit(b, n);

    void *rb = dlsym(h, "ep_3dlut_reg_base");
    if (!rb) { EMIT("NO reg_base symbol\nDONE\n"); return 0; }

    unsigned int base = *(unsigned int *)rb;
    n = 0; n += put_str(b + n, "RB="); n += put_hex(b + n, base, 8); b[n++] = '\n';
    emit(b, n);

    if (base == 0 || base == 0xffffffffu) {
        EMIT("regbase null, ISP not initialised\nDONE\n");
        return 0;
    }

    unsigned int cfg = *(unsigned int *)(base + 4);
    unsigned int a1 = *(unsigned int *)(base + 0x0c);
    unsigned int a2 = *(unsigned int *)(base + 0x10);
    n = 0;
    n += put_str(b + n, "cfg="); n += put_hex(b + n, cfg, 8);
    n += put_str(b + n, " a1="); n += put_hex(b + n, a1, 8);
    n += put_str(b + n, " a2="); n += put_hex(b + n, a2, 8);
    b[n++] = '\n'; emit(b, n);

    /* decode the bitfields we already mapped out */
    n = 0;
    n += put_str(b + n, "bit0=");  n += put_dec(b + n, cfg & 1u);
    n += put_str(b + n, " cbcr=");  n += put_dec(b + n, cfg & 3u);
    n += put_str(b + n, " lut=");   n += put_dec(b + n, (cfg >> 4) & 3u);
    n += put_str(b + n, " fmt=");   n += put_dec(b + n, (cfg >> 8) & 1u);
    b[n++] = '\n'; emit(b, n);

    /* raw bytes of GetReg: disassembly predicts a bare load/return */
    void *g = dlsym(h, "_udd_ep_3dl_reg_GetReg");
    if (g) {
        unsigned char *p = (unsigned char *)g;
        n = 0; n += put_str(b + n, "getreg=");
        for (k = 0; k < 12; k++) { b[n++] = HEXD[(p[k] >> 4) & 0xf]; b[n++] = HEXD[p[k] & 0xf]; }
        b[n++] = '\n'; emit(b, n);
    }

    EMIT("DONE\n");
    if (g_log != 1) close(g_log);
    return 0;
}
