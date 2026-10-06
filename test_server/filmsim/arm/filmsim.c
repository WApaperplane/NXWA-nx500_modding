/*
 * NX-KS2 阶段2B：完整 ARM 胶片配方引擎
 * 管线：JPEG 读 -> 色彩矩阵 -> 饱和度 -> 曲线 LUT -> 数学颗粒 -> JPEG 写回
 * 算法与 PC 端 engine.py 严格一致（-O0 编译，真机已验证稳定）
 * 用法: filmsim <in.jpg> <out.jpg> [recipe_id]  (默认 portra400)
 * 配方表: recipes_gen.h（由 export_recipes.py 生成）
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <jpeglib.h>
#include "recipes_gen.h"

#define CLAMP255(v) ((v) < 0 ? 0 : ((v) > 255 ? 255 : (v)))

/* 自实现 math（避免链接 libm：zig 生成 glibc libm stub 在沙箱下 AccessDenied） */
static double my_exp(double x) {
    /* 级数展开 e^x，|x|<=4 时 20 项内收敛 */
    double s = 1.0, term = 1.0;
    for (int n = 1; n <= 24; n++) {
        term *= x / n;
        s += term;
        if (term < 1e-13 && term > -1e-13) break;
    }
    return s;
}

/* 高斯噪声：中心极限定理近似（12 个均匀分布和），无需 sin/cos/log/sqrt */
static double gauss_noise(void) {
    double s = 0.0;
    for (int i = 0; i < 12; i++)
        s += rand() / (RAND_MAX + 1.0);
    return s - 6.0;
}

/* ---------------- 色彩矩阵 ---------------- */
static void apply_matrix(JSAMPLE *row, int width, const double m[3][3]) {
    for (int x = 0; x < width; x++) {
        unsigned char *p = row + x * 3;
        double r = p[0], g = p[1], b = p[2];
        p[0] = (JSAMPLE)CLAMP255((int)(m[0][0]*r + m[0][1]*g + m[0][2]*b + 0.5));
        p[1] = (JSAMPLE)CLAMP255((int)(m[1][0]*r + m[1][1]*g + m[1][2]*b + 0.5));
        p[2] = (JSAMPLE)CLAMP255((int)(m[2][0]*r + m[2][1]*g + m[2][2]*b + 0.5));
    }
}

/* ---------------- 饱和度（Pillow ImageEnhance.Color 等价） ---------------- */
static void apply_saturation(JSAMPLE *row, int width, double sat) {
    for (int x = 0; x < width; x++) {
        unsigned char *p = row + x * 3;
        double r = p[0], g = p[1], b = p[2];
        double lum = 0.299*r + 0.587*g + 0.114*b;
        p[0] = (JSAMPLE)CLAMP255((int)(lum + (r - lum)*sat + 0.5));
        p[1] = (JSAMPLE)CLAMP255((int)(lum + (g - lum)*sat + 0.5));
        p[2] = (JSAMPLE)CLAMP255((int)(lum + (b - lum)*sat + 0.5));
    }
}

/* ---------------- 曲线 LUT（与 engine.build_curve_lut 一致） ---------------- */
static void build_curve_lut(unsigned char *lut, double contrast,
                            double lift, double rolloff) {
    double k = 6.0 * contrast;
    if (k < 0.1) k = 0.1;
    for (int i = 0; i < 256; i++) {
        double x = i / 255.0;
        x = (x - 0.5) * contrast + 0.5;
        if (x < 0) x = 0; if (x > 1) x = 1;
        x = 1.0 / (1.0 + my_exp(-k * (x - 0.5)));
        x = x * (1.0 - rolloff) + lift;
        if (x < 0) x = 0; if (x > 1) x = 1;
        lut[i] = (unsigned char)(x * 255.0 + 0.5);
    }
}

/* ---------------- 数学颗粒（高斯噪声 + 盒式模糊 + overlay） ---------------- */
static void blur_noise(unsigned char *n, int w, int h, int k) {
    if (k <= 1) return;
    unsigned char *tmp = (unsigned char *)malloc((size_t)w * h);
    int r = k / 2;
    for (int y = 0; y < h; y++) {
        for (int x = 0; x < w; x++) {
            int s = 0, c = 0;
            for (int dy = -r; dy <= r; dy++) {
                for (int dx = -r; dx <= r; dx++) {
                    int yy = y + dy, xx = x + dx;
                    if (yy >= 0 && yy < h && xx >= 0 && xx < w) { s += n[yy*w+xx]; c++; }
                }
            }
            tmp[y*w+x] = (unsigned char)(s / c);
        }
    }
    memcpy(n, tmp, (size_t)w * h);
    free(tmp);
}

