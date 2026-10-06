/*
 * nxfilmui.c — FilmLab 配方选择器（EFL 版，NX500/NX1 机内）
 *
 * 为什么重写而不用 mod_gui（2026-10-05 从 mod_gui.c 源码查证）：
 *   mod_gui 的 key_down_callback 只认 13 个键：
 *     F6~F10 / KP_Home / Scroll_Lock / XF86PowerOff
 *     Hiragana / Muhenkan / Control_R / Alt_R / Katakana
 *     XF86Reload / XF86WWW / KP_Enter
 *   ★ 方向键 Up/Down/Left/Right 与 JOG1_CW/JOG1_CCW 全都落进 else 分支
 *     → quit_app() 直接退出。⇒ mod_gui 层「波轮切换」无解，必须自己写。
 *
 * 为什么不用 X11 版（nxflab.c，2026-08 已实机验证）：
 *   X11 满屏 720x480 在单核 NX500 上吃满 CPU，连 echo 都执行不完。
 *   ★ 本程序用 EFL/elementary（和 di-camera-app、mod_gui 同一套栈，
 *     已被固件自己加载并优化过），窗口走 evas 合成，不抢CPU。
 *
 * 交互（三通道并行，正是 mod_gui 缺的）：
 *   · 波轮    JOG1_CW / JOG1_CCW  → 上一个 / 下一个配方
 *             （也可退而用 Up/Down 方向键，X11 keycode 差异见下）
 *   · 触摸    直接点配方块 → 立即应用
 *   · 按键    OK(KP_Enter) 应用 / LEFT 退出
 *
 *   X11 keysym 对照（来自社区文档 "xinput test 8" 实测输出）：
 *     JOG1_CW=185  JOG1_CCW=186  JOG2_CW=171  JOG2_CCW=173
 *     S1=133  S2=134  MOBILE=233  AEL=164
 *   ★ 这些是 X11 keycode；ecore 回调给的 event->key 是 keysym 名，
 *     所以下面同时按 keysym 名（JOG1_CW）与字符（Up/Down）两种写法匹配，
 *     哪套生效由实机决定 —— 属于【必须实机确认】的清单项。
 *
 * 退出即应用（消除 mod_gui「点完就关窗、关了就没了」的问题）：
 *   选中的配方在【滚动时】就实时写入 prefman + 强制 ISP 重读，
 *   退出只负责关窗。所以「取消」= 不做任何回滚（本来就是即时预览语义）。
 *
 * 配方来源：/mnt/mmc/filmlab/recipes.txt（纯文本，每行一个配方）
 *   格式： key|label|R|G|B|HUE|SAT|SHARP|CON
 *   与 recipes.json 由filmlab.sh export 生成，解析代码复用 nxflab.c。
 *
 * 编译（-O0 是铁律，-O1+ 在真机段错误 139）：
 *   zig cc -target arm-linux-gnueabi.2.15 -O0 -mfloat-abi=soft \
 *          -fno-stack-protector nxfilmui.c \
 *          -L<sysroot>/lib -l:elementary -l:evas -l:ecore -l:ecore_input \
 *          -o nxfilmui.arm
 *   ★ EFL 头文件 sysroot 里没有（只有 .so），故下方全部手写 ABI 声明。
 *   ★ 需在 sysroot/lib 造符号链接：
 *       ln -s libelementary.so.1 libelementary.so
 *       ln -s libevas.so.1 libevas.so   (依实际 .so 名字)
 */
#define _GNU_SOURCE
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdio.h>
#include <signal.h>
#include <errno.h>
#include <time.h>
#include <sys/types.h>
#include <sys/stat.h>

/* ================= EFL / elementary ABI（手写，sysroot 无头文件）========== */
typedef void Evas_Object;
typedef void Evas_Canvas;
typedef void Elm_Widget;

typedef struct _Ecore_Event_Key {
    const char *key;        /* keysym 名，如 "JOG1_CW" / "Up" / "KP_Enter" */
    const char *string;
    const char *window;
    unsigned int keycode;
    unsigned int time;
    unsigned int flags;
    const void *window_key;
} Ecore_Event_Key;

typedef int Eina_Bool;
#define ECORE_CALLBACK_PASS_ON 1
#define ECORE_CALLBACK_STOP    0
#define ECORE_EVENT_KEY_DOWN   2
#define ECORE_EVENT_KEY_UP     3

