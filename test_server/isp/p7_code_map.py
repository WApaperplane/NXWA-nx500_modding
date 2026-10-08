#!/usr/bin/env python3
"""p7「B 区」代码地图构建器  (NX-KS2 / U01)

目标：把 16466 个 p7 函数归属到 211 个 C++ 源文件，产出模块级代码地图。

原理（三条已证事实）：
  1. p7 镜像里 `0x6edb88..0x733578` 是一段**连续的 .rodata.str1.1**，
     GCC/ARM 链接器按目标文件顺序排列 ⇒ 每个模块的 `__FILE__` 与它的日志格式串相邻。
     ⇒ 用 __FILE__ 地址给这段做**切分**，段内的字符串就属于该模块。
  2. `05_scalar_refs.txt` 给出「标量地址 → 引用它的指令地址」全表。
     字符串也是"被引用的标量" ⇒ 能拿到 **字符串 → 引用指令**。
  3. 指令地址落在哪个函数里（按 52_pseudocode_index.txt 的 start/size 二分）
     ⇒ **函数 → 它引用的字符串 → 字符串所属模块** ⇒ 函数归属模块。

判据纪律：
  · 一个函数可能引用多个模块的字符串（模板/内联/共用串）⇒ 采用**多数票 + 记录全部**
  · 无引用的函数（占多数）**不猜测归属**，单列 unknown，不污染统计
  · 所有归属都记「证据字符串」，可人工复核

用法：
  python p7_code_map.py                 # 产出 raw8/p7/p7_code_map.txt
  python p7_code_map.py --top 40        # 控制台只详列前 N 个模块
"""
from __future__ import annotations

import argparse
import bisect
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
P7DIR = os.path.join(REPO, "raw8", "p7")
GHDIR = os.path.join(P7DIR, "ghidra")

F_FUNCS = os.path.join(GHDIR, "52_pseudocode_index.txt")
F_STRINGS = os.path.join(GHDIR, "04_strings.txt")
F_SCALARS = os.path.join(GHDIR, "05_scalar_refs.txt")
OUT = os.path.join(P7DIR, "p7_code_map.txt")

FILE_STR = re.compile(r"\.(cpp|cxx|cc|c|h|hpp)$")


# ---------------------------------------------------------------- loaders
def load_functions(path):
    """-> list[(start, size, name)]"""
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


def load_strings(path):
    """-> dict[addr] = (len, text)"""
    out = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            p = ln.rstrip("\r\n").split("\t", 2)
            if len(p) == 3 and len(p[0]) == 8:
                try:
                    out[int(p[0], 16)] = (int(p[1]), p[2])
                except ValueError:
                    pass
    return out


def load_scalar_refs(path):
    """-> list[(addr, [ref tokens])]"""
    out = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            m = re.match(r"^([0-9a-fA-F]{8}) = .*?\t(\d+)\t\[(.*)\]\s*$", ln.rstrip("\r\n"))
            if not m:
                continue
            addr = int(m.group(1), 16)
            refs = [t.strip() for t in m.group(3).split(",") if t.strip()]
            out.append((addr, refs))
    return out


