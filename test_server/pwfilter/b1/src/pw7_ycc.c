/*
 * pw7-ycc.c — B2 route: write the 7 Picture Wizard dimensions via
 *             d5_ep_mc_set_custom_param_yccmixer.
 *
 * Why this route exists
 * --------------------
 * The 3D LUT entry points need a kernel-allocated handle: passing a stack
 * struct to d5_ep_3dlut_op_init segfaults immediately. But
 * d5_ep_mc_set_custom_param_yccmixer dereferences only its two arguments and
 * needs no handle, so it is reachable from plain user space.
 *
 * What the disassembly says it does (libudd5.so @ 0x29488, 288 bytes)
 * ---------------------------------------------------------------------
 *   p0 (r0) : base pointer;  [p0] is written straight into reg 0x280
 *   p1 (r1) : PW params;     [p1+0] -> reg 0x284
 *                        [p1+4] -> reg 0x280 (via the +0x280 store above)
 *                        (u8)[p1+3] bit[7:4] = 7      <- `mov r3,#7`
 *                        (u8)[p1+5] = p1[0] low byte
 *                        (u8)[p1+6] = p1[4] low byte
 *   then calls d5_ep_top_update_sreg(0x14)
 *        0x14 == 20 == the setusr index we already mapped to PW_TYPE,
 *        so this is the "apply now" trigger.
 *
 * Layout of p1 (as consumed by the function) -- 7 bytes at offsets 0..6:
 *   [0] value written to reg0x280 low
 *   [1] (unused by the stores we can see)
 *   [2] (unused)
 *   [3] bits[3:0] preserved, bits[7:4] = 7
 *   [4] value written to reg0x284
 *   [5] = [0]
 *   [6] = [4]
 *
 * The exact field order is NOT yet known. This probe therefore does two safe
 * things first:
 *   step 1: read-only: resolve symbols, print the two GOT-derived register
 *           addresses by calling the library's own accessor if available
 *   step 2: write one distinguishable pattern (a "monochrome" pattern:
 *           saturation = 0) and report the return value
 *
 * The user MUST visually confirm the effect; this program cannot see the
 * viewfinder. Read pwfilter/b1/PW7_PROBE.md before running step 2.
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
static int put_dec(char *b, unsigned int v) {
    char t[12]; int n = 0, i;
    if (!v) t[n++] = '0';
    while (v) { t[n++] = (char)('0' + (v % 10)); v /= 10; }
    for (i = 0; i < n; i++) b[i] = t[n - 1 - i];
    return n;
}
static int put_str(char *b, const char *s) { int n = 0; while (s[n]) { b[n] = s[n]; n++; } return n; }

/* signature guess: void f(void *regbase, void *params) */
typedef void (*fn_ycc)(void *, void *);
typedef int (*fn_sreg)(int);

int main(int argc, char **argv) {
    const char *path = (argc > 1) ? argv[1] : "/usr/lib/libudd5.so";
    /* mode 0 = dry run (resolve only), 1 = apply pattern */
    int apply = (argc > 2) ? atoi(argv[2]) : 0;
    unsigned int pat = (argc > 3) ? (unsigned int)strtoul(argv[3], 0, 0) : 0x00010101u;
    char b[256];
    int n;

    g_log = open("/mnt/mmc/_pwtest/pw7.log", O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (g_log < 0) g_log = 1;

    EMIT("=== PW7 via yccmixer ===\n");
    n = 0;
    n += put_str(b + n, "apply="); n += put_dec(b + n, (unsigned int)apply);
    n += put_str(b + n, " pat=");  n += put_hex(b + n, pat, 8);
    b[n++] = '\n'; emit(b, n);

    void *h = dlopen(path, RTLD_NOW | RTLD_GLOBAL);
    if (!h) { EMIT("FAIL dlopen\n"); return 1; }
    EMIT("OK dlopen\n");

    void *fy = dlsym(h, "d5_ep_mc_set_custom_param_yccmixer");
    void *fs = dlsym(h, "d5_ep_top_update_sreg");
    void *rb = dlsym(h, "ep_mc_reg_base");
    n = 0;
    n += put_str(b + n, "ycc=");  n += put_hex(b + n, (unsigned int)(unsigned long)fy, 8);
    n += put_str(b + n, " sreg="); n += put_hex(b + n, (unsigned int)(unsigned long)fs, 8);
    n += put_str(b + n, " mcbase="); n += put_hex(b + n, (unsigned int)(unsigned long)rb, 8);
    b[n++] = '\n'; emit(b, n);

    if (!fy) { EMIT("FAIL no yccmixer symbol\n"); return 1; }

    if (!apply) {
        EMIT("dry run: nothing written\n");
        /* still report what the mc base holds, read-only */
        if (rb) {
            unsigned int v = *(unsigned int *)rb;
            n = 0; n += put_str(b + n, "MC_BASE="); n += put_hex(b + n, v, 8);
            b[n++] = '\n'; emit(b, n);
        }
        EMIT("DONE\n");
        return 0;
    }

    /* Build the 7-byte params. Field order is a working hypothesis; the
       distinctive part is that byte 3 gets 0x7X where X is a selector. */
    unsigned char p[8];
    p[0] = (unsigned char)(pat & 0xff);        /* -> reg 0x280, and -> p[5] */
    p[1] = 0;
    p[2] = 0;
    p[3] = 0x70;                                /* bits[7:4]=7 (from mov r3,#7) */
    p[4] = (unsigned char)((pat >> 8) & 0xff); /* -> reg 0x284, and -> p[6] */
    p[5] = p[0];
    p[6] = p[4];
    p[7] = 0;

    n = 0;
    n += put_str(b + n, "params=");
    for (int i = 0; i < 7; i++) { b[n++] = HEXD[(p[i] >> 4) & 0xf]; b[n++] = HEXD[p[i] & 0xf]; }
    b[n++] = '\n'; emit(b, n);

    /* p0 is copied verbatim into reg 0x280, so pass a small non-null token. */
    unsigned int token = 0;
    void *p0 = &token;

    fn_ycc ycc = (fn_ycc)fy;
    ycc(p0, p);                 /* write registers + call update_sreg(0x14) */
    EMIT("yccmixer returned\n");
    EMIT("DONE\n");
    if (g_log != 1) close(g_log);
    return 0;
}