/* elementary 控件与风格 */
#define ELM_WIN_BASIC      1
#define ELM_BG             3
#define ELM_BOX            2
#define ELM_GENGRID        55
#define ELM_LABEL          8
#define ELM_SCROLLER       13

int  elm_init(int, char **, Eina_Bool);
int  elm_run(void);
void elm_exit(void);
Evas_Object *elm_win_add(Evas_Object *parent, const char *name, int type);
void elm_win_title_set(Evas_Object *win, const char *title);
void elm_win_resize_object_add(Evas_Object *win, Evas_Object *obj);
Evas_Object *elm_bg_add(Evas_Object *win);
Evas_Object *elm_box_add(Evas_Object *win, int horizontal);
void elm_box_pack_end(Evas_Object *box, Evas_Object *child);
Evas_Object *elm_gengrid_add(Evas_Object *parent);
void elm_gengrid_item_append(Evas_Object *grid, Evas_Object *item, void *cb, void *data);
Evas_Object *elm_scroller_add(Evas_Object *parent);
void elm_scroller_policy_set(Evas_Object *sc, int h, int v);
Evas_Object *elm_label_add(Evas_Object *box);
void elm_object_part_text_set(Evas_Object *obj, const char *part, const char *text);
void elm_object_style_set(Evas_Object *obj, const char *style, Eina_Bool reset);
Evas_Object *elm_button_add(Evas_Object *box);

/* ★★ 三个"我以为存在、但真机上查无实据"的 API —— 已全部弃用，不要加回来：
 *
 * 1. elm_box_recalculate()
 *    这个 API 在 EFL 里根本不存在（写错了）。box 在 pack_end 之后自己重算，
 *    mod_gui 源码里也没有任何调用。
 *
 * 2. elm_win_fullscreen_set()
 *    在真机 EFL 1.7.99 上，mod_gui 和 di-camera-app 都从未调用它。
 *    而 mod_gui 达成"满屏"实际只靠：
 *        elm_win_add(NULL, ...) + elm_win_resize_object_add(win, obj)
 *    把对象直接绑到窗口尺寸，EFL 自己铺满。→ 本程序照抄，不调 fullscreen。
 *
 * 3. elm_gengrid_page_size_set()
 *    同样无真机使用证据。改用 evas_object_size_hint_min_set 给格子定尺寸
 *    （mod_gui 排按钮就是这么干的）+ 外面套 elm_scroller_add，
 *    格子多了自动滚，完全不依赖 gengrid 的分页概念。
 *
 * 查证方法：test_server/filmlab/src/check_abi.py
 *   —— 白名单来自真机上跑通过的 mod_gui + di-camera-app 的 .dynsym 未定义符号，
 *      凡是它俩没用过的 EFL 符号，一律视为"未经证实"，不写进代码。
 */

/* evas（★ 每个符号都在真机跑过的 mod_gui / di-camera-app 的 .dynsym 里查证过）*/
void evas_object_show(Evas_Object *obj);
void evas_object_del(Evas_Object *obj);
int  evas_object_smart_callback_add(Evas_Object *obj, const char *name, void *func, void *data);
void evas_object_color_set(Evas_Object *obj, int r, int g, int b, int a);
void evas_object_size_hint_min_set(Evas_Object *obj, int w, int h);
void evas_object_size_hint_weight_set(Evas_Object *obj, float wx, float wy);
void evas_object_size_hint_max_set(Evas_Object *obj, int w, int h);
void evas_object_render_op_set(Evas_Object *obj, int op);

/* ecore
 * ★★ 这里必须【运行时 dlsym】，不能用链接期符号，原因是一个实测踩到的坑：
 *   ecore_event_handler_add 定义在真机 libecore.so.1 里，
 *   但该库没 dump 到本地（只有 libelementary/libevas/libecore_evas），
 *   若写成普通 extern 声明 +链接期 stub 占位，符号会被静态解析进二进制，
 *   实测确认：产物导入表里已经没有它了 —— 也就是真机上会调到【空函数】，
 *   表现 = 窗口能开、能触摸，但【波轮/按键完全无反应】，且不报错，
 *   极难排查（这正是"编译通过≠功能可用"的典型）。
 *   改成 dlsym(RTLD_DEFAULT,...) 后，符号留在导入表里，
 *   由真机的 ld-linux 按 libelementary → libecore 链在运行时解析到真函数。
 */
