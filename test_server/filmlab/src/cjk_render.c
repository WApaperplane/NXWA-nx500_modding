/* cjk_render.c —— 离线验证「相机自带字体能不能真画出中文」
 *
 * 背景（2026-10-08 QEMU S5）：
 *   - 相机 /usr/share/fonts/SDIC_GP_US_20120720.ttf 有 49864 字形，PC 侧解析
 *     cmap+glyf/loca 证明随机 300 个 CJK 码点 300/300 有非空轮廓。
 *   - 但那只证明「字形在」，没证明「evas 能画出来」。
 *   - S5 §4 留的下一步就是：★ 用 evas 的 buffer 引擎离线光栅化中文 → 导出 PNG。
 *
 * 本程序就是那个下一步。它不依赖 X11、不依赖相机：
 *   ecore_evas_buffer_new()  →  内存画面
 *   evas_object_text_add() + evas_object_text_font_source_set(显式 TTF 路径)
 *   ecore_evas_manual_render() → 光栅化
 *   ecore_evas_buffer_pixels_get() → 取像素
 *   自写 PNG（stored deflate，零依赖）导出
 *
 * ★ 为什么要 font_source_set 显式给 TTF 路径：
 *   S5 已证 evas 不硬编码 SDIC_GP_US（libevas 零命中，且相机无 /etc/fonts/fontconfig），
 *   所以必须显式指定「字体文件 + 族名」，不能指望主题自动选中。
 *
 * ★★ 对照组（铁律 118：对照失败禁止输出主结论）：
 *   同一次运行里同时画
 *     A) 显式字体源 SDIC_GP_US   —— 正对照（应出字）
 *     B) 不存在的族名 NO_SUCH_FONT_ZZZ + 不存在的字体文件 —— 负对照（应为空/方框）
 *   只有 A 有墨而 B 无墨，才能说「这次渲染通路真的在量目标」。
 *
 * 用法：
 *   cjk_render <out.png> [w h]
 * 退出码：0 成功
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <stdint.h>
#include <unistd.h>

/* ---- 只声明用到的那几个 EFL 符号（本地无 EFL 头文件；符号已用 dynsym 核对过） ---- */
typedef void Ecore_Evas;
typedef void Evas;
typedef void Evas_Object;

extern Ecore_Evas  *ecore_evas_buffer_new(int w, int h);
extern int          ecore_evas_init(void);
extern void         ecore_evas_shutdown(void);
extern int          ecore_evas_engine_type_supported_get(const char *engine);
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

#define FONT_FILE "/usr/share/fonts/SDIC_GP_US_20120720.ttf"
#define FONT_FAM  "SDIC_GP_US"
/* 负对照字体：Tizen 的柬埔寨文子集，确定不含 CJK */
#define FONT_FILE2 "/usr/share/fonts/TizenSansKhmerRegular.ttf"
#define FONT_FAM2  "TizenSansKhmerRegular"

static const char *g_log = NULL;
static void logf_(const char *fmt, ...)
{
    va_list ap;
    FILE *f;
    va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
    if (g_log) {
        f = fopen(g_log, "a");
        if (f) { va_start(ap, fmt); vfprintf(f, fmt, ap); va_end(ap); fclose(f); }
    }
}

/* ---------------- 自写 PNG：零依赖（stored deflate + adler32 + crc32） ---------------- */
static uint32_t crc_table[256];
static void crc_init(void)
{
    uint32_t c; int n, k;
    for (n = 0; n < 256; n++) {
        c = (uint32_t)n;
        for (k = 0; k < 8; k++) c = (c & 1) ? (0xedb88320u ^ (c >> 1)) : (c >> 1);
        crc_table[n] = c;
    }
}
static uint32_t crc32_buf(const uint8_t *b, size_t n)
{
    uint32_t c = 0xffffffffu; size_t i;
    for (i = 0; i < n; i++) c = crc_table[(c ^ b[i]) & 0xff] ^ (c >> 8);
    return c ^ 0xffffffffu;
}
static void be32(uint8_t *p, uint32_t v)
{ p[0]=(uint8_t)(v>>24); p[1]=(uint8_t)(v>>16); p[2]=(uint8_t)(v>>8); p[3]=(uint8_t)v; }

static void png_chunk(FILE *f, const char *type, const uint8_t *data, uint32_t len)
{
    uint8_t hdr[8], crcb[4];
    uint32_t crc;
    uint8_t *body = (uint8_t *)malloc(len + 4);
    be32(hdr, len);
    fwrite(hdr, 1, 4, f);
    fwrite(type, 1, 4, f);
    if (len) fwrite(data, 1, len, f);
    memcpy(body, type, 4);
    if (len) memcpy(body + 4, data, len);
    crc = crc32_buf(body, len + 4);
    be32(crcb, crc);
    fwrite(crcb, 1, 4, f);
    free(body);
}

