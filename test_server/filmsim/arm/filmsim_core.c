/* filmsim_core.c - 胶片仿真核心算法（纯 C，不依赖 libjpeg，可 PC/ARM 双编译）
 * 移植自 engine.py：矩阵 -> 饱和度 -> 曲线 LUT -> 颗粒
 * 注意：NX500 真机必须 -O0 编译（-O1/-O2 会段错误） */
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include "filmsim_core.h"

static inline int clip255(int v) {
    return v < 0 ? 0 : (v > 255 ? 255 : v);
}

/* ---------------- 伪随机（颗粒用） ---------------- */
static unsigned int s_seed = 0x9E3779B9u;

static unsigned int xs_rand(void) {
    unsigned int x = s_seed;
    x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    s_seed = x;
    return x;
}

/* 近似标准正态（12 个均匀值中心极限，[-6,6]） */
static double gauss01(void) {
    double s = 0.0;
    for (int i = 0; i < 12; i++)
        s += (double)(xs_rand() & 0xFFFF) / 65535.0;
    return s - 6.0;
}

/* ---------------- 色彩矩阵 ---------------- */
static void apply_matrix(unsigned char *rgb, int n, const double m[3][3]) {
    for (int i = 0; i < n; i++) {
        unsigned char *p = rgb + i * 3;
        double r = p[0], g = p[1], b = p[2];
        int nr = (int)floor(m[0][0]*r + m[0][1]*g + m[0][2]*b + 0.5);
        int ng = (int)floor(m[1][0]*r + m[1][1]*g + m[1][2]*b + 0.5);
        int nb = (int)floor(m[2][0]*r + m[2][1]*g + m[2][2]*b + 0.5);
        p[0] = (unsigned char)clip255(nr);
        p[1] = (unsigned char)clip255(ng);
        p[2] = (unsigned char)clip255(nb);
    }
}

/* ---------------- 饱和度 ---------------- */
static void apply_saturation(unsigned char *rgb, int n, double sat) {
    if (fabs(sat - 1.0) < 1e-6)
        return;
    for (int i = 0; i < n; i++) {
        unsigned char *p = rgb + i * 3;
        double r = p[0], g = p[1], b = p[2];
        double gray = 0.299*r + 0.587*g + 0.114*b;
        p[0] = (unsigned char)clip255((int)floor(gray + (r - gray)*sat + 0.5));
        p[1] = (unsigned char)clip255((int)floor(gray + (g - gray)*sat + 0.5));
        p[2] = (unsigned char)clip255((int)floor(gray + (b - gray)*sat + 0.5));
    }
}

/* ---------------- 曲线 LUT ---------------- */
static void build_curve_lut(unsigned char lut[256], double contrast,
                            double lift, double roll) {
    double k = 6.0 * contrast;
    if (k < 0.1) k = 0.1;
    for (int i = 0; i < 256; i++) {
        double x = i / 255.0;
        x = (x - 0.5) * contrast + 0.5;
        if (x < 0.0) x = 0.0; else if (x > 1.0) x = 1.0;
        x = 1.0 / (1.0 + exp(-k * (x - 0.5)));
        x = x * (1.0 - roll) + lift;
        if (x < 0.0) x = 0.0; else if (x > 1.0) x = 1.0;
        lut[i] = (unsigned char)(int)floor(x * 255.0 + 0.5);
    }
}

static void apply_lut(unsigned char *rgb, int n, const unsigned char lut[256]) {
    for (int i = 0; i < n * 3; i++)
        rgb[i] = lut[rgb[i]];
}

/* ---------------- 颗粒 ---------------- */
static unsigned char overlay_px(int a, int b) {
    /* a=底, b=噪声(0-255, 128 中性) */
    if (b < 128)
        return (unsigned char)(2 * a * b / 255);
    return (unsigned char)(255 - 2 * (255 - a) * (255 - b) / 255);
}

static void apply_grain(unsigned char *rgb, int w, int h, int grain_mono,
                        double intensity, double size) {
    if (intensity <= 0.0)
        return;
    double sigma = 6.0 + 45.0 * intensity;
    int nw = w, nh = h;
    unsigned char *noise = NULL;

    if (size > 1.0) {
        /* 粒度：先生成缩小噪声图，再放大 */
        nw = (int)(w / size); if (nw < 1) nw = 1;
        nh = (int)(h / size); if (nh < 1) nh = 1;
    }
    noise = (unsigned char *)malloc((size_t)nw * nh);
    if (!noise) return;
    for (int i = 0; i < nw * nh; i++) {
        double v = gauss01() * sigma;
        int iv = (int)floor(v + 128.0);
        noise[i] = (unsigned char)clip255(iv);
    }

    for (int y = 0; y < h; y++) {
        unsigned char *row = rgb + (size_t)y * w * 3;
        for (int x = 0; x < w; x++) {
            /* 从噪声小图取样（最近邻，放大=块状颗粒） */
            int sx = nw == w ? x : (x * nw / w);
            int sy = nh == h ? y : (y * nh / h);
            unsigned char ny = noise[(size_t)sy * nw + sx];
            unsigned char *p = row + (size_t)x * 3;
            if (grain_mono) {
                p[0] = overlay_px(p[0], ny);
                p[1] = overlay_px(p[1], ny);
                p[2] = overlay_px(p[2], ny);
            } else {
                /* 彩色颗粒：各通道独立噪声 */
                unsigned char nr = noise[(size_t)sy * nw + sx];
                unsigned char ng = noise[(size_t)sy * nw + ((sx * 7 + 3) % nw)];
                unsigned char nb = noise[(size_t)((sy * 5 + 1) % nh) * nw + ((sx * 3 + 5) % nw)];
                p[0] = overlay_px(p[0], nr);
                p[1] = overlay_px(p[1], ng);
                p[2] = overlay_px(p[2], nb);
            }
        }
    }
    free(noise);
}

/* ---------------- 入口 ---------------- */
void filmsim_apply(unsigned char *rgb, int w, int h, const FilmRecipe *r) {
    int n = w * h;
    apply_matrix(rgb, n, r->matrix);
    apply_saturation(rgb, n, r->saturation);
    unsigned char lut[256];
    build_curve_lut(lut, r->contrast, r->shadow_lift, r->highlight_rolloff);
    apply_lut(rgb, n, lut);
    apply_grain(rgb, w, h, r->grain_mono, r->grain_intensity, r->grain_size);
}

const FilmRecipe *filmsim_find(const char *id) {
    for (int i = 0; i < g_recipe_count; i++)
        if (strcmp(g_recipes[i].id, id) == 0)
            return &g_recipes[i];
    return NULL;
}
