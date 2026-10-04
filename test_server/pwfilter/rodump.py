#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rodump.py — 提取 .rodata 里的字符串 + 定位属性 ID 表

用法: python rodump.py <so> [关键词...]
"""
import struct, re, sys

path = sys.argv[1]
kws = [k.lower() for k in sys.argv[2:]]
d = open(path, 'rb').read()

# 段表
e_shoff, = struct.unpack_from('<I', d, 32)
e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<HHH', d, 46)
secs = []
for i in range(e_shnum):
    o = e_shoff + i * e_shentsize
    v = struct.unpack_from('<IIIIIIIIII', d, o)
    secs.append(dict(name=v[0], type=v[1], addr=v[3], off=v[4], size=v[5]))
st = secs[e_shstrndx]['off']
def nm(n):
    e = d.index(b'\0', st + n)
    return d[st + n:e].decode('utf-8', 'replace')

ro = next((s for s in secs if nm(s['name']) == '.rodata'), None)
if not ro:
    print('无 .rodata'); sys.exit(1)
print('=== .rodata  vaddr=0x%08x  offset=0x%x  size=%d (%.1f KB) ===' % (
    ro['addr'], ro['off'], ro['size'], ro['size'] / 1024.0))

blob = d[ro['off']:ro['off'] + ro['size']]

# 抽所有可打印字符串（长 >= 4）
print('\n=== 字符串（>=4 字符）===')
strs = []
cur = bytearray()
start = 0
for i, b in enumerate(blob):
    if 32 <= b < 127:
        if not cur:
            start = i
        cur.append(b)
    else:
        if len(cur) >= 4:
            strs.append((start, bytes(cur).decode('ascii')))
        cur = bytearray()
if len(cur) >= 4:
    strs.append((start, bytes(cur).decode('ascii')))

if kws:
    print('筛选关键词: %s' % ','.join(kws))
    hit = [(o, s) for o, s in strs if any(k in s.lower() for k in kws)]
    print('命中 %d / %d' % (len(hit), len(strs)))
    for o, s in hit:
        print('  0x%08x  %s' % (ro['addr'] + o, s))
else:
    print('共 %d 条，前 60 条' % len(strs))
    for o, s in strs[:60]:
        print('  0x%08x  %s' % (ro['addr'] + o, s))

# ★ 找 ID 表：连续递增的 16/32 位小整数
print('\n=== ★ 候选 ID 表（连续递增的小整数）===')
best = []
for width, step in ((4, 4), (2, 2)):
    run = []
    for i in range(0, len(blob) - width, step):
        v = struct.unpack_from('<I' if width == 4 else '<H', blob, i)[0]
        if 0 < v < 0x800:
            if run and v == run[-1][1] + 1:
                run.append((i, v))
            else:
                if len(run) >= 8:
                    best.append((width, run[0][0], run[-1][0], run))
                run = [(i, v)]
    if len(run) >= 8:
        best.append((width, run[0][0], run[-1][0], run))
best.sort(key=lambda x: -(x[3][-1][0] - x[3][0][0]))
for w, a, b, run in best[:3]:
    print('  宽度%d字节  0x%08x-0x%08x  共%d 项: %s' % (
        w, ro['addr'] + a, ro['addr'] + b, len(run),
        ' '.join(str(v) for _, v in run[:24])))
