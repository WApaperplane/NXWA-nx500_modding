#!/usr/bin/env python3
"""p7 · 类结构地图（RTTI 三跳）  (NX-KS2 / U01 扩展)

背景与依据
----------
U01 用「函数引用的字符串落在哪个 __FILE__ 段」把 3786/16466 个函数归属到模块。
但 A 区（0x580000-0x5FFFFF）那 4354 个类名/符号串**没有 __FILE__ 段可依**，
而它们恰好含有 p7 的 **Itanium RTTI 类型名**（形如 `17CBackend_Ldc_Base`，前缀十进制数 = 名字长度）。

★ 铁律 116 原先判定"该区零引用 ⇒ 死数据"，已被 U01 证伪（实测 80.16% 有引用）。
  本工具就用这些引用，做一条 **三跳数据流**，把「类名」还原成「类 → 方法」：

    跳1  字符串 VA 被某个数据字指向        → 那是 typeinfo 的 name 指针（typeinfo+4）
    跳2  typeinfo VA 被某个数据字指向      → 那是 vtable 的 typeinfo 指针（vtable-4）
    跳3  从 vtable-4+4 起连续读 0x8xxxxxxx → 方法函数 VA → 文件偏移 → Ghidra 函数名

判据纪律（铁律 117/118）
-----------------------
· 跳1 的命中**必须**通过跳2 非空来验证，否则那只是"代码里的日志串"（如
  `C3AStateS0Focusing` 被 FUN_000ace24 当字符串用），不是 typeinfo。
· 方法槽解析同时试 `f` 与 `f-1`（ARM 的 Thumb 函数指针会置 bit0）。
· 不做任何"名字像什么就归到什么"的猜测；每一条归属都附 vtable 地址可复核。

用法
  python p7_class_map.py            # -> raw8/p7/p7_class_map.txt
"""
from __future__ import annotations

import collections
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
P7 = os.path.join(REPO, "raw8", "p7")
IMG = os.path.join(P7, "p7_full.bin")
IDX = os.path.join(P7, "ghidra", "52_pseudocode_index.txt")
OUT = os.path.join(P7, "p7_class_map.txt")

VA = 0x80000000
A_LO, A_HI = 0x580000, 0x600000          # A 区（RTTI/符号串）
ITYPE = re.compile(r"^(\d{1,3})([A-Za-z_][A-Za-z0-9_:<>~]{2,80})$")  # <len><Name>


def load_functions(path):
    out = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            p = ln.rstrip("\r\n").split("\t")
            if len(p) >= 3 and p[0].startswith("0x"):
                try:
                    out[int(p[0], 16)] = p[2]
                except ValueError:
                    pass
    return out


def load_strings(path):
    out = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            p = ln.rstrip("\r\n").split("\t", 2)
            if len(p) == 3 and len(p[0]) == 8:
                try:
                    out[int(p[0], 16)] = p[2]
                except ValueError:
                    pass
    return out


