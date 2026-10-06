/*
 * nxflab.c — FilmLab X11 配方选择器（NX500 机内）
 *
 * 目标：在相机 LCD 上提供一个图形化配方选择器，弥补 mod_gui 的不足
 *      （mod_gui 只有文字按钮、无图片、无法显示参数细节）。
 *
 * 设计约束（全部来自 2026-10-04 实机验证）：
 *  - 屏幕 720x480 depth 24，Xorg :0 -ac（无 XAUTH）
 *  - sysroot 没有 X11 头文件，XlibABI 全部手写
 *  - 不访问 Visual / Screen 结构体字段（x11probe 的教训：猜错会伪装成画面异常）
 *  - 日志用 open+write 无缓冲（fprintf 会段错误 139）
 *  - 取景器画面拿不到（fb0 是 64x64 占位缓冲，st cap live dump 静默）
 *    → 所以本程序【不显示 liveview】，改为显示配方网格 + 参数可视化
 *
 * 交互：上下键选配方 / 左右键调选中的那一个维度 / Enter 应用 / Esc 退出
 *
 * 用法：nxflab [配方目录]
 *   配方从 /mnt/mmc/filmlab/recipes.txt 读（纯文本，每行一个配方）
 *   格式： key|label|R|G|B|HUE|SAT|SHARP|CON
 */
#define _GNU_SOURCE
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>   /* vsnprintf —— x11grab 实测可用 */
#include <signal.h>
#include <errno.h>
#include <sys/select.h>
#include <sys/time.h>
#include <time.h>
#include <sys/stat.h>
#include <sys/types.h>
#include "font5x7.h"

/* ================= Xlib ABI（手写） ================= */
typedef struct _XDisplay Display;
typedef unsigned int Window;
typedef unsigned int Drawable;
typedef unsigned long Pixmap;
typedef int Bool;
typedef int Status;
typedef struct _XGC *GC;
/* 只声明我们要用的字段（Xlib 的 XFontStruct 布局前段是固定的） */
struct _XFontStruct;
typedef struct _XFontStruct {
    void *ext_data;
    unsigned long fid;
    unsigned direction;
    unsigned min_char_or_byte2;
    unsigned max_char_or_byte2;
    unsigned min_byte1;
    unsigned max_byte1;
    Bool all_chars_exist;
    unsigned default_char;
    int n_properties;
    void *properties;
    struct _XFontStruct *min_bounds;
    struct _XFontStruct *max_bounds;
    struct _XFontStruct **per_char;
    int ascent;
    int descent;
} XFontStruct;
typedef struct _XRegion *Region;
typedef struct _XWindowAttributes XWindowAttributes;

#define True 1
#define False 0
#define ZPixmap 2
#define AllPlanes 0xFFFFFFFFUL
#define InputOutput 1
#define CopyFromParent 0L
/* 事件掩码 */
#define KeyPressMask       (1L<<0)
#define KeyReleaseMask     (1L<<1)
#define ButtonPressMask    (1L<<2)
#define ExposureMask       (1L<<15)
#define StructureNotifyMask (1L<<17)
#define FocusChangeMask    (1L<<21)

Display *XOpenDisplay(const char *);
int XCloseDisplay(Display *);
int XDefaultScreen(Display *);
int XDisplayWidth(Display *, int);
int XDisplayHeight(Display *, int);
Window XRootWindow(Display *, int);
Window XCreateSimpleWindow(Display *, Window, int, int, unsigned, unsigned,
                unsigned, unsigned long, unsigned long);
