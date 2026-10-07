#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
T6d: 穷尽枚举 32 位立即数构造 (MOVW / MOVT / 纯 ARM MOV 立即数),
     筛出高 16 位匹配的目标家族。

编码依据 (由 capstone 实测反推, 禁止手写推导):
  0xe300211e -> movw r2, #0x11e    bits27-20 = 0x030
  0xe3403104 -> movt r3, #0x104    bits27-20 = 0x034
  0xe3a03002 -> mov  r3, #2(纯立即数)
  imm16 = ((w>>16)&0xF)<<12 | (w&0xFFF)
  MOVT: result = imm16<<16 | (前一条 movw/imm 的低16)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from armcap import fw, off, VA_BASE, disasm
from fmap import func_of

CODE_LO, CODE_HI = 0x00000000, 0x00C40000    # 整镜像 (段布局 0..0xc3ffff)


def _imm12(w):
    return ((w >> 16) & 0xF) << 12 | (w & 0xFFF)


def _rd(w):
    return (w >> 12) & 0xF


def _cond_ok(w):
    return (w >> 28) in (0xE,)


def scan_pairs():
    """返回 [(mov_va, movt_va, full32, rd)]"""
    d = fw()
    n = len(d)
    out = []
    for o in range(CODE_LO - (CODE_LO % 4), min(CODE_HI, n), 4):
        w = struct.unpack_from("<I", d, o)[0]
        if not _cond_ok(w):
            continue
        if (w & 0x0FF00000) != 0x03400000:   # MOVT
            continue
        hi = _imm12(w)
        rd = _rd(w)
        if o < 4:
            continue
        pw = struct.unpack_from("<I", d, o - 4)[0]
        if not _cond_ok(pw):
            continue
        if _rd(pw) != rd:
            continue
        if (pw & 0x0FF00000) == 0x03000000:      # MOVW  (e3 0 0)
            lo = _imm12(pw)
        elif (pw & 0x0FF00000) == 0x03A00000:     # MOV (imm) (e3 a 0)
            rot = ((pw >> 8) & 0xF) * 2
            v = pw & 0xFF
            lo = (((v >> rot) | (v << (32 - rot))) & 0xFFFFFFFF) if rot else v
        else:
            continue
        out.append((o - 4 + VA_BASE, o + VA_BASE, ((hi << 16) | (lo & 0xFFFF)) & 0xFFFFFFFF, rd))
    return out


if __name__ == "__main__":
    want = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x104
    pairs = scan_pairs()
    sel = [x for x in pairs if ((x[2] >> 16) & 0xFFFF) == want]
    print("mov+movt 对总数: %d ;  高16 == 0x%03x: %d 个" % (len(pairs), want, len(sel)))
    agg = {}
    for mw, mt, full, rd in sel:
        f = func_of(off(mw))
        agg.setdefault(full, []).append((mw, f[0] if f else "?"))
    for full in sorted(agg):
        lst = agg[full]
        print("\n  == 0x%08x   (%d 处)" % (full, len(lst)))
        for mw, fn in lst[:20]:
            print("     mov@0x%08x  in %s" % (mw, fn))
        if len(lst) > 20:
            print("     ... 共 %d 处" % len(lst))