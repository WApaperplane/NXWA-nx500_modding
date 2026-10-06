/* x11probe.c — NX500 方案B 最小验证：裸 X11 全屏窗口能否在相机 :0 上弹出来。
 *
 * 不依赖 X11 头文件：sysroot 里没有 X11/Xlib.h，所以这里手工声明用到的 ABI。
 * 这样做的额外好处：若签名/类型与相机 libX11.so.6 不符，编译或运行会立刻暴露。
 *
 * 相机事实（2026-10-03 实测）：
 *   Xorg :0 -ac        <- 禁用访问控制，任何进程可连，无需 XAUTH
 *   libX11.so.6        <- X11 客户端库在（934152 字节）
 *   libelementary.so.1 / libevas / libecore 也在（EFL 方案备选）
 *
 * 编译：zig cc -target arm-linux-gnueabi.2.15 -O0 -mfloat-abi=soft
 * 运行：DISPLAY=:0 ./x11probe.arm
 */

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/* ================= 最小 X11 ABI 声明 ================= */

typedef int Bool;
typedef int Status;
typedef unsigned long XID;
typedef unsigned long Atom;
typedef unsigned long Time;
typedef unsigned long VisualID;
typedef unsigned long Window;
typedef unsigned long Pixmap;
typedef unsigned long Colormap;
typedef unsigned long Cursor;

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

typedef struct {
    Pixmap background_pixmap;
    unsigned long background_pixel;
    Pixmap border_pixmap;
    unsigned long border_pixel;
    int bit_gravity;
    int win_gravity;
    int backing_store;
    unsigned long backing_planes;
    unsigned long backing_pixel;
    Bool save_under;
    long event_mask;
    long do_not_propagate_mask;
    Bool override_redirect;
    Atom colormap;
    Cursor cursor;
} XSetWindowAttributes;

typedef struct {
    long flags;
    int x, y;
    int width, height;
    int min_width, min_height;
    int max_width, max_height;
    int width_inc, height_inc;
    struct { int x, y; } min_aspect, max_aspect;
    int base_width, base_height;
    int win_gravity;
    int backing_store;
    unsigned long backing_planes;
    unsigned long backing_pixel;
    Bool save_under;
    long event_mask;
    long do_not_propagate_mask;
    Bool override_redirect;
    Atom colormap;
    Cursor cursor;
} XSizeHints;

typedef struct {
    int type;
    unsigned long serial;
    Bool send_event;
    Display *display;
    Window window;
} XEvent;

/* X.h */
#define False 0
#define True 1

/* 事件掩码 */
#define KeyPressMask (1L << 0)
#define ButtonPressMask (1L << 2)
#define ExposureMask (1L << 15)
#define StructureNotifyMask (1L << 17)

/* 事件类型 */
#define KeyPress 2
#define Expose 12

/* Xutil.h */
#define PSize (1L << 3)
#define PMaxSize (1L << 5)

/* Xlib 函数 */
Display *XOpenDisplay(const char *);
int XCloseDisplay(Display *);
int XDefaultScreen(Display *);
Screen *XScreenOfDisplay(Display *, int);
Window XRootWindow(Display *, int);
GC XCreateGC(Display *, XID, unsigned long, void *);
int XFreeGC(Display *, GC);
Window XCreateSimpleWindow(Display *, Window, int, int, unsigned int, unsigned int,
                           unsigned int, unsigned long, unsigned long);
int XStoreName(Display *, XID, const char *);
int XSelectInput(Display *, XID, long);
int XMapWindow(Display *, XID);
int XUnmapWindow(Display *, XID);
int XClearWindow(Display *, XID);
int XFillRectangle(Display *, XID, GC, int, int, unsigned int, unsigned int);
void XDrawRectangle(Display *, XID, GC, int, int, unsigned int, unsigned int);
void XSetForeground(Display *, GC, unsigned long);
int XFlush(Display *);
int XSync(Display *, Bool);
int XSetWMNormalHints(Display *, XID, XSizeHints *);
Status XGetGeometry(Display *, XID, Window *, int *, int *, unsigned int *, unsigned int *,
                    unsigned int *, unsigned int *);
Status XGetWMName(Display *, XID, char **);
int XNextEvent(Display *, XEvent *);
int XPending(Display *);
int XFree(void *);
int XDisplayWidth(Display *, int);
int XDisplayHeight(Display *, int);
int XDefaultDepth(Display *, int);
Visual *XDefaultVisual(Display *, int);
unsigned long XBlackPixel(Display *, int);
unsigned long XWhitePixel(Display *, int);
Colormap XDefaultColormap(Display *, int);
Bool XQueryExtension(Display *, const char *, int *, int *, int *);

extern char **environ;

/* ================= 最小日志 =================
 * GUI 侧 stdout 看不到（telnet 只能看到 tty 输出），所以日志同时写 SD 卡文件。 */

static FILE *g_log;

static void L(const char *fmt, ...) {
    char buf[512];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof buf, fmt, ap);
    va_end(ap);
    if (g_log) {
        fputs(buf, g_log);
        fputc('\n', g_log);
        fflush(g_log);
    }
}

/* ================= 主程序 ================= */

