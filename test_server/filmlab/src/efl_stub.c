/*
 * efl_stub.c — ★ 仅供链接期使用的 EFL 符号桩库 ★
 *
 * 为什么需要
 * ----------
 * 本地 sysroot（.uploads/nx1_open/rootfs_dev/.../lib）里没有 EFL 库，
 * 头文件也没有，所以 nxfilmui.c 的 EFL 调用全是手写 ABI 声明。
 * 链接期需要从 -l:elementary / -l:evas 里解析符号，缺库就链接不过。
 *
 * 为什么这样做是安全的（关键）
 * -----------------------------
 * 1. 本文件只在【构建机上】参与链接，不会部署到相机。
 * 2. 每个桩函数的 soname 与真机完全一致（libelementary.so.1 / libevas.so.1），
 *    所以产物 DT_NEEDED 记的就是这两个名字。
 * 3. 相机上 ld-linux 加载产物时，找的是【真机的 libelementary.so.1】，
 *    按 ELF 符号解析规则把地址填进 GOT——桩函数地址从不进真机。
 *    ⇒ 与用真机 .so 链接的产物在运行时完全等价。
 * 4. 桩函数体是空的，但它们永远不会被执行。
 *
 * 与 ecore_event_handler_add 的区别
 * ---------------------------------
 * libecore.so.1 的那个符号**不走桩**，走 dlsym（见 nxfilmui.c 的说明）：
 * 那个坑是「链接期stub 静默吃掉了符号」，本文件的存在就是为了不重复它。
 * 但反过来，桩库里如果漏了某个符号，链接器会直接报错（可发现）；
 * 而 stub 被当成真库那样静态解析、运行时跳空，才是最危险的失败模式。
 * 所以下面这份桩的符号集合，必须与 nxfilmui.c 的引用集合严格对齐，
 * 由 check_abi.py 从真机 .dynsym 核对过。
 */
#define _GNU_SOURCE

/* ---- libelementary.so.1 ---- */
int  elm_init(int a, char **b, int c) { (void)a;(void)b;(void)c; return 0; }
int  elm_run(void) { return 0; }
void elm_exit(void) { }
void *elm_win_add(void *p, const char *n, int t) { (void)p;(void)n;(void)t; return 0; }
void elm_win_title_set(void *w, const char *t) { (void)w;(void)t; }
void elm_win_resize_object_add(void *w, void *o) { (void)w;(void)o; }
void *elm_bg_add(void *w) { (void)w; return 0; }
void *elm_box_add(void *w, int h) { (void)w;(void)h; return 0; }
void elm_box_pack_end(void *b, void *c) { (void)b;(void)c; }
void *elm_gengrid_add(void *p) { (void)p; return 0; }
void elm_gengrid_item_append(void *g, void *i, void *cb, void *d) {
    (void)g;(void)i;(void)cb;(void)d;
}
void *elm_scroller_add(void *p) { (void)p; return 0; }
void elm_scroller_policy_set(void *s, int h, int v) { (void)s;(void)h;(void)v; }
void *elm_label_add(void *b) { (void)b; return 0; }
void elm_object_part_text_set(void *o, const char *p, const char *t) {
    (void)o;(void)p;(void)t;
}
void elm_object_style_set(void *o, const char *s, int r) { (void)o;(void)s;(void)r; }
void *elm_button_add(void *b) { (void)b; return 0; }

/* ---- libevas.so.1 ---- */
void evas_object_show(void *o) { (void)o; }
void evas_object_del(void *o) { (void)o; }
int  evas_object_smart_callback_add(void *o, const char *n, void *f, void *d) {
    (void)o;(void)n;(void)f;(void)d; return 0;
}
void evas_object_color_set(void *o, int r, int g, int b, int a) {
    (void)o;(void)r;(void)g;(void)b;(void)a;
}
void evas_object_size_hint_min_set(void *o, int w, int h) { (void)o;(void)w;(void)h; }
void evas_object_size_hint_weight_set(void *o, float x, float y) { (void)o;(void)x;(void)y; }
void evas_object_size_hint_max_set(void *o, int w, int h) { (void)o;(void)w;(void)h; }
void evas_object_render_op_set(void *o, int op) { (void)o;(void)op; }
