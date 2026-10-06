#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
全固件字面池引用扫描器: 找出所有 `ldr rX, [pc, #imm]` 装入目标 32 位值的指令。
用于回答 "谁引用了全局符号 X"。
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from armcap import fw, off, VA_BASE

# ARM LDR (立即数, PC 相对) 编码位域 —— 由 capstone 实测反推, 不手写推导:
#   e59f305c -> ldr r3, [pc, #0x5c]   (Rn=pc, Rt=r3)
#   bit27-25 == 010 (0x04000000), bit22 I==0, bit21 B==0, bit19 L==1, bit24 P==1
#   bit20 W 可为 1(P=1,W=1 即 LDRT, ARMv7 非特权加载, capstone 仍显示 ldr)
def is_ldr_imm(word):
    if (word & 0x0E000000) != 0x04000000:   # bits27-25 == 010
        return False
    if word & 0x00400000:                   # bit22 I==0 -> 立即数偏移
        return False
    if word & 0x00200000:                   # bit21 B==0
        return False
    if not (word & 0x00080000):             # bit19 L==1 -> LDR
        return False
    return True


def literal_xrefs(value, lo=0x000F0000, hi=0x0600000):
    d = fw()
    n = len(d)
    hits = []
    for o in range(lo - (lo % 4), min(hi, n), 4):
        w = struct.unpack_from("<I", d, o)[0]
        if not is_ldr_imm(w):
            continue
        U = (w >> 23) & 1
        P = (w >> 24) & 1
        imm = w & 0xFFF
        add = (U == 1) == (P == 1)
        if not P:
            continue                      # 只看 PC 相对
        pc = o + VA_BASE
        addr = (pc + 8 + imm) if add else (pc + 8 - imm)
        po = off(addr)
        if 0 <= po + 4 <= n and struct.unpack_from("<I", d, po)[0] == value:
            rn = (w >> 16) & 0xF      # Rn = bit19-16
            rt = (w >> 12) & 0xF      # Rt = bit15-12
            hits.append((pc, rt, rn, addr))
    return hits


def func_of(pc):
    """用 Ghidra 02_functions.txt 定位所属函数 (委托 fmap, 避免列序解析重复出错)。"""
    from fmap import func_of as _f
    r = _f(pc)
    return (r[0], r[1], r[2]) if r else None


if __name__ == "__main__":
    v = int(sys.argv[1], 0)
    lo = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x000F0000
    hi = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x0600000
    xs = literal_xrefs(v, lo, hi)
    print("字面池引用 %#010x : %d 处" % (v, len(xs)))
    for pc, rt, rn, pool in xs:
        f = func_of(off(pc))          # fmap 用文件偏移
        fs = ("%s @0x%06x (size %d)" % f) if f else "?"
        print("  ldr r%-2d, [pc,#..] @0x%08x  (pool %#010x = %#010x)  in %s"
              % (rt, pc, pool, v, fs))