#include <dlfcn.h>
typedef int (*fn_ecore_eh_add)(int type, int (*func)(void *, int, void *), void *data);
static fn_ecore_eh_add p_ecore_event_handler_add = NULL;

/* ================= 配方数据 ================= */
#define MAXR 32
typedef struct {
    char key[48];
    char label[48];
    int  v[7];              /* R G B HUE SAT SHARP CONTRAST */
} Rec;
static Rec g_rec[MAXR];
static int  g_nrec = 0;
static int  g_sel  = 0;

/* ================= 运行时配置 ================= */
#define PW_BASE 41964        /* 0xa3ec */
#define PSTEP   52
#define SSTEP   4
#define SLOT9   9            /* UI「自定义1」，FilmLab 恒定写这一槽 */
#define ENUM9   0x140009

/* 日志：fprintf 在这台机器上会段错误 139（x11grab 实测），用 write */
static int g_log = -1;
static void logopen(void) {
    const char *p = "/mnt/mmc/filmlab/filmui.log";
    g_log = open(p, O_WRONLY | O_CREAT | O_APPEND, 0644);
}
static void logf_(const char *fmt, ...) {
    if (g_log < 0) return;
    char b[512];
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(b, sizeof(b), fmt, ap);
    va_end(ap);
    if (n > 0) { if (n > (int)sizeof(b) - 1) n = sizeof(b) - 1; if (write(g_log, b, n) < 0) { } }
}

/* ================= 配方表解析（逻辑移植自 nxflab.c，已实机验证过的分段读法）========== */
static int parse_line(char *s, Rec *r) {
    /* 逐段以 | 切开：key|label|R|G|B|HUE|SAT|SHARP|CON */
    char *f[9];
    int i = 0;
    f[i++] = s;
    while (i < 9) {
        char *p = strchr(f[i - 1], '|');
        if (!p) break;
        *p = 0;
        f[i++] = p + 1;
    }
    if (i < 9) return -1;                 /* 段数不足，丢弃 */
    if (f[0][0] == '#' || f[0][0] == 0) return -1;
    if (strlen(f[0]) >= sizeof(r->key)) return -1;
    if (strlen(f[1]) >= sizeof(r->label)) return -1;
    strcpy(r->key, f[0]);
    /* label 里若含 | 的残留，strchr 已切断，这里不会出现 */
    strcpy(r->label, f[1]);
    for (i = 0; i < 7; i++) r->v[i] = atoi(f[2 + i]);
    return 0;
}

