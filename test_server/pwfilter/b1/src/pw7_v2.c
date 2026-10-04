/*
 * pw7_v2.c — B2 corrected: initialise first, then write.
 *
 * What the crash taught us (see b1/CRASH_ANALYSIS.md)
 * ---------------------------------------------------
 * The v1 probe called d5_ep_mc_set_custom_param_yccmixer directly and died
 * with SIGSEGV. Root cause: the function obtains its register-group pointer
 * through the PLT slot at 0x54450, which resolves to
 * _udd_ep_nog_seed_load_switch (NOG = Noise Generator). If NOG was never
 * initialised that call returns 0 and the function then writes to
 * address 0x00000280 -> SEGV.
 *
 * Correct order:
 *   1. dlopen
 *   2. _udd_ep_nog_reg_struct_init()          <- must come first
 *   3. optionally d5_ep_nog_set_noisegen(p)   <- sets sigma/gamma/rv_type
 *   4. d5_ep_mc_set_custom_param_yccmixer(p0, p1)
 *
 * Modes (argv[2]):
 *   0 = dry run, resolve only, call nothing
 *   1 = init + yccmixer
 *   2 = init + noisegen only  (grain test)
 *   3 = init + noisegen + yccmixer
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <stddef.h>
#include <stdlib.h>
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
    char t[8]; int n = 0, i;
    if (!v) t[n++] = '0';
    while (v) { t[n++] = HEXD[v & 0xf]; v >>= 4; }
    while (n < pad) t[n++] = '0';
    for (i = 0; i < n; i++) b[i] = t[n - 1 - i];
    return n;
}
static int put_dec(char *b, int sv) {
    char t[12]; int n = 0, i;
    unsigned int v = (sv < 0) ? (unsigned int)(-(long)sv) : (unsigned int)sv;
    if (!v) t[n++] = '0';
    while (v) { t[n++] = (char)('0' + (v % 10)); v /= 10; }
    if (sv < 0 && n < 11) t[n++] = '-';
    for (i = 0; i < n; i++) b[i] = t[n - 1 - i];
    return n;
}
static int put_str(char *b, const char *s) { int n = 0; while (s[n]) { b[n] = s[n]; n++; } return n; }

typedef int (*fn_void)(void);
typedef int (*fn_nog)(void *);
typedef void (*fn_ycc)(void *, void *);

int main(int argc, char **argv) {
    const char *path = (argc > 1) ? argv[1] : "/usr/lib/libudd5.so";
    int mode = (argc > 2) ? atoi(argv[2]) : 0;
    unsigned int pat = (argc > 3) ? (unsigned int)strtoul(argv[3], 0, 0) : 0x00010101u;
    unsigned int sigma = (argc > 4) ? (unsigned int)strtoul(argv[4], 0, 0) : 0u;
    char b[256];
    int n;

    g_log = open("/mnt/mmc/_pwtest/pw7b.log", O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (g_log < 0) g_log = 1;

    EMIT("=== PW7 v2 (init first) ===\n");
    n = 0;
    n += put_str(b + n, "mode="); n += put_dec(b + n, mode);
    n += put_str(b + n, " pat=");  n += put_hex(b + n, pat, 8);
    n += put_str(b + n, " sig=");  n += put_hex(b + n, sigma, 8);
    b[n++] = '\n'; emit(b, n);

    void *h = dlopen(path, RTLD_NOW | RTLD_GLOBAL);
    if (!h) { EMIT("FAIL dlopen\n"); return 1; }
    EMIT("OK dlopen\n");

    void *f_init = dlsym(h, "_udd_ep_nog_reg_struct_init");
    void *f_ng = dlsym(h, "d5_ep_nog_set_noisegen");
    void *f_ycc = dlsym(h, "d5_ep_mc_set_custom_param_yccmixer");
    n = 0;
    n += put_str(b + n, "noginit="); n += put_hex(b + n, (unsigned int)(unsigned long)f_init, 8);
    n += put_str(b + n, " noisegen="); n += put_hex(b + n, (unsigned int)(unsigned long)f_ng, 8);
    n += put_str(b + n, " ycc="); n += put_hex(b + n, (unsigned int)(unsigned long)f_ycc, 8);
    b[n++] = '\n'; emit(b, n);

    if (mode == 0) { EMIT("dry run, nothing called\nDONE\n"); return 0; }

    /* ---- step 1: NOG register group init ---- */
    if (f_init) {
        int rc = ((fn_void)f_init)();
        n = 0; n += put_str(b + n, "nog_init_rc="); n += put_dec(b + n, rc);
        b[n++] = '\n'; emit(b, n);
        if (rc != 0) {
            EMIT("nog init failed -> NOG needs a handle too\nDONE\n");
            return 2;
        }
    } else {
        EMIT("no nog_init symbol\n");
    }

    /* ---- step 2: noise generator (grain) ---- */
    if ((mode == 2 || mode == 3) && f_ng) {
        /* struct per d5_ep_nog_set_noisegen:
             [0x00] sigma, [0x04] gamma, [0x08] seed/handle,
             [0x0c] ?, [0x10] rv_type                              */
        unsigned int np[8];
        for (int i = 0; i < 8; i++) np[i] = 0;
        np[0] = sigma;        /* std sigma = grain strength */
        np[1] = sigma >> 8;
        np[2] = 0;            /* gamma low */
        np[3] = 0x0100;       /* gamma high (guess: 0x0100) */
        np[4] = 0;            /* seed/handle -- unknown, 0 */
        n = 0; n += put_str(b + n, "noisegen_params=");
        for (int i = 0; i < 5; i++) { b[n++] = HEXD[(np[i] >> 4) & 0xf]; b[n++] = HEXD[np[i] & 0xf]; }
        b[n++] = '\n'; emit(b, n);
        int rc = ((fn_nog)f_ng)(np);
        n = 0; n += put_str(b + n, "noisegen_rc="); n += put_dec(b + n, rc);
        b[n++] = '\n'; emit(b, n);
        EMIT("noisegen done, check viewfinder for grain\n");
    }

    /* ---- step 3: PW yccmixer ---- */
    if (mode == 1 || mode == 3) {
        if (!f_ycc) { EMIT("no ycc symbol\nDONE\n"); return 3; }
        unsigned char p[8];
        p[0] = (unsigned char)(pat & 0xff);
        p[1] = 0;
        p[2] = 0;
        p[3] = 0x70;
        p[4] = (unsigned char)((pat >> 8) & 0xff);
        p[5] = p[0];
        p[6] = p[4];
        p[7] = 0;
        n = 0;
        n += put_str(b + n, "ycc_params=");
        for (int i = 0; i < 7; i++) { b[n++] = HEXD[(p[i] >> 4) & 0xf]; b[n++] = HEXD[p[i] & 0xf]; }
        b[n++] = '\n'; emit(b, n);
        unsigned int token = 0;
        ((fn_ycc)f_ycc)(&token, p);
        EMIT("yccmixer returned OK\n");
    }

    EMIT("DONE\n");
    if (g_log != 1) close(g_log);
    return 0;
}
