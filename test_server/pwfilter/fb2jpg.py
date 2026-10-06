#!/usr/bin/env python3
# ============================================================
# fb2jpg.py - 把 NX500 /dev/fb0 dump 的 raw 帧转成可看的图
#
# 背景: fb-probe.sh 抓的是 LCD 实际显示像素, raw 无格式头。
#       本脚本按已知 w x h x BPP 还原成 PNG, 顺便输出帧间差分
#       (用来判断 liveview 是否真的在刷新)。
#
# 用法:
#   python fb2jpg.py in.raw 1024 768 32 out.png     # BGRA/RGBA
#   python fb2jpg.py in.raw 1280 720 16 out.png     # RGB565
#   python fb2jpg.py --diff a.raw b.raw 1024 768 32 out.png
#
# NX500 屏幕实际分辨率: 翻转屏 1040x608 / 常规屏 800x600 之类,
# 具体以 fb-probe.sh check 读到的 virtual_size 为准。
# ============================================================
import sys
import struct


def load(path, w, h, bpp):
    with open(path, "rb") as f:
        data = f.read()
    need = w * h * bpp // 8
    if len(data) < need:
        print(f"[warn] 文件只有 {len(data)} 字节, 不足 {need} 字节, 按实际数据处理")
        h = len(data) // (w * bpp // 8)
        if h == 0:
            raise SystemExit("数据量不足一帧")
        need = w * h * bpp // 8
        data = data[:need]
    return data, w, h


def to_rgb(data, w, h, bpp, layout):
    """layout: 'BGRA' / 'RGBA' / 'RGB565'"""
    px = bytearray(w * h * 3)
    if bpp == 32:
        if layout == "BGRA":
            # B G R A
            px[0::3] = data[2::4]
            px[1::3] = data[1::4]
            px[2::3] = data[0::4]
        else:
            # R G B A
            px[0::3] = data[0::4]
            px[1::3] = data[1::4]
            px[2::3] = data[2::4]
    elif bpp == 16:
        n = w * h
        for i in range(n):
            v = data[2 * i] | (data[2 * i + 1] << 8)
            r = (v >> 11) & 0x1F
            g = (v >> 5) & 0x3F
            b = v & 0x1F
            px[3 * i] = r << 3
            px[3 * i + 1] = g << 2
            px[3 * i + 2] = b << 3
    elif bpp == 24:
        px[0::3] = data[0::3]
        px[1::3] = data[1::3]
        px[2::3] = data[2::3]
    else:
        raise SystemExit(f"未支持的 bpp: {bpp}")
    return bytes(px)


def write_png(path, w, h, rgb):
    """不依赖第三方库的最小 PNG 写入器"""
    import zlib
    raw = b"".join(b"\x00" + rgb[y * w * 3:(y + 1) * w * 3] for y in range(h))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 6))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def diff_stats(a, b):
    """返回 (变化字节数, 变化比例, 最大单通道差)"""
    n = min(len(a), len(b))
    changed = 0
    mx = 0
    for i in range(n):
        d = a[i] - b[i]
        if d:
            changed += 1
            ad = d if d > 0 else -d
            if ad > mx:
                mx = ad
    return changed, changed / n if n else 0, mx


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    if args[0] == "--diff":
        a, b, w, h, bpp, out = args[1], args[2], int(args[3]), int(args[4]), int(args[5]), args[6]
        da, _, _ = load(a, w, h, bpp)
        db, _, _ = load(b, w, h, bpp)
        changed, ratio, mx = diff_stats(da, db)
        print(f"变化字节: {changed} / {min(len(da), len(db))}  ({ratio*100:.2f}%)  最大差值: {mx}")
        if ratio < 0.0001:
            print("→ 两帧几乎完全相同, liveview 没有在刷新")
        elif ratio < 0.01:
            print("→ 变化很小, 可能是画面基本静止")
        else:
            print("→ 画面有明显变化, liveview 在刷新 (正常)")
        return

    src, w, h, bpp, out = args[0], int(args[1]), int(args[2]), int(args[3]), args[4]
    layout = args[5].upper() if len(args) > 5 else ("BGRA" if bpp == 32 else "RGB565")

    data, w, h = load(src, w, h, bpp)
    print(f"读取 {src}: {w}x{h} @{bpp}bpp ({layout}) = {len(data)} 字节")
    rgb = to_rgb(data, w, h, bpp, layout)
    n = write_png(out, w, h, rgb)
    print(f"写出 {out}: {n} 字节")


if __name__ == "__main__":
    main()