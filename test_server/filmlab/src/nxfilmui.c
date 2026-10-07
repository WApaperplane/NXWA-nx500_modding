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

/*★★★★★★ 2026-10-07 14:20★★ 主循环改用 ecore_main_loop_iterate（mod_gui 实证写法）
 *   缘由（★ 一条对照实验推翻了我此前的全部前提）：
 *     eflmin（最简 win+bg+box+label，无任何多余控件）
 *       走完 init→win→box→show→elm_run，★ 同样【立即返回】
 *     而 mod_gui（社区版，社区用了十年能出窗口）
 *       ★ 它的未定义符号表里有 ecore_main_loop_iterate，且【不调 elm_run】
 *   ⇒ ★★ elm_run() 在这个 EFL 1.7.99 构建上就是立即返回的
 *      ⇒ 改用 mod_gui 实证过的 ecore_main_loop_iterate 自己写循环
 *
 * ★ 同样走 dlsym（本地无 libecore.so），且它与 ecore_event_handler_add
 *   在同一库里⇒ 若 dlsym 失败说明整个 libecore 都不可用，直接报错退出。
 */
typedef int (*fn_ecore_main_loop_iterate)(void);
static fn_ecore_main_loop_iterate p_ecore_main_loop_iterate = NULL;

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

/* ★★★ setusr 20 <enum> —— 把 ISP 的 PW 风格槽切到目标值
 * ★ 关键：同值写入是【空操作】，ISP 不会重读 PW 段（画面看起来"没反应"）。
 *   所以当"当前值 == 目标值"时，必须先切到一个中间值再切回，制造跳变让 ISP 重读。
 * ★★ 三层判断（逐字照抄 filmlab-apply.sh:114-119，已实机验证 9 个配方）：
 *   MID 必须既不等于 CUR 也不等于 TGT。
 *   FilmLab 恒写 slot9 = enum 0x140009 ⇒ TGT 恒为 0x140009
 *   ⇒ MID 若也取 0x140009 就等于 TGT ⇒ 必须退到 0x140000 / 0x14000a
 */
static void set_enum(unsigned v) {
    char b[96];
    snprintf(b, sizeof(b),
             "st cap capdtm setusr 20 0x%06x >/dev/null 2>&1", v);
    run(b);
    usleep(1200000);            /* ★ 与 filmlab.sh 的 sleep 1 对齐，让 ISP 消化 */
}

/* ★ 返回 0 = 生效，-1 = 校验失败 */
static int force_reload(void) {
    int cur = cur_enum();
    unsigned mid = 0;
    int now;

    if (cur < 0) {
        logf_("force_reload: CUR unknown => direct\n");
        set_enum(ENUM9);
        return cur_enum() == (int)ENUM9 ? 0 : -1;
    }

    if (cur == (int)ENUM9) {
        /* ★★ 同值 ⇒ 必须借道。MID 不能等于 TGT，故取 0x140000 */
        mid = 0x140000;
        if (mid == ENUM9) mid = 0x14000a;
        logf_("force_reload: CUR==TGT(%06x) => borrow MID=%06x\n", ENUM9, mid);
        set_enum(mid);
    } else {
        logf_("force_reload: CUR=%06x != TGT => direct\n", cur);
    }
    set_enum(ENUM9);

    /* ★★ 自证：不信 setusr 退出码，回读确认（照抄 filmlab.sh:131-134）*/
    now = cur_enum();
    if (now != (int)ENUM9) {
        logf_("VERIFY-FAIL want=%06x now=%06x\n", ENUM9, now);
        return -1;
    }
    logf_("reload ok now=%06x (via %06x)\n", now, mid);
    return 0;
}

/* ★ 与 filmlab.sh 的 pw_force_reload 同一套借道逻辑：
     enum 与目标相同 = 同值空操作 → ISP 不重读 PW 段 → 按键看起来"没反应"。 */
/*★★ v3：apply 节流
 *  ★ 为什么需要：单次 apply 要跑 7 次 prefman set + 借道重读 ≈ 1.5 秒。
 *    若用户快速连转波轮，会在 system() 上排队，越积越多 ⇒ 看起来"卡住"。
 *  ★ 做法：转过一格【立即应用】（保持"转到哪生效哪"的直觉），
 *    但同一格在 400ms 内重复触发则跳过。
 */