int XStoreName(Display *, Window, const char *);
int XSelectInput(Display *, Window, long);
int XMapWindow(Display *, Window);
int XUnmapWindow(Display *, Window);
int XNextEvent(Display *, void *);
int XPending(Display *);
int XConnectionNumber(Display *);
int XPeekEvent(Display *, void *);
GC XCreateGC(Display *, Drawable, unsigned long, void *);
int XFreeGC(Display *, GC);
int XSetForeground(Display *, GC, unsigned long);
int XFillRectangle(Display *, Drawable, GC, int, int, unsigned, unsigned);
int XDrawRectangle(Display *, Drawable, GC, int, int, unsigned, unsigned);
int XDrawLine(Display *, Drawable, GC, int, int, int, int);
int XFillArc(Display *, Drawable, GC, int, int, unsigned, unsigned, int, int);
int XDrawString(Display *, Drawable, GC, int, int, const char *, int);
int XFlush(Display *);
int XSync(Display *, Bool);
Pixmap XCreatePixmap(Display *, Drawable, unsigned, unsigned, unsigned);
int XFreePixmap(Display *, Pixmap);
XFontStruct *XLoadQueryFont(Display *, const char *);
int XSetFont(Display *, GC, XFontStruct *);
int XFreeFont(Display *, XFontStruct *);
char *XSetLocaleModifiers(const char *);
char *XSupportsLocale(void);
int XSetGraphicsExposures(Display *, Drawable, Bool);
Pixmap XCreateBitmapFromData(Display *, Drawable, char *, unsigned, unsigned);
Region XCreateRegion(void);
int XDestroyRegion(Region);
int XUnionRectRegion(Region, XWindowAttributes *, Region);

/* XEvent 前 64 字节足够覆盖我们要读的 type / keycode / x / y / window */
typedef struct {
    int type;
    unsigned long serial;
    Bool send_event;
    Display *display;
    Window window;
    int x, y;
    int x_root, y_root;
    unsigned int state;
    unsigned int keycode;
    Bool same_screen;
} XEv;

/* 键码（X11 硬件键码，与 XKeysym 无直接关系，用常见 PC 布局值） */
#define K_LEFT   0xFF51
#define K_UP     0xFF52
#define K_RIGHT  0xFF53
#define K_DOWN   0xFF54
#define K_ENTER  0xFF0D
#define K_ESC    0xFF1B
#define K_SPACE  0x0020
#define K_q      0x0071
#define K_1      0x0031

/* ================= 颜色（RGB → 16bit 打包） ================= */
#define RGB(r, g, b) ((((r)>>3)<<11) | (((g)>>3)<<5) | ((b)>>3))
static unsigned long C_BG, C_PANEL, C_SEL, C_TXT, C_DIM, C_ACC, C_BAR, C_BARTXT, C_WARN;

static void init_colors(Display *d, int scr) {
    C_BG    = RGB(18, 20, 24);
    C_PANEL = RGB(32, 36, 42);
    C_SEL   = RGB(0, 90, 150);
    C_TXT   = RGB(235, 238, 242);
    C_DIM   = RGB(120, 128, 138);
    C_ACC   = RGB(220, 160, 40);
    C_BAR   = RGB(50, 58, 68);
    C_BARTXT= RGB(250, 250, 250);
    C_WARN  = RGB(200, 70, 60);
}

/* ================= 点阵文字绘制（不用 X font） =================
   相机 X server 无 core font（XSetFont → BadFont 致命错误），
   所以自己用 XFillRectangle 画 5x7 点阵。*/
static void draw_text(Display *d, Drawable w, GC gc, int x, int y,
                      const char *s, int scale) {
    if (!s) return;
    for (; *s; s++) {
        int ch = (unsigned char)*s;
        const unsigned char *g = font5x7_get(ch);
        for (int col = 0; col < 5; col++) {
            unsigned char bits = g[col];
            for (int row = 0; row < 7; row++) {
                if (bits & (1 << row)) {
                    XFillRectangle(d, w, gc,
                        x + col * scale, y + row * scale,
                        scale, scale);
                }
            }
        }
        x += 6 * scale;
    }
}

/* 带最大字符数限制的版本（避免超长串跑出屏幕） */
static void draw_text_n(Display *d, Drawable w, GC gc, int x, int y,
                        const char *s, int scale, int maxch) {
    if (!s) return;
    int n = 0;
    for (; *s && n < maxch; s++, n++) {
        int ch = (unsigned char)*s;
        const unsigned char *g = font5x7_get(ch);
        for (int col = 0; col < 5; col++) {
            unsigned char bits = g[col];
            for (int row = 0; row < 7; row++) {
                if (bits & (1 << row)) {
                    XFillRectangle(d, w, gc,
                        x + col * scale, y + row * scale,
                        scale, scale);
                }
            }
        }
        x += 6 * scale;
    }
}

static int text_w(int n, int scale) { return n * 6 * scale; }

/* ================= 日志（open+write，禁用 stdio 缓冲） ================= */
static int g_log = -1;
static void L(const char *fmt, ...) {
    char buf[600];
    va_list ap; va_start(ap, fmt);
    int n = vsnprintf(buf, sizeof buf, fmt, ap);
    va_end(ap);
    if (n > 0 && g_log >= 0) { if (write(g_log, buf, n) < 0) {} }
}