static void apply_grain_all(unsigned char *px, int w, int h, const FilmRecipe *rec) {
    if (rec->grain_intensity <= 0) return;
    double sigma = 6.0 + 45.0 * rec->grain_intensity;
    int k = (int)round((rec->grain_size - 1.0) * 2.8 + 1.0);
    if (k < 1) k = 1;
    if ((k & 1) == 0) k++;

    unsigned char *n = (unsigned char *)malloc((size_t)w * h);
    srand(12345);  /* 固定种子：输出可复现 */
    for (int i = 0; i < w * h; i++) {
        double v = 128.0 + gauss_noise() * sigma;
        n[i] = (unsigned char)CLAMP255((int)v);
    }
    blur_noise(n, w, h, k);

    /* overlay：以图像像素为 base，噪声为 overlay（Pillow ImageChops.overlay 等价） */
    for (int i = 0; i < w * h; i++) {
        int nv = n[i];
        for (int c = 0; c < 3; c++) {
            int b = px[i*3+c];
            int v = (b <= 128) ? (2*b*nv/255) : (255 - 2*(255-b)*(255-nv)/255);
            px[i*3+c] = (unsigned char)v;
        }
    }
    free(n);
}

/* ---------------- 配方查找 ---------------- */
static const FilmRecipe *find_recipe(const char *id) {
    for (int i = 0; i < NUM_RECIPES; i++)
        if (strcmp(RECIPES[i].id, id) == 0)
            return &RECIPES[i];
    return NULL;
}

static void list_recipes(void) {
    for (int i = 0; i < NUM_RECIPES; i++)
        fprintf(stderr, "  %s - %s\n", RECIPES[i].id, RECIPES[i].name);
}

/* ---------------- 主流程 ---------------- */
int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: %s <in.jpg> <out.jpg> [recipe_id]\n", argv[0]);
        list_recipes();
        return 1;
    }
    const char *rid = (argc >= 4) ? argv[3] : "portra400";
    const FilmRecipe *rec = find_recipe(rid);
    if (!rec) {
        fprintf(stderr, "unknown recipe: %s\n", rid);
        list_recipes();
        return 1;
    }

    FILE *fin = fopen(argv[1], "rb");
    if (!fin) { perror("open in"); return 1; }

    /* 解码 */
    struct jpeg_decompress_struct dinfo;
    struct jpeg_error_mgr jerr;
    dinfo.err = jpeg_std_error(&jerr);
    jpeg_create_decompress(&dinfo);
    jpeg_stdio_src(&dinfo, fin);
    jpeg_read_header(&dinfo, TRUE);
    dinfo.out_color_space = JCS_RGB;
    jpeg_start_decompress(&dinfo);

    int w = dinfo.output_width, h = dinfo.output_height;
    int row_stride = w * dinfo.output_components;
    unsigned char *pixels = (unsigned char *)malloc((size_t)w * h * 3);

    unsigned char lut[256];
    build_curve_lut(lut, rec->contrast, rec->shadow_lift, rec->highlight_rolloff);

    JSAMPARRAY buf = (*dinfo.mem->alloc_sarray)((j_common_ptr)&dinfo, JPOOL_IMAGE,
                                                row_stride, 1);
    while (dinfo.output_scanline < h) {
        jpeg_read_scanlines(&dinfo, buf, 1);
        apply_matrix(buf[0], w, rec->matrix);
        apply_saturation(buf[0], w, rec->saturation);
        for (int x = 0; x < row_stride; x++)
            buf[0][x] = lut[buf[0][x]];
        memcpy(pixels + (size_t)(dinfo.output_scanline - 1) * row_stride,
               buf[0], (size_t)row_stride);
    }

    /* 颗粒（整幅） */
    apply_grain_all(pixels, w, h, rec);

    jpeg_finish_decompress(&dinfo);
    jpeg_destroy_decompress(&dinfo);
    fclose(fin);

    /* 编码 */
    FILE *fout = fopen(argv[2], "wb");
    if (!fout) { perror("open out"); free(pixels); return 1; }
    struct jpeg_compress_struct cinfo;
    struct jpeg_error_mgr jerr2;
    cinfo.err = jpeg_std_error(&jerr2);
    jpeg_create_compress(&cinfo);
    jpeg_stdio_dest(&cinfo, fout);
    cinfo.image_width = w;
    cinfo.image_height = h;
    cinfo.input_components = 3;
    cinfo.in_color_space = JCS_RGB;
    jpeg_set_defaults(&cinfo);
    jpeg_set_quality(&cinfo, 92, TRUE);
    jpeg_start_compress(&cinfo, TRUE);

    JSAMPROW rowptr = pixels;
    while (cinfo.next_scanline < h) {
        jpeg_write_scanlines(&cinfo, &rowptr, 1);
        rowptr += row_stride;
    }
    jpeg_finish_compress(&cinfo);
    jpeg_destroy_compress(&cinfo);
    fclose(fout);
    free(pixels);

    printf("[NX-KS2] filmsim: %dx%d -> %s recipe=%s (%s)\n",
           w, h, argv[2], rec->id, rec->name);
    return 0;
}