static long last_apply_ms = 0;
static int  last_apply_sel = -1;
static long now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long)(ts.tv_sec * 1000 + ts.tv_nsec / 1000000);
}

static void apply_sel(int sel) {
    if (sel < 0 || sel >= g_nrec) return;
    Rec *r = &g_rec[sel];
    char b[160];
    long t;
    int i, rc;

    /* ★ 节流：同格 400ms 内只应用一次 */
    t = now_ms();
    if (sel == last_apply_sel && (t - last_apply_ms) < 400) {
        logf_("throttle sel=%d (only %ldms since last)\n", sel, t - last_apply_ms);
        return;
    }
    last_apply_sel = sel;
    last_apply_ms = t;

    /* ★ 先写 7 维 PW（slot 9 = UI「自定义1」）*/
    for (i = 0; i < 7; i++) set_pw(i, r->v[i]);

    /* ★★ 读回自证：不信 prefman 写入的退出码，逐个回读（只读，便宜）
     *   ★ 这是"参数值到底写没写进去"的判据，与 force_reload 的"ISP 有没有重读"
     *     是两件独立的事，必须分别验。*/
    {
        int bad = 0;
        for (i = 0; i < 7; i++) {
            int got = get_pw(i);
            if (got != r->v[i]) {
                logf_("PW-VERIFY-FAIL dim=%d want=%d got=%d\n", i, r->v[i], got);
                bad++;
            }
        }
        logf_("pw write %s (sel=%d key=%s)\n", bad ? "MISMATCH" : "ok",
              sel, r->key);
    }

    /* ★★★ 借道强制 ISP 重读（照抄实机跑通的 filmlab.sh）*/
    rc = force_reload();
    logf_("applied sel=%d key=%s reload=%s\n", sel, r->key, rc == 0 ? "ok" : "FAIL");

    /* 记录索引，用户下次打开时知道当前是哪个 */
    snprintf(b, sizeof(b), "echo %d > /mnt/mmc/filmlab/cur.idx 2>/dev/null", sel);
    run(b);
}

/* ================= UI ================= */
static Evas_Object *g_win, *g_grid, *g_status, *g_title;
static int g_quit = 0;
/* 每个格子的句柄，供波轮移动光标时改颜色做高亮反馈。
   ★★ 2026-10-07 起改用 elm_box 排布（gengrid_item_append 已被实测证实在
      EFL 1.7.99 上崩溃），box 不会懒回收，但保留判空更安全。 */
static Evas_Object *g_item[MAXR];
/* ★★ item 显示文本缓存：paint_sel 要给选中项加 "  <" 后缀，
   若每次重算 item_text 就会丢掉高亮标记 ⇒ 原文存一份。*/
static char g_item_text[MAXR][96];

static void sel_changed(void);

/*★★ v3 新增：ASCII 降级开关（★ 阶段 1 强制开，避免中文字体渲染成空白）
 *   相机 /usr/share/fonts 无中文字体 ⇒ 中文标签 = 空白块
 *   ⇒ 默认走 ASCII（key 名本身是 ASCII：portra400 / velvia50 ...）
 *   ⇒ 想试中文时用 nxfilmui <recipes> cjk
 */
static int g_ascii = 1;

/* ★★★ v3 新增：只读探测模式（不进 elm_run，telnet 里可直接跑）
 *   用途：GUI 出问题时，用它把"配方读到了吗 / 通道通吗"分离出来判断
 *   ★ 它只做只读动作（load_recipes + get_pw），不写 prefman
 */
