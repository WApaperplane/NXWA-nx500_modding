#!/usr/bin/env python3
"""p7 · EP 地址窗口全聚类  (NX-KS2 / U03)

问题：官方只给了 EP 的「10 个子块」（控制面划分），但 p7 里实测有 342 个 EP 常量，
      其中 `0x2082121c` / `0x2082a0xx` / 230 处 `0x2083xx` **不在那 10 块表内**。
      它们是什么？EP 内部到底有多少寄存器窗口？

方法（铁律 112：ARMv7 的 32 位常量必须靠 MOV/MOVW + MOVT 配对重建）：
  扫全镜像，收集所有 (hi<<16)|lo 配对常量，取 EP 范围 0x20800000-0x208FFFFF，
  按 0x100 粒度做直方图，再按访问函数归并 ⇒ 得到"第 11~N 块"。

产出：raw8/p7/p7_ep_windows.txt
"""
from __future__ import annotations

import bisect
import collections
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
P7 = os.path.join(REPO, "raw8", "p7")
IMG = os.path.join(P7, "p7_full.bin")
IDX = os.path.join(P7, "ghidra", "52_pseudocode_index.txt")
OUT = os.path.join(P7, "p7_ep_windows.txt")

EP_LO, EP_HI = 0x20800000, 0x20900000

# 官方 10 块（控制面）+ 我们已知的两个参数块
OFFICIAL = [
    ("top",       0x20820000, 0x1c00),
    ("ldc",       0x20823000, 0x1000),
    ("mc",        0x20824000, 0x2000),
    ("rsz",       0x20826000, 0x1000),
    ("lvr",       0x20827000, 0x1000),
    ("bblt",      0x20828000, 0x1000),
    ("fd",        0x20829000, 0x1000),
    ("jpeg",      0x2082a000, 0x1000),
    ("3dlut",     0x2082b000, 0x1000),
    ("nog",       0x20821c00, 0x0100),
]
EXTRA = [
    ("isp-param-A", 0x20821300, 0x1500),
    ("isp-param-B", 0x20821700, 0x0500),
    ("OSD-array",   0x20830000, 0x10000),
]


def load_functions(path):
    out = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            p = ln.rstrip("\r\n").split("\t")
            if len(p) >= 3 and p[0].startswith("0x"):
                try:
                    out.append((int(p[0], 16), int(p[1]), p[2]))
                except ValueError:
                    pass
    out.sort()
    return out


def rebuild_constants(img):
    """MOV/MOVW + MOVT 配对重建 -> list[(const, insn_off)]"""
    n = len(img)
    mov_bases = collections.defaultdict(list)
    consts = []
    for a in range(0, n - 4, 4):
        w = struct.unpack_from("<I", img, a)[0]
        rd = (w >> 12) & 0xF
        # MOV Rd,#imm8 (with rotate)
        if (w & 0x0FE00000) == 0x03A00000:
            i12 = w & 0xFFF
            rot = ((i12 >> 8) & 0xF) * 2
            v = (((i12 & 0xFF) >> rot) | ((i12 & 0xFF) << (32 - rot))) & 0xFFFFFFFF if rot else (i12 & 0xFF)
            mov_bases[rd].append((a, v & 0xFFFF))
        # MOVW Rd,#imm16
        if (w & 0xFFF00000) == 0xE3000000:
            mov_bases[rd].append((a, ((w >> 16) & 0xF) << 12 | (w & 0xFFF)))
    for a in range(0, n - 4, 4):
        w = struct.unpack_from("<I", img, a)[0]
        rd = (w >> 12) & 0xF
        if (w & 0xFFF00000) == 0xE3400000:  # MOVT
            hi = ((w >> 16) & 0xF) << 12 | (w & 0xFFF)
            for pa, pv in mov_bases.get(rd, ()):
                if 0 <= a - pa <= 32:
                    consts.append((((hi << 16) | (pv & 0xFFFF)) & 0xFFFFFFFF, pa))
    return consts


