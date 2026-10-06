#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 Ghidra 导出的全量伪代码里做结构化检索（抓主干用）。

输入: raw8/p7/ghidra/53_all_pseudocode.c  (16466 个函数)
用法:
  python ps_scan.py matrix          # 找 3x3 色彩矩阵写入（1.0f/0.5f 密集）
  python ps_scan.py floats <hex>    # 找含指定浮点位模式的函数
  python ps_scan.py callers <FUN_x> # 反向调用表
  python ps_scan.py callees <FUN_x> # 正向调用表
  python ps_scan.py ep              # EP 寄存器访问全表（已验证判据）
  python ps_scan.py stats           # 统计
"""
import re
import sys
import collections
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANDIDATES = [
    HERE.parent.parent / "raw8" / "p7" / "ghidra" / "53_all_pseudocode.c",
    HERE / "53_all_pseudocode.c",
    Path(r"E:\ghidra_out\53_all_pseudocode.c"),
]
PS = next((p for p in CANDIDATES if p.exists()), CANDIDATES[0])

HDR = re.compile(r"// ==== (\S+) @ (0x[0-9a-f]+) size=(\d+) ====")


def load():
    """返回 [(func_name, addr, size, [lines...]), ...]"""
    out = []
    name = addr = size = None
    buf = []
    for line in PS.open(encoding="utf-8", errors="replace"):
        m = HDR.match(line)
        if m:
            if name:
                out.append((name, addr, size, buf))
            name, addr, size = m.group(1), int(m.group(2), 16), int(m.group(3))
            buf = []
        else:
            buf.append(line)
    if name:
        out.append((name, addr, size, buf))
    return out


def cmd_matrix(funcs):
    """3x3 矩阵写入 = 同一函数里 >=6 个 0x3f8xxxxx (≈1.0f) 或 0x3f0/0x400 区常量"""
    print("=== 3x3 色彩矩阵候选（1.0f 密集）===")
    hits = []
    for name, addr, size, lines in funcs:
        txt = "".join(lines)
        c10 = len(re.findall(r"0x3f8[0-9a-f]{5}", txt))
        c05 = len(re.findall(r"0x3f0[0-9a-f]{5}", txt))
        c20 = len(re.findall(r"0x400[0-9a-f]{5}", txt))
        score = c10 * 3 + c05 + c20
        if score >= 8:
            hits.append((score, c10, c05, c20, name, addr, size))
    hits.sort(reverse=True)
    for s, a, b, c, name, addr, size in hits[:20]:
        print(f"  {name} @ 0x{addr:x} size={size}  1.0f={a} 0.5f={b} 2.0f={c} score={s}")
    if not hits:
        print("  (无)")
    return hits


def cmd_floats(funcs, pat):
    print(f"=== 含 {pat} 的函数 ===")
    rx = re.compile(pat)
    n = 0
    for name, addr, size, lines in funcs:
        c = sum(1 for l in lines if rx.search(l))
        if c:
            n += 1
            if n <= 25:
                print(f"  {name} @ 0x{addr:x} size={size}  {c} 处")
    print(f"  total = {n}")


def cmd_callers(funcs, target):
    callers = collections.defaultdict(set)
    rx = re.compile(r"\b" + re.escape(target) + r"\s*\(")
    for name, addr, size, lines in funcs:
        for l in lines:
            if rx.search(l):
                callers[name].add(target)
    print(f"=== 谁调用 {target} ({len(callers)} 个) ===")
    for c in sorted(callers):
        print("   ", c)


def cmd_callees(funcs, target):
    rx = re.compile(r"\b(FUN_[0-9a-f]+)\s*\(")
    for name, addr, size, lines in funcs:
        if name != target:
            continue
        print(f"=== {target} @ 0x{addr:x} 调用了 ===")
        seen = []
        for l in lines:
            for t in rx.findall(l):
                if t != target and t not in seen:
                    seen.append(t)
        for t in seen:
            print("   ", t)
        print(f"  total = {len(seen)}")
        return
    print(f"  {target} 不在伪代码里")


EP = re.compile(r"0x(2082[0-9a-f]{4}|208[0-9a-f]{5})")


def cmd_ep(funcs):
    print("=== EP 寄存器访问全表（地址 -> 函数）===")
    hits = collections.defaultdict(lambda: collections.defaultdict(list))
    for name, addr, size, lines in funcs:
        for i, l in enumerate(lines):
            for a in EP.findall(l):
                hits["0x" + a][name].append(i)
    for a in sorted(hits, key=lambda x: -sum(len(v) for v in hits[x].values())):
        tot = sum(len(v) for v in hits[a].values())
        fns = sorted(hits[a])
        print(f"  {a}  x{tot:<3} {len(fns)} 个函数: {fns[:4]}")


def cmd_stats(funcs):
    tot = sum(len(l) for _, _, _, l in funcs)
    print(f"functions = {len(funcs)}   total lines = {tot}")
    sizes = sorted((sz for _, _, sz, _ in funcs), reverse=True)
    print("top sizes:", sizes[:15])
    # EP 段统计
    epf = [(n, a) for n, a, _, l in funcs if any(EP.search(x) for x in l)]
    print(f"functions touching EP = {len(epf)}")


if __name__ == "__main__":
    if not PS.exists():
        print("找不到伪代码文件:", PS)
        sys.exit(1)
    F = load()
    c = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if c == "matrix":
        cmd_matrix(F)
    elif c == "floats":
        cmd_floats(F, sys.argv[2] if len(sys.argv) > 2 else r"0x3f8[0-9a-f]{5}")
    elif c == "callers":
        cmd_callers(F, sys.argv[2] if len(sys.argv) > 2 else "FUN_004b6894")
    elif c == "callees":
        cmd_callees(F, sys.argv[2] if len(sys.argv) > 2 else "FUN_004b6894")
    elif c == "ep":
        cmd_ep(F)
    else:
        cmd_stats(F)