static int probe_mode(const char *rpath) {
    int n, i, k;
    logopen();
    logf_("=== probe start rc=%d ascii=%d ===\n", (int)getpid(), g_ascii);
    printf("nxfilmui probe: recipes=%s ascii=%d\n", rpath, g_ascii);

    n = load_recipes(rpath);
    printf("load_recipes(%s) -> %d\n", rpath, n);
    if (n <= 0) {
        printf("★ 没有配方可用（这是第一步要确认的事）\n");
        return 1;
    }
    printf("\n%-3s %-16s %-40s %s\n", "#", "key", "label(ascii)", "7 values");
    printf("  --------------------------------------------------------------\n");
    for (i = 0; i < n && i < 40; i++) {
        char lab[64];
        int has_cjk = 0;
        for (k = 0; g_rec[i].label[k]; k++)
            if ((unsigned char)g_rec[i].label[k] >= 0x80) { has_cjk = 1; break; }
        /* 有 CJK 且 g_ascii ⇒ 用 key 名代替（屏幕上一定有可读文字）*/
        if (g_ascii && has_cjk) snprintf(lab, sizeof(lab), "(cjk) %s", g_rec[i].key);
        else                     snprintf(lab, sizeof(lab), "%s", g_rec[i].label);

        printf("%-3d %-16s %-40s", i, g_rec[i].key, lab);
        for (k = 0; k < 7; k++) printf(" %d", g_rec[i].v[k]);
        printf("\n");
    }
    printf("\n--- 只读回读当前 slot9 的 PW 值（不写任何东西）---\n");
    {
        static const char *NAMES7[7] = { "R","G","B","HUE","SAT","SHARP","CON" };
        for (i = 0; i < 7; i++) printf("  PW[%d] %-6s = %d\n", i, NAMES7[i], get_pw(i));
    }
    printf("\n--- 当前 enum（只读）= 0x%06x（ENUM9=0x%06x）---\n",
           cur_enum(), ENUM9);
    printf("\n★★ probe 不进 GUI、不写 prefman。想试GUI：nxfilmui %s\n",
           g_ascii ? "" : "cjk");
    printf("=== probe done ===\n");
    logf_("=== probe done ===\n");
    return 0;
}

/* 触摸/点击某个配方块 */
static void cb_item(void *data, Evas_Object *obj, void *ev) {
    int i = (int)(long)data;
    if (i < 0 || i >= g_nrec) return;
    g_sel = i;
    /* ★ 先刷高亮再应用：顺序反了会在 apply 的 system() 阻塞期间
       画面停在旧光标上，用户看不出自己点的是哪个 */
    logf_("step: calling sel_changed\n");
    sel_changed();
    logf_("step: sel_changed done\n");
    apply_sel(i);
    /* ★ 不关窗：连续点多个配方即时对比，这是 mod_gui 做不到的
     * ★★ 状态栏已由 sel_changed 更新成 "[n/N] key"（纯 ASCII）
     *   —— 原来这里用 g_rec[i].label（含中文），
     *   在无 CJK 字体的机器上有渲染风险，故去掉。*/
}

/* ★ 生成一个 item 的显示文本（ASCII 降级在此统一，v3）
 *   g_ascii=1（默认）：标签含非 ASCII ⇒ 用 key（key 本身是 ASCII）
 *   g_ascii=0（cjk）  ：用原label（★ 相机无中文字体 ⇒ 会渲染空白，仅调试）
 *   ★★ 无论哪种，屏幕上【保证有可读文字】，不会出现空白块。
 */
static void item_text(int i, char *out, size_t n) {
    Rec *r = &g_rec[i];
    int has_cjk = 0, k;
    for (k = 0; r->label[k]; k++)
        if ((unsigned char)r->label[k] >= 0x80) { has_cjk = 1; break; }

    if (has_cjk && g_ascii) snprintf(out, n, "%d. %s", i + 1, r->key);
    else                     snprintf(out, n, "%s", r->label);
}