int main(int argc, char **argv) {
    int secs = (argc > 1) ? atoi(argv[1]) : 8;
    const char *logpath = (argc > 3) ? argv[3] : "/opt/storage/sdcard/filmlab-probe.log";

    g_log = fopen(logpath, "w");
    L("=== x11probe start (secs=%d) ===", secs);
    L("DISPLAY env = %s", (environ && environ[0]) ? environ[0] : "(null)");

    const char *dpy_name = (argc > 2) ? argv[2] : getenv("DISPLAY");
    if (!dpy_name) dpy_name = ":0";
    L("opening display \"%s\"", dpy_name);

    Display *d = XOpenDisplay(dpy_name);
    if (!d) {
        L("FAIL: XOpenDisplay(\"%s\") returned NULL", dpy_name);
        L("HINT: Xorg running? DISPLAY value right? -ac flag present?");
        if (g_log) fclose(g_log);
        return 2;
    }
    L("OK: XOpenDisplay succeeded");

    int scr = XDefaultScreen(d);
    L("default screen = %d", scr);
    int W = XDisplayWidth(d, scr);
    int H = XDisplayHeight(d, scr);
    L("display size = %d x %d", W, H);

    Window root = XRootWindow(d, scr);
    /* 刻意不访问 Visual 的任何字段。
     * X11 的 Visual/Screen 结构体布局在 ABI 上随实现变化（visualid vs visualId、
     * class 字段位置等），猜错读到的是垃圾，而现象会伪装成"画面异常"，
     * 极难排查。凡是 libX11 自己导出为函数/宏的（XDefaultVisual 返回指针、
     * XDefaultDepth 返回 int），一律走符号，不碰结构体。 */
    Visual *vis = XDefaultVisual(d, scr);
    L("default visual ptr = %p", (void *)vis);
    L("default depth = %d", XDefaultDepth(d, scr));
    L("black_pixel=0x%lx white_pixel=0x%lx colormap=0x%lx",
      (unsigned long)XBlackPixel(d, scr), (unsigned long)XWhitePixel(d, scr),
      (unsigned long)XDefaultColormap(d, scr));
    L("root = 0x%lx", (unsigned long)root);

    /* 探一下有没有 XKB / XInput 扩展，说明 X server 是完整实现而非精简版 */
    {
        int op, err, ev;
        if (XQueryExtension(d, "XKEYBOARD", &op, &err, &ev)) {
            L("XKEYBOARD extension: present (major_opcode=%d)", op);
        } else {
            L("XKEYBOARD extension: absent");
        }
    }

    if (W <= 0 || H <= 0) { W = 1024; H = 768; L("fallback geometry"); }

    /* 注意：XCreateSimpleWindow 不接受 attributes，override_redirect 拿不到。
     * 第一版先用 simple window 验证"能不能出现"，appearance 后续用
     * XCreateWindow 补。 */
    Window w = XCreateSimpleWindow(d, root, 0, 0, (unsigned)W, (unsigned)H, 0,
                                   0x00FF0000, /* border red   */
                                   0x00181818  /* bg dark gray */);
    L("created window id = 0x%lx", (unsigned long)w);

    XStoreName(d, w, "nx-film-lab");
    L("stored window name");

    XSizeHints sh;
    memset(&sh, 0, sizeof sh);
    sh.flags = PSize | PMaxSize;
    sh.width = W;
    sh.height = H;
    sh.max_width = W;
    sh.max_height = H;
    XSetWMNormalHints(d, w, &sh);
    L("set size hints %dx%d (fixed)", W, H);

    XSelectInput(d, w, ExposureMask | KeyPressMask | ButtonPressMask | StructureNotifyMask);

    GC gc = XCreateGC(d, w, 0, NULL);
    L("created GC = %p", (void *)gc);

    XMapWindow(d, w);
    XSync(d, False);
    L("mapped window, syncing");

    /* 画色块证明能写像素 */
    XSetForeground(d, gc, 0x00E0A030);
    XFillRectangle(d, w, gc, W / 8, H / 8, (unsigned)(W * 3 / 4), (unsigned)(H / 6));
    XSetForeground(d, gc, 0x00FFFFFF);
    for (int i = 0; i < 8; i++) {
        XDrawRectangle(d, w, gc, 4 + i, 4 + i,
                       (unsigned)(W - 8 - 2 * i), (unsigned)(H - 8 - 2 * i));
    }
    XSync(d, False);
    L("drew color block + border");

    int events = 0, exposed = 0, keypress = 0;
    for (int i = 0; i < secs * 10; i++) {
        while (XPending(d)) {
            XEvent ev;
            XNextEvent(d, &ev);
            events++;
            if (ev.type == Expose) exposed++;
            if (ev.type == KeyPress) keypress++;
        }
        if (keypress) { L("keypress received, exiting early"); break; }
        usleep(100 * 1000);
    }
    L("event loop: events=%d exposed=%d keypress=%d", events, exposed, keypress);

    Window rr;
    int rx, ry;
    unsigned int rw, rh, rb, rd;
    if (XGetGeometry(d, w, &rr, &rx, &ry, &rw, &rh, &rb, &rd) != 0) {
        L("geometry recheck OK: %ux%u at %d,%d depth=%u", rw, rh, rx, ry, rd);
    } else {
        L("geometry recheck FAILED (window destroyed?)");
    }

    char *wname = NULL;
    if (XGetWMName(d, w, &wname) != 0 && wname) {
        L("wm name = %s", wname);
        XFree(wname);
    }

    L("unmapping, closing");
    XUnmapWindow(d, w);
    XFreeGC(d, gc);
    XCloseDisplay(d);

    const char *verdict = (exposed > 0) ? "WINDOW_VISIBLE_AND_PAINTED"
                       : (events > 0) ? "MAPPED_NO_EXPOSE"
                       : "MAPPED_NO_EVENTS";
    L("=== VERDICT = %s ===", verdict);
    if (g_log) fclose(g_log);
    return 0;
}
