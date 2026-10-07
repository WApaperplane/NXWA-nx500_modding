#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
T6e: 穷尽搜索对 st3dlutParam(+0x20/+0x21/+0x22/+0x40) 的 strb 写。
思路: 这些字段的唯一权威载体是全局块 0x81433cc8 (768字节)。
  1) 找所有把 0x81433cc8 装入寄存器的指令 (litref)  -> 已知 10 处, 全是传参
  2) 但写入可能通过 "基址+偏移" 的通用参数加载器 (memcpy/循环) 完成,
     所以还要找所有对 0x81433cc8..0x81433fc8 区间的 strb/str。
本脚本用 capstone 全镜像线性反汇编不可行(有数据段), 改用 ARM 编码匹配:
  STRB imm: cond 01 0 1 P U 1 W L Rn Rt imm12   (bit22=1)
  STR  imm: cond 01 0 1 P U 0 W L Rn Rt imm12   (bit22=0, bit24 P=1)
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from armcap import fw, off, VA_BASE, disasm
from fmap import func_of
from litref import literal_xrefs

TARGETS = {
    0x20: "byte B", 0x21: "byte C", 0x22: "byte D", 0x40: "byte A(via +0x10)",
}


def find_strb_reg(lo=0, hi=0x00C40000):
    """返回所有 (addr, rn, rt, offset, is_strb)"""
    d = fw()
    n = len(d)
    out = []
    for o in range(lo - (lo % 4), min(hi, n), 4):
        w = struct.unpack_from("<I", d, o)[0]
        if w >> 28 != 0xE:
            continue
        if (w & 0x0E000000) != 0x04000000:     # bits27-25 == 010
            continue
        P = (w >> 24) & 1
        U = (w >> 23) & 1
        I = (w >> 22) & 1
        B = (w >> 21) & 1
        W = (w >> 20) & 1
        L = (w >> 19) & 1
        if P != 1 or W != 0:
            continue
        if L == 1:
            continue                              # 只看存储
        rn = (w >> 16) & 0xF
        rt = (w >> 12) & 0xF
        imm = w & 0xFFF
        offset = imm if U else -imm
        if not B:
            out.append((o + VA_BASE, rn, rt, offset, bool(I)))
        else:
            out.append((o + VA_BASE, rn, rt, "reg", bool(I)))
    return out


if __name__ == "__main__":
    print("=" * 78)
    print(" 所有 strb/str 立即数偏移 落在 0x20/0x21/0x22/0x40 的指令")
    print("=" * 78)
    hits = find_strb_reg()
    sel = [x for x in hits if x[3] in TARGETS]
    print("总 str/strb(imm) 数: %d ;偏移命中 4 个目标: %d\n" % (len(hits), len(sel)))

    # 只报告 3DLUT 模块内的(0x8011c000..0x80120000)
    for a, rn, rt, offv, isb in sel:
        if 0x80118000 <= a <= 0x80122000:
            f = func_of(off(a))
            ins = disasm(a, 4)[0]
            print("  0x%08x %-6s %-26s  <- %s | %s"
                  % (a, ins.mnemonic, ins.op_str, TARGETS[offv],
                     ("%s @0x%06x" % (f[0], f[1])) if f else "?"))