#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extract_a2.py —— 从 p7_a2.bin 提取 A2 测试区段（供 a2_harness.s .incbin）。

区段：
  seg_norm.bin    0x51090 + 0x350  归一化器全链（含 A2 改扩块前的原始 A1 域检查）
  seg_11500.bin   0x11500 + 0x90   A1 块（改扩版 @0x11504）+ A2 块 @0x11530
  seg_wrap.bin    0x4cc00 + 0x200  外部写包装 0x4ccf4 区 + 字面量池

自检（关键字节）：
  0x510b0 = 13 01 ff ea（重定向）
  0x11508 = 0b 00 53 e3（cmp #0xB——改扩）
  0x4cd30 = fe 11 ff eb（bl 0x11530——改道）
  0x11530 = e9 2d 40 70（A2 块：push {r4,r5,r6,lr}）

用法: python extract_a2.py <p7_a2.bin> <outdir>
"""
import hashlib
import os
import sys

SEGS = [
    ("seg_norm.bin", 0x51090, 0x350),
    ("seg_11500.bin", 0x11500, 0x90),
    ("seg_wrap.bin", 0x4cc00, 0x200),
]
CHECKS = [
    (0x510B0, "1301ffea", "重定向"),
    (0x11508, "0b0053e3", "A1 块改扩（cmp #0xB）"),
    (0x4CD30, "fe11ffeb", "改道（bl 0x80011530）"),
    (0x11530, "70402de9", "A2 块首指令（push，LE）"),
]
fails = []


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    src, outdir = sys.argv[1], sys.argv[2]
    data = open(src, "rb").read()
    print("源: %s（%d B, md5 %s）" % (src, len(data), hashlib.md5(data).hexdigest()))
    os.makedirs(outdir, exist_ok=True)
    for name, off, ln in SEGS:
        seg = data[off:off + ln]
        open(os.path.join(outdir, name), "wb").write(seg)
        print("[OK  ] %s = [%#x, +%#x) %d B" % (name, off, ln, len(seg)))
    print("-- 关键字节自检 --")
    for off, expect, why in CHECKS:
        got = data[off:off + len(expect) // 2].hex()
        ok = got == expect
        print("[%s] %#x == %s（%s）实 %s" % ("OK  " if ok else "FAIL", off, expect, why, got))
        if not ok:
            fails.append(off)
    print("\n==== %s ====" % ("提取自检 PASS" if not fails else "提取自检 FAIL"))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