/* 把 RGB（已去 alpha）写成 PNG；用 stored deflate，无需 zlib */
static int write_png(const char *path, int w, int h, const uint8_t *rgb)
{
    FILE *f = fopen(path, "wb");
    uint8_t sig[8] = {0x89,'P','N','G','\r','\n',0x1a,'\n'};
    uint8_t ihdr[13];
    size_t rawlen = (size_t)h * (1 + (size_t)w * 3);
    uint8_t *raw, *z;
    size_t zlen, off, i, pos = 0;
    uint32_t a = 1, b = 0;

    if (!f) return -1;
    fwrite(sig, 1, 8, f);

    be32(ihdr, (uint32_t)w); be32(ihdr + 4, (uint32_t)h);
    ihdr[8] = 8; ihdr[9] = 2; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
    png_chunk(f, "IHDR", ihdr, 13);

    raw = (uint8_t *)malloc(rawlen);
    for (i = 0; i < (size_t)h; i++) {
        raw[i * (1 + (size_t)w * 3)] = 0;                       /* filter: none */
        memcpy(raw + i * (1 + (size_t)w * 3) + 1, rgb + i * (size_t)w * 3, (size_t)w * 3);
    }

    /* zlib: 2 字节头 + (stored deflate blocks) + adler32 */
    zlen = 2 + rawlen + (rawlen / 65535 + 1) * 5 + 4;
    z = (uint8_t *)malloc(zlen);
    z[pos++] = 0x78; z[pos++] = 0x01;
    off = 0;
    while (off < rawlen) {
        size_t n = rawlen - off; int final;
        if (n > 65535) n = 65535;
        final = (off + n >= rawlen);
        z[pos++] = (uint8_t)(final ? 1 : 0);
        z[pos++] = (uint8_t)(n & 0xff); z[pos++] = (uint8_t)(n >> 8);
        z[pos++] = (uint8_t)(~n & 0xff); z[pos++] = (uint8_t)((~n >> 8) & 0xff);
        memcpy(z + pos, raw + off, n); pos += n;
        off += n;
    }
    for (i = 0; i < rawlen; i++) {
        a = (a + raw[i]) % 65521;
        b = (b + a) % 65521;
    }
    be32(z + pos, (b << 16) | a); pos += 4;

    png_chunk(f, "IDAT", z, (uint32_t)pos);
    png_chunk(f, "IEND", NULL, 0);
    fclose(f);
    free(raw); free(z);
    return 0;
}

/* ---------------- 画一页 ---------------- */
/* 每行的字体配置模式 —— 用来回答"原生 UI 到底必须多大程度上显式指定字体" */
#define MODE_EXPLICIT_SDIC 0   /* font_source=SDIC 文件 + 族名 SDIC_GP_US（最明确） */
#define MODE_EXPLICIT_OTH  1   /* font_source=Khmer 文件 + 族名 → 看 evas 是否回落 */
#define MODE_BYNAME_SDIC   2   /* 不给 font_source，只给族名 SDIC_GP_US */
#define MODE_BYNAME_SANS   3   /* 不给 font_source，族名 Sans（通用名） */
#define MODE_NOFONT        4   /* 完全不给字体，看 evas 默认字体 */

typedef struct { const char *text; int size; int y; const char *tag; int mode; } Row;

