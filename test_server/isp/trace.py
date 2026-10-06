#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p7 调用链上溯/下钻 + 子系统定性（抓主干核心工具）。

为什么需要这个：2026-10-06 曾因"访问形态相似"把 **OSD 窗口定位**
误判成 **ISP 调参**（两者都写EP 块，形态一模一样）。
⇒ ★ **定性必须靠调用链上溯到收敛点，看入口函数的参数语义。**

用法:
  python trace.py up FUN_004b6894 [层数]      # 上溯（找入口）
  python trace.py down FUN_0017a658 [层数]    # 下钻（找落地）
  python trace.py qual FUN_003d0b4c          # 定性：看入口参数怎么用
  python trace.py fanin 0x2082                # 某 EP 段的所有写入者+上溯
  python trace.py settle FUN_004afe3c        # 自动上溯到收敛点并定性
"""
import re
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent.parent
PSEUDO = ROOT / "raw8" / "p7" / "ghidra" / "53_all_pseudocode.c"

HDR = re.compile(r"// ==== (\S+) @ (0x[0-9a-f]+) size=(\d+) ====")
CALL = re.compile(r"\b((?:thunk_)?FUN_[0-9a-f]+)\s*\(")

DB = {}          # name -> (addr, size, [lines])
REV = defaultdict(set)
FWD = defaultdict(set)


def load():
    if DB:
        return
    fn = None
    for line in PSEUDO.open(encoding="utf-8", errors="replace"):
        m = HDR.match(line)
        if m:
            fn = m.group(1)
            DB[fn] = [int(m.group(2), 16), int(m.group(3)), []]
            continue
        if fn:
            DB[fn][2].append(line)
            for t in CALL.findall(line):
                if t != fn:
                    REV[t].add(fn)
                    FWD[fn].add(t)


def show(name, tag=""):
    if name not in DB:
        return "%-18s @ ?????" % name
    a, s, _ = DB[name]
    return "%-18s @ 0x%-8x %5dB %s" % (name, a, s, tag)


def cmd_up(seed, depth=5):
    load()
    level = {seed}
    seen = {seed}
    print("=== 上溯: %s ===" % seed)
    for d in range(1, depth + 1):
        nxt = set()
        for t in sorted(level):
            for c in REV.get(t, set()):
                if c not in seen:
                    seen.add(c)
                    nxt.add(c)
        print("\n[d%d] %d 个" % (d, len(nxt)))
        for c in sorted(nxt, key=lambda x: DB.get(x, [0])[0])[:20]:
            print("   " + show(c))
        level = nxt
        if not level:
            print("   ← 收敛")
            break
    return sorted(seen)


def cmd_down(seed, depth=3):
    load()
    level = {seed}
    seen = {seed}
    print("=== 下钻: %s ===" % seed)
    for d in range(1, depth + 1):
        nxt = set()
        for t in sorted(level):
            for c in FWD.get(t, set()):
                if c not in seen:
                    seen.add(c)
                    nxt.add(c)
        print("\n[d%d] %d 个" % (d, len(nxt)))
        for c in sorted(nxt, key=lambda x: DB.get(x, [0])[0])[:20]:
            print("   " + show(c))
        level = nxt
        if not level:
            print("   ← 叶子")
            break


def cmd_qual(name):
    """定性：打印入口/核心函数里所有含算术的语句，看参数被怎么用。"""
    load()
    if name not in DB:
        print("不在伪代码里:", name)
        return
    a, s, lines = DB[name]
    print("=== %s @ 0x%x (%dB) 参数用法 ===" % (name, a, s))
    sig = [l for l in lines[:14] if l.strip() and not re.match(r"^\s*(undefined|int|uint|byte|char|short|long|float|double)\b", l)]
    for l in sig[:6]:
        print("  " + l.rstrip()[:100])
    print("  --- 关键运算 ---")
    n = 0
    for l in lines:
        t = l.strip()
        if not re.search(r"[a-zA-Z_]\w*\s*[+\-*/]=?\s*(param_|u?Var|iVar|local_|\d)", t):
            continue
        if re.match(r"^(undefined|int|uint|byte|char|short|long|float|double)\b.*;$", t):
            continue
        print("    " + t[:100])
        n += 1
        if n >= 22:
            break


def cmd_fanin(seg):
    load()
    print("=== EP 段 %s 的所有写入者 ===" % seg)
    wr = set()
    for name, (a, s, lines) in DB.items():
        for l in lines:
            if seg in l and re.search(r"\*\s*\(\s*(undefined4|uint|int)\s*\*\s*\)", l):
                m = re.search(r"=\s*([^=]+);", l)
                if m and re.search(r"\b(param_|uVar|iVar|local|puVar)", m.group(1)):
                    wr.add(name)
                    break
    for w in sorted(wr, key=lambda x: DB[x][0]):
        print("   " + show(w))
    return sorted(wr)


def cmd_settle(seed):
    """自动上溯到收敛点并逐层定性。"""
    load()
    seen = cmd_up(seed, 6)
    print("\n=== 收敛点定性 ===")
    for f in sorted(seen, key=lambda x: DB.get(x, [0])[0]):
        up = REV.get(f, set())
        if not up:
            print("\n### %s  (无上游=入口)" % f)
            cmd_qual(f)


if __name__ == "__main__":
    if not PSEUDO.exists():
        print("缺", PSEUDO)
        sys.exit(1)
    c = sys.argv[1] if len(sys.argv) > 1 else "up"
    if c == "up":
        cmd_up(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 5)
    elif c == "down":
        cmd_down(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 3)
    elif c == "qual":
        cmd_qual(sys.argv[2])
    elif c == "fanin":
        cmd_fanin(sys.argv[2] if len(sys.argv) > 2 else "0x2082")
    elif c == "settle":
        cmd_settle(sys.argv[2])
    else:
        print(__doc__)
