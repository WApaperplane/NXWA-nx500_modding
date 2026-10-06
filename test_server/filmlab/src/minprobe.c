/* minprobe.c — 极简诊断：把「段错误发生在哪一步」定位到具体一行。
 *
 * x11probe 段错误(139) 有多种可能，逐个排除太慢。这里只做最小的三件事：
 *   1. fopen 日志          -> 验证 libc 动态链接没问题
 *   2. XOpenDisplay(":0")  -> 验证 X11 动态链接 + -ac 开放
 *   3. XDefaultScreen/Width -> 验证返回的 Display 指针可用
 *
 * 每步都立刻 flush 到 SD 卡文件，段错误后看最后写到哪一行就知道卡在哪。
 * 日志用 write() 到已 open 的 fd（不依赖 stdio 缓冲），最抗崩溃。
 */
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

typedef int Bool;
#define True 1
#define False 0
typedef unsigned long XID;
typedef unsigned long Window;
typedef unsigned long Colormap;
typedef struct _XDisplay Display;
typedef struct _XGC *GC;
typedef struct {
    void *ext_data;
    Display *display;
    unsigned long resourceid;
    unsigned long screen;
} Visual;
typedef struct {
    int x, y;
    unsigned int width, height;
    unsigned int border_width;
    int depth;
    Visual *visual;
    XID root;
    int class;
    long visual_mask;
    long *visual_ids;
    int backing_store;
    unsigned long backing_planes;
    unsigned long backing_pixel;
    int save_unders;
    long colormap;
    int bitmap_inc;
} Screen;

Display *XOpenDisplay(const char *);
int XDefaultScreen(Display *);
Screen *XScreenOfDisplay(Display *, int);
Window XRootWindow(Display *, int);
int XDisplayWidth(Display *, int);
int XDisplayHeight(Display *, int);
int XCloseDisplay(Display *);
int XSync(Display *, Bool);
int XDefaultDepth(Display *, int);
Colormap XDefaultColormap(Display *, int);
unsigned long XBlackPixel(Display *, int);
unsigned long XWhitePixel(Display *, int);
Window XCreateSimpleWindow(Display *, Window, int, int, unsigned int, unsigned int,
                           unsigned int, unsigned long, unsigned long);
int XMapWindow(Display *, XID);
int XSelectInput(Display *, XID, long);
int XStoreName(Display *, XID, const char *);
GC XCreateGC(Display *, XID, unsigned long, void *);
int XFreeGC(Display *, GC);
int XFlush(Display *);
int XUnmapWindow(Display *, XID);
#define ExposureMask (1L << 15)
#define KeyPressMask (1L << 0)

static int g_fd = -1;

static void LOG(const char *msg) {
    if (g_fd < 0) return;
    /* write() 不缓冲，段错误后已写入的内容一定在盘上 */
    ssize_t n = write(g_fd, msg, strlen(msg));
    (void)n;
    n = write(g_fd, "\n", 1);
    (void)n;
}

static void LOGN(const char *label, long v) {
    char buf[128];
    int i = 0;
    while (label[i] && i < 60) { buf[i] = label[i]; i++; }
    buf[i++] = '=';
    /* 手写十进制，避免 snprintf 依赖 stdio */
    char num[24];
    int j = 0;
    if (v < 0) { num[j++] = '-'; v = -v; }
    if (v == 0) num[j++] = '0';
    while (v > 0 && j < 20) { num[j++] = (char)('0' + v % 10); v /= 10; }
    while (j > 0) buf[i++] = num[--j];
    buf[i++] = '\n';
    ssize_t n = write(g_fd, buf, i);
    (void)n;
}

int main(void) {
    const char *lp = "/opt/storage/sdcard/filmlab-probe.log";

    LOG("STAGE1 fopen");
    g_fd = open(lp, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (g_fd < 0) {
        /* 退而求其次写 /tmp */
        g_fd = open("/tmp/filmlab-probe.log", O_WRONLY | O_CREAT | O_TRUNC, 0644);
        LOG("STAGE1 fopen sdcard failed, using /tmp");
    }
    if (g_fd < 0) return 9;
    LOG("STAGE1 ok, libc works");

    LOG("STAGE2 XOpenDisplay");
    Display *d = XOpenDisplay(":0");
    LOGN("STAGE2 XOpenDisplay ptr", (long)(size_t)d);
    if (!d) {
        LOG("STAGE2 FAIL: null (no -ac? wrong DISPLAY? Xorg not running?)");
        close(g_fd);
        return 2;
    }
    LOG("STAGE2 ok");

    LOG("STAGE3 XDefaultScreen");
    int scr = XDefaultScreen(d);
    LOGN("STAGE3 screen", scr);

    LOG("STAGE4 display size");
    int W = XDisplayWidth(d, scr);
    int H = XDisplayHeight(d, scr);
    LOGN("STAGE4 width", W);
    LOGN("STAGE4 height", H);

    LOG("STAGE5 colors");
    LOGN("STAGE5 black", (long)XBlackPixel(d, scr));
    LOGN("STAGE5 white", (long)XWhitePixel(d, scr));
    LOGN("STAGE5 colormap", (long)XDefaultColormap(d, scr));
    LOGN("STAGE5 depth", XDefaultDepth(d, scr));

    LOG("STAGE6 root window");
    Window root = XRootWindow(d, scr);
    LOGN("STAGE6 root", (long)root);

    LOG("STAGE7 create window");
    Window w = XCreateSimpleWindow(d, root, 0, 0, (unsigned)W, (unsigned)H, 0, 0x00FF0000, 0x00181818);
    LOGN("STAGE7 window id", (long)w);

    LOG("STAGE8 store name");
    XStoreName(d, w, "nx-film-lab");
    LOG("STAGE8 ok");

    LOG("STAGE9 map");
    XSelectInput(d, w, ExposureMask | KeyPressMask);
    XMapWindow(d, w);
    XSync(d, False);
    LOG("STAGE9 ok, window should be visible now");

    LOG("STAGE10 gc");
    GC gc = XCreateGC(d, w, 0, NULL);
    LOGN("STAGE10 gc", (long)(size_t)gc);

    LOG("STAGE11 hold 6s");
    sleep(6);
    LOG("STAGE11 done");

    LOG("STAGE12 cleanup");
    XUnmapWindow(d, w);
    XFreeGC(d, gc);
    XCloseDisplay(d);
    LOG("ALL STAGES PASSED");
    close(g_fd);
    return 0;
}
