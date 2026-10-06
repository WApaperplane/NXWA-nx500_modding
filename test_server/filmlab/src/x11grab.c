/*
 * x11grab.c — X11 抓屏探针（方案 B 延伸）
 *
 * 目的：验证「能否用 XGetImage 从 X server 抓到 liveview 画面」。
 * 背景（2026-10-03 实测）：相机上的 liveview 显示进程 isf-panel-efl
 *   链接 libecore_x.so.1.7.99 且 DISPLAY=:0，即它本身把 liveview 画成
 *   X11 窗口。若如此，XGetImage(root) 就能拿到画面。
 *
 * 本探针回答唯一问题：XGetImage(root) 返回的像素里有没有真实图像内容。
 * 输出 PPM(P6) 到文件，PC 端直接看图判真伪。
 *
 * 用法：x11grab <outfile.ppm> [帧数]
 *
 * ABI：sysroot 无 X11 头文件，全部手写。不访问 Visual/Screen 结构体字段
 *      （布局随实现变化，猜错的现象会伪装成"画面异常"，极难排查）。
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdarg.h>

typedef struct _XDisplay Display;
typedef unsigned long XID;
typedef unsigned int Window;
typedef unsigned int Drawable;
typedef unsigned long Pixmap;
typedef unsigned long VisualID;
typedef int Bool;
typedef int Status;
typedef struct _XGC *GC;

#define True 1
#define False 0
#define ZPixmap 2
#define AllPlanes 0xFFFFFFFFUL

/* ---- Xlib ABI ---- */
Display *XOpenDisplay(const char *);
int XCloseDisplay(Display *);
int XDefaultScreen(Display *);
int XDisplayWidth(Display *, int);
int XDisplayHeight(Display *, int);
int XDefaultDepth(Display *, int);
unsigned long XBlackPixel(Display *, int);
unsigned long XWhitePixel(Display *, int);
Window XRootWindow(Display *, int);
GC XCreateGC(Display *, Drawable, unsigned long, void *);
int XFreeGC(Display *, GC);
int XFree(void *);
int XFlush(Display *);
int XSync(Display *, Bool);
char *XGetDefault(Display *, char *, char *);
int XDisplayString(Display *, char **, int);

/* XGetImage 返回 XImage*（不是 int）。真实原型：
 *   XImage *XGetImage(Display*, Drawable, int, int, unsigned, unsigned,
 *                     unsigned long, int);
 * XImage 结构体不完整定义 —— 我们只把它当 char* 用，自己按已知布局读字段，
 * 这样既拿到正确指针类型，又不必复制整个结构定义。
 */
typedef struct _XImage XImage;
XImage *XGetImage(Display *, Drawable, int, int, unsigned, unsigned,
                  unsigned long, int);

/* ---- 日志（不用 stdio 缓冲，直接 write 落盘，避免段错误）---- */
static int g_fd = -1;
static void L(const char *fmt, ...) {
    char buf[512];
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(buf, sizeof buf, fmt, ap);
    va_end(ap);
    if (n > 0 && g_fd >= 0) {
        if (write(g_fd, buf, n) < 0) { /* 忽略 */ }
    }
}

