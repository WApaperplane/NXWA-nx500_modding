#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_lut_compare.py —— NX500 3D LUT 离线渲染对比（测试图案 → 过表 → 拼图 PNG）

用途：把 p7 镜像内的内置 3D LUT 应用到一张合成测试图（天空高光/中灰墙/色块/暗部/灰阶楔），
逐像素做三线性插值（17³ 非均匀格点），输出多面板对比 PNG —— 用于判读
"写某表 → 画面应呈现什么" vs "实机观察"，裁决链路忠实性。

用法：
  python render_lut_compare.py <image.bin> <out.png> [VA:label ...]
  例：python render_lut_compare.py chunk-05.bin cmp.png 0x8AAFC0:id1 0x897BC0:ID0 0x892EC0:std
  （不带 VA 时只输出原始测试图）
"""
import struct
import sys
import zlib

GRID = [min(i * 16, 255) for i in range(17)]  # 0,16,...,240,255


def load_tab(data, va):
    off = va
    tab = []
    for i in range(4913):
        r, g, b, pad = data[off + i * 4:off + i * 4 + 4]
        tab.append((r, g, b))
    return tab


def norm(v):
    for i in range(16):
        if v <= GRID[i + 1]:
            span = GRID[i + 1] - GRID[i]
            f = (v - GRID[i]) / span if span else 0.0
            return i, i + 1, f
    return 15, 16, 1.0


def apply_lut(tab, r, g, b):
    ri, ri2, rf = norm(r)
    gi, gi2, gf = norm(g)
    bi, bi2, bf = norm(b)

    def T(i, j, k):
        return tab[(k * 17 + j) * 17 + i]

    def lerp(a, b_, f):
        return a + (b_ - a) * f

    out = []
    for c in range(3):
        c000 = T(ri, gi, bi)[c]; c100 = T(ri2, gi, bi)[c]
        c010 = T(ri, gi2, bi)[c]; c110 = T(ri2, gi2, bi)[c]
        c001 = T(ri, gi, bi2)[c]; c101 = T(ri2, gi, bi2)[c]
        c011 = T(ri, gi2, bi2)[c]; c111 = T(ri2, gi2, bi2)[c]
        c00 = lerp(c000, c100, rf); c10 = lerp(c010, c110, rf)
        c01 = lerp(c001, c101, rf); c11 = lerp(c011, c111, rf)
        c0 = lerp(c00, c10, gf); c1 = lerp(c01, c11, gf)
        out.append(int(round(lerp(c0, c1, bf))))
    return tuple(max(0, min(255, x)) for x in out)


def make_test_image(W=256, H=224):
    px = [[(0, 0, 0)] * W for _ in range(H)]
    # 天空渐变（0-55）：蓝 -> 白（高光区）
    for y in range(56):
        t = y / 55
        for x in range(W):
            px[y][x] = (int(140 + 115 * t), int(170 + 85 * t), int(220 + 35 * t))
    # 中灰墙（56-139）
    for y in range(56, 140):
        for x in range(W):
            px[y][x] = (200, 198, 195)
    # 中灰墙上的色块：皮肤/红/绿/蓝/黄
    blocks = [(20, 70, 40, 40, (224, 178, 148)),
              (70, 70, 40, 40, (200, 60, 60)),
              (120, 70, 40, 40, (70, 160, 80)),
              (170, 70, 40, 40, (70, 90, 200)),
              (210, 70, 36, 40, (230, 200, 90))]
    for bx, by, bw, bh, c in blocks:
        for y in range(by, by + bh):
            for x in range(bx, bx + bw):
                px[y][x] = c
    # 暗部条（140-169）：深灰/黑/暗红/暗绿/暗蓝
    darks = [(20, (60, 58, 56)), (60, (30, 28, 26)), (100, (10, 10, 10)),
             (140, (80, 40, 40)), (180, (40, 80, 40)), (220, (40, 40, 80))]
    for x0, c in darks:
        for y in range(140, 170):
            for x in range(x0, x0 + 36):
                px[y][x] = c
    # 灰阶楔（170-223）：0..255 水平渐变
    for y in range(170, 224):
        for x in range(W):
            v = int(round(x / 255 * 255))
            px[y][x] = (v, v, v)
    return W, H, px


def write_png(path, W, H, rows):
    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        c += struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
        return c

    raw = b''
    for row in rows:
        raw += b'\x00' + bytes([v for p in row for v in p])
    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(raw, 9))
    png += chunk(b'IEND', b'')
    open(path, 'wb').write(png)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    binpath, outpath = sys.argv[1], sys.argv[2]
    data = open(binpath, 'rb').read()
    W, H, base = make_test_image()

    panels = [(None, base)]
    for spec in sys.argv[3:]:
        va_s = spec.split(':')[0]
        va = int(va_s, 16)
        tab = load_tab(data, va)
        out = [[apply_lut(tab, *base[y][x]) for x in range(W)] for y in range(H)]
        panels.append((spec, out))
        print(f'  rendered {spec}')

    # 横向拼接，2px 白色分隔
    TW = W * len(panels) + 2 * (len(panels) - 1)
    rows = []
    for y in range(H):
        row = []
        for i, (_, img) in enumerate(panels):
            row.extend(img[y])
            if i < len(panels) - 1:
                row.extend([(255, 255, 255)] * 2)
        rows.append(row)
    write_png(outpath, TW, H, rows)
    print(f'  -> {outpath}  ({TW}x{H})  面板顺序: 原图 | ' +
          ' | '.join(s for s, _ in panels[1:]))


if __name__ == '__main__':
    main()