static int load_recipes(const char *path) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) return -1;
    char buf[512];
    g_nrec = 0;
    int held = 0;
    for (;;) {
        buf[held] = 0;
        int got = read(fd, buf + held, sizeof(buf) - 1 - held);
        if (got <= 0) {
            if (held > 0 && g_nrec < MAXR)
                if (parse_line(buf, g_rec + g_nrec) == 0) g_nrec++;
            break;
        }
        held += got;
        int start = 0, i;
        for (i = 0; i < held; i++) {
            if (buf[i] != '\n') continue;
            buf[i] = 0;
            if (g_nrec < MAXR)
                if (parse_line(buf + start, g_rec + g_nrec) == 0) g_nrec++;
            start = i + 1;
        }
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

/* ================= 写配方（prefman + 强制 ISP 重读）===================== */
/* 全部通过 fork/exec 调外部命令，不直接链接 libprefman：
   与 filmlab.sh 的通道保持一致，避免两套写入逻辑漂移。 */
static void run(const char *cmd) {
    logf_("CMD: %s\n", cmd);
    if (system(cmd) < 0) logf_("system failed: %s\n", strerror(errno));
}
static void runq(const char *cmd) { run(cmd); }

static int set_pw(int idx, int val) {
    char b[128];
    int addr = PW_BASE + idx * PSTEP + SLOT9 * SSTEP;
    snprintf(b, sizeof(b), "prefman set 0 0x%05x l %d >/dev/null 2>&1", addr, val);
    runq(b);
    return 0;
}
static int get_pw(int idx) {
    char b[160];
    int addr = PW_BASE + idx * PSTEP + SLOT9 * SSTEP;
    snprintf(b, sizeof(b),
             "prefman get 0 0x%05x l 2>/dev/null | tr -d '\\r' "
             "| sed -n 's/.*value = \\([-0-9]*\\).*/\\1/p'", addr);
    FILE *p = popen(b, "r");
    if (!p) return -1;
    char buf[64];
    int v = -1;
    if (fgets(buf, sizeof(buf), p)) v = atoi(buf);
    pclose(p);
    return v;
}

static int cur_enum(void) {
    FILE *p = popen("st cap capdtm getusr 20 2>/dev/null | tr -d '\\r' "
                    "| sed -n 's/.*UserData is [A-Z_0-9]* (\\(0x[0-9a-f]*\\)).*/\\1/p'",
                    "r");
    if (!p) return -1;
    char buf[64];
    long v = -1;
    if (fgets(buf, sizeof(buf), p)) v = strtol(buf, NULL, 16);
    pclose(p);
    return (int)v;
}

/* ★ 与 filmlab.sh 的 pw_force_reload 同一套借道逻辑：
     enum 与目标相同 = 同值空操作 → ISP 不重读 PW 段 → 按键看起来"没反应"。 */
static void apply_sel(int sel) {
    if (sel < 0 || sel >= g_nrec) return;
    Rec *r = &g_rec[sel];
    char b[128];
    int i;
    for (i = 0; i < 7; i++) set_pw(i, r->v[i]);
    logf_("applied sel=%d key=%s\n", sel, r->key);

    int cur = cur_enum();
    if (cur == ENUM9) {
        run("st cap capdtm setusr 20 0x140009 >/dev/null 2>&1; sleep 1");
    }
    snprintf(b, sizeof(b), "st cap capdtm setusr 20 0x%06x >/dev/null 2>&1", ENUM9);
    run(b);
    run("sleep 1");

    int now = cur_enum();
    if (now != ENUM9)
        logf_("VERIFY-FAIL want=%06x now=%06x\n", ENUM9, now);
    else
        logf_("reload ok now=%06x\n", now);

    /* 记录索引用户下次打开时知道当前是哪个 */
    snprintf(b, sizeof(b), "echo %d > /mnt/mmc/filmlab/cur.idx 2>/dev/null", sel);
    run(b);
}

/* ================= UI ================= */
static Evas_Object *g_win, *g_grid, *g_status, *g_title;
static int g_quit = 0;
/* 每个格子的句柄，供波轮移动光标时改颜色做高亮反馈。
   gengrid 会在滚动时懒创建/回收 item，所以句柄可能变 NULL —— 高亮时判空即可。 */
static Evas_Object *g_item[MAXR];

static void sel_changed(void);

/* 触摸/点击某个配方块 */
static void cb_item(void *data, Evas_Object *obj, void *ev) {
    int i = (int)(long)data;
    if (i < 0 || i >= g_nrec) return;
    g_sel = i;
    /* ★ 先刷高亮再应用：顺序反了会在 apply 的 system() 阻塞期间
       画面停在旧光标上，用户看不出自己点的是哪个 */
    sel_changed();
    apply_sel(i);
    /* ★ 不关窗：连续点多个配方即时对比，这是 mod_gui 做不到的 */
    elm_object_part_text_set(g_status, "label", g_rec[i].label);
}

static Evas_Object *mk_item(int i) {
    Rec *r = &g_rec[i];
    char t[96];
    Evas_Object *b = elm_button_add(g_grid);
    /* ★ 零 CJK 字体（实测 /usr/share/fonts 只有 9 个 ttf，无中文字体）
       → 标签里的中文会渲染成空白。这里做一次降级：
         纯 ASCII 就用原名，含 CJK 就退化成 "第N个" 序号 + key，
         保证屏幕上一定有可读文字，不会出现空白块。*/
    int has_cjk = 0, k;
    for (k = 0; r->label[k]; k++)
        if ((unsigned char)r->label[k] >= 0x80) { has_cjk = 1; break; }
    if (has_cjk) snprintf(t, sizeof(t), "%d. %s", i + 1, r->key);
    else         snprintf(t, sizeof(t), "%s", r->label);

    elm_object_part_text_set(b, "label", t);
    elm_object_style_set(b, "transparent", 1);
    evas_object_color_set(b, 200, 200, 200, 255);
    /* 2 列 × 每行 54px，720 宽正好 2 列 */
    evas_object_size_hint_min_set(b, 340, 54);
    evas_object_show(b);
    g_item[i] = b;
    return b;
}

/* ★ 光标高亮：波轮每转一格必须让用户看见焦点在哪，
   否则在单屏 9 个配方里用波轮是盲操作。
   判空是因为 gengrid 滚动时会懒回收 item。 */
static void paint_sel(void) {
    int i;
    for (i = 0; i < g_nrec; i++) {
        if (!g_item[i]) continue;
        if (i == g_sel) evas_object_color_set(g_item[i], 255, 200,  80, 255);
        else           evas_object_color_set(g_item[i], 200, 200, 200, 255);
    }
}

static void build_grid(void) {
    int i;
    for (i = 0; i < g_nrec; i++) {
        Evas_Object *it = mk_item(i);
        /* 回调同时挂两处：smart callback（"clicked"）与 gengrid 的 item cb。
          两个都挂，因为 elm_gengrid_item_append 自己的 cb 语义
          依赖 gengrid item class，而 mod_gui 没用到 gengrid，
          「哪种回调在1.7.99 上真的触发」属于【必须实机确认】项 —— 挂两个兜底。*/
        evas_object_smart_callback_add(it, "clicked", (void *)cb_item, (void *)(long)i);
        elm_gengrid_item_append(g_grid, it, cb_item, (void *)(long)i);
    }
}

static void sel_changed(void) {
    if (g_nrec == 0) return;
    g_sel = ((g_sel % g_nrec) + g_nrec) % g_nrec;
    char b[128];
    int k, has_cjk = 0;
    for (k = 0; g_rec[g_sel].label[k]; k++)
        if ((unsigned char)g_rec[g_sel].label[k] >= 0x80) { has_cjk = 1; break; }
    if (has_cjk) snprintf(b, sizeof(b), "%d/%d", g_sel + 1, g_nrec);
    else         snprintf(b, sizeof(b), "%s", g_rec[g_sel].label);
    elm_object_part_text_set(g_status, "label", b);
    paint_sel();
    logf_("sel -> %d (%s)\n", g_sel, g_rec[g_sel].key);
}

static Eina_Bool on_key(void *data, int type, void *ev) {
    Ecore_Event_Key *e = (Ecore_Event_Key *)ev;
    const char *k = e->key;
    if (!k) return ECORE_CALLBACK_PASS_ON;

    /* ★ 波轮：三个候选写法同时匹配，谁生效由实机决定（见文件头说明） */
    if (!strcmp(k, "JOG1_CW") || !strcmp(k, "Up") || !strcmp(k, "KP_Up")) {
        g_sel--;
        sel_changed();
        apply_sel(g_sel);
        return ECORE_CALLBACK_STOP;
    }
    if (!strcmp(k, "JOG1_CCW") || !strcmp(k, "Down") || !strcmp(k, "KP_Down")) {
        g_sel++;
        sel_changed();
        apply_sel(g_sel);
        return ECORE_CALLBACK_STOP;
    }
    /* 应用（确认） */
    if (!strcmp(k, "KP_Enter") || !strcmp(k, "Return")) {
        apply_sel(g_sel);
        g_quit = 1;
        return ECORE_CALLBACK_STOP;
    }
    /* 退出 */
    if (!strcmp(k, "Left") || !strcmp(k, "Escape") || !strcmp(k, "XF86PowerOff")) {
        g_quit = 1;
        return ECORE_CALLBACK_STOP;
    }
    return ECORE_CALLBACK_PASS_ON;
}

static void on_quit(void *data, Evas_Object *obj, void *ev) {
    g_quit = 1;
}

int main(int argc, char **argv) {
    const char *rpath = (argc > 1) ? argv[1] : "/mnt/mmc/filmlab/recipes.txt";
    logopen();
    logf_("=== start rc=%d ===\n", (int)getpid());

    if (elm_init(argc, argv, 1) != 0) {
        logf_("elm_init FAILED\n");
        return 1;
    }

    /* ★ 运行时解析按键注册函数（见文件头说明：不能链接期静态绑定） */
    p_ecore_event_handler_add =
        (fn_ecore_eh_add)(long)dlsym(RTLD_DEFAULT, "ecore_event_handler_add");
    if (!p_ecore_event_handler_add) {
        logf_("FATAL: ecore_event_handler_add not found (%s)\n",
              dlerror() ? dlerror() : "?");
        fprintf(stderr, "ecore_event_handler_add missing -> 波轮/按键不可用\n");
        elm_exit();
        return 2;
    }
    logf_("ecore_event_handler_add resolved @ %p\n",
          (void *)(long)p_ecore_event_handler_add);
    p_ecore_event_handler_add(ECORE_EVENT_KEY_DOWN, on_key, NULL);

    g_win = elm_win_add(NULL, "nxfilmui", ELM_WIN_BASIC);
    if (!g_win) { logf_("elm_win_add FAILED\n"); return 1; }
    elm_win_title_set(g_win, "FilmLab");
    evas_object_smart_callback_add(g_win, "delete,request", (void *)on_quit, NULL);
    /* ★ 满屏 = 仿 mod_gui 的做法：只靠 elm_win_resize_object_add 把对象绑到窗口尺寸，
       不调 elm_win_fullscreen_set（真机上查无使用证据，见文件头注释区）。*/

    Evas_Object *bg = elm_bg_add(g_win);
    evas_object_color_set(bg, 24, 24, 24, 255);
    elm_win_resize_object_add(g_win, bg);
    evas_object_show(bg);

    Evas_Object *box = elm_box_add(g_win, 0 /* vertical */);
    evas_object_show(box);
    elm_win_resize_object_add(g_win, box);

    g_title = elm_label_add(box);
    elm_object_part_text_set(g_title, "label", "FilmLab  Recipes");
    /* ★ 这个 EFL 版本（1.7.99）没有 elm_object_text_color_set /
     elm_label_alignment_set（已用 ELF 符号表逐个核实），
     颜色统一走 evas_object_color_set —— 它在 libevas.so.1 里确实存在。*/
    evas_object_color_set(g_title, 255, 200, 80, 255);
    evas_object_size_hint_min_set(g_title, 0, 28);
    elm_box_pack_end(box, g_title);
    evas_object_show(g_title);

    if (load_recipes(rpath) <= 0) {
        elm_object_part_text_set(g_title, "label",
                                 "no recipes: /mnt/mmc/filmlab/recipes.txt");
        logf_("load_recipes FAILED: %s\n", strerror(errno));
        /* ★ 仍进主循环：给用户看到报错画面，而不是静默退出。
           注意不要再注册一遍 on_key —— 上面 main 开头已经注册过，
           重复注册会让一次按键回调触发两次（波轮一次转两格）。 */
        elm_run();
        elm_exit();
        return 1;
    }
    logf_("loaded %d recipes\n", g_nrec);

    /* 当前索引恢复（camera 重启后仍知道上次选到哪个） */
    FILE *p = popen("cat /mnt/mmc/filmlab/cur.idx 2>/dev/null", "r");
    if (p) {
        char b[32];
        if (fgets(b, sizeof(b), p)) {
            int v = atoi(b);
            if (v >= 0 && v < g_nrec) g_sel = v;
        }
        pclose(p);
    }

    /* ★ 外层套 elm_scroller_add（替代无真机证据的 elm_gengrid_page_size_set）：
      格子数超过一屏时自动可滚，不依赖 gengrid 分页。
      policy 设为 SCROLLER_POLICY_ON/SCROLLER_AUTO（=0/1，EFL 枚举值），
      即两个方向都允许 —— 波轮切配方时手也可以滑动列表。*/
    Evas_Object *scroll = elm_scroller_add(box);
    evas_object_color_set(scroll, 24, 24, 24, 255);
    evas_object_show(scroll);
    elm_scroller_policy_set(scroll, 1 /*h*/, 1 /*v*/);
    elm_box_pack_end(box, scroll);

    g_grid = elm_gengrid_add(scroll);
    evas_object_size_hint_min_set(g_grid, 0, 0);
    evas_object_size_hint_weight_set(g_grid, 1.0f, 1.0f);
    evas_object_show(g_grid);
    build_grid();

    g_status = elm_label_add(box);
    evas_object_color_set(g_status, 120, 255, 160, 255);
    evas_object_size_hint_min_set(g_status, 0, 26);
    elm_box_pack_end(box, g_status);
    evas_object_show(g_status);
    sel_changed();

    elm_run();
    elm_exit();
    logf_("=== exit===\n");
    return 0;
}
