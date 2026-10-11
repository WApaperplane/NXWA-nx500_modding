#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_mmio.py —— MMIO 窗口全镜像引用扫描器（字节级，不依赖反汇编器）

扫描目标：给定物理地址窗口（默认 0x2082b000 3DLUT 块，范围 [0x20800000,0x20900000)）
的两类引用：
  A) 字面量：u32 值落在范围内的字节序列（含任何对齐相位；字面量池/裸常量）
  B) movw/movt 指令构造：movt #0x2082（高位）+ 配对 movw（低 16 位）
     另列：裸 movt #0x2082 命中点（供人工核对配对）

用法：python scan_mmio.py <binary> [--va 0x80000000] [--lo 0x20800000] [--hi 0x20900000]
输出：stdout（含上下文 hexdump）；建议重定向存档。
"""
import array
import argparse
import struct
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('binary')
    ap.add_argument('--va', type=lambda x: int(x, 16), default=None,
                    help='文件偏移→VA 基址（如 p7 用 0x80000000）')
    ap.add_argument('--lo', type=lambda x: int(x, 16), default=0x2082a000)
    ap.add_argument('--hi', type=lambda x: int(x, 16), default=0x2082d000)
    ap.add_argument('--noalign', action='store_true', help='关闭 4 字节对齐过滤')
    args = ap.parse_args()

    data = open(args.binary, 'rb').read()
    n = len(data)
    print(f"# scan_mmio: {args.binary}  size={n} (0x{n:x})")
    print(f"# range = [0x{args.lo:08x}, 0x{args.hi:08x})  va_base={args.va}")

    def fa(off):
        if args.va is not None:
            return f"file 0x{off:06x} / VA 0x{args.va + off:08x}"
        return f"file 0x{off:06x}"

    def hexdump(off, span=48):
        lo = max(0, off - span // 2)
        hi = min(n, off + span)
        b = data[lo:hi]
        s = ' '.join(f"{x:02x}" for x in b)
        return s

    # ---------- A) 字面量扫描 ----------
    hits_a = []
    hi16_lo = args.lo >> 16
    hi16_hi = args.hi >> 16  # 闭区间包含
    for hi16 in range(hi16_lo, hi16_hi + 1):
        pat = struct.pack('<H', hi16 & 0xFFFF)
        start = 0
        while True:
            m = data.find(pat, start)
            if m < 0:
                break
            start = m + 1
            p = m - 2  # u32 起点
            if p < 0 or p + 4 > n:
                continue
            if not args.noalign and (p & 3) != 0:
                continue
            v = int.from_bytes(data[p:p + 4], 'little')
            if args.lo <= v < args.hi:
                hits_a.append((p, v))

    # 去重（同一位置可能被相邻搜索重复命中）
    hits_a = sorted(set(hits_a))
    print(f"\n## A) 字面量 u32 in range —— {len(hits_a)} 处（4 对齐过滤={not args.noalign}）")
    for p, v in hits_a:
        print(f"  [{fa(p)}] = 0x{v:08x}   ctx: {hexdump(p, 24)}")

    # ---------- B) movw/movt/mov 扫描 ----------
    m = n // 4
    words = array.array('I')
    words.frombytes(data[:m * 4])

    def ror32(v, r):
        r &= 31
        return ((v >> r) | (v << (32 - r))) & 0xFFFFFFFF if r else v

    low_list = []   # (pos, rd, val) —— 低 16 位构造：MOVW 或 MOV(imm8-ror)
    movt_list = []
    for i, w in enumerate(words):
        m27 = w & 0x0FE00000
        if m27 == 0x03000000:      # movw
            imm16 = ((w >> 16) & 0xF) << 12 | (w & 0xFFF)
            rd = (w >> 12) & 0xF
            low_list.append((i * 4, rd, imm16, 'movw'))
        elif m27 == 0x03A00000 and ((w >> 16) & 0xF) == 0:  # mov rd, #imm8 ror 2*rot (Rn=0)
            rot = (w >> 8) & 0xF
            val = ror32(w & 0xFF, rot * 2)
            rd = (w >> 12) & 0xF
            low_list.append((i * 4, rd, val, 'mov'))

    # movt 单独扫（mask 0x0FE00000 与 mov 有重叠风险：movt = bits27:21 = 0011010 → 0x03400000）
    for i, w in enumerate(words):
        if (w & 0x0FE00000) == 0x03400000:  # movt (bits27:20=00110100)
            imm16 = ((w >> 16) & 0xF) << 12 | (w & 0xFFF)
            rd = (w >> 12) & 0xF
            movt_list.append((i * 4, rd, imm16))

    # B1: movt #0x2082 命中 + 配对低值构造
    print(f"\n## B1) movt #0x2082 命中 + 配对低 16 位构造（回溯 ≤64 条指令，同 Rd）")
    tgt_hi = 0x2082
    low_by_rd = {}
    for (pos, rd, val, kind) in low_list:
        low_by_rd.setdefault(rd, []).append((pos, val, kind))
    for k in low_by_rd:
        low_by_rd[k].sort()

    n_b1 = 0
    n_pair = 0
    inrange = []
    for pos, rd, imm16 in movt_list:
        if imm16 != tgt_hi:
            continue
        n_b1 += 1
        # 回溯找同 Rd 的最近低值构造（≤64 条 = 256B）
        pair = None
        cands = low_by_rd.get(rd, [])
        # 二分找 pos 之前最近的
        best = None
        for (wp, wval, wkind) in cands:
            if wp < pos and pos - wp <= 256:
                if best is None or wp > best[0]:
                    best = (wp, wval, wkind)
        pair = best
        if pair:
            n_pair += 1
            val = (imm16 << 16) | pair[1]
            in_rng = args.lo <= val < args.hi
            if in_rng:
                inrange.append((pos, val, rd, pair))
            flag = '★IN-RANGE' if in_rng else ''
            print(f"  [{fa(pos)}] movt r{rd},#0x2082 + {pair[2]} r{rd},#0x{pair[1]:04x}"
                  f" @ {fa(pair[0])}  => 0x{val:08x}  {flag}")
        else:
            print(f"  [{fa(pos)}] movt r{rd},#0x2082  (配对低值未在 256B 内)")
    print(f"  (movt#0x2082 命中 {n_b1}；配对成功 {n_pair}；★IN-RANGE {len(inrange)})")

    # B1b: 直接列出"低 16 位 ∈ 窗口低段 [a000, cfff]"的低值构造（无论配对与否），供交叉
    print(f"\n## B1b) 低值构造（mov/movw）值 ∈ [0xa000, 0xd000) —— 潜在窗口基址低半部")
    n_b1b = 0
    for (pos, rd, val, kind) in low_list:
        if 0xa000 <= val < 0xd000:
            n_b1b += 1
            print(f"  [{fa(pos)}] {kind} r{rd},#0x{val:04x}   ctx: {hexdump(pos, 16)}")
    print(f"  (低段构造命中 {n_b1b})")

    print("\n# done")


if __name__ == '__main__':
    main()
