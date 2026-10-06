/*
 * NX-KS2 阶段2A：jpeg_film 调试版
 * 每一步写 stderr 日志（重定向进 filmsim.log），用于定位 SIGSEGV 崩点
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <jpeglib.h>

#define DBG(fmt, ...) fprintf(stderr, "[dbg] " fmt "\n", ##__VA_ARGS__)

static void apply_matrix(JSAMPLE *row, int width, const double m[3][3]) {
    for (int x = 0; x < width; x++) {
        unsigned char *p = row + x * 3;
        double r = p[0], g = p[1], b = p[2];
        int nr = (int)(m[0][0]*r + m[0][1]*g + m[0][2]*b + 0.5);
        int ng = (int)(m[1][0]*r + m[1][1]*g + m[1][2]*b + 0.5);
        int nb = (int)(m[2][0]*r + m[2][1]*g + m[2][2]*b + 0.5);
        p[0] = (JSAMPLE)(nr < 0 ? 0 : (nr > 255 ? 255 : nr));
        p[1] = (JSAMPLE)(ng < 0 ? 0 : (ng > 255 ? 255 : ng));
        p[2] = (JSAMPLE)(nb < 0 ? 0 : (nb > 255 ? 255 : nb));
    }
}

int main(int argc, char **argv) {
    DBG("main start argc=%d", argc);
    if (argc < 3) {
        fprintf(stderr, "usage: %s <in.jpg> <out.jpg>\n", argv[0]);
        return 1;
    }
    double m[3][3] = {{1.06, 0.04, -0.02},
                      {0.01, 1.00, 0.02},
                      {-0.02, 0.05, 0.92}};

    DBG("opening %s", argv[1]);
    FILE *fin = fopen(argv[1], "rb");
    if (!fin) { perror("open in"); return 1; }
    DBG("open in ok");

    struct jpeg_decompress_struct dinfo;
    struct jpeg_error_mgr jerr;
    dinfo.err = jpeg_std_error(&jerr);
    DBG("create_decompress");
    jpeg_create_decompress(&dinfo);
    DBG("create ok, stdio_src");
    jpeg_stdio_src(&dinfo, fin);
    DBG("read_header");
    jpeg_read_header(&dinfo, TRUE);
    DBG("header ok, w=%d h=%d", dinfo.image_width, dinfo.image_height);
    dinfo.out_color_space = JCS_RGB;
    DBG("start_decompress");
    jpeg_start_decompress(&dinfo);
    DBG("decompress started, w=%d h=%d comp=%d", dinfo.output_width,
        dinfo.output_height, dinfo.output_components);

    int w = dinfo.output_width, h = dinfo.output_height;
    int row_stride = w * dinfo.output_components;

    DBG("open out %s", argv[2]);
    FILE *fout = fopen(argv[2], "wb");
    if (!fout) { perror("open out"); return 1; }
    struct jpeg_compress_struct cinfo;
    struct jpeg_error_mgr jerr2;
    cinfo.err = jpeg_std_error(&jerr2);
    DBG("create_compress");
    jpeg_create_compress(&cinfo);
    jpeg_stdio_dest(&cinfo, fout);
    cinfo.image_width = w;
    cinfo.image_height = h;
    cinfo.input_components = 3;
    cinfo.in_color_space = JCS_RGB;
    jpeg_set_defaults(&cinfo);
    jpeg_set_quality(&cinfo, 92, TRUE);
    DBG("start_compress");
    jpeg_start_compress(&cinfo, TRUE);

    DBG("alloc sarray");
    JSAMPARRAY buf = (*cinfo.mem->alloc_sarray)((j_common_ptr)&cinfo, JPOOL_IMAGE, row_stride, 1);
    DBG("loop: h=%d", h);
    int line = 0;
    while (dinfo.output_scanline < h) {
        jpeg_read_scanlines(&dinfo, buf, 1);
        apply_matrix(buf[0], w, m);
        jpeg_write_scanlines(&cinfo, buf, 1);
        line++;
        if (line % 100 == 0) DBG("  line %d", line);
    }
    DBG("loop done: %d lines", line);

    jpeg_finish_compress(&cinfo);
    DBG("finish_compress ok");
    jpeg_destroy_compress(&cinfo);
    jpeg_finish_decompress(&dinfo);
    jpeg_destroy_decompress(&dinfo);
    fclose(fin);
    fclose(fout);
    DBG("ALL DONE OK");
    return 0;
}
