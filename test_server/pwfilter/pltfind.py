#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pltfind.py — 找 so 里的 PLT 条目与对应符号（用于反推 GOT 槽）

用法: python pltfind.py <so> [关键词...]
"""
import struct, sys, re

path = sys.argv[1]
kws = [k.lower() for k in sys.argv[2:]]
d = open(path, 'rb').read()

e_shoff, = struct.unpack_from('<I', d, 32)
e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<HHH', d, 46)
secs = []
for i in range(e_shnum):
    o = e_shoff + i * e_shentsize
    v = struct.unpack_from('<IIIIIIIIII', d, o)
    secs.append(dict(name=v[0], type=v[1], addr=v[3], off=v[4], size=v[5],
                     link=v[6], entsize=v[9], info=v[7]))
st = secs[e_shstrndx]['off']
def nm(n):
    e = d.index(b'\0', st + n)
    return d[st + n:e].decode('utf-8', 'replace')

dynsym = next(s for s in secs if nm(s['name']) == '.dynsym')
dynstr = next(s for s in secs if nm(s['name']) == '.dynstr')
relplt = next((s for s in secs if nm(s['name']) == '.rel.plt'), None)
plt = next((s for s in secs if nm(s['name']) == '.plt'), None)
got = next((s for s in secs if nm(s['name']) == '.got'), None)
print('段: .plt=%s .rel.plt=%s .got=%s(0x%x+%d)' % (
    hex(plt['addr']) if plt else '-',
    hex(relplt['addr']) if relplt else '-',
    nm(got['name']) if got else '-',
    got['addr'] if got else 0, got['size'] if got else 0))

# 动态符号表
SYMS = []
for i in range(dynsym['size'] // 16):
    o = dynsym['off'] + i * 16
    st_name, st_value, st_size, st_info, st_other, st_shndx = \
        struct.unpack_from('<IIIBBH', d, o)
    e = d.index(b'\0', dynstr['off'] + st_name)
    SYMS.append((st_value, d[dynstr['off'] + st_name:e].decode('utf-8', 'replace'),
                 st_shndx, st_info))

# .rel.plt 每一项4 字节 ARM：offset(24) | info(8)
ents = []
if relplt:
    for i in range(relplt['size'] // 8):
        r_off, r_info = struct.unpack_from('<II', d, relplt['off'] + i * 8)
        symidx = r_info >> 8
        name = SYMS[symidx][1] if symidx < len(SYMS) else '?'
        rel = i + 1          # .plt[0] 是 PLT0，条目从 1 开始
        ents.append((rel, r_off, name))

print('\n.plt 条目共 %d 个' % len(ents))
if kws:
    hit = [e for e in ents if any(k in e[2].lower() for k in kws)]
    print('命中 %d:' % len(hit))
    for rel, off, nmv in hit:
        pltaddr = plt['addr'] + rel * 12 if plt else 0
        print('  PLT 0x%08x  GOT[0x%08x]  %s' % (pltaddr, off, nmv))
else:
    for rel, off, nmv in ents[:60]:
        print('  PLT 0x%08x  GOT[0x%08x]  %s' % (
            plt['addr'] + rel * 12 if plt else 0, off, nmv))

# ★ 关键：查有没有 ep_* / reg_info / d5_ep_* 相关的 import
print('\n=== ★ ISP/EP 相关 import ===')
for rel, off, nmv in ents:
    if re.search(r'ep_|reg_info|d5_ep|lut|nog|mixer|idd|ipcc', nmv, re.I):
        print('  PLT 0x%08x  GOT[0x%08x]  %s' % (
            plt['addr'] + rel * 12 if plt else 0, off, nmv))