def main():
    img = open(IMG, "rb").read()
    n = len(img)
    funcs = load_functions(IDX)
    strings = load_strings(os.path.join(P7, "ghidra", "04_strings.txt"))
    print(f"functions={len(funcs)} strings={len(strings)}")

    # 逆索引：值 -> 存放它的文件偏移（只收 0x8xxxxxxx 指针）
    inv = collections.defaultdict(list)
    for off in range(0, n - 4, 4):
        v = struct.unpack_from("<I", img, off)[0]
        if VA <= v < VA + n:
            inv[v].append(off)
    print(f"inverse-index entries (0x8xxxxxxx pointers) = {len(inv)}")

    # 候选类名串（A 区）
    cands = []
    for a, t in strings.items():
        if not (A_LO <= a < A_HI):
            continue
        m = ITYPE.match(t)
        if not m:
            continue
        ln, nm = int(m.group(1)), m.group(2)
        if ln != len(nm):
            continue                      # 长度前缀必须自洽（Itanium 未修饰名的形态）
        cands.append((a, nm))
    print(f"candidate RTTI class names (A 区, 长度前缀自洽) = {len(cands)}")

    classes = {}          # name -> dict
    for a, nm in cands:
        sva = a + VA
        vt_methods = []
        vt_addrs = []
        for L in inv.get(sva, ()):
            ti_off = L - 4                # typeinfo: name ptr 在 +4
            ti_va = ti_off + VA
            refs = inv.get(ti_va, ())
            if not refs:                  # 跳2 为空 ⇒ 不是 typeinfo（多半是代码里的日志串）
                continue
            for M in refs:
                vs = M + 4
                if not (0 <= vs <= n - 8):
                    continue
                meth = []
                for k in range(64):
                    w = struct.unpack_from("<I", img, vs + k * 4)[0]
                    if not (VA <= w < VA + n):
                        break
                    f = w - VA
                    meth.append(funcs.get(f) or funcs.get(f - 1) or f"0x{f:x}")
                if len(meth) >= 2:
                    vt_addrs.append(vs)
                    vt_methods.append(meth)
        if vt_methods:
            classes[nm] = {"str": a, "vtables": vt_addrs, "methods": vt_methods}

    print(f"resolved classes = {len(classes)}")

    # 类的方法函数集合 -> 反向：函数 -> 类
    fn2cls = collections.defaultdict(set)
    for nm, d in classes.items():
        for meth in d["methods"]:
            for f in meth:
                if f.startswith("FUN_") or f == "Reset":
                    fn2cls[f].add(nm)

    print(f"functions attributed to a class = {len(fn2cls)}")

    # 合并 U01 模块地图里的归属，算总覆盖率
    # ★ 优先读 TSV（全量、不截断）；txt 的明细曾按 40/模块 截断，不能作数（铁律 94 同源）
    mod_of = {}
    tsv = os.path.join(P7, "p7_code_map.tsv")
    if os.path.exists(tsv):
        with open(tsv, encoding="utf-8", errors="replace") as fh:
            next(fh, None)
            for ln in fh:
                p = ln.rstrip("\r\n").split("\t")
                if len(p) >= 2 and p[0]:
                    mod_of[p[0]] = p[1]
        print(f"module map loaded from TSV: {len(mod_of)} functions")
    else:
        cur = None
        mp = os.path.join(P7, "p7_code_map.txt")
        if os.path.exists(mp):
            with open(mp, encoding="utf-8", errors="replace") as fh:
                for ln in fh:
                    m = re.match(r"^### (.+?)\s+\(\d+ 个函数\)", ln)
                    if m:
                        cur = m.group(1)
                        continue
                    m2 = re.match(r"^\s+(FUN_[0-9a-f]+|Reset)\s", ln)
                    if m2 and cur:
                        mod_of[m2.group(1)] = cur
        print(f"module map loaded from TXT (⚠ 明细被截断): {len(mod_of)} functions")
    mod_only = set(mod_of) - set(fn2cls)
    cls_only = set(fn2cls) - set(mod_of)
    both = set(mod_of) & set(fn2cls)
    total = len(funcs)
    print(f"module-only={len(mod_only)} class-only={len(cls_only)} both={len(both)} "
          f"-> combined={len(set(mod_of)|set(fn2cls))}/{total} "
          f"({100.0*len(set(mod_of)|set(fn2cls))/total:.2f}%)")

    # 输出
    lines = []
    lines.append("=" * 96)
    lines.append("p7 · 类结构地图（RTTI 三跳：类名 → typeinfo → vtable → 方法）  (NX-KS2 / U01 扩展)")
    lines.append("=" * 96)
    lines.append(f"函数总数                       : {total}")
    lines.append(f"A 区候选 RTTI 类名（长度自洽）  : {len(cands)}")
    lines.append(f"成功解出 vtable 的类            : {len(classes)}")
    lines.append(f"被类归属的函数                  : {len(fn2cls)}")
    lines.append(f"U01 模块归属（仅模块）          : {len(mod_only)}")
    lines.append(f"类归属（仅类）                  : {len(cls_only)}")
    lines.append(f"两者都有                        : {len(both)}")
    lines.append(f"★ 合计已归属                    : {len(set(mod_of)|set(fn2cls))} / {total} "
                 f"({100.0*len(set(mod_of)|set(fn2cls))/total:.2f}%)")
    lines.append("")
    lines.append("方法与判据：跳1（串被数据字指向）必须通过跳2（typeinfo 被数据字指向）验证；")
    lines.append("方法槽同时试 f 与 f-1（Thumb 指针 bit0）。每条归属都附 vtable 文件偏移，可复核。")
    lines.append("")
    lines.append("-" * 96)
    lines.append("## 类表（按方法数降序，top 120）")
    lines.append("-" * 96)
    lines.append(f"{'方法数':>5} {'vtable 数':>8}  {'类名':<46} 首个 vtable (file offset)")
    for nm, d in sorted(classes.items(), key=lambda kv: -len(kv[1]["methods"][0]))[:120]:
        lines.append(f"{len(d['methods'][0]):>5} {len(d['vtables']):>8}  {nm:<46} "
                     f"{', '.join(hex(x) for x in d['vtables'][:3])}")

    lines.append("")
    lines.append("-" * 96)
    lines.append("## 类 → 方法明细（top 60 类）")
    lines.append("-" * 96)
    for nm, d in sorted(classes.items(), key=lambda kv: -len(kv[1]["methods"][0]))[:60]:
        lines.append("")
        lines.append(f"### {nm}   (串 @ {d['str']:#08x}, vtable @ "
                     f"{', '.join(hex(x) for x in d['vtables'])})")
        m = d["methods"][0]
        for i, f in enumerate(m):
            mark = "  ← 与 U01 模块一致" if f in fn2cls and f in mod_of else ""
            lines.append(f"    [{i:>2}] {f}{mark}")
        if len(d["methods"]) > 1:
            lines.append(f"    （另有 {len(d['methods'])-1} 个 vtable："
                         f"{[hex(x) for x in d['vtables'][1:]]}）")

    lines.append("")
    lines.append("-" * 96)
    lines.append("## 仅由「类」归属的函数（U01 模块地图没覆盖到的）")
    lines.append("-" * 96)
    for f in sorted(cls_only):
        lines.append(f"  {f:<22} {', '.join(sorted(fn2cls[f]))}")

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"wrote {OUT}")

    # ★ 机器可读全量：类 / vtable / 方法函数（不截断），供下游直接消费
    tsv = os.path.join(P7, "p7_class_map.tsv")
    rows = 0
    with open(tsv, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("class\tvtable_offset\tmethod_index\tfunc\n")
        for nm, d in sorted(classes.items()):
            for vto, meth in zip(d["vtables"], d["methods"]):
                for i, f in enumerate(meth):
                    fh.write(f"{nm}\t{vto:#x}\t{i}\t{f}\n")
                    rows += 1
    print(f"wrote {tsv}  ({rows} rows, 全量不截断)")

    print("\n--- top classes ---")
    for nm, d in sorted(classes.items(), key=lambda kv: -len(kv[1]["methods"][0]))[:25]:
        print(f"  {len(d['methods'][0]):>3} methods  {nm}")


if __name__ == "__main__":
    sys.exit(main())