/* ================= 外部控制文件 =================
   ★ 问题：X11 窗口收不到机身按键（不是 EFL 窗口，无输入焦点）
   ★ 方案：监听 SD 卡上的控制文件，触屏/按键脚本写它来驱动 X11
     /mnt/mmc/filmlab/cmd  内容为一行命令：
       up / down / left / right / apply / quit
     文件 mtime 变化才处理（避免每 200ms 读盘）
   ============================================== */
#define CMDPATH "/tmp/flab_cmd"
static time_t g_cmd_mtime = 0;

/* ★ 握手协议：读到内容后立刻把文件清空（truncate to 0）
   —— 不用 mtime 判断。tmpfs mtime 只有秒级精度，
   连续两次同秒写入会被漏掉（2026-10-04 实测踩到）。
   清空后文件大小为 0，下次写入立刻被识别。 */
static int poll_cmd(char *buf, int buflen) {
    struct stat st;
    if (stat(CMDPATH, &st) != 0) return 0;
    if (st.st_size == 0) return 0;      /* 空 = 无命令 */
    int fd = open(CMDPATH, O_RDONLY);
    if (fd < 0) return 0;
    int n = read(fd, buf, buflen - 1);
    close(fd);
    if (n <= 0) return 0;
    buf[n] = 0;
    /* ★ 立刻清空，让下一次写入能被识别 */
    int w = open(CMDPATH, O_WRONLY | O_TRUNC);
    if (w >= 0) close(w);
    /* 只取第一行 */
    for (int i = 0; i < n; i++) if (buf[i] == '\n' || buf[i] == '\r') { buf[i] = 0; break; }
    L("cmd file: [%s]", buf);
    return 1;
}

/* ================= 退出机制（三条路径） =================
   ① 信号：kill / 退出 mod_gui 时能被终止
   ② 定时：IDLE_LIMIT 秒无输入自动退出（防"卡死无法关闭"）
   ③ 屏幕：右上角 EXIT 热区 + 顶部提示条
   ============================================ */
static volatile int g_quit = 0;
static void on_sig(int s) { (void)s; g_quit = 1; }

/* ★ 用 sigaction + SA_RESTART 显式安装，并把 errno 清零。
   之前用 signal() 安装，实测被 SIGHUP 杀死后日志无 "bye"
   → 说明处理器设了 g_quit 但 select() 永久重启，没回到循环头检查。 */
static void install_sig(int sig) {
    struct sigaction sa;
    memset(&sa, 0, sizeof sa);
    sa.sa_handler = on_sig;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = 0;              /* ★ 不要 SA_RESTART：让 select 返回 EINTR */
    sigaction(sig, &sa, NULL);
}

/* ================= 配方 ================= */
#define MAXR 32
struct Rec {
    char key[32];
    char label[40];
    int  v[7];      /* R G B HUE SAT SHARP CON */
};
static struct Rec g_rec[MAXR];
static int g_nrec = 0;

/* 解析一行： key|label|R|G|B|HUE|SAT|SHARP|CON
   成功返回 0 并填好 rec；跳过（注释/空行/格式错）返回 -1 */
static int parse_line(char *line, struct Rec *r) {
    int L = 0;
    while (line[L] && line[L] != '\n') L++;
    line[L] = 0;
    /* ★ 容忍 CRLF：Windows 写的文件最后字段会带 '\r'，
       不去掉会让"纯数字"校验失败 → 整行被跳过 */
    while (L > 0 && (line[L-1] == '\r' || line[L-1] == ' ')) line[--L] = 0;
    if (line[0] == 0 || line[0] == '#') return -1;
    /* 手工 split '|'，最多 9 段 */
    char *f[9]; int nf = 0; char *p = line;
    while (nf < 9) {
        f[nf++] = p;
        char *q = strchr(p, '|');
        if (!q) break;
        *q = 0; p = q + 1;
    }
    if (nf < 9) return -1;
    /* key必须全小写 ASCII（跳过中文注释行） */
    int i, ok = 1;
    for (i = 0; f[0][i]; i++) {
        char c = f[0][i];
        if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_')) { ok = 0; break; }
    }
    if (!ok || f[0][0] == 0) return -1;
    strncpy(r->key, f[0], 31); r->key[31] = 0;
    strncpy(r->label, f[1], 39); r->label[39] = 0;
    for (i = 0; i < 7; i++) {
        /* 只接受纯数字 */
        char *q = f[2 + i];
        if (q[0] == 0) return -1;
        int neg = 0, k = 0;
        if (q[0] == '-') { neg = 1; k = 1; }
        if (q[k] == 0) return -1;
        for (; q[k]; k++) if (q[k] < '0' || q[k] > '9') return -1;
        r->v[i] = atoi(q) * (neg ? -1 : 1);
    }
    return 0;
}

