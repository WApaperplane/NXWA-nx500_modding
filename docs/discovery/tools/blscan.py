#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
T6 全固件 BL 调用点扫描器 —— 直接按 4 字节对齐读 ARM cond 字段判定 BL。
不依赖 capstone 连续反汇编, 因此不受"某段数据导致反汇编中断"影响;
命中后再交给 capstone 逐条验证。
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from armcap import fw, off, VA_BASE


def bl_sites(target, lo=0, hi=None):
    """返回所有 bl到 target 的指令虚拟地址。"""
    d = fw()
    n = len(d)
    if hi is None:
        hi = n
    hits = []
    tgt = target
    for o in range(lo - (lo % 4), hi, 4):
        if o + 4 > n:
            break
        w = struct.unpack_from("<I", d, o)[0]
        if (w & 0x0F000000) != 0x0B000000:      # cond==AL(0xE) 且 opcode==BL
            continue
        if (w >> 28) not in (0xE,):
            continue
        imm = w & 0x00FFFFFF
        if imm & 0x00800000:
            imm -= 0x1000000
        pc = o + VA_BASE
        dst = pc + 8 + (imm << 2)
        if dst == tgt:
            hits.append(pc)
    return hits


if __name__ == "__main__":
    t = int(sys.argv[1], 0)
    lo = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0
    hi = int(sys.argv[3], 0) if len(sys.argv) > 3 else len(fw())
    hs = bl_sites(t, lo, hi)
    print("bl %#x : %d hits" % (t, len(hs)))
    for h in hs:
        print("   0x%08x  (off 0x%06x)" % (h, off(h)))