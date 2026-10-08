#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""g5p3_iqr_epmc_map.py —— G5-3 关联表生成器（C14：21 槽 ISP 参数语义映射）

输入（全部已在手，纯离机）:
  raw8/gates/u1/iqr_dump.txt            st cap iqr 184 ID 值 dump（上机产物）
  raw8/gates/u1/epmc_0_1728_nz_0x1300.log  EP 0x20821300/1700 区非零扫描（上机产物）

静态依据（本轮从 53_all_pseudocode.c 解出）:
  FUN_004b6894  A 池写入器  base=0x20821300  slot 0..20 stride 0x100 ch +0x00/+0x80
  FUN_004b6b98  B 池写入器  base=0x20821700  同构
  FUN_004ba6a8  提交 = *(u32*)0x20821044 = 1<<(slot+4)   ← 修正记忆里的 0x20820044
  每通道写 +0x00..0x24 九个字（+0x0c/+0x10 读改写，+0x10 强制 |0x30）
  槽尾 +0xfc 为初始化器写的版本戳（A 区 0x13061809 / B 区 0x13060516），写入器不碰

产出:
  raw8/gates/u1/iqr_epmc_map.tsv   关联表（G5-3 验收物）
  stdout 摘要（匹配统计 + 锚点）
"""
from __future__ import annotations

import os
import re
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
U1 = os.path.join(REPO, "raw8", "gates", "u1")
IQR = os.path.join(U1, "iqr_dump.txt")
EPMC = os.path.join(U1, "epmc_0_1728_nz_0x1300.log")
OUT = os.path.join(U1, "iqr_epmc_map.tsv")

POOL_A = 0x20821300
POOL_B = 0x20821700
TOP = 0x20820000


ANSI = re.compile(r"\x1b\[[0-9;]*m")


def load_iqr():
    """-> list[(idx, name, dec)]  （源文件含 NUL 前缀 + ANSI 颜色码，先清洗）"""
    out = []
    rx = re.compile(r"^\s*\[\s*(\d+)\]\|\s*(eIQ_ID_\w+)\s*\|")
    with open(IQR, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            ln = ANSI.sub("", raw.lstrip("\x00 \t"))
            m = rx.match(ln)
            if m:
                idx = int(m.group(1))
                name = m.group(2)
                # 值列：| dec | 0xhex |  —— 取 dec（跳过 enum 文本列）
                m2 = re.search(r"\|\s*(-?\d+)\s*\|", ln[m.end():])
                dec = int(m2.group(1)) if m2 else None
                out.append((idx, name, dec))
    return out


def load_epmc():
    """-> list[(off, val)]（相对 0x20820000）"""
    out = []
    rx = re.compile(r"^\s*\+0x([0-9a-f]+) = 0x([0-9a-f]+)")
    with open(EPMC, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            m = rx.match(ln)
            if m:
                out.append((int(m.group(1), 16), int(m.group(2), 16)))
    return out


def slot_of(off):
    """把 EP 偏移标注为 (池, slot, ch, 字段偏移) 或 (区域, None, None, None)"""
    if 0x1300 <= off < 0x1700:
        return ("A", (off - 0x1300) // 0x100, (off % 0x100) // 0x80, off % 0x80)
    if 0x1700 <= off < 0x1b00:
        return ("B", (off - 0x1700) // 0x100, (off % 0x100) // 0x80, off % 0x80)
    return ("?", None, None, None)


def f32(v):
    try:
        return struct.unpack("<f", struct.pack("<I", v))[0]
    except Exception:
        return None


def main():
    iqr = load_iqr()
    epmc = load_epmc()
    print("iqr rows: %d  epmc nonzero: %d" % (len(iqr), len(epmc)))
    if len(iqr) < 180 or len(epmc) < 30:
        print("!! 输入不完整，中止")
        return 1

    # iqr 值索引（dec -> [(idx,name)]；★ 只收非零——0 无区分度，全是噪声）
    by_val = {}
    for idx, name, dec in iqr:
        if dec is None or dec == 0:
            continue
        by_val.setdefault(dec, []).append((idx, name))

    # 尺寸对锚点：iqr 里已知 (W,H) 型相邻对（15,16)=AF_IMAGE_SIZE(W,H)
    dim_pairs = {}
    for wi, wname, wv in iqr:
        if not wv or wv < 8:
            continue
        for hi_, hname, hv in iqr:
            if hv == wv * 2 // 3 and 8 <= hv:  # 4:3 家族
                dim_pairs.setdefault((wv, hv), []).append("%s/%s" % (wname, hname))

    rows = []
    n_hit = 0
    for off, val in sorted(epmc):
        pool, slot, ch, fld = slot_of(off)
        cands = []

        def add(kind, note):
            if len(cands) < 4:
                cands.append((kind, note))

        # a) u32 精确
        for idx, name in by_val.get(val, []):
            add("u32", "iqr[%d] %s = %d" % (idx, name, val))
        # b) u16 拆分（hi/lo）——尺寸对 (W,H) 常见；跳过 0 半字（无区分度）
        hi, lo = (val >> 16) & 0xFFFF, val & 0xFFFF
        for part, tag in ((hi, "hi16"), (lo, "lo16")):
            if part == 0:
                continue
            for idx, name in by_val.get(part, []):
                add("u16-" + tag, "iqr[%d] %s = %d" % (idx, name, part))
            # c) ±1（如 719 vs 720：W-1）；低信息量跳过
            if part > 2:
                for delta in (-1, 1):
                    for idx, name in by_val.get(part + delta, []):
                        add("u16-%s±1" % tag, "iqr[%d] %s = %d (off内=%d)" % (idx, name, part + delta, part))
        # b') 尺寸对专门检测（+0x20/+0x24/+0x28 = (W-1,H-1)/(W,H)/(W,H) 三元组）
        if fld in (0x20, 0x24, 0x28) and hi > 8 and lo > 8:
            if (hi, lo) in dim_pairs:
                add("DIM-PAIR", "(%d,%d) ↔ %s" % (hi, lo, ";".join(dim_pairs[(hi, lo)])))
            if (hi + 1, lo + 1) in dim_pairs:
                add("DIM-PAIR", "(%d,%d)-1 ↔ %s" % (hi, lo, ";".join(dim_pairs[(hi + 1, lo + 1)])))
        # d) 槽尾版本戳（写入器不写 +0xfc，初始化器写的）
        if fld == 0x7C and ch == 1:
            add("tag", "槽尾版本戳（初始化器写，非槽写入器）")
        # e) +0x10 的强制 0x30 位（写入器模板）
        if fld == 0x10 and val == 0x30:
            add("const", "写入器强制 |0x30 模板位")

        fv = f32(val)
        note_f = ("f32=%.6g" % fv) if fv is not None and abs(fv) > 1e-9 else ""
        if cands:
            n_hit += 1
        rows.append((off, pool, slot, ch, fld, "0x%08x" % val, val,
                     "; ".join("%s:%s" % (k, n) for k, n in cands) or "-", note_f))

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# G5-3 / C14 —— iqr(184 ID) x epmc(A/B 槽池) 关联表\n")
        fh.write("# 生成: %s | 输入: iqr_dump.txt + epmc_0_1728_nz_0x1300.log\n" % "2026-10-08")
        fh.write("# 槽池结构（静态实锤，53_all_pseudocode.c）:\n")
        fh.write("#   A 池 0x20821300 / B 池 0x20821700, 各 21 槽 x stride 0x100, 每槽 ch0(+0x00)/ch1(+0x80)\n")
        fh.write("#   写入器 FUN_004b6894(A)/FUN_004b6b98(B) 只写每通道 +0x00..0x24; +0xfc 版本戳为初始化器写\n")
        fh.write("#   提交 = *(u32*)0x20821044 = 1<<(slot+4)  [修正: 非 0x20820044]\n")
        fh.write("# 列: ep_off  pool  slot  ch  fld  hex  dec  iqr_match  f32\n")
        for r in rows:
            fh.write("0x%04x\t%s\t%s\t%s\t0x%02x\t%s\t%d\t%s\t%s\n" % r)

    print("== 匹配统计: %d/%d 个非零寄存器有 iqr 锚点 ==" % (n_hit, len(epmc)))
    print("\n== 有锚点的行 ==")
    for r in rows:
        if r[7] != "-":
            print("  +0x%04x [%s s%s c%s f0x%02x] %s -> %s %s" % (r[0], r[1], r[2], r[3], r[4], r[5], r[7], r[8]))
    print("\n== 无锚点（槽池私有参数：流描述符/浮点对）示例 ==")
    shown = 0
    for r in rows:
        if r[7] == "-" and shown < 12:
            print("  +0x%04x [%s s%s c%s f0x%02x] %s %s" % (r[0], r[1], r[2], r[3], r[4], r[5], r[8]))
            shown += 1
    print("\n产物: %s" % OUT)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
