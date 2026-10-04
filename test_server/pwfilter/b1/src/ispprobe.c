/*
 * ispprobe.c — ISP 探针 v2
 *
 * mode=1只 dlsym 解析符号（绝对安全）
 * mode=2  ★调 SingletonI<CCapVirtualAddrIf>::getInstance() 拿实例
 * mode=3  ★拿实例后调 GetVirtTopAddr()（只读成员）
 *
 * ★ 教训 1：GetCameraIfHandle() 直接调会崩（相机框架未初始化）
 * ★ 教训 2：C++ 继承里 dlsym 要用【基类】方法名（不带 C 后缀）
 * ★ 教训 3：同类库在不同进程里基址不同（ASLR）
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <signal.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int g_log = -1;
static void emit(const char *s, int n) {
    if (g_log >= 0 && n > 0) { ssize_t w = write(g_log, s, (size_t)n); (void)w; }
}
static char b[4096];
static void puts_(const char *s) {
    int n = 0; while (s[n] && n < 3000) { b[n] = s[n]; n++; }
    b[n] = 0; emit(b, n); emit("\n", 1);
}
static void puthex(unsigned int v, int pad) {
    static const char H[] = "0123456789abcdef";
    char t[12]; int n = 0, i;
    if (!v) t[n++] = '0';
    while (v) { t[n++] = H[v & 0xf]; v >>= 4; }
    while (n < pad) t[n++] = '0';
    for (i = n - 1; i >= 0; i--) b[i] = t[n - 1 - i];
    b[n] = 0; emit(b, n);
}
static void putdec(unsigned int v) {
    char t[12]; int n = 0, i;
    if (!v) t[n++] = '0';
    while (v) { t[n++] = (char)('0' + v % 10); v /= 10; }
    for (i = n - 1; i >= 0; i--) b[i] = t[n - 1 - i];
    b[n] = 0; emit(b, n);
}
static void crash_h(int s) {
    puts_("  ★★★ SIGNAL caught (进程即将崩溃，已拦截)");
    puts_("  ★ 结论：该函数不能在探针进程里调（需相机框架上下文）");
    if (g_log >= 0) close(g_log);
    _exit(0);
}

typedef void *(*fn0)(void);
typedef unsigned int (*fnm)(void *);

int main(int argc, char **argv) {
    int mode = (argc > 1) ? atoi(argv[1]) : 1;
    g_log = open("/mnt/mmc/_fl2/ispprobe.log", O_WRONLY | O_CREAT | O_TRUNC, 0644);

    puts_("=== ispprobe v2 ===");
    signal(SIGSEGV, crash_h);
    signal(SIGABRT, crash_h);
    signal(SIGBUS, crash_h);

    void *h = dlopen("/usr/lib/libcapture-fw-prod.so", RTLD_NOW | RTLD_GLOBAL);
    if (!h) { puts_(dlerror()); return 1; }
    puts_("dlopen OK");

    static const char *gi[] = {
        "_ZN9SingletonI17CCapVirtualAddrIfE11getInstanceEv",
        "_ZN9SingletonI18CCaptureControllerE11getInstanceEv",
        "_ZN9SingletonI9CTraceLogE11getInstanceEv",
        "_ZN9SingletonI17CCapturePublisherE11getInstanceEv",
        "_ZN9SingletonI11CMCBAdapterE11getInstanceEv",
        NULL
    };
    puts_("");
    puts_("=== SingletonI::getInstance ===");
    void *inst[5];
    for (int i = 0; i < 5; i++) inst[i] = 0;
    for (int i = 0; gi[i]; i++) {
        void *p = dlsym(h, gi[i]);
        puts_(gi[i]);
        emit("  -> ", 5);
        puthex((unsigned int)(unsigned long)p, 8);
        inst[i] = p;
        emit("\n", 1);
    }

    if (mode >= 2) {
        puts_("");
        puts_("=== call getInstance(CCapVirtualAddrIf) ===");
        if (inst[0]) {
            fn0 f = (fn0)inst[0];
            void *r = f();
            emit("  instance = ", 13);
            puthex((unsigned int)(unsigned long)r, 8);
            emit("\n", 1);
            if (r) {
                void **vt = *(void ***)r;
                emit("  vtable = ", 10);
                puthex((unsigned int)(unsigned long)vt, 8);
                emit("\n", 1);
                if (vt) {
                    puts_("  --- vtable[0..7] ---");
                    for (int i = 0; i < 8; i++) {
                        emit("    [", 5); putdec((unsigned)i);
                        emit("] = ", 5);
                        puthex((unsigned int)(unsigned long)vt[i], 8);
                        emit("\n", 1);
                    }
                }
                puts_("  --- instance members +0x00..+0x30 ---");
                unsigned char *hp = (unsigned char *)r;
                for (int i = 0; i < 0x30; i += 4) {
                    emit("    +", 4); putdec((unsigned)i);
                    emit(" = ", 3);
                    puthex((unsigned)(hp[i] | (hp[i+1] << 8) |
                                       (hp[i+2] << 16) | ((unsigned)hp[i+3] << 24)), 8);
                    emit("\n", 1);
                }
                if (mode >= 3) {
                    puts_("");
                    puts_("=== call GetVirtTopAddr() ===");
                    void *gs = dlsym(h, "_ZN17CCapVirtualAddrIf14GetVirtTopAddrEv");
                    emit("  dlsym -> ", 11);
                    puthex((unsigned int)(unsigned long)gs, 8);
                    emit("\n", 1);
                    if (gs) {
                        fnm g = (fnm)gs;
                        unsigned int top = g(r);
                        emit("  VirtTopAddr = ", 16);
                        puthex(top, 8);
                        emit("\n", 1);
                    }
                }
                /* ★ mode=4: 调 GetAddressMap（4 个出参） */
                if (mode >= 4) {
                    puts_("");
                    puts_("=== call GetAddressMap(&a,&b,&c,&d) ===");
                    void *am = dlsym(h, "_ZN17CCapVirtualAddrIf13GetAddressMapEPjjS0_S0_");
                    emit("  dlsym -> ", 11);
                    puthex((unsigned int)(unsigned long)am, 8);
                    emit("\n", 1);
                    if (am) {
                        typedef void (*fnmap)(void *, void **, void **, void **, void **);
                        fnmap m4 = (fnmap)am;
                        unsigned int a = 0, b = 0, c = 0, d = 0;
                        m4(r, (void **)&a, (void **)&b, (void **)&c, (void **)&d);
                        emit("  out1 = ", 9); puthex(a, 8);
                        emit("\n  out2 = ", 9); puthex(b, 8);
                        emit("\n  out3 = ", 9); puthex(c, 8);
                        emit("\n  out4 = ", 9); puthex(d, 8);
                        emit("\n", 1);
                    }
                }
                /* ★ mode=5: 调 ConvToVirtAddrOnly(phys, &v, &sz) */
                if (mode >= 5) {
                    puts_("");
                    puts_("=== call ConvToVirtAddrOnly ===");
                    void *cv = dlsym(h, "_ZN17CCapVirtualAddrIf18ConvToVirtAddrOnlyEjPjj");
                    emit("  dlsym -> ", 11);
                    puthex((unsigned int)(unsigned long)cv, 8);
                    emit("\n", 1);
                    if (cv) {
                        typedef void (*fncv)(void *, unsigned int, unsigned int *, unsigned int *);
                        fncv f2 = (fncv)cv;
                        unsigned int v = 0, sz = 0;
                        /* ★ 试CMA 区物理地址 0x94000000（dmesg 已知）*/
                        f2(r, 0x94000000u, &v, &sz);
                        emit("  phys=0x94000000 -> virt=", 25);
                        puthex(v, 8);
                        emit(" size=", 6);
                        puthex(sz, 8);
                        emit("\n", 1);
                        /* 试 ISP 段（从 /proc/maps 看到 0x85400000 等）*/
                        f2(r, 0x85400000u, &v, &sz);
                        emit("  phys=0x85400000 -> virt=", 25);
                        puthex(v, 8);
                        emit(" size=", 6);
                        puthex(sz, 8);
                        emit("\n", 1);
                    }
                }
            }
        }
    }

    puts_("");
    puts_("=== done ===");
    close(g_log);
    return 0;
}
