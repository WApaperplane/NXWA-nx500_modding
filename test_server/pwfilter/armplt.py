#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
armplt.py — ARM .so 静态分析器（NX500 / libudd5.so 专用，零外部依赖除 capstone）

已验证事实（2026-10-04）:
  - libudd5.so 是 **纯 ARM 模式**（零 Thumb 混排）→ 必须用 CS_MODE_ARM
  - .plt 区 = 0x830c..0x91c0，12 字节/条，共 304 条，模式:
        add ip, pc, #0 / add ip, ip, #0x4b000 / ldr pc, [ip, #imm]!
    GOT slot = (plt+8) + 0x4b000 + imm
  - .rodata 0x49c08起，.data 文件偏移 0x4c8e0，.bss 0x4dd8c
  - dynsym 文件偏移 0x11e4 / 552 项；dynstr 偏移 0x3464

用法:
  python armplt.py plts                # 列出全部 304 条 PLT 映射
  python armplt.py immap               # 导出 PLT/GOT/符号 全映射到 json
  python armplt.py dis <函数名>        # 反汇编某个导出符号
  python armplt.py callsto <函数名>     # 谁调用了它（扫 .text 全量bl）
  python armplt.py str <关键字>         # 搜 .rodata 字符串
"""
import struct
import sys
import re
import json

try:
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
except ImportError:
    sys.exit('需要 capstone: python -m pip install capstone --target .')

# ---- NX500 libudd5.so 布局常量 ----
DS_OFF, DS_SZ = 0x11e4, 0x2280
ST_OFF = 0x3464
TEXT_OFF, TEXT_SIZE = 0x91c0, 0x40a40
PLT_LO, PLT_HI = 0x830c, 0x91c0
RODATA_OFF, RODATA_SIZE = 0x49c08, 0x2600
RELA = ((0x6b88, 0xdb8), (0x7940, 0x9c0))
GOT_BIAS = 0x4b000


def load(path='libudd5.so'):
    return open(path, 'rb').read()


def dynstr(d, x):
    e = d.index(b'\x00', ST_OFF + x)
    return d[ST_OFF + x:e].decode('latin1')


def symbols(d):
    """返回 {name: (addr, size, type)}"""
    out = {}
    for i in range(DS_SZ // 16):
        o = DS_OFF + i * 16
        sn, sv, ssz, si, so, sh = struct.unpack_from('<IIIBBH', d, o)
        if not sn:
            continue
        t = si & 0xf
        out.setdefault(dynstr(d, sn), (sv, ssz, {1: 'OBJ', 2: 'FUNC'}.get(t, str(t))))
    return out


def by_addr(d):
    out = {}
    for name, (sv, ssz, t) in symbols(d).items():
        if t == 'FUNC':
            out.setdefault(sv, (name, ssz))
    return out


def got_map(d):
    g = {}
    for off, size in RELA:
        for i in range(size // 8):
            o, info = struct.unpack_from('<II', d, off + i * 8)
            g[o] = dynstr(d, struct.unpack_from('<I', d, DS_OFF + (info >> 8) * 16)[0])
    return g


def plt_map(d):
    """PLT 跳板地址 -> 目标符号名"""
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    g = got_map(d)
    m = {}
    for plt in range(PLT_LO, PLT_HI, 4):
        ins = list(md.disasm(d[plt:plt + 4], plt))
        if not ins or ins[0].mnemonic != 'add' or 'ip' not in ins[0].op_str:
            continue
        j = list(md.disasm(d[plt + 4:plt + 8], plt + 4))
        if not j or j[0].mnemonic != 'add' or hex(GOT_BIAS) not in j[0].op_str:
            continue
        k = list(md.disasm(d[plt + 8:plt + 12], plt + 8))
        if not k or k[0].mnemonic != 'ldr' or 'pc' not in k[0].op_str:
            continue
        mm = re.search(r'#(0x[0-9a-f]+|\d+)', k[0].op_str)
        if mm:
            slot = (plt + 8) + GOT_BIAS + int(mm.group(1), 0)
            m[plt] = g.get(slot, '?GOT_%x' % slot)
    return m


def disasm(d, name, syms=None, maxb=None):
    syms = syms or symbols(d)
    if name not in syms:
        return None
    v, sz, t = syms[name]
    if t != 'FUNC':
        return None
    sz = maxb or sz
    sym2 = by_addr(d)
    p = plt_map(d)
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    lines = ['%s @0x%08x size=%d' % (name, v, sz), '=' * 72]
    for ins in md.disasm(d[v:v + sz], v):
        ann = ''
        if ins.mnemonic.startswith('b') and ins.mnemonic != 'bic' and '#' in ins.op_str:
            try:
                t2 = int(ins.op_str.split('#')[-1], 0)
            except ValueError:
                t2 = None
            if t2 is not None:
                if t2 in sym2:
                    ann = '   ; %s' % sym2[t2][0]
                elif t2 in p:
                    ann = '   ; [plt]%s' % p[t2]
                elif t2 in got_map(d):
                    ann = '   ; %s' % got_map(d)[t2]
        lines.append('%08x  %-8s %-30s%s' % (ins.address, ins.mnemonic, ins.op_str, ann))
    return '\n'.join(lines)


def callsto(d, target):
    """扫 .text 全量找 bl/blx 到 target"""
    syms = by_addr(d)
    p = plt_map(d)
    hits = []
    for addr, (n, sz) in syms.items():
        if n == target:
            target = addr
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    for ins in md.disasm(d[TEXT_OFF:TEXT_OFF + TEXT_SIZE], TEXT_OFF):
        if ins.mnemonic in ('bl', 'blx') and '#' in ins.op_str:
            try:
                t2 = int(ins.op_str.split('#')[-1], 0)
            except ValueError:
                continue
            if t2 == target or p.get(t2) == target:
                caller = None
                for a, (nn, ss) in syms.items():
                    if a <= ins.address < a + ss:
                        caller = '%s+0x%x' % (nn, ins.address - a)
                hits.append((ins.address, caller or '?'))
    return hits


def strings(d, kw):
    out = set()
    for m in re.finditer(rb'[\x20-\x7e]{4,}', d[RODATA_OFF:RODATA_OFF + RODATA_SIZE]):
        s = m.group().decode('latin1')
        if kw.lower() in s.lower():
            out.add(s)
    return sorted(out)


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'plts'
    # 默认库文件；也可作为最后一个参数指定
    lib = 'libudd5.so'
    if cmd not in ('plts', 'immap') and len(sys.argv) > 3 and sys.argv[-1].endswith('.so'):
        lib = sys.argv.pop()
    d = load(lib)
    if cmd == 'plts':
        m = plt_map(d)
        for a in sorted(m):
            print('0x%04x -> %s' % (a, m[a]))
        print('# 共 %d 条' % len(m))
    elif cmd == 'immap':
        json.dump({'plt': {'0x%x' % k: v for k, v in plt_map(d).items()},
                   'got': {'0x%x' % k: v for k, v in got_map(d).items()}},
                  open('libudd5_plt.json', 'w'), indent=1, ensure_ascii=False)
        print('-> libudd5_plt.json')
    elif cmd == 'dis':
        print(disasm(d, sys.argv[2]) or 'not found')
    elif cmd == 'callsto':
        for a, c in callsto(d, sys.argv[2]):
            print('  0x%08x  in %s' % (a, c))
    elif cmd == 'str':
        for s in strings(d, sys.argv[2]):
            print('', s)
    elif cmd == 'raw':
        # 用法: raw <起始地址> [长度]   —— 解任意地址区间（PLT 未解出的静态函数用）
        start = int(sys.argv[2], 0)
        n = int(sys.argv[3], 0) if len(sys.argv) > 3 else 128
        sym2 = by_addr(d)
        p = plt_map(d)
        g = got_map(d)
        md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
        for ins in md.disasm(d[start:start + n], start):
            ann = ''
            if ins.mnemonic.startswith('b') and ins.mnemonic != 'bic' and '#' in ins.op_str:
                try:
                    t2 = int(ins.op_str.split('#')[-1], 0)
                except ValueError:
                    t2 = None
                if t2 in sym2:
                    ann = '   ; %s' % sym2[t2][0]
                elif t2 in p:
                    ann = '   ; [plt]%s' % p[t2]
                elif t2 in g:
                    ann = '   ; %s' % g[t2]
            print('%08x  %-8s %-30s%s' % (ins.address, ins.mnemonic, ins.op_str, ann))