/* 从 /mnt/mmc/filmlab/recipes.txt 读
   格式： key|label|R|G|B|HUE|SAT|SHARP|CON
   注释行以 # 开头，空行忽略 */
static int load_recipes(const char *path) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) return -1;
    char buf[512];
    g_nrec = 0;
    int held = 0;                /* buf 里已保留的字节数（处理跨 read 的半行） */
    for (;;) {
        /*保证 buf 以'\0' 结尾 */
        buf[held] = 0;
        int got = read(fd, buf + held, sizeof(buf) - 1 - held);
        if (got <= 0) {
            /*处理最后一行（无换行结尾） */
            if (held > 0 && g_nrec < MAXR) {
                if (parse_line(buf, g_rec + g_nrec) == 0) g_nrec++;
            }
            break;
        }
        held += got;
        /* 逐行切分 */
        int start = 0, i;
        for (i = 0; i < held; i++) {
            if (buf[i] != '\n') continue;
            buf[i] = 0;
            if (g_nrec < MAXR) {
                if (parse_line(buf + start, g_rec + g_nrec) == 0) g_nrec++;
            }
            start = i + 1;
        }
        /* 把未成行的残余移到开头 */
        held -= start;
        if (held > 0 && start > 0) {
            int k;
            for (k = 0; k < held; k++) buf[k] = buf[start + k];
        }
        if (g_nrec >= MAXR) break;
    }
    close(fd);
    return g_nrec;
}

/* ================= 绘制 ================= */
static const char *DIMNAME[7] = {
    "R", "G", "B", "HUE", "SAT", "SHRP", "CON"
};
/* 各维度的取值范围（用于条形图归一化）
   实机依据：R/G/B 中性=100；HUE/SAT/SHRP/CON 中性=10
   厂商厂商槽的 HUE/SAT 有脏数据，所以上限按 UI 可调范围给 */
static const int DIMMIN[7] = {  0,  0,  0,   0,  0,   0,  0 };
static const int DIMMAX[7] = {200, 200, 200, 20, 15,  15,  15 };