def main():
    img = open(IMG, "rb").read()
    funcs = load_functions(IDX)
    starts = [f[0] for f in funcs]

    def owner(a):
        i = bisect.bisect_right(starts, a) - 1
        if i < 0:
            return None
        s, sz, n = funcs[i]
        return n if s <= a < s + max(sz, 4) else None

    consts = rebuild_constants(img)
    ep = [(c, o) for c, o in consts if EP_LO <= c < EP_HI]
    allfn = collections.Counter(owner(o) for _, o in ep)
    print(f"total reconstructed consts = {len(consts)}")
    print(f"EP-range consts           = {len(ep)}  (unique {len({c for c,_ in ep})})")
    print(f"accessing functions       = {len(allfn)}")

    # 0x100 粒度直方图
    hist = collections.Counter((c >> 8) << 8 for c, _ in ep)
    # 归并相邻
    keys = sorted(hist)
    clusters = []
    cur = [keys[0]]
    for k in keys[1:]:
        if k - cur[-1] <= 0x100:
            cur.append(k)
        else:
            clusters.append(cur)
            cur = [k]
    clusters.append(cur)

    def label(addr):
        for name, base, size in OFFICIAL + EXTRA:
            if base <= addr < base + size:
                return name
        return "??"

    lines = []
    lines.append("=" * 92)
    lines.append("p7 · EP 地址窗口全聚类 (NX-KS2 / U03)")
    lines.append("=" * 92)
    lines.append(f"重建常量总数        : {len(consts)}")
    lines.append(f"EP 范围 (0x20800000-0x208FFFFF) 常量 : {len(ep)}   唯一值 {len({c for c,_ in ep})}")
    lines.append(f"触及 EP 的函数数    : {len(allfn)}")
    lines.append(f"0x100 粒度对齐后的窗口段数 : {len(clusters)}")
    lines.append("")
    lines.append("方法：MOV/MOVW + MOVT 配对重建（铁律 112），窗口 = 0x100 粒度直方图 + 相邻归并")
    lines.append("")

    lines.append("-" * 92)
    lines.append("## 窗口段全表（按段内常量数降序）")
    lines.append("-" * 92)
    lines.append(f"{'段起点':>12} {'段终(含)':>12} {'常量数':>7} {'唯一':>6} {'函数数':>6}  {'官方归属':<14} 代表地址")
    rows = []
    for cl in clusters:
        lo, hi = cl[0], cl[-1] + 0xFF
        sub = [(c, o) for c, o in ep if lo <= c <= hi]
        uniq = len({c for c, _ in sub})
        fns = len({owner(o) for _, o in sub})
        lbl = label(lo)
        sample = ", ".join(f"{c:#x}" for c, _ in sorted(set(sub))[:4])
        rows.append((len(sub), lo, hi, uniq, fns, lbl, sample))
    for cnt, lo, hi, uniq, fns, lbl, sample in sorted(rows, reverse=True):
        flag = "" if lbl != "??" else "  ★表外"
        lines.append(f"{lo:>#12x} {hi:>#12x} {cnt:>7} {uniq:>6} {fns:>6}  {lbl:<14}{flag} {sample}")

    lines.append("")
    lines.append("-" * 92)
    lines.append("## 与官方表的差集：官方 10 块里【一个常量都没有】的块")
    lines.append("-" * 92)
    for name, base, size in OFFICIAL:
        n = sum(1 for c, _ in ep if base <= c < base + size)
        lines.append(f"  {name:<12} {base:#010x}+{size:#06x}  常量数 = {n}")
    lines.append("")
    lines.append("-" * 92)
    lines.append("## 表外区域明细（这些是官方 10 块之外的真实窗口）")
    lines.append("-" * 92)
    for name, base, size in EXTRA:
        sub = [(c, o) for c, o in ep if base <= c < base + size]
        if not sub:
            continue
        fns = collections.Counter(owner(o) for _, o in sub)
        lines.append(f"\n### {name}  {base:#010x}  (常量 {len(sub)}, 唯一 {len({c for c,_ in sub})}, 函数 {len(fns)})")
        for c, n in sorted(collections.Counter(c for c, _ in sub).items()):
            lines.append(f"    {c:#010x}  x{n}")
        lines.append("  访问函数:")
        for f, n in fns.most_common(20):
            lines.append(f"    {f}  x{n}")

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"wrote {OUT}")

    print("\n--- top windows ---")
    for cnt, lo, hi, uniq, fns, lbl, sample in sorted(rows, reverse=True)[:20]:
        print(f"  {cnt:>5}  {lo:#010x}-{hi:#010x}  fns={fns:<4} {lbl}")


if __name__ == "__main__":
    sys.exit(main())