static Evas_Object *mk_item(int i) {
    Rec *r = &g_rec[i];
    char t[96];
    Evas_Object *b = elm_button_add(g_grid);

    item_text(i, t, sizeof(t));
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
   ★★ v3：除了变色，还【重写 label 加 ">" 前缀】
      —— 因为 elm_button 的 part text 在 style "transparent" 下
         改颜色未必明显，加前缀保证"哪一项被选中"一定可见。
   判空是因为 gengrid 滚动时会懒回收 item。 */
static void paint_sel(void) {
    int i;
    char t[128];
    for (i = 0; i < g_nrec; i++) {
        if (!g_item[i]) continue;
        /* ★★ 从缓存取原文（不含高亮后缀），再按需追加 "  <" */
        snprintf(t, sizeof(t), "%s", g_item_text[i]);
        if (i == g_sel) {
            evas_object_color_set(g_item[i], 255, 200,  80, 255);
            if (strlen(t) + 4 < sizeof(t)) strcat(t, "  <");
        } else {
            evas_object_color_set(g_item[i], 200, 200, 200, 255);
        }
        elm_object_part_text_set(g_item[i], "label", t);
    }
}

/* ★★★ build_grid：★ 用 elm_box 排布，★ 不用 elm_gengrid
 *
 * ★★★★ 2026-10-07 13:18 实测定位（eflgrid.arm 四模式对照）：
 *   btnonly  : elm_button_add(grid)          ✅ 成功，返回有效指针
 *   append   : elm_gengrid_item_append(...)  ★★ signal=11 崩溃
 *   scanvas  : evas_object_rectangle_add(grid) 返回 nil
 *   scanvas2 : 同上
 *   ⇒ ★★ **`elm_gengrid_item_append` 在真机 EFL 1.7.99 上不可用**
 *   ⇒ ★ 这正是白名单查证时就该警觉的那一点：**mod_gui 从不用 gengrid**
 *     （check_abi.py 已提示 elm_gengrid_reorder / page_size_set 无真机证据）
 *
 * ★ 替代方案：elm_box(vertical) + 每行两个 elm_box(horizontal) + 按钮
 *   ⇒ 全部只用【已实机验证成功】的 elm_box_add / elm_button_add
 *   ⇒ 代价：没有 gengrid 的懒回收与自动分页
 *     但配方数 ≤ MAXR(32)，2 列 × 16 行在 720×480 内放得下
 *     ⇒ 外层仍有 elm_scroller，条目多了可滚
 */
static Evas_Object *g_row[MAXR];      /* 每行的 horizontal box（可选，仅用于布局）*/

static void build_grid(void) {
    int i;
    int ncol = 2;
    int roww = 350, rowh = 54;
    Evas_Object *cur_row = NULL;
    int col = 0;

    for (i = 0; i < g_nrec; i++) {
        Evas_Object *it;

        /* 每 ncol 个开一个新行 */
        if (col == 0) {
            cur_row = elm_box_add(g_grid, 1 /* horizontal */);
            evas_object_show(cur_row);
            elm_box_pack_end(g_grid, cur_row);
        }

        it = elm_button_add(cur_row);
        item_text(i, g_item_text[i], sizeof(g_item_text[i]));
        elm_object_part_text_set(it, "label", g_item_text[i]);
        evas_object_size_hint_min_set(it, roww, rowh);
        evas_object_show(it);
        g_item[i] = it;

        /* 触摸回调：★ 只挂 smart callback（"clicked"）——
           gengrid 的 item cb 已证实不可用（append 崩溃）*/
        evas_object_smart_callback_add(it, "clicked", (void *)cb_item,
                                       (void *)(long)i);

        /* ★★ 这里不用 evas_object_color_set 设常态色：
           它在 elm_button 上会覆盖主题，导致按钮看不见（btnonly 实测虽成功，
           但真正决定可读性的是 part text 的颜色）。
           ⇒ 常态交给主题（transparent 风格），选中态才用 evas_object_color_set。*/

        col++;
        if (col == ncol) col = 0;
    }
    logf_("build_grid: %d items in %d columns\n", g_nrec, ncol);
}

static void sel_changed(void) {
    if (g_nrec == 0) return;
    g_sel = ((g_sel % g_nrec) + g_nrec) % g_nrec;

    /* ★★ 状态栏：★ 必带序号，★★ 必用 key（ASCII）——
     *   因为 key 一定是 ASCII，中文字体缺失时只有它可读。
     *   格式形如 "[2/9] velvia50"
     */
    char b[128];
    snprintf(b, sizeof(b), "[%d/%d] %s", g_sel + 1, g_nrec, g_rec[g_sel].key);
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
    const char *rpath = "/mnt/mmc/filmlab/recipes.txt";
    int want_probe = 0, i;

    /* ★★★ v3 参数解析（★ 不再靠 argv[1] 猜，猜错会把参数当路径）
     *   nxfilmui probe              只读探测，不开GUI、不写 prefman
     *   nxfilmui gui                正常开 GUI（默认）
     *   nxfilmui <recipes.txt>      旧写法仍支持（兼容性）
     *   nxfilmui gui cjk            强行用中文标签（会渲染空白，仅调试用）
     *   nxfilmui probe cjk
     */
    for (i = 1; i < argc; i++) {
        const char *a = argv[i];
        if (!strcmp(a, "probe")) want_probe = 1;
        else if (!strcmp(a, "gui") || !strcmp(a, "cjk")) {
            if (!strcmp(a, "cjk")) g_ascii = 0;
        } else if (a[0] == '/') {
            rpath = a;
        }
    }

    logopen();
    logf_("=== start rc=%d probe=%d ascii=%d ===\n",
          (int)getpid(), want_probe, g_ascii);

    /* ★ 只读探测：★ 先跑它，把"配方读到了吗"与"GUI 起得来吗"分离 */
    if (want_probe) return probe_mode(rpath);

    /* ★★★ elm_init 判据方向（2026-10-07 13:14 实测纠正，极易搞反）
     *   EFL 1.7 的约定：★ 成功返回 1，失败返回 0
     *   实测：首次调用返回 1（成功）；再调一次返回 2（EFL 不支持重复 init）
     *   ⇒ ★★★ 判失败必须用 `== 0`，绝不能写 `!= 0`
     *
     * ★★ 第三个参数用 0（不是 1）：★ 与 eflmin.c 已验证能停住的调用完全一致。
     *   该参数是 Eina_Bool exit_on_error；eflmin 用 0 时 elm_run 能阻塞，
     *   而 nxfilmui 此前用 1 ⇒ 这是与【唯一已验证成功路径】的真实差异。
     */
    if (elm_init(argc, argv, 0) == 0) {
        logf_("elm_init FAILED (returned 0)\n");
        printf("elm_init FAILED (returned 0)\n");
        return 1;
    }
    logf_("elm_init ok (exit_on_error=0)\n");

    /*★★★ 2026-10-07 14:15 新增：★ 按键回调注册是唯一与【已验证成功路径】
     *   （eflmin full 模式）不同的步骤，且它的函数地址来自 dlsym ——
     *   ⇒★ dlsym 拿到的地址从未在真机被验证过，可能是野指针
     *   ⇒ 用 NXKS_NOKEY=1 可临时跳过它，用于二分定位 elm_run 秒退的真因
     */
    if (getenv("NXKS_NOKEY")) {
        logf_("SKIP key handler (NXKS_NOKEY set)\n");
    } else {
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
    }

    /*★★★★★★ 主循环函数：★ 与上面同一个 libecore.so，一并 dlsym
     *   ★★ mod_gui 用的就是它（未定义符号表里有），而它【不调 elm_run】
     */
    p_ecore_main_loop_iterate =
        (fn_ecore_main_loop_iterate)(long)dlsym(RTLD_DEFAULT,
                                             "ecore_main_loop_iterate");
    logf_("ecore_main_loop_iterate %s @ %p\n",
          p_ecore_main_loop_iterate ? "resolved" : "★ NOT FOUND",
          (void *)(long)p_ecore_main_loop_iterate);

    g_win = elm_win_add(NULL, "nxfilmui", ELM_WIN_BASIC);
    if (!g_win) { logf_("elm_win_add FAILED\n"); return 1; }
    elm_win_title_set(g_win, "FilmLab");
    evas_object_smart_callback_add(g_win, "delete,request", (void *)on_quit, NULL);
    /* ★ 满屏 = 仿 mod_gui 的做法：只靠 elm_win_resize_object_add 把对象绑到窗口尺寸，
       不调 elm_win_fullscreen_set（真机上查无使用证据，见文件头注释区）。*/

    /* ★★★ 2026-10-07 13:22 修正（★ 这是 elm_run 立即返回的原因）
     *   原来把 bg 和 box 【都】elm_win_resize_object_add 到 g_win ——
     *   ★★ elm_win_resize_object_add 是"独占 resize 槽"的：一个 window 只能绑一个，
     *      后绑的 box 会顶掉先绑的 bg ⇒ 窗口没有可见内容
     *      ⇒ elm_run() 认为无事可做，【立即返回】⇒ 程序瞬间退出、无窗口
     *   ⇒ 正确结构（与 eflmin.c 实测通过的 full 模式一致）：
     *      ① 只把 box 绑到窗口（box 是真正的内容容器）
     *      ② ★★ 末尾必须 evas_object_show(g_win) —— 原代码从未show 窗口！
     */
    Evas_Object *box = elm_box_add(g_win, 0 /* vertical */);
    evas_object_show(box);
    elm_win_resize_object_add(g_win, box);

    g_title = elm_label_add(box);
    elm_object_part_text_set(g_title, "label", "FilmLab Recipes  (jog=select  tap=apply)");
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
           重复注册会让一次按键回调触发两次（波轮一次转两格）。
           ★★ 这里不能用 elm_run（该构建上它立即返回）⇒ 用 usleep 静态等待，
              让进程活着好让用户看清报错；退出靠 killall。*/
        evas_object_show(g_win);
        for (;;) usleep(200000);
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
    logf_("step: title done, creating scroller\n");
    Evas_Object *scroll = elm_scroller_add(box);
    evas_object_color_set(scroll, 24, 24, 24, 255);
    evas_object_show(scroll);
    elm_scroller_policy_set(scroll, 1 /*h*/, 1 /*v*/);
    elm_box_pack_end(box, scroll);

    logf_("step: scroller ok, creating gengrid\n");
    /* ★★★ 2026-10-07：这里从 elm_gengrid_add 改成 elm_box_add
     *   原因：elm_gengrid_item_append 在真机 EFL 1.7.99 上 signal=11 崩溃
     *   （eflgrid.arm append 模式实测）。elm_box_add 已在同环境验证成功。
     *   g_grid 现在是"vertical box"—— 每行是一个 horizontal box。*/
    g_grid = elm_box_add(scroll, 0 /* vertical */);
    evas_object_size_hint_min_set(g_grid, 0, 0);
    evas_object_size_hint_weight_set(g_grid, 1.0f, 1.0f);
    evas_object_show(g_grid);
    logf_("step: grid(box) shown, building items\n");
    build_grid();
    logf_("step: build_grid done\n");

    logf_("step: creating status label\n");
    g_status = elm_label_add(box);
    evas_object_color_set(g_status, 120, 255, 160, 255);
    evas_object_size_hint_min_set(g_status, 0, 26);
    elm_box_pack_end(box, g_status);
    evas_object_show(g_status);
    sel_changed();

    /* ★★★ show 窗口 —— 缺这行窗口不可见 */
    logf_("step: showing window\n");
    evas_object_show(g_win);

    /*★★★★★★ 主循环：★ 不再用 elm_run（这个构建上它立即返回），改用
     *   ecore_main_loop_iterate —— ★★ mod_gui 实证使用的写法
     *
     *   循环体三条纪律（照mod_gui 的行为反推）：
     *     ① 每次 iterate 后让出 CPU（单核铁律：不给就会把相机压死）
     *     ② 用 g_quit 作为唯一退出条件（按键/窗口关闭都写它）
     *     ③ 间隔递增 sleep：空闲时不必高频轮询
     */
    logf_("step: entering ecore_main_loop_iterate loop (quit=%d)\n", g_quit);

    if (p_ecore_main_loop_iterate) {
        int spin = 0;
        int r0 = -999;
        while (!g_quit) {
            int r = p_ecore_main_loop_iterate();
            if (spin < 3)
                logf_("loop: iterate[%d] r=%d\n", spin, r);
            /* ★★ 高频心跳：每 2000 次打一行。日志的【最后一行】就是死亡位置 */
            if (spin % 2000 == 0)
                logf_("loop: spin=%d alive\n", spin);
            if (r0 == -999) r0 = r;
            /* ★★★ 不再因为 r 的大小退出：实测 r 恒为 0/1（14:20 实测）
             *   唯一退出条件是 g_quit（按键/关窗口写它）
             * ★ 也【不插usleep】—— ★★ 实测插了会导致进程在第 5 次后无日志消失
             *   ⇒ 单核相机上 ecore_main_loop_iterate 自己会阻塞在 select，
             *      ★ 我们不需要（也不该）再插sleep（那等于抢它的等待）
             */
            spin++;
        }
        logf_("step: loop exited spins=%d first_r=%d\n", spin, r0);
    } else {
        logf_("★ ecore_main_loop_iterate 不可用，fallback到 elm_run\n");
        logf_("step: entering elm_run\n");
        logf_("step: elm_run returned r=%d\n", elm_run());
    }

    elm_exit();
    logf_("=== exit ===\n");
    return 0;
}