static void draw(Display *d, Window w, GC gc, int W, int H,
                 int cur, int curdim, char *msg, int show_exit) {
    XSetForeground(d, gc, C_BG);
    XFillRectangle(d, w, gc, 0, 0, W, H);

    /* ---- 标题栏 ---- */
    XSetForeground(d, gc, C_PANEL);
    XFillRectangle(d, w, gc, 0, 0, W, 28);
    XSetForeground(d, gc, C_ACC);
    draw_text(d, w, gc, 8, 8, "FilmLab  X11 Recipe Selector", 2);
    XSetForeground(d, gc, C_DIM);
    draw_text(d, w, gc, 300, 10, "arrows=move  Enter=apply  q=quit", 1);
    if (show_exit) {
        /* ★ 右上角 EXIT 热区：告诉用户 telnet 里 kill <pid> 也能关 */
        int ew = text_w(12, 1);
        XSetForeground(d, gc, C_WARN);
        XFillRectangle(d, w, gc, W - ew - 12, 4, ew + 8, 18);
        XSetForeground(d, gc, C_BG);
        draw_text(d, w, gc, W - ew - 8, 9, "EXIT: q key", 1);
    }

    if (g_nrec == 0) {
        XSetForeground(d, gc, C_WARN);
        draw_text(d, w, gc, 8, 60, "No recipes loaded.", 2);
        XSetForeground(d, gc, C_TXT);
        draw_text(d, w, gc, 8, 90, "Check /mnt/mmc/filmlab/recipes.txt", 1);
        XSetForeground(d, gc, C_DIM);
        draw_text(d, w, gc, 8, 130, "Format:  key|label|R|G|B|HUE|SAT|SHARP|CON", 1);
        XFlush(d);
        return;
    }

    /* ---- 左栏：配方列表 ---- */
    int LX = 6, LY = 34, LW = 196, ITEM = 26;
    XSetForeground(d, gc, C_PANEL);
    XFillRectangle(d, w, gc, LX, LY - 2, LW, ITEM * g_nrec + 4);
    for (int i = 0; i < g_nrec; i++) {
        int y = LY + i * ITEM;
        if (i == cur) {
            XSetForeground(d, gc, C_SEL);
            XFillRectangle(d, w, gc, LX, y, LW, ITEM - 2);
        }
        /* ASCII标签（点阵字体无中文）；label 非 ASCII 时用 key 代替 */
        const char *txt = g_rec[i].label;
        int ascii_ok = 1;
        for (const char *q = txt; *q; q++)
            if ((unsigned char)*q < 0x20 || (unsigned char)*q > 0x7E) { ascii_ok = 0; break; }
        if (!ascii_ok) txt = g_rec[i].key;
        XSetForeground(d, gc, (i == cur) ? C_BARTXT : C_TXT);
        if (i == cur) {
            XSetForeground(d, gc, C_ACC);
            XFillRectangle(d, w, gc, LX + 3, y + 8, 3, 3);
            XSetForeground(d, gc, C_BARTXT);
        }
        draw_text_n(d, w, gc, LX + 10, y + 8, txt, 1, 28);
    }

    /* ---- 右栏：7 维条形图 ---- */
    int RX = 210, RY = 60, RH = 30, GAP = 5;
    XSetForeground(d, gc, C_TXT);
    draw_text(d, w, gc, RX, 38, "Picture Wizard - 7 dimensions", 1);
    for (int i = 0; i < 7; i++) {
        int y = RY + i * (RH + GAP);
        /* 名称 */
        XSetForeground(d, gc, (i == curdim) ? C_ACC : C_DIM);
        draw_text(d, w, gc, RX, y + 10, DIMNAME[i], 1);
        /* 底条 */
        int bx = RX + 40, bw = 300, bh = 16;
        XSetForeground(d, gc, C_BAR);
        XFillRectangle(d, w, gc, bx, y + 3, bw, bh);
        /* 值条 */
        int mn = DIMMIN[i], mx = DIMMAX[i];
        int v = g_rec[cur].v[i];
        if (v < mn) v = mn;
        if (v > mx) v = mx;
        int len = (mx > mn) ? (bw * (v - mn)) / (mx - mn) : 0;
        if (len < 2) len = 2;
        XSetForeground(d, gc, (i == curdim) ? C_ACC : RGB(90, 150, 210));
        XFillRectangle(d, w, gc, bx, y + 3, len, bh);
        /* 中性刻线（100for RGB, 10 for others） */
        int nt = (i < 3) ? 100 : 10;
        if (nt > mn && nt < mx) {
            int nx = bx + (bw * (nt - mn)) / (mx - mn);
            XSetForeground(d, gc, C_DIM);
            XFillRectangle(d, w, gc, nx, y + 1, 1, bh + 4);
        }
        /* 边框 */
        XSetForeground(d, gc, C_DIM);
        XDrawRectangle(d, w, gc, bx, y + 3, bw, bh);
        /* 数值 */
        char nb[16];
        char *p = nb;
        int vv = g_rec[cur].v[i];
        if (vv < 0) { *p++ = '-'; vv = -vv; }
        if (vv >= 100) *p++ = (char)('0' + vv / 100);
        if (vv >= 10)  *p++ = (char)('0' + (vv / 10) % 10);
        *p++ = (char)('0' + vv % 10);
        *p = 0;
        XSetForeground(d, gc, C_BARTXT);
        draw_text(d, w, gc, bx + bw + 8, y + 7, nb, 1);
    }

    /* ---- 底部：当前配方 key + 提示 ---- */
    int BY = RY + 7 * (RH + GAP) + 14;
    XSetForeground(d, gc, C_PANEL);
    XFillRectangle(d, w, gc, 6, BY, W - 12, 54);
    XSetForeground(d, gc, C_TXT);
    draw_text_n(d, w, gc, 14, BY + 8, g_rec[cur].key, 2, 34);
    XSetForeground(d, gc, C_DIM);
    draw_text(d, w, gc, 14, BY + 30, "up/down: recipe   left/right: dimension", 1);
    draw_text(d, w, gc, 14, BY + 42, "recipes: /mnt/mmc/filmlab/recipes.txt", 1);
    if (msg && msg[0]) {
        XSetForeground(d, gc, C_ACC);
        draw_text_n(d, w, gc, 300, BY + 8, msg, 1, 40);
    }

    XFlush(d);
}

