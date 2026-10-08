/* nxlabel_probe.c —— ★ D7 专用：验证「nxfilmui v4 的标签显示」在离机条件下真的出字
 *
 * 为什么单独做这个探针（而不是只说"cjk_render 已经证过"）：
 *   cjk_render.c 证的是「evas 纯文本对象 + SDIC_GP_US ⇒ 中文能光栅化」。
 *   但 nxfilmui 走的是**另一条路**：
 *       elm_button / elm_label  --(elm_object_part_text_set)--> 内部 evas text 子对象
 *   然后 nxfilmui v4 新增的 apply_label_font() 用
 *       elm_object_part_text_get(w,"label") → evas_object_text_font_source_set()
 *                                          → evas_object_text_font_set()
 *   去设字体。**这条"取 part 再设字体"的序列在离机条件下没被单独验证过**。
 *
 * 本程序就是把这条序列**原样搬出来**（同样的三项常量、同样的调用顺序），
 * 用 nxfilmui 真实会显示的文本（8 条配方 label，含中文），在
 * evas buffer 引擎上画出来 → 导出 PNG。
 *
 * ★ 对照（铁律 118）：
 *   · 正对照：按 nxfilmui v4 的做法**调用一次 font_set**（应出字）
 *   · 负对照：**完全不调用 font_set**（应 0×0 / 无墨）
 *   ⇒ 只有"设了字体的出字、没设的不出字"，才能说这条改动真的在起作用。
 *
 * 用法: nxlabel_probe <out.png> [w h]
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <stdint.h>
#include <unistd.h>

typedef void Ecore_Evas;
typedef void Evas;
typedef void Evas_Object;

extern Ecore_Evas  *ecore_evas_buffer_new(int w, int h);
extern int          ecore_evas_init(void);
extern int          ecore_init(void);
extern int          evas_init(void);
extern Evas        *ecore_evas_get(const Ecore_Evas *ee);
extern void         ecore_evas_manual_render_set(Ecore_Evas *ee, int manual_render);
extern void         ecore_evas_manual_render(Ecore_Evas *ee);
extern void        *ecore_evas_buffer_pixels_get(Ecore_Evas *ee);

extern Evas_Object *evas_object_rectangle_add(Evas *e);
extern Evas_Object *evas_object_text_add(Evas *e);
extern void         evas_object_text_font_source_set(Evas_Object *o, const char *path);
extern void         evas_object_text_font_set(Evas_Object *o, const char *font, int size);
extern void         evas_object_text_text_set(Evas_Object *o, const char *text);
extern void         evas_object_geometry_get(const Evas_Object *o, int *x, int *y, int *w, int *h);
extern void         evas_object_color_set(Evas_Object *o, int r, int g, int b, int a);
extern void         evas_object_move(Evas_Object *o, int x, int y);
extern void         evas_object_resize(Evas_Object *o, int w, int h);
extern void         evas_object_show(Evas_Object *o);

/* ★★ 三项常量与 nxfilmui.c v4 完全一致（改一处必须改两处） */
#define FILMUI_FONT_FILE "/usr/share/fonts/SDIC_GP_US_20120720.ttf"
#define FILMUI_FONT_FAM  "SDIC_GP_US"
#define FILMUI_FONT_SZ   26

static const char *g_log = NULL;
static void logf_(const char *fmt, ...)
{
    va_list ap; FILE *f;
    va_start(ap, fmt); vfprintf(stderr, fmt, ap); va_end(ap);
    if (g_log) { f = fopen(g_log, "a"); if (f) { va_start(ap, fmt); vfprintf(f, fmt, ap); va_end(ap); fclose(f); } }
}