/* 读日志内容（供 PC 端判读） */
static int g_logfd = -1;
static void openlog(void) {
    g_logfd = open("/opt/storage/sdcard/x11grab.log",
                   O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (g_logfd >= 0) g_fd = g_logfd;
}

int main(int argc, char **argv) {
    openlog();

    const char *out = (argc > 1) ? argv[1] : "/opt/storage/sdcard/grab.ppm";
    int frames = (argc > 2) ? atoi(argv[2]) : 1;

    L("STAGE1 open display");
    Display *d = XOpenDisplay(NULL);
    if (!d) { L("FAIL no display"); return 2; }
    int scr = XDefaultScreen(d);
    L("STAGE2 connected, screen=%d", scr);

    int W = XDisplayWidth(d, scr);
    int H = XDisplayHeight(d, scr);
    int depth = XDefaultDepth(d, scr);
    Window root = XRootWindow(d, scr);
    L("STAGE3 %dx%d depth=%d root=0x%x", W, H, depth, root);
    L("       black=0x%lx white=0x%lx",
      XBlackPixel(d, scr), XWhitePixel(d, scr));

    /* 屏幕可能不是 root 大小；先用root 尺寸试 */
    L("STAGE4 XCreateGC");
    GC gc = XCreateGC(d, root, 0, NULL);
    L("       gc=%p", (void *)gc);

    /* XGetImage 的 XImage 结构：我们要自己按 32bpp 布局读。
     * 深度 24 + 32bpp 是X11 最常见布局（ZPixmap），
     * 但为安全起见先只抓一个小区域（如 64x64）验证不崩。 */
    int tw = (W < 64) ? W : 64;
    int th = (H < 64) ? H : 64;

    L("STAGE5 XGetImage test %dx%d", tw, th);
    /* 注意：XGetImage 需要 sync 后调用，否则可能读到未定义的图像 */
    XSync(d, False);
    void *img = XGetImage(d, root, 0, 0, tw, th, AllPlanes, ZPixmap);
    if (!img) { L("FAIL XGetImage returned NULL"); return 3; }
    L("       XGetImage ptr=%p", img);

    /*
     * XImage 结构布局（Xlib.h）：
     *   int width, height;
     *   int xoffset;
     *   int format;        // 1 = XYBitmap, 2 = XYPixmap, 0 = ZPixmap
     *   char *data;
     *   int byte_order;
     *   int bitmap_unit;
     *   int bitmap_bit_order;
     *   int bitmap_pad;
     *   int depth;
     *   int bytes_per_line;
     *   int bits_per_pixel;
     *   int red_mask, green_mask, blue_mask;
     *   ...
     * 全部是 int，除 data 是 char*，所以偏移：
     *   width@0 height@4 xoffset@8 format@12 data@16 (64位下对齐到16)
     */
    int *ip = (int *)img;
    int iw = ip[0], ih = ip[1], ifmt = ip[3];
    char *idata = (char *)ip[4];
    int bpl = ip[10];
    int bpp = ip[11];
    int rm = ip[12], gm = ip[13], bm = ip[14];
    L("       XImage w=%d h=%d format=%d data=%p", iw, ih, ifmt, (void *)idata);
    L("       bytes_per_line=%d bits_per_pixel=%d", bpl, bpp);
    L("       masks R=0x%x G=0x%x B=0x%x", rm, gm, bm);

    if (!idata || bpl <= 0 || bpp < 8) {
        L("FAIL bad XImage geometry");
        return 4;
    }

    /* 抓一张完整图 */
    L("STAGE6 full grab %dx%d", W, H);
    XSync(d, False);
    void *full = XGetImage(d, root, 0, 0, W, H, AllPlanes, ZPixmap);
    if (!full) { L("FAIL full XGetImage NULL"); return 5; }
    int *fp = (int *)full;
    char *fdata = (char *)fp[4];
    int fbpl = fp[10];
    int fbpp = fp[11];
    L("       full data=%p bpl=%d bpp=%d", (void *)fdata, fbpl, fbpp);

    /* 像素统计：判断是否有真实图像内容（非纯色） */
    unsigned long long sum = 0, n = 0;
    unsigned int mn = 0xFFFFFFFF, mx = 0;
    for (int y = 0; y < H; y += 3) {
        unsigned char *row = (unsigned char *)fdata + y * fbpl;
        for (int x = 0; x < W; x += 3) {
            unsigned int v;
            if (fbpp == 32)
                v = ((unsigned int *)row)[x];
            else if (fbpp == 24) {
                v = (row[x * 3] << 16) | (row[x * 3 + 1] << 8) | row[x * 3 + 2];
            } else if (fbpp == 16) {
                v = ((unsigned short *)row)[x] & 0xFFFF;
            } else {
                v = row[x];
            }
            sum += v; n++;
            if (v < mn) mn = v;
            if (v > mx) mx = v;
        }
    }
    L("STAGE7 stats sampled=%llu mean=%llu min=%u max=%u",
      n, n ? sum / n : 0, mn, mx);
    if (n && mx > mn)
        L("       NOT uniform -> there IS image content");
    else
        L("       UNIFORM -> no liveview content (blank)");

    /* 写 PPM（P6），按 32bpp 假定转 RGB */
    L("STAGE8 write ppm %s", out);
    FILE *f = fopen(out, "wb");
    if (!f) { L("FAIL cannot open out"); return 6; }
    fprintf(f, "P6\n%d %d\n255\n", W, H);
    for (int y = 0; y < H; y++) {
        unsigned char *row = (unsigned char *)fdata + y * fbpl;
        for (int x = 0; x < W; x++) {
            unsigned char rgb[3];
            if (fbpp == 32) {
                unsigned int v = ((unsigned int *)row)[x];
                rgb[0] = (v >> 16) & 0xFF; rgb[1] = (v >> 8) & 0xFF; rgb[2] = v & 0xFF;
            } else if (fbpp == 16) {
                unsigned short v = ((unsigned short *)row)[x];
                rgb[0] = ((v >> 11) & 0x1F) << 3;
                rgb[1] = ((v >> 5) & 0x3F) << 2;
                rgb[2] = (v & 0x1F) << 3;
            } else {
                rgb[0] = rgb[1] = rgb[2] = row[x];
            }
            fwrite(rgb, 1, 3, f);
        }
    }
    fclose(f);
    L("STAGE9 done, frames arg=%d (unused)", frames);
    L("ALL PASSED");
    if (g_fd >= 0) { fsync(g_fd); close(g_fd); }
    return 0;
}