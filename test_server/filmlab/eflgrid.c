/* eflgrid.c — 定位 elm_gengrid 相关崩溃（2026-10-07 13:17）
 *
 * 现象：nxfilmui 崩在 build_grid() 里（signal=11 / strncmp）
 * 已知：elm_init / elm_win_add / elm_bg / elm_box / elm_label / elm_scroller
 *       / elm_gengrid_add 全部成功（nxfilmui 分步日志已确认到"gengrid shown"）
 *   ⇒ 崩在 build_grid() 内的两个调用之一：
 *       elm_button_add(g_grid)              ← 父对象是 gengrid，★ 存疑
 *       elm_gengrid_item_append(g_grid, …)  ← ★ 头号怀疑对象
 *
 * ★ 关键怀疑：elm_gengrid 的子对象 API 有严格约定 ——
 *   gengrid 的 item 必须是【elm_gengrid_item】类，
 *   而 elm_button_add(gengrid) 会创建一个"父对象是 gengrid 的 button"，
 *   在 1.7.99 上可能不被支持（mod_gui 从没用过 gengrid —— 这是白名单查证时就该警觉的）。
 *
 * 用法（★ 一次只跑一条）：
 *   eflgrid btnonly     只做 elm_button_add，不 append
 *   eflgrid append      btn + gengrid_item_append
 *   eflgrid scanvas     ★ 用 evas_object_rectangle_add 代替 button（绕开 elm 主题依赖）
 *   eflgrid scanvas2    ★ rectangle + elm_gengrid_item_append
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

typedef void Evas_Object;
typedef int  Eina_Bool;

int  elm_init(int, char **, Eina_Bool);
int  elm_run(void);
void elm_exit(void);
Evas_Object *elm_win_add(Evas_Object *, const char *, int);
Evas_Object *elm_bg_add(Evas_Object *);
Evas_Object *elm_box_add(Evas_Object *, int);
Evas_Object *elm_scroller_add(Evas_Object *);
Evas_Object *elm_gengrid_add(Evas_Object *);
Evas_Object *elm_button_add(Evas_Object *);
Evas_Object *elm_label_add(Evas_Object *);
void elm_gengrid_item_append(Evas_Object *, Evas_Object *, void *, void *);
void elm_win_resize_object_add(Evas_Object *, Evas_Object *);
void elm_box_pack_end(Evas_Object *, Evas_Object *);
void elm_object_part_text_set(Evas_Object *, const char *, const char *);
void evas_object_show(Evas_Object *);
void evas_object_color_set(Evas_Object *, int, int, int, int);
void evas_object_size_hint_min_set(Evas_Object *, int, int);
void evas_object_size_hint_weight_set(Evas_Object *, float, float);
Evas_Object *evas_object_rectangle_add(Evas_Object *);
Evas_Object *evas_object_smart_callback_add(Evas_Object *, const char *, void *, void *);

#define ELM_WIN_BASIC 1

#define LOG(...) do { printf(__VA_ARGS__); fflush(stdout); } while (0)

int main(int argc, char **argv)
{
    const char *mode = argc > 1 ? argv[1] : "btnonly";
    Evas_Object *win, *bg, *box, *scroll, *grid, *o;
    int rc;

    LOG("mode=%s\n", mode);
    rc = elm_init(argc, argv, 1);
    LOG("elm_init = %d\n", rc);
    if (rc == 0) { LOG("init failed\n"); return 1; }

    win = elm_win_add(NULL, "eflgrid", ELM_WIN_BASIC);
    LOG("win=%p\n", (void *)win);
    bg  = elm_bg_add(win);
    evas_object_size_hint_min_set(bg, 720, 480);
    elm_win_resize_object_add(win, bg);
    evas_object_show(bg);
    LOG("bg ok\n");

    box = elm_box_add(win, 0);
    elm_win_resize_object_add(win, box);
    evas_object_show(box);
    scroll = elm_scroller_add(box);
    evas_object_show(scroll);
    elm_box_pack_end(box, scroll);
    LOG("box+scroller ok\n");

    grid = elm_gengrid_add(scroll);
    evas_object_size_hint_weight_set(grid, 1.0f, 1.0f);
    evas_object_show(grid);
    LOG("grid=%p ok\n", (void *)grid);

    if (!strcmp(mode, "btnonly") || !strcmp(mode, "append")) {
        LOG("--> elm_button_add(grid)\n");
        o = elm_button_add(grid);
        LOG("button=%p\n", (void *)o);
        if (o) {
            elm_object_part_text_set(o, "label", "B1");
            evas_object_size_hint_min_set(o, 340, 54);
            evas_object_show(o);
            LOG("button configured ok\n");
        }
        if (!strcmp(mode, "append") && o) {
            LOG("--> elm_gengrid_item_append(grid, button, NULL, NULL)\n");
            elm_gengrid_item_append(grid, o, NULL, NULL);
            LOG("append ok\n");
        }
    } else if (!strcmp(mode, "scanvas") || !strcmp(mode, "scanvas2")) {
        LOG("--> evas_object_rectangle_add(grid)\n");
        o = evas_object_rectangle_add(grid);
        LOG("rect=%p\n", (void *)o);
        if (o) {
            evas_object_color_set(o, 200, 200, 200, 255);
            evas_object_size_hint_min_set(o, 340, 54);
            evas_object_show(o);
            LOG("rect configured ok\n");
        }
        if (!strcmp(mode, "scanvas2") && o) {
            LOG("--> elm_gengrid_item_append(grid, rect, NULL, NULL)\n");
            elm_gengrid_item_append(grid, o, NULL, NULL);
            LOG("append ok\n");
        }
    }
    LOG("== ALL OK, entering elm_run ==\n");
    fflush(stdout);
    elm_run();
    elm_exit();
    return 0;
}
