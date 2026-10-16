#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extract_slots.py — 从 p7 镜像静态表池提取实体表（U7 输入资产）

静态池（依 lut_slot_catalog_2026-10-16.json）：
  Block A @file 0x8592C0 × 20 槽 ; Block B @file 0x8B9AC0 × 22 槽
  槽步长 0x4D00 (19712B) ; 表体 4913×4 = 19652B ; 尾部至 19712 为填充

分类（只读判定）：empty（全零）/ gray（R==G==B）/ color（真彩色）
产出：<out>/<Blk><idx>_<cls>.bin（19712B 整槽，可直接被 lutpick.sh apply）
并把新表**追加**进 <out>/../manifest.json（供 deploy_luts.py push 使用）
严格 identity 判定不在本工具范围内（见 lut_slot_verify.py）。

用法: python extract_slots.py <p7_image.bin> [--out <dir>] [--limit N]
"""
import argparse
import hashlib
import json
import os

SLOT = 0x4D00
TABLE = 4913 * 4
BLOCKS = [("A", 0x8592C0, 20), ("B", 0x8B9AC0, 22)]


def md5b(b):
    return hashlib.md5(b).hexdigest()


def classify(blk):
    body = blk[:TABLE]
    if not any(body):
        return "empty"
    for i in range(0, TABLE, 4):
        r, g, b = body[i], body[i + 1], body[i + 2]
        if not (r == g == b):
            return "color"
    return "gray"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  "build", "luts"))
    ap.add_argument("--limit", type=int, default=0, help="每类最多提取 N 张（0=不限）")
    a = ap.parse_args()

    data = open(a.image, "rb").read()
    os.makedirs(a.out, exist_ok=True)
    rows, counts, kept = [], {}, {}
    for tag, base, n in BLOCKS:
        for i in range(n):
            off = base + i * SLOT
            blk = data[off:off + SLOT]
            if len(blk) < SLOT:
                print(f"  !! {tag}{i:02d} 越界（0x{off:x}）")
                continue
            cls = classify(blk)
            counts[cls] = counts.get(cls, 0) + 1
            if cls == "empty":
                continue
            if a.limit and kept.get(cls, 0) >= a.limit:
                continue
            kept[cls] = kept.get(cls, 0) + 1
            name = f"{tag}{i:02d}_{cls}"
            dst = os.path.join(a.out, name + ".bin")
            with open(dst, "wb") as fh:
                fh.write(blk)
            rows.append(dict(name=name, src=f"image:{tag}[{i}]@file 0x{off:x}",
                             bin=name + ".bin", md5=md5b(blk), size=len(blk)))
            print(f"  OK  {name + '.bin':26s} file=0x{off:x}  md5={md5b(blk)}")

    print("分类计数: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))

    mfp = os.path.join(os.path.dirname(a.out.rstrip("/\\")), "manifest.json")
    man = {"luts": []}
    if os.path.exists(mfp):
        try:
            man = json.load(open(mfp, encoding="utf-8"))
        except Exception:
            pass
    have = {it.get("name") for it in man.get("luts", [])}
    for r in rows:
        if r["name"] not in have:
            man.setdefault("luts", []).append(
                {k: r[k] for k in ("name", "src", "bin", "md5", "size")})
    os.makedirs(os.path.dirname(mfp), exist_ok=True)
    with open(mfp, "w", encoding="utf-8") as fh:
        json.dump(man, fh, ensure_ascii=False, indent=2)
    print(f"追加 {len(rows)} 表 → {mfp}（manifest 共 {len(man['luts'])} 表）")


if __name__ == "__main__":
    main()
