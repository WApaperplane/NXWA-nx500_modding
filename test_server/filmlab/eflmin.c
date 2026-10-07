/* eflmin.c — 最小 EFL 初始化探针：二分定位 elm_init 失败的原因
 *
 * ★ 为什么要它：nxfilmui 在真机 elm_init FAILED（13:08 与 13:11 两次），
 *   而同一目录/同一 DISPLAY 下 mod_gui 的 EFL 初始化完全正常
 *   （它走到了"读配置文件"那步才报错）。
 *   ⇒ 问题在我的程序，不在环境。
 *   ⇒ 用最小程序逐项加东西，看哪一步让它挂。
 *
 * ★★ 关键怀疑点（按优先级）：
 *   ① ★★★ `elm_init(argc, argv, 1)` 的第三个参数 —— mod_gui 传的是 0
 *      EFL 1.7 的签名是 elm_init(int argc, char **argv, Eina_Bool exit_on_error)
 *      传 1 表示"出错就 exit"…… 但更可能的问题是 argv 里带着
 *      我们的自定义参数 "gui"/"probe"，而 elm_init 会去解析 EFL 自己的参数。
 *   ② ★★ 我们的 argv[0] 路径与 mod_gui 不同（不影响 elm_init）
 *   ③ ★ env：mod_gui 可能在特定 env 下跑（如由 loadgui.sh 设置过什么）
 *
 * 用法（★ 一次只跑一条）：
 *   eflmin                只测 elm_init，不建任何控件
 *   eflmin win            elm_init + elm_win_add
 *   eflmin full           elm_init + win + bg + box + label
 *   eflmin ev             打印 env（DISPLAY/WAYLAND/XDG_*）
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

typedef void Evas_Object;
typedef void Elm_Widget;
typedef int  Eina_Bool;

int  elm_init(int, char **, Eina_Bool);
int  elm_run(void);
void elm_exit(void);
Evas_Object *elm_win_add(Evas_Object *, const char *, int);
Evas_Object *elm_bg_add(Evas_Object *);
Evas_Object *elm_box_add(Evas_Object *, int);
Evas_Object *elm_label_add(Evas_Object *);
void elm_win_resize_object_add(Evas_Object *, Evas_Object *);
void elm_win_title_set(Evas_Object *, const char *);
void elm_box_pack_end(Evas_Object *, Evas_Object *);
void elm_object_part_text_set(Evas_Object *, const char *, const char *);
void evas_object_show(Evas_Object *);
void evas_object_size_hint_min_set(Evas_Object *, int, int);

#define ELM_WIN_BASIC 1

int main(int argc, char **argv)
{
    const char *mode = (argc > 1) ? argv[1] : "min";
    int rc;

    printf("== eflmin mode=%s argc=%d\n", mode, argc);
    { int i; for (i = 0; i < argc; i++) printf("   argv[%d]=%s\n", i, argv[i]); }

    printf("-- env --\n");
    printf("   DISPLAY=[%s]\n", getenv("DISPLAY") ? getenv("DISPLAY") : "(unset)");
    printf("   WAYLAND_DISPLAY=[%s]\n",
           getenv("WAYLAND_DISPLAY") ? getenv("WAYLAND_DISPLAY") : "(unset)");
    printf("   XDG_RUNTIME_DIR=[%s]\n",
           getenv("XDG_RUNTIME_DIR") ? getenv("XDG_RUNTIME_DIR") : "(unset)");
    printf("   HOME=[%s]\n", getenv("HOME") ? getenv("HOME") : "(unset)");
    printf("   LD_LIBRARY_PATH=[%s]\n",
           getenv("LD_LIBRARY_PATH") ? getenv("LD_LIBRARY_PATH") : "(unset)");
    fflush(stdout);

    /*★★★★★★ 判据方向（2026-10-07 13:14 实测纠正，极易搞反）
     *   EFL 1.7 的 elm_init() 约定：
     *       成功 -> 返回 1
     *       失败 -> 返回 0
     *       重复 init -> 返回 2（EFL 不支持第二次 init）
     *   ⇒ ★★★ 判失败应当用 `== 0`（或 `< 1`），**绝不是 `!= 0`**
     *   ⇒ 我首版写成 `if (elm_init(...) != 0) { FAILED; return 1; }`
     *      ⇒ init 其实成功（返回1）⇒ 被误判为失败 ⇒ 直接退出 ⇒ 窗口永不出现
     *   ⇒ 这是"编译通过、ABI 正确、逻辑却反了"的典型：只有实机能发现
     */
    rc = elm_init(argc, argv, 0);
    printf("elm_init(argc,argv,0) = %d  (%s)\n", rc,
           rc == 1 ? "SUCCESS (EFL 约定: 1=ok)" :
           rc == 0 ? "FAILURE (0=fail)"   : "其他（重复 init? 2）");
    fflush(stdout);

    if (rc == 0) {
        printf("★ elm_init 真失败（返回 0）—— 这次是环境/依赖问题\n");
        /* ★ 不要再试第二次：EFL 不支持重复 init（实测第二次返回 2）*/
        return 1;
    }
    if (rc != 1)
        printf("★ 注意：返回值不是 1（可能已初始化过），但继续往下走\n");
    printf("== elm_init OK ==\n");
    fflush(stdout);

    if (!strcmp(mode, "min")) { printf("== done(min) ==\n"); return 0; }

    {
        Evas_Object *win = elm_win_add(NULL, "eflmin", ELM_WIN_BASIC);
        printf("elm_win_add = %p\n", (void *)win);
        if (!win) { printf("★ win 失败\n"); return 2; }
        elm_win_title_set(win, "EFLMIN");
        fflush(stdout);
        if (!strcmp(mode, "win")) { printf("== done(win) ==\n"); return 0; }

        {
            Evas_Object *bg = elm_bg_add(win);
            evas_object_size_hint_min_set(bg, 720, 480);
            elm_win_resize_object_add(win, bg);
            evas_object_show(bg);
            printf("bg ok\n");
        }
        {
            Evas_Object *box = elm_box_add(win, 0);
            Evas_Object *lb  = elm_label_add(box);
            elm_win_resize_object_add(win, box);
            elm_object_part_text_set(lb, "label", "EFLMIN READY");
            evas_object_size_hint_min_set(lb, 0, 40);
            elm_box_pack_end(box, lb);
            evas_object_show(box);
            evas_object_show(lb);
            printf("box+label ok\n");
        }
        fflush(stdout);
        printf("== entering elm_run (mode=full) ==\n");
        fflush(stdout);
        elm_run();
        elm_exit();
    }
    printf("== done(full) ==\n");
    return 0;
}
