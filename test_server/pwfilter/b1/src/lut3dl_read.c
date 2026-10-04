/*
 * lut3dl-read.c — stage 2: read back whatever the ISP currently has in the 3D LUT.
 *
 * Stage 1 result (2026-10-04): all 26 dlsym lookups succeed; runtime - static
 * offset is exactly 0xb6d29000 for every symbol, confirming the static
 * disassembly is correct. But `ep_3dlut_reg_base` *contains* 0.
 *
 * Interpretation: that global pointer is filled in by kernel/ISP-side code at
 * init. A plain user process sees 0 because it has not been populated for us.
 * So we must go through the library's own entry points instead, which will
 * resolve the handle internally.
 *
 * This stage uses d5_ep_3dl_save_lut (mode = 2 = READ). Read-only by design:
 * we do NOT call load_lut / SetReg / ConfigProcessMode here.
 *
 * Usage: lut3dl_read <libpath> <handle> <index> <lut_type>
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

/* 12-byte protocol struct, per reverse engineering */
struct ep3dl_st {
    unsigned int f30;      /* [0x00] mode: 1=write 2=read */
    unsigned int f2c;      /* [0x04] (constant 1 in load_lut) */
    unsigned int f20;      /* [0x08] = index */
    unsigned int handle;   /* [0x0c] */
    unsigned int lut_type; /* [0x10] 0=LUT0 1=LUT1 */
    unsigned int index;    /* [0x14] */
};

typedef int (*fn_op_init)(struct ep3dl_st *);
typedef int (*fn_save)(unsigned int handle, unsigned int index, unsigned int lut_type, void *arg3);

int main(int argc, char **argv) {
    const char *path = (argc > 1) ? argv[1] : "/usr/lib/libudd5.so";
    unsigned int handle = (argc > 2) ? (unsigned int)strtoul(argv[2], 0, 0) : 0;
    unsigned int index = (argc > 3) ? (unsigned int)strtoul(argv[3], 0, 0) : 0;
    unsigned int type = (argc > 4) ? (unsigned int)strtoul(argv[4], 0, 0) : 0;
    char b[256];
    int n;

    g_log = open("/mnt/mmc/_pwtest/lut3dl2.log", O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (g_log < 0) g_log = 1;

    EMIT("=== stage2 read back ===\n");
    n = 0;
    n += put_str(b + n, "handle="); n += put_hex(b + n, handle, 8);
    n += put_str(b + n, " index="); n += put_dec(b + n, index);
    n += put_str(b + n, " type=");  n += put_dec(b + n, type);
    b[n++] = '\n'; emit(b, n);

    void *h = dlopen(path, RTLD_NOW | RTLD_GLOBAL);
    if (!h) { EMIT("FAIL dlopen\n"); return 1; }

    fn_op_init op_init = (fn_op_init)dlsym(h, "d5_ep_3dlut_op_init");
    fn_save save_lut = (fn_save)dlsym(h, "d5_ep_3dl_save_lut");
    if (!op_init || !save_lut) { EMIT("FAIL dlsym\n"); return 1; }

    /* op_init validates [0] in {0,1}, [8] <= 2, [0xc] == 1, [0x10] == 2.
       Build a struct that satisfies those checks. */
    struct ep3dl_st st;
    st.f30 = 0;       /* read mode for init */
    st.f2c = 1;
    st.f20 = index;   /* must be <= 2 */
    st.handle = 1;
    st.lut_type = 0;
    st.index = 2;     /* must == 2 */
    int rc = op_init(&st);
    n = 0; n += put_str(b + n, "op_init rc="); n += put_dec(b + n, (unsigned int)rc);
    b[n++] = '\n'; emit(b, n);
    if (rc != 0) {
        EMIT("op_init rejected; handle probably wrong\n");
        /* still try save_lut with the raw handle so we learn its error code */
    }

    /* save_lut(handle, index, lut_type, arg3). arg3 is documented unused. */
    rc = save_lut(handle, index, type, 0);
    n = 0; n += put_str(b + n, "save_lut rc="); n += put_dec(b + n, (unsigned int)rc);
    b[n++] = '\n'; emit(b, n);

    /* Expected return codes seen in disassembly:
         -1   : handle == 0
         -2   : (0x12c negated => 300) device-not-ready class
          0   : success
       We also read ep_3dlut_reg_base again in case op_init populated it. */
    void *rb = dlsym(h, "ep_3dlut_reg_base");
    if (rb) {
        unsigned int v = *(unsigned int *)rb;
        n = 0; n += put_str(b + n, "RB after="); n += put_hex(b + n, v, 8);
        b[n++] = '\n'; emit(b, n);
    }

    EMIT("DONE\n");
    if (g_log != 1) close(g_log);
    return 0;
}
