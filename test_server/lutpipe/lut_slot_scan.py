#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lut_slot_scan.py — p7 镜像内静态 3D LUT 表池「槽目录」扫描（C1 输入资产）

依据：3DLUT_TABLE_FORMAT_2026-10-08
  表 = 4913 项 × 4B {R,G,B,pad=0}，槽步长 0x4D00（19712B）；
  尾部指纹 = 「末项 ×3 + 48×0x00」。

用法: python lut_slot_scan.py <p7_image.bin> [--json out.json]
产出：42 槽（Block A 20 + Block B 22）的逐槽特征表（E0/diag8/指纹/灰度/类型猜测）。
"""
import argparse
import json
import os

SLOT = 0x4D00
TABLE = 4913 * 4           # 19652
BLOCKS = [("A", 0x808592C0, 20), ("B", 0x808B9AC0, 22)]
KNOWN = {(21, 0, 13): "标准(已知)",
         (0, 0, 0): "黑点0（**非**identity——严格比对见 lut_slot_verify.py）"}


def item(blk, idx):
    o = idx * 4
    return (blk[o], blk[o + 1], blk[o + 2])


def guess_type(e0, is_gray, is_id):
    if e0 in KNOWN:
        return KNOWN[e0]
    if is_id:
        # 注意：黑点为零 ≠ identity（2026-10-16 修正；严格 identity 全池为 0）
        return f"黑点0（非identity；E0={e0}）"
    if is_gray:
        return f"灰阶类（E0={e0}）"
    if e0[0] == e0[1] and e0[2] != e0[0]:
        return f"蓝影lift?（E0={e0}）"
    return f"其他（E0={e0}）"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--json", dest="json_out", default=None)
    a = ap.parse_args()

    d = open(a.image, "rb").read()
    print(f"图像: {a.image}  ({len(d)}B)")
    print(f"假设: VA = file_offset + 0x80000000；槽步长 0x{SLOT:X}；表 {TABLE}B")
    print()
    print(f"{'块':<3}{'#':<4}{'VA':<12}{'E0(R,G,B)':<14}{'diag8':<14}{'指纹':<6}{'pad零':<7}{'灰度':<6}类型")
    print("-" * 92)

    rows = []
    for name, base_va, n in BLOCKS:
        for i in range(n):
            va = base_va + i * SLOT
            off = va - 0x80000000
            blk = d[off:off + TABLE]
            if len(blk) < TABLE:
                print(f"{name:<3}{i:<4}{va:#x}  <超界>")
                continue
            e0 = item(blk, 0)
            e8 = item(blk, ((8 * 17 + 8) * 17 + 8))
            eL4 = blk[4912 * 4:4912 * 4 + 4]          # 末项 4 字节（含 pad）
            tail = d[off + TABLE: off + TABLE + 60]
            fp_ok = tail[:12] == bytes(eL4) * 3 and tail[12:] == b"\x00" * 48
            pad_ok = all(blk[j * 4 + 3] == 0 for j in range(0, 4913, 11))
            is_gray = all(len(set(item(blk, j))) == 1 for j in range(0, 4913, 53))
            is_id = is_gray and e0 == (0, 0, 0)
            t = guess_type(e0, is_gray, is_id)
            print(f"{name:<3}{i:<4}{va:#x}    {str(e0):<14}{str(e8):<14}"
                  f"{'OK' if fp_ok else 'BAD':<6}{'OK' if pad_ok else 'BAD':<7}"
                  f"{'是' if is_gray else '否':<6}{t}")
            rows.append(dict(block=name, idx=i, va=hex(va), file_off=hex(off),
                             e0=e0, e8=e8, tail_item=tuple(eL4), fingerprint_ok=fp_ok,
                             pad_zero_ok=pad_ok, is_gray=is_gray, guess=t))

    n_std = sum(1 for r in rows if r["guess"].startswith("标准"))
    n_id = sum(1 for r in rows if r["e0"] == (0, 0, 0))
    print("-" * 92)
    print(f"合计 {len(rows)} 槽；标准类 {n_std}；E0=(0,0,0)（黑点0，**非 identity**）{n_id}；"
          f"指纹异常 {sum(1 for r in rows if not r['fingerprint_ok'])}")

    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as f:
            json.dump(dict(image=a.image, image_size=len(d), slot=hex(SLOT),
                           table_bytes=TABLE, slots=rows), f,
                      ensure_ascii=False, indent=1)
        print(f"json -> {a.json_out}")


if __name__ == "__main__":
    main()