def scan_literal_pool_xrefs(img, string_addrs):
    """自建 PC-relative / 立即数 引用扫描（ARM 态）。

    ★ 为什么需要自建：Ghidra 导出的 05_scalar_refs.txt 只含**数值常量**，
      不含字符串指针（已实测 0 命中）。而 11_string_xref_stats 的引用来自
      Ghidra Java API 的 getReferencesTo，没有被导出成可解析的文本。

    ★★ 关键语义（第一版写错的地方）：`LDR Rt,[PC,#imm]` 载入的是
      **literal pool 槽的地址**；槽里的**内容**才是字符串指针。
      所以必须再解引用一层。

    三种形态都覆盖：
      A. LDR Rt,[PC,#±imm12]   (0xE59Fxxxx) → pool 槽地址 → 读 u32 → 比对
      B. ADD Rd,PC,#imm12      (0xE28Fxxxx) → 直接算出地址 → 比对
      C. MOVW/MOVT 配对        (0xE30xxxxx / 0xE34xxxxx) → 32 位常量 → 比对
    -> dict[string_addr] = [instruction addr, ...]
    """
    import struct

    hits = defaultdict(list)
    n = len(img)

    movw = {}
    for off in range(0, n - 4, 4):
        w = struct.unpack_from("<I", img, off)[0]
        rd = (w >> 12) & 0xF

        # A. LDR Rt,[PC,#±imm12]
        if (w & 0x0FFF0000) == 0x059F0000 and (w & 0xF0000000) == 0xE0000000:
            imm = w & 0xFFF
            pool = (off + 8 + imm) if ((w >> 23) & 1) else (off + 8 - imm)
            if 0 <= pool <= n - 4:
                val = struct.unpack_from("<I", img, pool)[0]
                if val in string_addrs:
                    hits[val].append(off)

        # B. ADD Rd,PC,#imm12
        elif (w & 0x0FFF0000) == 0x028F0000 and (w & 0xF0000000) == 0xE0000000:
            imm = w & 0xFFF
            t = (off + 8 + imm) & 0xFFFFFFFF
            if t in string_addrs:
                hits[t].append(off)

        # C. MOVW / MOVT
        if (w & 0xFFF00000) == 0xE3000000:  # MOVW Rd,#imm16
            movw[rd] = ((w >> 16) & 0xF) << 12 | (w & 0xFFF)
        elif (w & 0xFFF00000) == 0xE3400000:  # MOVT Rd,#imm16
            hi = ((w >> 16) & 0xF) << 12 | (w & 0xFFF)
            lo = movw.get(rd)
            if lo is not None:
                v = (hi << 16) | lo
                if v in string_addrs:
                    hits[v].append(off)
        else:
            movw.pop(rd, None)

    return hits


# ---------------------------------------------------------------- helpers
class FuncIndex:
    def __init__(self, funcs):
        self.funcs = funcs
        self.starts = [f[0] for f in funcs]

    def owner(self, addr):
        """返回包含 addr 的函数 (start,size,name)；找不到返回 None"""
        i = bisect.bisect_right(self.starts, addr) - 1
        if i < 0:
            return None
        s, sz, n = self.funcs[i]
        # 函数体按 start+size 界定；size 为 0 时放宽到下一个函数起点
        end = s + sz if sz else (self.funcs[i + 1][0] if i + 1 < len(self.funcs) else s + 0x10000)
        return (s, sz, n) if s <= addr < max(end, s + 4) else None