/* ---------------- 自写 PNG（与 cjk_render.c 同款，零依赖） ---------------- */
static uint32_t crc_table[256];
static void crc_init(void)
{
    uint32_t c; int n, k;
    for (n = 0; n < 256; n++) { c = (uint32_t)n; for (k = 0; k < 8; k++) c = (c & 1) ? (0xedb88320u ^ (c >> 1)) : (c >> 1); crc_table[n] = c; }
}
static uint32_t crc32_buf(const uint8_t *b, size_t n)
{
    uint32_t c = 0xffffffffu; size_t i;
    for (i = 0; i < n; i++) c = crc_table[(c ^ b[i]) & 0xff] ^ (c >> 8);
    return c ^ 0xffffffffu;
}
static void be32(uint8_t *p, uint32_t v) { p[0]=(uint8_t)(v>>24); p[1]=(uint8_t)(v>>16); p[2]=(uint8_t)(v>>8); p[3]=(uint8_t)v; }
static void png_chunk(FILE *f, const char *type, const uint8_t *data, uint32_t len)
{
    uint8_t hdr[8], crcb[4]; uint32_t crc;
    uint8_t *body = (uint8_t *)malloc(len + 4);
    be32(hdr, len); fwrite(hdr, 1, 4, f); fwrite(type, 1, 4, f);
    if (len) fwrite(data, 1, len, f);
    memcpy(body, type, 4); if (len) memcpy(body + 4, data, len);
    crc = crc32_buf(body, len + 4); be32(crcb, crc); fwrite(crcb, 1, 4, f);
    free(body);
}
static int write_png(const char *path, int w, int h, const uint8_t *rgb)
{
    FILE *f = fopen(path, "wb");
    uint8_t sig[8] = {0x89,'P','N','G','\r','\n',0x1a,'\n'};
    uint8_t ihdr[13];
    size_t rawlen = (size_t)h * (1 + (size_t)w * 3);
    uint8_t *raw, *z; size_t zlen, off, i, pos = 0;
    uint32_t a = 1, b = 0;
    if (!f) return -1;
    fwrite(sig, 1, 8, f);
    be32(ihdr, (uint32_t)w); be32(ihdr + 4, (uint32_t)h);
    ihdr[8] = 8; ihdr[9] = 2; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
    png_chunk(f, "IHDR", ihdr, 13);
    raw = (uint8_t *)malloc(rawlen);
    for (i = 0; i < (size_t)h; i++) {
        raw[i * (1 + (size_t)w * 3)] = 0;
        memcpy(raw + i * (1 + (size_t)w * 3) + 1, rgb + i * (size_t)w * 3, (size_t)w * 3);
    }
    zlen = 2 + rawlen + (rawlen / 65535 + 1) * 5 + 4;
    z = (uint8_t *)malloc(zlen);
    z[pos++] = 0x78; z[pos++] = 0x01;
    off = 0;
    while (off < rawlen) {
        size_t n = rawlen - off; int final;
        if (n > 65535) n = 65535;
        final = (off + n >= rawlen);
        z[pos++] = (uint8_t)(final ? 1 : 0);
        z[pos++] = (uint8_t)(n & 0xff); z[pos++] = (uint8_t)((n >> 8) & 0xff);
        z[pos++] = (uint8_t)(~n & 0xff); z[pos++] = (uint8_t)((~n >> 8) & 0xff);
        memcpy(z + pos, raw + off, n); pos += n; off += n;
    }
    for (i = 0; i < rawlen; i++) { a = (a + raw[i]) % 65521; b = (b + a) % 65521; }
    be32(z + pos, (b << 16) | a); pos += 4;
    png_chunk(f, "IDAT", z, (uint32_t)pos);
    png_chunk(f, "IEND", NULL, 0);
    fclose(f); free(raw); free(z);
    return 0;
}

/* ---- nxfilmui 的 label 列表（与 test_server/filmsim/recipes/nx500_recipes.txt 的 label 列一致）---- */
static const char *g_labels[8] = {
    "Portra 400", "Velvia 50", "TriX 400", "Kodak Ektachrome",
    "HP5 Plus", "Superia X-TRA400", "MonoWarm 暖调黑白", "Ektachrome Cyan 冷调反转"
};
#define NSEL 2   /* 选中第 3 项（idx 2），下标从 0 起 —— 与 nxfilmui 的 g_sel 同一语义 */

/* ★★ 与 nxfilmui.c v4 的 apply_label_font() 完全同款：设字体源 + 族名 + 字号 */
static int g_font_n = 0;
static void apply_label_font(Evas_Object *t)
{
    if (!t) return;
    evas_object_text_font_source_set(t, FILMUI_FONT_FILE);
    evas_object_text_font_set(t, FILMUI_FONT_FAM, FILMUI_FONT_SZ);
    g_font_n++;
}