/* ================= 调色板核对 ================= */
static int nearest_rgb(unsigned long px) {
    int r = (px >> 11) & 0x1F, g = (px >> 5) & 0x1F, b = px & 0x1F;
    return (r << 11) | (g << 5) | b;
}

/* ================= main ================= */
int main(int argc, char **argv) {
    const char *rpath = (argc > 1) ? argv[1] : "/mnt/mmc/filmlab/recipes.txt";
    const char *logp = (argc > 2) ? argv[2] : "/mnt/mmc/_pwtest/nxflab.log";
    /* 第三参数：自动退出秒数（<=0 表示永不自动退出，靠信号/热区退出） */
    int idle_limit = (argc > 3) ? atoi(argv[3]) : 0;

    install_sig(SIGTERM);
    install_sig(SIGINT);
    install_sig(SIGHUP);

    g_log = open(logp, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    L("nxflab start, recipes=%s idle_limit=%d", rpath, idle_limit);

    XSupportsLocale();
    XSetLocaleModifiers("");

    Display *d = XOpenDisplay(NULL);
    if (!d) { L("FAIL no display"); return 2; }
    int scr = XDefaultScreen(d);
    int W = XDisplayWidth(d, scr), H = XDisplayHeight(d, scr);
    Window root = XRootWindow(d, scr);
    L("OK display %dx%d screen=%d", W, H, scr);

    init_colors(d, scr);

    int n = load_recipes(rpath);
    L("loaded %d recipes", n);
    if (n <= 0) L("WARN no recipes loaded -- UI will show empty");

    Window win = XCreateSimpleWindow(d, root, 0, 0, W, H, 1,
                    C_TXT, C_BG);
    XStoreName(d, win, "FilmLab");
    XSelectInput(d, win, ExposureMask | KeyPressMask | StructureNotifyMask);
    XMapWindow(d, win);
    XSync(d, False);
    L("window created and mapped");

    GC gc = XCreateGC(d, win, 0, NULL);

    /* 字体：优先 6x13 固定字体（X server 自带，最稳） */
    /* ★ 字体：相机 X server 上XLoadQueryFont 全部返回非 NULL，
       但资源实际无效（XSetFont 立刻触发 BadFont 致命错误，
       错误码 Resource id=0x0 = 字体 ID 为 0）。
       结论：这个 X server 没有 core font 目录。
       → 不用字体，改用【矢量线段画字】（见 draw_glyph）。
       这里只探测一下，不做 XSetFont。 */
    XFontStruct *f = XLoadQueryFont(d, "6x13");
    L("font probe 6x13 -> %p (NOT used, we draw glyphs manually)", (void *)f);
    f = NULL;

    int cur = 0, curdim = 0;
    char msg[64] = "";
    int show_exit = 1;          /* EXIT 热区显示中 */
    draw(d, win, gc, W, H, cur, curdim, msg, show_exit);

    /* ==== 事件循环：select 超时轮询，不用 XNextEvent 阻塞 ==== */
    int xfd = XConnectionNumber(d);
    time_t last_input = time(NULL);
    for (;;) {
        if (g_quit) { L("quit by signal"); break; }

        /* ---- 外部控制文件（触屏/按键脚本驱动）---- */
        char cb[64];
        if (poll_cmd(cb, sizeof cb)) {
            last_input = time(NULL);
            if      (!strcmp(cb, "up"))    { cur = (cur + g_nrec - 1) % g_nrec; msg[0] = 0; }
            else if (!strcmp(cb, "down"))  { cur = (cur + 1) % g_nrec; msg[0] = 0; }
            else if (!strcmp(cb, "left"))  { curdim = (curdim + 6) % 7; msg[0] = 0; }
            else if (!strcmp(cb, "right")) { curdim = (curdim + 1) % 7; msg[0] = 0; }
            else if (!strcmp(cb, "apply")) {
                char c2[160]; int i2 = 0;
                const char *pre = "/opt/usr/nx-ks/filmlab.sh apply ";
                const char *kk = g_rec[cur].key;
                while (*pre && i2 < 60) c2[i2++] = *pre++;
                while (*kk && i2 < 120) c2[i2++] = *kk++;
                c2[i2++] = 0;
                int rc2 = system(c2);
                L("cmd apply %s rc=%d", g_rec[cur].key, rc2);
                strncpy(msg, "applied", 60); msg[59] = 0;
            }
            else if (!strcmp(cb, "quit")) { L("cmd quit"); break; }
            else { L("unknown cmd"); }
            draw(d, win, gc, W, H, cur, curdim, msg, show_exit);
        }

        /* 定时检查：是否超时 */
        if (idle_limit > 0) {
            time_t now = time(NULL);
            if (now - last_input >= idle_limit) {
                L("idle %lds -> auto quit", (int)(now - last_input));
                break;
            }
            /* 临近超时才显示 EXIT 热区（提示用户可以按 q） */
            show_exit = (idle_limit - (now - last_input)) <= 5;
        }

        if (!XPending(d)) {
            /* 没有事件：用 select 等 200ms 然后回来检查信号/超时 */
            fd_set fds; struct timeval tv;
            FD_ZERO(&fds); FD_SET(xfd, &fds);
            tv.tv_sec = 1; tv.tv_usec = 0;          /* ★ 1秒：单核相机，2秒一次足够 */
            if (select(xfd + 1, &fds, NULL, NULL, &tv) < 0 && errno == EINTR) {
                continue;      /* 被信号打断 → 回到循环头查 g_quit */
            }
            continue;
        }

        XEv ev;
        XNextEvent(d, &ev);
        last_input = time(NULL);
        if (ev.type == 2 /* Expose */) {
            draw(d, win, gc, W, H, cur, curdim, msg, show_exit);
            continue;
        }
        if (ev.type == 3 /* DestroyNotify */) break;
        if (ev.type != 10 /* KeyPress */) continue;

        unsigned kc = ev.keycode;
        if (kc == K_UP) {
            cur = (cur + g_nrec - 1) % g_nrec;
            msg[0] = 0; draw(d, win, gc, W, H, cur, curdim, msg, show_exit);
        } else if (kc == K_DOWN) {
            cur = (cur + 1) % g_nrec;
            msg[0] = 0; draw(d, win, gc, W, H, cur, curdim, msg, show_exit);
        } else if (kc == K_LEFT) {
            curdim = (curdim + 6) % 7; msg[0] = 0;
            draw(d, win, gc, W, H, cur, curdim, msg, show_exit);
        } else if (kc == K_RIGHT) {
            curdim = (curdim + 1) % 7; msg[0] = 0;
            draw(d, win, gc, W, H, cur, curdim, msg, show_exit);
        } else if (kc == K_q || kc == K_ESC) {
            L("quit by key");
            break;
        } else if (kc == K_ENTER) {
            /* 应用：把当前配方写到 SD 卡的一个临时文件，交给 shell 脚本执行
               —— X11 程序不直接调 prefman（避免再写一遍 JSON 解析） */
            L("APPLY %s", g_rec[cur].key);
            char cmd[160];
            const char *kk = g_rec[cur].key;
            /* 构造：filmlab.sh apply <key> */
            int i = 0;
            const char *pre = "/opt/usr/nx-ks/filmlab.sh apply ";
            while (*pre && i < 60) cmd[i++] = *pre++;
            while (*kk && i < 120) cmd[i++] = *kk++;
            cmd[i++] = ' '; cmd[i++] = '&'; cmd[i++] = 0;
            /* system() 会阻塞直到 shell 完成，配方写入约 1 秒 */
            int rc = system(cmd);
            L("apply rc=%d", rc);
            /* 提示 */
            msg[0] = 0;
            const char *m = "applied to slot; check UI";
            int ml = 0;
            while (m[ml] && ml < 60) { msg[ml] = m[ml]; ml++; }
            msg[ml] = 0;
            draw(d, win, gc, W, H, cur, curdim, msg, show_exit);
        } else if (kc == K_SPACE) {
            cur = (cur + 1) % g_nrec; msg[0] = 0;
            draw(d, win, gc, W, H, cur, curdim, msg, show_exit);
        }
    }

    if (f) XFreeFont(d, f);
    XFreeGC(d, gc);
    XCloseDisplay(d);
    L("bye");
    return 0;
}
