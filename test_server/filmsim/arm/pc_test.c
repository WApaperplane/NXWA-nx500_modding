/* pc_test.c - PC 端算法验证工具（PPM P6 输入输出，不依赖 libjpeg）
 * 用法: pc_test <in.ppm> <out.ppm> <recipe_id>
 * 对比对象：engine.py（Pillow）——同一配方同一输入，输出像素应接近 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "filmsim_core.h"

static unsigned char *load_ppm(const char *path, int *w, int *h) {
    FILE *f = fopen(path, "rb");
    if (!f) { perror("open in"); return NULL; }
    char magic[4] = {0};
    if (fscanf(f, "%3s", magic) != 1 || strcmp(magic, "P6") != 0) {
        fprintf(stderr, "not P6 ppm\n"); fclose(f); return NULL;
    }
    if (fscanf(f, "%d %d", w, h) != 2) { fclose(f); return NULL; }
    int maxv;
    if (fscanf(f, "%d", &maxv) != 1 || maxv != 255) { fclose(f); return NULL; }
    fgetc(f); /* 单个空白符 */
    size_t n = (size_t)(*w) * (*h) * 3;
    unsigned char *rgb = (unsigned char *)malloc(n);
    if (!rgb || fread(rgb, 1, n, f) != n) { free(rgb); fclose(f); return NULL; }
    fclose(f);
    return rgb;
}

static int save_ppm(const char *path, unsigned char *rgb, int w, int h) {
    FILE *f = fopen(path, "wb");
    if (!f) return 1;
    fprintf(f, "P6\n%d %d\n255\n", w, h);
    fwrite(rgb, 1, (size_t)w * h * 3, f);
    fclose(f);
    return 0;
}

int main(int argc, char **argv) {
    if (argc < 4) {
        fprintf(stderr, "usage: %s <in.ppm> <out.ppm> <recipe_id>\n", argv[0]);
        return 1;
    }
    const FilmRecipe *r = filmsim_find(argv[3]);
    if (!r) { fprintf(stderr, "unknown recipe\n"); return 1; }
    int w = 0, h = 0;
    unsigned char *rgb = load_ppm(argv[1], &w, &h);
    if (!rgb) return 1;
    filmsim_apply(rgb, w, h, r);
    int rc = save_ppm(argv[2], rgb, w, h);
    free(rgb);
    fprintf(stderr, "pc_test: %s %dx%d recipe=%s -> %s (rc=%d)\n",
            argv[1], w, h, r->id, argv[2], rc);
    return rc;
}