def parse_ref(tok):
    """引用项 -> 指令地址（int）"""
    if tok.startswith("FUN_"):
        try:
            return int(tok[4:], 16)
        except ValueError:
            return None
    if re.fullmatch(r"[0-9a-fA-F]{8}", tok):
        return int(tok, 16)
    return None


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args()

    funcs = load_functions(F_FUNCS)
    strings = load_strings(F_STRINGS)
    fidx = FuncIndex(funcs)
    print(f"functions={len(funcs)}  strings={len(strings)}")

    img = open(os.path.join(P7DIR, "p7_full.bin"), "rb").read()
    # ★★ 关键：p7 带 MMU，运行时用**虚拟地址 0x8xxxxxxx**（identity 映射 1:1）。
    #    而 04_strings.txt 里的地址是 Ghidra 以 base 0x0 分析出来的**文件偏移**。
    #    ⇒ 代码里的指针 = 文件偏移 + 0x80000000。第一版没加上，所以几乎零命中。
    VA = 0x80000000
    va2file = {s + VA: s for s in strings}
    xrefs_va = scan_literal_pool_xrefs(img, set(va2file))
    xrefs = defaultdict(list)
    for va, instrs in xrefs_va.items():
        xrefs[va2file[va]].extend(instrs)
    print(f"literal-pool xref scanner: referenced strings = {len(xrefs)}  "
          f"(vs Ghidra 报告 894)")

    # 1) 找出 __FILE__ 并切段
    file_markers = sorted(
        (a, t) for a, (_, t) in strings.items() if FILE_STR.search(t) and ("/" in t)
    )
    if not file_markers:
        print("ERROR: no __FILE__ markers found")
        return 1
    print(f"__FILE__ markers = {len(file_markers)}")

    # 段：每个 __FILE__ 到下一个 __FILE__ 之前
    # ★ 修正（2026-10-08）：最后一个 marker 没有"下一个"作上界，原先用 max(strings)+1
    #   ⇒ 把其后 806 个串全吞进最后一个模块（实测把 `divide.c` 撑成假大模块）。
    #   .rodata.str1.1 段长 median=426B / mean=9.3KB ⇒ 给末段一个 0x2000 的保守上界。
    seg_start = file_markers[0][0]
    seg_end = max(strings)
    LAST_SEG_CAP = 0x2000
    bounds = [a for a, _ in file_markers] + [file_markers[-1][0] + LAST_SEG_CAP]
    mod_of_addr = {}
    for i, (a, t) in enumerate(file_markers):
        lo, hi = bounds[i], bounds[i + 1]
        for s in strings:
            if lo <= s < hi:
                mod_of_addr[s] = t

    # 2) 字符串 -> 引用它的函数
    str_to_funcs = defaultdict(Counter)
    for saddr, instrs in xrefs.items():
        for ia in instrs:
            o = fidx.owner(ia)
            if o:
                str_to_funcs[saddr][o[2]] += 1

    # 3) 函数 -> 模块（多数票）
    func_votes = defaultdict(Counter)
    func_evidence = defaultdict(dict)  # func -> {module: sample string}
    for saddr, fcounts in str_to_funcs.items():
        mod = mod_of_addr.get(saddr)
        if not mod:
            continue
        for fname, c in fcounts.items():
            func_votes[fname][mod] += c
            func_evidence[fname].setdefault(mod, strings[saddr][1][:70])

    mod_funcs = defaultdict(list)
    multi = []
    for fname, votes in func_votes.items():
        best, n = votes.most_common(1)[0]
        mod_funcs[best].append((fname, n, sum(votes.values()), len(votes)))
        if len(votes) > 1:
            multi.append((fname, votes.most_common(3)))

    att = len(func_votes)
    print(f"attributed functions = {att} / {len(funcs)}  ({100.0*att/len(funcs):.2f}%)")
    print(f"modules with >=1 function = {len(mod_funcs)} / {len(file_markers)}")
    print(f"multi-module (ambiguous) functions = {len(multi)}")

    # 4) 输出
    lines = []
    lines.append("=" * 78)
    lines.append("p7「B 区」代码地图  (NX-KS2 / U01)")
    lines.append("=" * 78)
    lines.append(f"函数总数            : {len(funcs)}")
    lines.append(f"__FILE__ 模块数     : {len(file_markers)}")
    lines.append(f"有引用关系的字符串  : {len(str_to_funcs)}")
    lines.append(f"成功归属模块的函数  : {att}  ({100.0*att/len(funcs):.2f}%)")
    lines.append(f"归属到 >=1 函数的模块: {len(mod_funcs)}")
    lines.append(f"跨模块歧义函数      : {len(multi)}")
    lines.append("")
    lines.append("★ 未被归属的函数（多数）不猜测 —— 它们不引用任何 B 区日志串。")
    lines.append("★ 归属判据 = 该函数引用的字符串落在哪个 __FILE__ 段内（多数票，附样本）。")
    lines.append("")

    lines.append("-" * 78)
    lines.append("## ★★ 与铁律 116 的对照：符号区（0x580000+）真的是「零引用死数据」吗？")
    lines.append("-" * 78)
    n_code = sum(1 for s in strings if s < 0x580000)
    n_sym = sum(1 for s in strings if 0x580000 <= s < 0x600000)
    n_bz = sum(1 for s in strings if s >= 0x600000)
    h_code = sum(1 for s in xrefs if s < 0x580000)
    h_sym = sum(1 for s in xrefs if 0x580000 <= s < 0x600000)
    h_bz = sum(1 for s in xrefs if s >= 0x600000)
    lines.append(f"{'区间':<34} {'串总数':>8} {'被引用':>8} {'引用率':>9}")
    for label, tot, got in (
        ("< 0x580000  (代码带内串)", n_code, h_code),
        ("0x580000-0x5FFFFF (符号区)", n_sym, h_sym),
        (">= 0x600000 (B 区格式串)", n_bz, h_bz),
    ):
        lines.append(f"{label:<34} {tot:>8} {got:>8} {100.0*got/tot if tot else 0:>8.2f}%")
    lines.append("")
    lines.append("★ 判据纪律：「被引用」= 存在**精确指向该串起始地址**的 32 位指针")
    lines.append("  （LDR literal pool / ADD PC / MOVW+MOVT 三形态，且需解引用后精确相等）。")
    lines.append("  故本表是**下界**；但已远高于 Ghidra 只导出的 894（4.10%）。")
    lines.append("")

    lines.append("-" * 78)
    lines.append("## 模块族归类（路径前缀聚合）")
    lines.append("-" * 78)
    fam = Counter()
    famf = Counter()
    for mod, fl in mod_funcs.items():
        parts = mod.replace("\\", "/").split("/")
        key = parts[0] if parts[0] not in ("product", "source", "src") else "/".join(parts[:2])
        fam[key] += 1
        famf[key] += len(fl)
    lines.append(f"{'族':<42} {'模块数':>6} {'函数数':>7}")
    for k, v in famf.most_common(40):
        lines.append(f"{k:<42} {fam[k]:>6} {v:>7}")
    lines.append("")

    lines.append("-" * 78)
    lines.append("## 模块表（按函数数降序）")
    lines.append("-" * 78)
    lines.append(f"{'函数数':>6} {'串数':>6}  {'__FILE__ 地址':>12}  模块路径")
    for mod, fl in sorted(mod_funcs.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        addr = next(a for a, t in file_markers if t == mod)
        nstr = sum(1 for s, m in mod_of_addr.items() if m == mod)
        lines.append(f"{len(fl):>6} {nstr:>6}  {addr:>#12x}  {mod}")

    lines.append("")
    lines.append("-" * 78)
    lines.append("## 各模块函数明细（函数名 / 命中票数 / 该函数引用串总数 / 涉及模块数）")
    lines.append("-" * 78)
    for mod, fl in sorted(mod_funcs.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        lines.append("")
        lines.append(f"### {mod}   ({len(fl)} 个函数)")
        for fname, n, tot, nm in sorted(fl, key=lambda x: -x[1]):     # ★ 不再截断
            lines.append(f"    {fname:<22} votes={n:<3} strrefs={tot:<3} modules={nm}   e.g. {func_evidence[fname].get(mod,'')!r}")

    lines.append("")
    lines.append("-" * 78)
    lines.append("## 跨模块歧义函数（top 40）")
    lines.append("-" * 78)
    for fname, top3 in sorted(multi, key=lambda x: -x[1][0][1])[:40]:
        lines.append(f"  {fname:<22} " + "  |  ".join(f"{m}({c})" for m, c in top3))

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")

    # ★ 机器可读全量归属表（不截断）—— 供 p7_class_map.py 等下游工具直接消费
    tsv = os.path.join(P7DIR, "p7_code_map.tsv")
    with open(tsv, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("func\tmodule\tvotes\tstrrefs\tmodules\tsample\n")
        for fname, votes in sorted(func_votes.items()):
            best, n = votes.most_common(1)[0]
            fh.write(f"{fname}\t{best}\t{n}\t{sum(votes.values())}\t{len(votes)}\t"
                     f"{func_evidence[fname].get(best,'')}\n")
    print(f"wrote {tsv}  ({att} rows, 全量不截断)")

    # 控制台摘要
    print("\n--- top modules ---")
    for mod, fl in sorted(mod_funcs.items(), key=lambda kv: -len(kv[1]))[: args.top]:
        print(f"  {len(fl):>5}  {mod}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
