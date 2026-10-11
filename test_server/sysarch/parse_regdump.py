#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""parse_regdump.py —— 解析 lutapi 的 3D LUT 4KB 窗口 dump（离线，纯文本处理）

来源文件：regdump_*.txt / load_*.log（lutapi 输出，含 "3D LUT @ 0x2082b000 size=4096"
+ 寄存器行 "+0xNNN = 0xVVVVVVVV"；只列非零项）。

功能：
  1. 提取全部寄存器项（去重）→ 统计非零结构（按 16 单元 × 64 u32 模型分类）
  2. --bin 导出 4KB 二进制（未列出项按 0）
  3. --diff 与另一份（4KB bin 或另一 dump 文本）逐 u32 对比，输出差异分类明细

用法：
  python parse_regdump.py regdump_t6.txt
  python parse_regdump.py load_id1.log --bin id1.bin
  python parse_regdump.py load_id1.log --diff regdump_after.txt
"""
import argparse
import re
import struct
from collections import Counter

REG_RE = re.compile(r'\+0x([0-9a-fA-F]{3})\s*=\s*0x([0-9a-fA-F]{8})')


def parse_dump(fn):
    txt = open(fn, encoding='utf-8', errors='replace').read()
    regs = {}
    for m in REG_RE.finditer(txt):
        regs[int(m.group(1), 16)] = int(m.group(2), 16)
    return regs


def to4k(regs):
    buf = bytearray(4096)
    for off, v in regs.items():
        if off < 4096:
            struct.pack_into('<I', buf, off, v)
    return bytes(buf)


def classify(regs):
    """按 16 单元（每 0x100）模型分类统计"""
    c = Counter()
    for off, v in regs.items():
        k, o = off // 0x100, off % 0x100
        if k > 15:
            c['out-of-window'] += 1
            continue
        if o == 0x00:
            c[f'+0x00 OnOff = {v:#x}'] += 1
        elif o == 0x04:
            c[f'+0x04 Cfg = {v:#x}'] += 1
        elif o == 0x08:
            c[f'+0x08 = {v:#x}'] += 1
        elif o == 0x0c:
            c[f'+0x0c LUT0 = {v:#010x}'] += 1
        elif o == 0x10:
            c[f'+0x10 LUT1 = {v:#010x}'] += 1
        elif 0x14 <= o <= 0xf8:
            c[f'fill(0x14..0xf8) = {v:#x}'] += 1
        elif o == 0xfc:
            c[f'+0xfc sentinel = {v:#x}'] += 1
        else:
            c[f'other +{o:#x} = {v:#x}'] += 1
    return c


def unit_table(regs, key_offsets):
    print(f'  {"单元":<4}', ' '.join(f'+0x{o:03x}' for o in key_offsets))
    for k in range(16):
        vals = ' '.join(
            (f'{regs[k*0x100+o]:08x}' if (k*0x100+o) in regs else '--------')
            for o in key_offsets)
        print(f'  单元{k:<2d} {vals}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dump')
    ap.add_argument('--bin', dest='binout')
    ap.add_argument('--diff', dest='other')
    args = ap.parse_args()

    regs = parse_dump(args.dump)
    print(f'# {args.dump}: 提取 {len(regs)} 个非零项')
    print()
    print('## 结构分类（16 单元 × 64 u32 模型）:')
    for k, v in sorted(classify(regs).items()):
        print(f'   {k}: {v}')
    print()
    print('## 头部速览:')
    unit_table(regs, [0x00, 0x04, 0x08, 0x0c, 0x10])

    if args.binout:
        data = to4k(regs)
        open(args.binout, 'wb').write(data)
        import hashlib
        print()
        print(f'## 导出 {args.binout} (4KB) md5={hashlib.md5(data).hexdigest()}')

    if args.other:
        if args.other.endswith('.bin'):
            xb = open(args.other, 'rb').read()
            name_b = args.other
        else:
            xb = to4k(parse_dump(args.other))
            name_b = args.other
        xa = to4k(regs)
        diffs = [i for i in range(0, 4096, 4) if xa[i:i+4] != xb[i:i+4]]
        print()
        print(f'## diff vs {name_b}: {len(diffs)} 个 u32 差异')
        c = Counter()
        ex = {}
        for o in diffs:
            k, r = o // 0x100, o % 0x100
            a = struct.unpack_from('<I', xa, o)[0]
            b = struct.unpack_from('<I', xb, o)[0]
            if r == 0x08:
                key = '+0x08'
            elif r == 0x0c:
                key = '+0x0c(LUT0)'
            elif 0x14 <= r <= 0xf8:
                key = 'fill(0x14..0xf8)'
            elif r == 0xfc:
                key = '+0xfc(sentinel)'
            else:
                key = f'other +{r:#x}'
            c[key] += 1
            ex.setdefault(key, (o, k, a, b))
        for kk, vv in sorted(c.items()):
            o, k, a, b = ex[kk]
            print(f'   {kk}: {vv} 处   例: 单元{k} @+0x{o:03x}  '
                  f'A=0x{a:08x} B=0x{b:08x}')


if __name__ == '__main__':
    main()
