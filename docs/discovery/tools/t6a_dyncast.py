#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""T2-1: 穷尽枚举 FUN_00524194(__dynamic_cast) 的 138 个调用点, 解码其 type_info 实参。"""
import sys, os, struct, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from armcap import fw, off, disasm, VA_BASE

PS = r"D:/download/NX-KS2-88/raw8/p7/ghidra/53_all_pseudocode.c"
d = fw()


def cstr(va):
    o = off(va)
    if o < 0 or o >= len(d):
        return None
    e = d.find(b"\x00", o)
    if e < 0 or e - o > 120:
        return None
    try:
        s = d[o:e].decode("ascii")
    except Exception:
        return None
    return s if all(32 <= ord(c) < 127 for c in s) else None


def tinfo(va):
    """解码 type_info: {vptr, name}; 若为 __si_class_type_info 还有 base@+8。"""
    o = off(va)
    if o < 0 or o + 8 > len(d):
        return None
    vp = struct.unpack_from("<I", d, o)[0]
    nmp = struct.unpack_from("<I", d, o + 4)[0]
    nm = cstr(nmp)
    if nm is None:
        return None
    base = None
    if 0x80700000 <= vp < 0x80800000:
        bo = off(vp) + 8
        if 0 <= bo + 4 <= len(d):
            bv = struct.unpack_from("<I", d, bo)[0]
            if 0x80700000 <= bv < 0x80800000:
                bn = cstr(struct.unpack_from("<I", d, off(bv) + 4)[0])
                if bn:
                    base = (bv, bn)
    return (vp, nmp, nm, base)


txt = open(PS, encoding="utf-8", errors="replace").read()
lines = txt.split("\n")

# ---- 找出 FUN_00524194 的全部调用点(按伪代码行) ----
hits = []
cur_fn = None
for i, ln in enumerate(lines):
    m = re.match(r"//==== (FUN_[0-9a-f]+) @ (0x[0-9a-f]+) size=(\d+)", ln)
    if m:
        cur_fn = (m.group(1), int(m.group(2), 16), int(m.group(3)))
    if "FUN_00524194(" in ln and ln.strip().startswith("FUN_00524194(") is False:
        # 抓这一行里的实参
        call = ln[ln.index("FUN_00524194("):]
        hits.append((i + 1, cur_fn, call.strip()))

print("伪代码中 FUN_00524194 调用行数: %d" % len(hits))

# ---- 反汇编层面: 全text 扫描 bl 0x80524194 ----
print("\n" + "=" * 78)
print(" 全text 扫描 BL 0x80524194 (ARM 模式)")
print("=" * 78)
CODE_START, CODE_END = 0x000F0000, 0x0600000
md_bl = []
ins = disasm(VA_BASE + CODE_START, CODE_END - CODE_START)
cnt = 0
by_target = {}
for x in ins:
    if x.mnemonic == "bl" and x.op_str.strip() == "#0x80524194":
        cnt += 1
        md_bl.append(x.address)
print(" 反汇编窗口 0x%08x..0x%08x, BL 总数 = %d" % (VA_BASE + CODE_START, VA_BASE + CODE_END, cnt))

# 取每个调用点前8 条指令, 解析 r1/r2 的字面池 => type_info
print("\n每个调用点的 (r1, r2, r3) 实参解析:")
print("-" * 78)
rows = []
for a in md_bl:
    pre = disasm(a - 32, 32)
    r1 = r2 = None
    r3 = None
    for x in pre:
        if x.address >= a:
            break
        if x.mnemonic == "ldr" and "[pc" in x.op_str:
            pc = x.address + 8
            try:
                imm = int(x.op_str.split("#")[1].rstrip("]"), 0)
            except Exception:
                continue
            pool = pc + imm
            po = off(pool)
            if 0 <= po + 4 <= len(d):
                val = struct.unpack_from("<I", d, po)[0]
                reg = x.op_str.split(",")[0].strip()
                if reg == "r1":
                    r1 = val
                elif reg == "r2":
                    r2 = val
        if x.mnemonic in ("mov", "movs") and x.op_str.startswith("r3"):
            r3 = x.op_str.split(",")[-1].strip()
    t1 = tinfo(r1) if r1 else None
    t2 = tinfo(r2) if r2 else None
    n1 = t1[2] if t1 else None
    n2 = t2[2] if t2 else None
    rows.append((a, r1, n1, r2, n2, r3))

from collections import Counter
pairs = Counter()
for a, r1, n1, r2, n2, r3 in rows:
    pairs[(n1, n2)] += 1
print("\n(src_type, dst_type) 组合统计:")
for (n1, n2), c in pairs.most_common():
    print("  %4d x  %-22s -> %s" % (c, n1, n2))

print("\n前 20 个调用点明细:")
for a, r1, n1, r2, n2, r3 in rows[:20]:
    print("  bl@0x%08x  r1=%#010x(%s)  r2=%#010x(%s)  r3=%s" % (a, r1 or 0, n1, r2 or 0, n2, r3))