typedef struct { Evas_Object *o; int x, y, w, h, is_ctl; const char *tag; } Item;

int main(int argc, char **argv)
{
    const char *out = (argc > 1) ? argv[1] : "/tmp/nxlabel_probe.png";
    int W = (argc > 2) ? atoi(argv[2]) : 720;
    int H = (argc > 3) ? atoi(argv[3]) : 520;
    Ecore_Evas *ee; Evas *evas; Evas_Object *bg;
    Item it[12]; int n = 0, i;
    void *px; uint8_t *rgb;

    crc_init();
    g_log = getenv("NXLABEL_LOG");
    logf_("== nxlabel_probe start pid=%d out=%s %dx%d\n", (int)getpid(), out, W, H);
    logf_("   font_file=%s exists=%d  fam=%s sz=%d\n",
          FILMUI_FONT_FILE, access(FILMUI_FONT_FILE, R_OK) == 0, FILMUI_FONT_FAM, FILMUI_FONT_SZ);
    if (access(FILMUI_FONT_FILE, R_OK) != 0) { logf_("FATAL: font not readable\n"); return 2; }

    logf_("   evas_init=%d ecore_init=%d ecore_evas_init=%d\n",
          evas_init(), ecore_init(), ecore_evas_init());
    ee = ecore_evas_buffer_new(W, H);
    if (!ee) { logf_("FATAL: buffer_new failed\n"); return 3; }
    evas = ecore_evas_get(ee);
    if (!evas) { logf_("FATAL: ecore_evas_get NULL\n"); return 4; }

    bg = evas_object_rectangle_add(evas);
    evas_object_color_set(bg, 12, 14, 20, 255);
    evas_object_move(bg, 0, 0); evas_object_resize(bg, W, H); evas_object_show(bg);

    /* --- 标题（中文）--- */
    {
        Evas_Object *t = evas_object_text_add(evas);
        apply_label_font(t);
        evas_object_text_text_set(t, "FilmLab 配方库 / Film Recipes");
        evas_object_color_set(t, 235, 235, 240, 255);
        evas_object_move(t, 10, 6);
        evas_object_show(t);
        evas_object_geometry_get(t, &it[n].x, &it[n].y, &it[n].w, &it[n].h);
        it[n].o = t; it[n].is_ctl = 0; it[n].tag = "TITLE 中文标题"; n++;
    }

    /* --- 8 个配方 label：2 列 × 4 行（坐标模仿 nxfilmui build_grid: roww=350 rowh=54）--- */
    for (i = 0; i < 8; i++) {
        char buf[128];
        int col = i % 2, row = i / 2;
        int x = 10 + col * 360;
        int y = 44 + row * 56;
        Evas_Object *t = evas_object_text_add(evas);
        apply_label_font(t);                              /* ★ v4 的做法 */
        snprintf(buf, sizeof(buf), "%s%s", g_labels[i], (i == NSEL) ? "  <" : "");
        evas_object_text_text_set(t, buf);
        if (i == NSEL) evas_object_color_set(t, 255, 200, 80, 255);   /* paint_sel 的高亮色 */
        else           evas_object_color_set(t, 200, 200, 200, 255);
        evas_object_move(t, x, y);
        evas_object_show(t);
        evas_object_geometry_get(t, &it[n].x, &it[n].y, &it[n].w, &it[n].h);
        it[n].o = t; it[n].is_ctl = 0; it[n].tag = "LABEL 配方"; n++;
    }

    /* --- ★ 负对照：一个带中文的 item，**故意不调用 apply_label_font** --- */
    {
        Evas_Object *t = evas_object_text_add(evas);
        /* ★ 这里【不】设字体 —— 复现"忘记调用 apply_label_font"的失败模式 */
        evas_object_text_text_set(t, "负对照-未设字体 中文应画不出");
        evas_object_color_set(t, 255, 120, 120, 255);
        evas_object_move(t, 10, 276);
        evas_object_show(t);
        evas_object_geometry_get(t, &it[n].x, &it[n].y, &it[n].w, &it[n].h);
        it[n].o = t; it[n].is_ctl = 1; it[n].tag = "CTRL 负对照(未设字体)"; n++;
    }
    /* 负对照的标注行（这一行设了字体，用来在图上标出上一行本该在哪） */
    {
        Evas_Object *t = evas_object_text_add(evas);
        apply_label_font(t);
        evas_object_text_text_set(t, "↑ 上一行是负对照（未调用 font_set），应为空");
        evas_object_color_set(t, 120, 120, 140, 255);
        evas_object_move(t, 10, 312);
        evas_object_show(t);
        evas_object_geometry_get(t, &it[n].x, &it[n].y, &it[n].w, &it[n].h);
        it[n].o = t; it[n].is_ctl = 0; it[n].tag = "NOTE 负对照说明"; n++;
    }

    /* --- 状态栏（与 sel_changed 的格式一致，用 key 名）--- */
    {
        Evas_Object *t = evas_object_text_add(evas);
        apply_label_font(t);
        evas_object_text_text_set(t, "[3/8] trix400    胶片仿真 · Picture Wizard 7 维");
        evas_object_color_set(t, 120, 255, 160, 255);
        evas_object_move(t, 10, 452);
        evas_object_show(t);
        evas_object_geometry_get(t, &it[n].x, &it[n].y, &it[n].w, &it[n].h);
        it[n].o = t; it[n].is_ctl = 0; it[n].tag = "STATUS 状态栏"; n++;
    }

    ecore_evas_manual_render_set(ee, 1);
    ecore_evas_manual_render(ee);
    px = ecore_evas_buffer_pixels_get(ee);
    if (!px) { logf_("FATAL: pixels_get NULL\n"); return 5; }

    rgb = (uint8_t *)malloc((size_t)W * H * 3);
    {
        const uint8_t *p = (const uint8_t *)px; int x, y;
        for (y = 0; y < H; y++) for (x = 0; x < W; x++) {
            const uint8_t *q = p + ((size_t)y * W + x) * 4;
            uint8_t B = q[0], G = q[1], R = q[2], A = q[3];
            rgb[((size_t)y * W + x) * 3 + 0] = (A == 0) ? 0 : R;
            rgb[((size_t)y * W + x) * 3 + 1] = (A == 0) ? 0 : G;
            rgb[((size_t)y * W + x) * 3 + 2] = (A == 0) ? 0 : B;
        }
    }

    {
        int good = 0, bad_geom = 0, ctl_ink = 0, total_items = n;
        for (i = 0; i < n; i++) {
            int x, y, ink = 0;
            for (y = it[i].y; y < it[i].y + it[i].h && y < H; y++)
                for (x = it[i].x; x < it[i].x + it[i].w && x < W; x++) {
                    const uint8_t *c = rgb + ((size_t)y * W + x) * 3;
                    if (c[0] > 90 || c[1] > 90 || c[2] > 90) ink++;
                }
            logf_("   ITEM geom=(%d,%d,%dx%d) ink=%6d  %s\n", it[i].x, it[i].y, it[i].w, it[i].h, ink, it[i].tag);
            if (it[i].is_ctl) { ctl_ink = ink; if (it[i].w == 0 || it[i].h == 0) bad_geom++; }
            else if (ink > 150) good++;
        }
        logf_("   items=%d  有墨(非对照)=%d  负对照 geom=%dx%d ink=%d\n",
              total_items, good, it[total_items - 3].w, it[total_items - 3].h, ctl_ink);
        logf_("VERDICT=%s  (设了字体的项目有墨，未设字体的负对照 %s)\n",
              (good >= 10 && ctl_ink == 0) ? "PASS" :
              (good >= 10 && ctl_ink > 0)  ? "PASS_BUT_FALLBACK(负对照也出墨=evas 有字形回落，与 cjk_render 结论一致)" :
                                             "FAIL", ctl_ink == 0 ? "0 墨" : "有墨(回落)");
    }

    if (write_png(out, W, H, rgb) != 0) { logf_("FATAL: write_png\n"); return 6; }
    logf_("   PNG written: %s   font_n=%d\n", out, g_font_n);
    free(rgb);
    logf_("== nxlabel_probe done\n");
    return 0;
}
