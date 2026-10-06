#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p7 veneer thunk 递归解链器 + EP 块功能分类器（抓主干工具 v2）。

背景：p7 有 4 字节定长 veneer（`movs Rd,Ra` + `b <real>`，nop 补齐），
Ghidra 识别不出，导致 `switch` 反编译成 `halt_baddata()`。
且 veneer 会**多层串联**（A -> B -> C -> 真实实现），必须递归追到底。

用法:
  python p7trace.py chain 0x3f3fa4        # 递归追 veneer 链，打印每层
  python p7trace.py chains 0x3f3f64 0x54 # 批量: 先扫表再逐个追链
  python p7trace.py classify              # EP 块功能分类（全量伪代码）
  python p7trace.py callers2 0x3f464c 3   # 递归反向: 谁(深度2)调用了 0x3f464c
"""
import sys
import re
import struct
import capstone
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent.parent
BIN = ROOT / "raw8" / "p7" / "p7_full.bin"
PSEUDO = ROOT / "raw8" / "p7" / "ghidra" / "53_all_pseudocode.c"

THUMB = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
THUMB.detail = False
B = None

NOP32 = 0x2FE1          # nop.w
MAXCHAIN = 12


def load():
    global B
    if B is None:
        B = BIN.read_bytes()
    return B


def ins2(a):
    """解 1 条 Thumb 指令(2字节)。"""
    o = list(THUMB.disasm(load()[a:a + 2], a))
    return o[0] if o else None


def veneer_at(a):
    """若 a 处是 veneer，返回 (dst, src, target)；否则 None。"""
    i1, i2 = ins2(a), ins2(a + 2)
    if not i1 or not i2:
        return None
    if i1.mnemonic != "movs" or i2.mnemonic != "b":
        return None
    try:
        d, s = [x.strip() for x in i1.op_str.split(",")]
        t = int(i2.op_str.replace("#", ""), 0)
    except Exception:
        return None
    return d, s, t


def resolve(a, depth=0, seen=None, out=None):
    """递归追 veneer 链，返回链条列表 [(addr, type, detail)]。"""
    if seen is None:
        seen = set()
    if out is None:
        out = []
    if depth > MAXCHAIN or a in seen:
        return out
    seen.add(a)
    v = veneer_at(a)
    if v:
        d, s, t = v
        out.append((a, "veneer", "%s, %s -> 0x%x" % (d, s, t)))
        return resolve(t, depth + 1, seen, out)
    # 不是 veneer => 真实实现，展开几条指令看看
    out.append((a, "impl", ""))
    return out


def cmd_chain(a):
    print("=== veneer 链 @ 0x%x ===" % a)
    for addr, kind, det in resolve(a):
        tag = "VENEER" if kind == "veneer" else "IMPL "
        print("  [%d] %s 0x%-9x %s" % (len(det) and 0 or 0, tag, addr, det))
    print()
    print("--- 末端实现反汇编 ---")
    ch = resolve(a)
    end = ch[-1][0]
    for i, ins in enumerate(THUMB.disasm(load()[end:end + 80], end)):
        print("  0x%-9x %-10s %s" % (ins.address, ins.mnemonic, ins.op_str))
        if i > 22:
            break


def cmd_chains(start, size):
    a = start
    end = start + size
    print("=== 批量追链 @ 0x%x..0x%x ===" % (start, end))
    rows = []
    while a < end:
        w = int.from_bytes(load()[a + 2:a + 4], "little")
        if w == NOP32:
            a += 4
            continue
        v = veneer_at(a)
        if v:
            d, s, t = v
            ch = resolve(a)
            last = ch[-1][0]
            depth = len(ch)
            # 末端实现里找 ldr/str 偏移（字段访问）
            offs = set()
            for ins in THUMB.disasm(load()[last:last + 60], last):
                m = re.search(r"\[(r\d+|sp)(?:,\s*#(0x[0-9a-f]+|\d+))?\]", ins.op_str)
                if m and m.group(2):
                    offs.add(int(m.group(2), 0))
            rows.append((a, "%s,%s" % (d, s), t, last, depth, sorted(offs)[:6]))
        a += 4
    print("  %-10s %-10s %-10s %-10s %-6s %s" % ("veneer", "mov", "hop1", "impl", "depth", "内存偏移"))
    for r in rows:
        print("  0x%-8x %-10s 0x%-8x 0x%-8x %-6d %s" % r)


HDR = re.compile(r"// ==== (\S+) @ (0x[0-9a-f]+) size=(\d+) ====")
EP = re.compile(r"0x(208[0-9a-f]{4,6})")


def load_pseudo():
    fn = None
    buf = []
    out = []
    for line in PSEUDO.open(encoding="utf-8", errors="replace"):
        m = HDR.match(line)
        if m:
            if fn:
                out.append((fn, buf))
            fn = m.group(1)
            buf = []
        else:
            buf.append(line)
    if fn:
        out.append((fn, buf))
    return out


# EP 子块名（来自实机 ioctl 探测的物理基址，见topics/nx500-arch.md）
EP_NAMES = {
    "0x20820": "top (0x20820000, 0x1c00)",
    "0x20821": "NOG (0x20821c00) + 邻块",
    "0x20826": "未命名块 0x20826000",
    "0x20830": "0x20830000 段 (x6)",
    "0x20830(5|6|9|c)": "0x20830xxx 段族",
    "0x20831": "0x20831000 段 (x18)",
    "0x20810": "0x20810000 段 (含 0x2081030c)",
    "0x20821": "NOG 0x20821c00",
}


def cmd_classify():
    """给 EP 块做功能分类：看访问模式（只读/只写/位域/浮点）。"""
    funcs = load_pseudo()
    print("=== EP 块功能分类 ===")
    blocks = defaultdict(lambda: {"wr": set(), "rd": set(),
                                  "flt": 0, "and": 0, "idx": 0, "n": 0})
    for fn, lines in funcs:
        txt = "".join(lines)
        if "0x208" not in txt:
            continue
        for l in lines:
            if "0x208" not in l:
                continue
            for a in EP.findall(l):
                # 取 0x208xxx 的 6 位十六进制 = 4KB 对齐的段
                s = a if len(a) >= 6 else a.ljust(6, "0")
                blk = blocks["0x" + s[:5]]
                blk["n"] += 1
                if re.search(r"\*\s*\(\s*(undefined4|uint|int|byte|undefined1)\s*\*\s*\)", l):
                    m = re.search(r"=\s*([^=]+);", l)
                    if m and re.search(r"\b(param_|uVar|iVar|local|puVar)", m.group(1)):
                        blk["wr"].add(fn)
                    else:
                        blk["rd"].add(fn)
                if re.search(r"0x(3f|40|bf)[0-9a-f]{6}", l):
                    blk["flt"] += 1
                if re.search(r"&\s*0x[0-9a-f]+", l):
                    blk["and"] += 1
                if re.search(r"\*\s*0x100|\*\s*\w+\s*\+", l):
                    blk["idx"] += 1
    print("  %-12s %-6s %-6s %-6s %-6s %-6s %-6s  %s" %
          ("EP段", "访问", "写", "读", "浮点", "位掩码", "索引", "备注"))
    for base in sorted(blocks):
        b = blocks[base]
        note = EP_NAMES.get(base, "")
        print("  %-12s %-6d %-6d %-6d %-6d %-6d %-6d  %s" %
              (base, b["n"], len(b["wr"]), len(b["rd"]),
               b["flt"], b["and"], b["idx"], note))


def cmd_callers2(target, maxdepth=2):
    """递归反向: 找谁调用了 target（直接+间接）。"""
    funcs = load_pseudo()
    name_rx = re.compile(r"\b" + re.escape(target) + r"\s*\(")
    rev = defaultdict(set)
    for fn, lines in funcs:
        for l in lines:
            m = re.search(r"\b(FUN_[0-9a-f]+|thunk_FUN_[0-9a-f]+)\s*\(", l)
            if m:
                rev[m.group(1)].add(fn)
    seen = {target}
    level = [target]
    print("=== 反向调用 (深度<=%d) 目标 %s ===" % (maxdepth, target))
    for d in range(1, maxdepth + 1):
        nxt = []
        for t in level:
            cs = rev.get(t, set())
            print("  [d%d] %s <- %d: %s" % (d, t, len(cs), sorted(cs)[:12]))
            for c in cs:
                if c not in seen:
                    seen.add(c)
                    nxt.append(c)
        level = nxt
        if not level:
            break


if __name__ == "__main__":
    if not BIN.exists():
        print("缺 p7_full.bin:", BIN)
        sys.exit(1)
    c = sys.argv[1] if len(sys.argv) > 1 else "classify"
    if c == "chain":
        cmd_chain(int(sys.argv[2], 0))
    elif c == "chains":
        cmd_chains(int(sys.argv[2], 0), int(sys.argv[3], 0))
    elif c == "classify":
        cmd_classify()
    elif c == "callers2":
        cmd_callers2(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 2)
    else:
        print(__doc__)