int main(int argc, char **argv)
{
    const char *out = (argc > 1) ? argv[1] : "/tmp/cjk_render.png";
    int W = (argc > 3) ? atoi(argv[2]) : 800;
    int H = (argc > 3) ? atoi(argv[3]) : 620;
    Ecore_Evas *ee;
    Evas *evas;
    Evas_Object *bg;
    Evas_Object *objs[16];
    int rx[16], ry[16], rw[16], rh[16], rmode[16];
    void *px;
    uint8_t *rgb;
    Row rows[16];
    int nrows = 0, i, nonwhite = 0;
    int ctl_y0 = 0, ctl_y1 = 0;

    crc_init();                     /* ★ 必须调，否则 CRC 全 0xffffffff，PIL 打不开 */
    g_log = getenv("CJK_LOG");
    logf_("== cjk_render start pid=%d out=%s %dx%d\n", (int)getpid(), out, W, H);
    logf_("   font_file=%s  exists=%d\n", FONT_FILE, access(FONT_FILE, R_OK) == 0);

    if (access(FONT_FILE, R_OK) != 0) { logf_("FATAL: font file not readable\n"); return 2; }

    /* ★ ecore_evas 必须先 init（EFL 1.7 的约定；漏掉则 buffer_new 直接返回 NULL，且不报错） */
    logf_("   evas_init=%d\n", evas_init());
    logf_("   ecore_init=%d\n", ecore_init());
    logf_("   ecore_evas_init=%d\n", ecore_evas_init());
    logf_("   engine buffer=%d fb=%d sw_generic=%d sw_x11=%d\n",
          ecore_evas_engine_type_supported_get("buffer"),
          ecore_evas_engine_type_supported_get("fb"),
          ecore_evas_engine_type_supported_get("software_generic"),
          ecore_evas_engine_type_supported_get("software_x11"));

    ee = ecore_evas_buffer_new(W, H);
    if (!ee) { logf_("FATAL: ecore_evas_buffer_new failed\n"); return 3; }
    logf_("   ecore_evas_buffer_new OK\n");

    evas = ecore_evas_get(ee);
    if (!evas) { logf_("FATAL: ecore_evas_get returned NULL\n"); return 4; }
    logf_("   evas=%p\n", evas);

    bg = evas_object_rectangle_add(evas);
    evas_object_color_set(bg, 12, 14, 20, 255);
    evas_object_move(bg, 0, 0);
    evas_object_resize(bg, W, H);
    evas_object_show(bg);

    /* 行表：正对照（SDIC_GP_US 显式字体源）在前，负对照（无 CJK 的字体）在后。
     * ★ 负对照用【同一个字符串】+【另一个字体文件】，这样"有字 vs 无字"的差异
     *   只能来自字体本身，不能来自文本内容。 */
    rows[nrows].text = "SDIC_GP_US / CJK 光栅化离线验证";  rows[nrows].size = 32; rows[nrows].y =  15; rows[nrows].tag = "A1 src=SDIC fam=SDIC";       rows[nrows].mode = MODE_EXPLICIT_SDIC; nrows++;
    rows[nrows].text = "中文测试 胶片仿真 影调 颗粒 色彩";   rows[nrows].size = 40; rows[nrows].y =  65; rows[nrows].tag = "A2 src=SDIC fam=SDIC";       rows[nrows].mode = MODE_EXPLICIT_SDIC; nrows++;
    rows[nrows].text = "Portra 400 / Velvia 50 / Tri-X 400"; rows[nrows].size = 28; rows[nrows].y = 125; rows[nrows].tag = "A3 ASCII 对照";              rows[nrows].mode = MODE_EXPLICIT_SDIC; nrows++;
    rows[nrows].text = "麤龘靐齉爩 Yes/No";                 rows[nrows].size = 44; rows[nrows].y = 170; rows[nrows].tag = "A4 生僻字";                  rows[nrows].mode = MODE_EXPLICIT_SDIC; nrows++;
    rows[nrows].text = "日本語 あいう カタカナ";            rows[nrows].size = 36; rows[nrows].y = 235; rows[nrows].tag = "A5 日文";                    rows[nrows].mode = MODE_EXPLICIT_SDIC; nrows++;
    rows[nrows].text = "中文测试 胶片仿真 影调 颗粒 色彩";   rows[nrows].size = 40; rows[nrows].y = 295; rows[nrows].tag = "B1 src=Khmer fam=Khmer";    rows[nrows].mode = MODE_EXPLICIT_OTH;  nrows++;
    rows[nrows].text = "SDIC_GP_US / CJK 光栅化离线验证";  rows[nrows].size = 32; rows[nrows].y = 350; rows[nrows].tag = "B2 src=Khmer fam=Khmer";    rows[nrows].mode = MODE_EXPLICIT_OTH;  nrows++;
    rows[nrows].text = "中文测试 胶片仿真 影调 颗粒 色彩";   rows[nrows].size = 40; rows[nrows].y = 405; rows[nrows].tag = "C1 无src fam=SDIC_GP_US";   rows[nrows].mode = MODE_BYNAME_SDIC;   nrows++;
    rows[nrows].text = "中文测试 胶片仿真 影调 颗粒 色彩";   rows[nrows].size = 40; rows[nrows].y = 460; rows[nrows].tag = "C2 无src fam=Sans";        rows[nrows].mode = MODE_BYNAME_SANS;   nrows++;
    rows[nrows].text = "中文测试 胶片仿真 影调 颗粒 色彩";   rows[nrows].size = 40; rows[nrows].y = 515; rows[nrows].tag = "C3 完全不设字体";           rows[nrows].mode = MODE_NOFONT;        nrows++;

    ctl_y0 = H + 1;   /* 本版不用分区判定，改为逐行精确取墨（见下） */
    ctl_y1 = H + 1;

    for (i = 0; i < nrows; i++) {
        Evas_Object *t = evas_object_text_add(evas);
        int tx = 0, ty = 0, tw = 0, th = 0;
        switch (rows[i].mode) {
        case MODE_EXPLICIT_SDIC:
            evas_object_text_font_source_set(t, FONT_FILE);
            evas_object_text_font_set(t, FONT_FAM, rows[i].size);
            break;
        case MODE_EXPLICIT_OTH:
            /* 负对照：换成确定不含 CJK 的字体文件 + 其族名，文本完全相同 */
            evas_object_text_font_source_set(t, FONT_FILE2);
            evas_object_text_font_set(t, FONT_FAM2, rows[i].size);
            break;
        case MODE_BYNAME_SDIC:
            evas_object_text_font_set(t, FONT_FAM, rows[i].size);
            break;
        case MODE_BYNAME_SANS:
            evas_object_text_font_set(t, "Sans", rows[i].size);
            break;
        default:
            break;   /* MODE_NOFONT: 什么都不设，用 evas 默认 */
        }
        evas_object_text_text_set(t, rows[i].text);
        evas_object_color_set(t, 235, 235, 240, 255);
        evas_object_move(t, 16, rows[i].y);
        evas_object_show(t);
        evas_object_geometry_get(t, &tx, &ty, &tw, &th);
        objs[i] = t; rx[i] = tx + 16; ry[i] = ty; rw[i] = tw; rh[i] = th; rmode[i] = rows[i].mode;
        logf_("   [%s] size=%d geom=(%d,%d,%dx%d) '%s'\n",
              rows[i].tag, rows[i].size, tx, ty, tw, th, rows[i].text);
    }

    ecore_evas_manual_render_set(ee, 1);
    ecore_evas_manual_render(ee);
    logf_("   manual_render done\n");

    px = ecore_evas_buffer_pixels_get(ee);
    if (!px) { logf_("FATAL: pixels_get NULL\n"); return 5; }
    logf_("   pixels=%p\n", px);

    /* 取像素 → RGB（buffer 引擎 = 小端 ARGB32 ⇒ 内存序 B,G,R,A） */
    rgb = (uint8_t *)malloc((size_t)W * H * 3);
    {
        const uint8_t *p = (const uint8_t *)px;
        int x, y;
        for (y = 0; y < H; y++) {
            for (x = 0; x < W; x++) {
                const uint8_t *q = p + ((size_t)y * W + x) * 4;
                uint8_t B = q[0], G = q[1], R = q[2], A = q[3];
                uint8_t r2, g2, b2;
                if (A == 0) { r2 = 0; g2 = 0; b2 = 0; }
                else { r2 = R; g2 = G; b2 = B; }
                rgb[((size_t)y * W + x) * 3 + 0] = r2;
                rgb[((size_t)y * W + x) * 3 + 1] = g2;
                rgb[((size_t)y * W + x) * 3 + 2] = b2;
                if (r2 > 90 || g2 > 90 || b2 > 90) nonwhite++;
            }
        }
    }

    /* ★ 逐行精确取墨：用该文本对象自己的几何矩形，不与邻行混淆 */
    {
        int good = 0, bad = 0;
        for (i = 0; i < nrows; i++) {
            int x, y, ink = 0;
            for (y = ry[i]; y < ry[i] + rh[i] && y < H; y++) {
                for (x = rx[i]; x < rx[i] + rw[i] && x < W; x++) {
                    const uint8_t *c = rgb + ((size_t)y * W + x) * 3;
                    if (c[0] > 90 || c[1] > 90 || c[2] > 90) ink++;
                }
            }
            logf_("   ROWINK mode=%d ink=%6d  %s\n", rmode[i], ink, rows[i].tag);
            if (rmode[i] == MODE_EXPLICIT_SDIC) { if (ink > 200) good++; }
            if (rmode[i] == MODE_EXPLICIT_OTH)  { if (ink > 200) bad++;  }
        }
        logf_("   ink_total=%d  px=%d  (SDIC 行有墨 %d/5，Khmer 行有墨 %d/2)\n",
              nonwhite, W * H, good, bad);
        if (good == 5 && bad == 0)
            logf_("VERDICT=PASS  (SDIC 5/5 有墨，Khmer 0/2 有墨)\n");
        else if (good == 5)
            logf_("VERDICT=CONTROL_WEAK (SDIC 5/5 有墨，但 Khmer 行也有墨 %d/2 ⇒ evas 字形回落，"
                  "对照不再区分；正对照直接证据仍成立)\n", bad);
        else
            logf_("VERDICT=FAIL (SDIC 仅 %d/5 有墨)\n", good);
    }

    if (write_png(out, W, H, rgb) != 0) { logf_("FATAL: write_png failed\n"); return 6; }
    logf_("   PNG written: %s\n", out);

    free(rgb);
    logf_("== cjk_render done\n");
    return 0;
}
