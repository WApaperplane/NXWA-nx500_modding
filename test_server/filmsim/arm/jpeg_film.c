/*
 * NX-KS2 阶段2A：ARM 胶片引擎骨架
 * 链接相机自带 libjpeg-turbo：读 JPEG -> 3x3 色彩矩阵 -> 写回 JPEG
 * 用法: jpeg_film <in.jpg> <out.jpg> [m00,m01,m02,m10,m11,m12,m20,m21,m22]
 * 默认矩阵 = 暖调 (Portra 风格)
 * 阶段2 之后扩展：配方 JSON / 3D LUT / 颗粒（tint yccMixer）
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <jpeglib.h>

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
    if (argc < 3) {
        fprintf(stderr, "usage: %s <in.jpg> <out.jpg> [matrix 9x]\n", argv[0]);
        return 1;
    }
    double m[3][3] = {{1.06, 0.04, -0.02},
                      {0.01, 1.00, 0.02},
                      {-0.02, 0.05, 0.92}};
    if (argc >= 12) {
        int k = 3;
        for (int i = 0; i < 3; i++)
            for (int j = 0; j < 3; j++)
                m[i][j] = atof(argv[k++]);
    }

    FILE *fin = fopen(argv[1], "rb");
    if (!fin) { perror("open in"); return 1; }

    /* --- 解码 --- */
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

    /* --- 编码 --- */
    FILE *fout = fopen(argv[2], "wb");
    if (!fout) { perror("open out"); jpeg_destroy_decompress(&dinfo); fclose(fin); return 1; }
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

    JSAMPARRAY buf = (*cinfo.mem->alloc_sarray)((j_common_ptr)&cinfo, JPOOL_IMAGE, row_stride, 1);
    while (dinfo.output_scanline < h) {
        jpeg_read_scanlines(&dinfo, buf, 1);
        apply_matrix(buf[0], w, m);
        jpeg_write_scanlines(&cinfo, buf, 1);
    }

    jpeg_finish_compress(&cinfo);
    jpeg_destroy_compress(&cinfo);
    jpeg_finish_decompress(&dinfo);
    jpeg_destroy_decompress(&dinfo);
    fclose(fin);
    fclose(fout);
    printf("[NX-KS2] jpeg_film: %dx%d -> %s (matrix applied)\n", w, h, argv[2]);
    return 0;
}
