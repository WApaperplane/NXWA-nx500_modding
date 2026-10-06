#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""T6b: 对每个 bl FUN_00524194 调用点解析 r1/r2/r3 -> type_info 对, 统计 (src,dst) 组合。"""
import sys, os, struct
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from armcap import fw, off, disasm, VA_BASE
from blscan import bl_sites

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
    o = off(va)
    if o < 0 or o + 8 > len(d):
        return None
    vp = struct.unpack_from("<I", d, o)[0]
    nmp = struct.unpack_from("<I", d, o + 4)[0]
    nm = cstr(nmp)
    return (vp, nmp, nm) if nm else None


def analyze(call_va):
    """向前回溯最多 12 条指令, 解析 r1/r2 字面池与 r3 立即数。"""
    r1 = r2 = None
    r3 = None
    for x in disasm(call_va - 48, 48):
        if x.address >= call_va:
            break
        op = x.op_str
        if x.mnemonic == "ldr" and "[pc" in op:
            try:
                imm = int(op.split("#")[1].rstrip("]"), 0)
            except Exception:
                continue
            pool = x.address + 8 + imm
            po = off(pool)
            if 0 <= po + 4 <= len(d):
                val = struct.unpack_from("<I", d, po)[0]
                reg = op.split(",")[0].strip()
                if reg == "r1":
                    r1 = val
                elif reg == "r2":
                    r2 = val
        elif x.mnemonic in ("mov", "movs") and op.startswith("r3,"):
            r3 = op.split(",")[-1].strip()
    t1 = tinfo(r1) if r1 else None
    t2 = tinfo(r2) if r2 else None
    return (t1[2] if t1 else None, t2[2] if t2 else None, r1, r2, r3)


if __name__ == "__main__":
    sites = bl_sites(0x80524194)
    print("dynamic_cast (FUN_00524194) 调用点 = %d\n" % len(sites))
    pairs = Counter()
    rec = []
    for a in sites:
        s, t, r1, r2, r3 = analyze(a)
        pairs[(s, t)] += 1
        rec.append((a, s, t, r3))
    print("(src_type, dst_type) 组合 TOP:")
    for (s, t), c in pairs.most_common(30):
        print("  %4d x  %-20s -> %s" % (c, s, t))
    print("\n涉及 3DLUT 模块的调用点:")
    for a, s, t, r3 in rec:
        if a < 0x80120000 and (s and "dlut" in s or (t and "dlut" in t)):
            print("   bl@0x%08x  %s -> %s  r3=%s" % (a, s, t, r3))