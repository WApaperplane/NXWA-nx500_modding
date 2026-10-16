#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
p7_pool_refs.py — p7 表池地址「引用点」全量搜索（T4 补证工具 · 2026-10-16）

目标（GOALS T4）：为「源表 → 复制/生成 → 运行时池 → 装载」映射提供**带地址的**证据。
方法：p7 flat 镜像上搜索目标地址的所有构造/引用形态（单遍扫描 + 编码字典）：
  A. 字面量池（4 字节小端常量）
  B. movw Rd,#lo16 + movt Rd,#hi16（成对，≤MAXGAP 字节）
  C. mov Rd,#imm12(rot) + movt Rd,#hi16（p7 常用写法）

地址集：运行时池（View 4 + Still 静态 6 + Still BV 12，去重 18）+ MCB 4；
        镜像内静态池 42 槽（Block A 20 + Block B 22）。

用法: python p7_pool_refs.py <p7_image.bin> [--group runtime|static|all] [--json out.json]
"""
import argparse
import array
import json
import struct

MASK = 0xFFFFFFFF
STATIC_A = 0x808592C0
STATIC_B = 0x808B9AC0
SLOT = 0x4D00
MAXGAP = 16          # movw 与 movt 之间的最大字节距离

RUNTIME = {
    "view_std": 0x810FD100, "view_bw": 0x81101E00, "view_film": 0x81106B00, "view_skin": 0x81115200,
    "still_s1": 0x81119F00, "still_s3": 0x8111EC00, "still_s4": 0x8110B800, "still_s6": 0x81110500,
    "bv_1": 0x8116C000, "bv_2": 0x81175A00, "bv_3": 0x81167300, "bv_4": 0x81170D00,
    "bv_5": 0x81184100, "bv_7": 0x81188E00, "bv_9": 0x8115D900, "bv_10": 0x8117A700,
    "bv_11": 0x81162600, "bv_12": 0x8117F400,
    "mcb_1": 0x813D8800, "mcb_2": 0x813DD500, "mcb_3": 0x813E2200, "mcb_4": 0x813E6F00,
}


def enc_movw(rd, imm16):
    return (0xE3000000 | (((imm16 >> 12) & 0xF) << 16) | (rd << 12) | (imm16 & 0xFFF)) & MASK


def enc_movt(rd, imm16):
    return (0xE3400000 | (((imm16 >> 12) & 0xF) << 16) | (rd << 12) | (imm16 & 0xFFF)) & MASK


def mov_rot_variants(rd, val):
    out = []
    v = val & MASK
    for rot in range(16):
        sh = 2 * rot
        if sh == 0:
            if v <= 0xFF:
                out.append((0xE3A00000 | (rd << 12) | v) & MASK)
        else:
            imm8 = ((v << sh) | (v >> (32 - sh))) & MASK
            if imm8 <= 0xFF:
                out.append((0xE3A00000 | (rot << 8) | (rd << 12) | imm8) & MASK)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--group", default="all", choices=["runtime", "static", "all"])
    ap.add_argument("--json", dest="json_out", default=None)
    ap.add_argument("--verbose", action="store_true", help="附带显示未配对的单条指令命中（多噪声）")
    a = ap.parse_args()
    d = open(a.image, "rb").read()
    print(f"镜像: {a.image} ({len(d)}B)  VA = off + 0x80000000")

    targets = {}
    if a.group in ("runtime", "all"):
        targets.update({f"RT:{k}": v for k, v in RUNTIME.items()})
    if a.group in ("static", "all"):
        for i in range(20):
            targets[f"SA{i:02d}"] = STATIC_A + i * SLOT
        for i in range(22):
            targets[f"SB{i:02d}"] = STATIC_B + i * SLOT

    # ---- 构建编码字典：low28 -> (kind, name, rd) ----
    enc2key = {}
    for name, va in targets.items():
        lo, hi = va & 0xFFFF, (va >> 16) & 0xFFFF
        for rd in range(13):
            for kind, e in (("movw", enc_movw(rd, lo)), ("movt", enc_movt(rd, hi))):
                enc2key.setdefault(e & 0x0FFFFFFF, []).append((kind, name, rd))
            for e in mov_rot_variants(rd, lo):
                enc2key.setdefault(e & 0x0FFFFFFF, []).append(("mov", name, rd))

    # ---- 单遍扫描 ----
    n = len(d) // 4
    words = array.array("I")
    words.frombytes(d[:n * 4])
    hits = []          # (off, kind, name, rd)
    for i, w in enumerate(words):
        k = w & 0x0FFFFFFF
        v = enc2key.get(k)
        if v:
            for kind, name, rd in v:
                hits.append((i * 4, kind, name, rd))

    # ---- 字面量 ----
    lits = []
    for name, va in targets.items():
        pat = struct.pack("<I", va)
        i = d.find(pat)
        while i != -1:
            lits.append((i, name))
            i = d.find(pat, i + 1)
    print(f"扫描完成：指令形态命中 {len(hits)} 处；字面量命中 {len(lits)} 处")

    # ---- 分组与配对 ----
    by_name = {}
    for off, kind, name, rd in hits:
        by_name.setdefault(name, []).append((off, kind, rd))
    rows = []
    for name in sorted(targets, key=lambda x: targets[x]):
        items = by_name.get(name, [])
        pair = []
        for off, kind, rd in items:
            if kind in ("movw", "mov"):
                for o2, k2, r2 in items:
                    if k2 == "movt" and r2 == rd and 0 < o2 - off <= MAXGAP:
                        pair.append((off, o2, rd, kind))
        lits_n = [(o, nm) for o, nm in lits if nm == name]
        if items or lits_n:
            va = targets[name]
            print(f"\n=== {name}  VA {va:#010x} ===  字面量 {len(lits_n)} / 配对 {len(pair)}"
                  + (f" / 单条指令 {len(items)}" if a.verbose else ""))
            for o, nm in lits_n:
                print(f"   [literal] off {o:#08x}  VA {o + 0x80000000:#010x}")
            for off, o2, rd, kind in pair:
                print(f"   ★[{kind}+movt] r{rd}  off {off:#08x}/{o2:#08x}  "
                      f"VA {off + 0x80000000:#010x}")
            if a.verbose:
                for off, kind, rd in items:
                    print(f"   [{kind:4}] r{rd:<2} off {off:#08x}  VA {off + 0x80000000:#010x}")
            rows.append(dict(name=name, va=hex(va), instr=len(items), literal=len(lits_n),
                             pairs=[[hex(p[0]), hex(p[1]), p[2], p[3]] for p in pair],
                             literal_offs=[hex(o) for o, _ in lits_n],
                             instr_offs=[[hex(o), k, r] for o, k, r in items]))

    print(f"\n== 汇总：{len(rows)}/{len(targets)} 个地址有引用（指令或字面量）==")
    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as f:
            json.dump(dict(image=a.image, group=a.group, refs=rows), f, ensure_ascii=False, indent=1)
        print(f"json -> {a.json_out}")


if __name__ == "__main__":
    main()
