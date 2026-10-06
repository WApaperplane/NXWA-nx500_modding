#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
idtab.py — 在 .rodata/.data.rel.ro 里找「字符串指针数组 + 相邻整数表」结构
思路：E_CAP_CMD_* 字符串在 .rodata，它们的指针会在 .data.rel.ro / .rodata 里排成表，
      表旁边往往就是对应的 int 枚举值。
"""
import struct, sys, re

path = sys.argv[1]
d = open(path, 'rb').read()
e_shoff, = struct.unpack_from('<I', d, 32)
e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<HHH', d, 46)
secs = []
for i in range(e_shnum):
    o = e_shoff + i * e_shentsize
    v = struct.unpack_from('<IIIIIIIIII', d, o)
    secs.append(dict(name=v[0], type=v[1], addr=v[3], off=v[4], size=v[5],
                     link=v[6]))
st = secs[e_shstrndx]['off']
def nm(n):
    e = d.index(b'\0', st + n)
    return d[st + n:e].decode('utf-8', 'replace')

# 建立 vaddr -> 文件偏移 映射（PT_LOAD）
loads = []
e_phoff, = struct.unpack_from('<I', d, 28)
e_phentsize, e_phnum = struct.unpack_from('<HH', d, 42)
for i in range(e_phnum):
    o = e_phoff + i * e_phentsize
    p_type, p_off, p_va, p_pa, p_fsz, p_msz = struct.unpack_from('<IIIIII', d, o)
    if p_type == 1:
        loads.append((p_va, p_off, p_msz))
def v2o(v):
    for va, off, msz in loads:
        if va <= v < va + msz:
            return off + (v - va)
    return None

def readstr(v):
    o = v2o(v)
    if o is None or o >= len(d):
        return None
    e = d.find(b'\0', o, o + 200)
    if e < 0:
        return None
    try:
        s = d[o:e].decode('ascii')
    except Exception:
        return None
    return s if len(s) >= 3 and all(32 <= ord(c) < 127 for c in s) else None

print('=== 扫描「指向字符串的指针」并找连续数组 ===')
# 找所有 .rodata 内的 4 字节值，若它指向一个字符串，就收集
text = next(s for s in secs if nm(s['name']) == '.rodata')
blob = d[text['off']:text['off'] + text['size']]

ptrs = {}
for i in range(0, len(blob) - 4, 4):
    v = struct.unpack_from('<I', blob, i)[0]
    s = readstr(v)
    if s and (s.startswith('E_') or 'PW' in s or 'ATTRIBUTE' in s.upper()):
        ptrs[text['addr'] + i] = s

print('找到 %d 个指向 E_*/PW* 字符串的指针' % len(ptrs))
addrs = sorted(ptrs)
# 找连续聚簇（间隔 <= 8 字节）
clusters = []
cur = [addrs[0]] if addrs else []
for a in addrs[1:]:
    if a - cur[-1] <= 8:
        cur.append(a)
    else:
        if len(cur) >= 4:
            clusters.append(cur)
        cur = [a]
if len(cur) >= 4:
    clusters.append(cur)

for c in clusters[:6]:
    print('\n--- 指针数组 0x%08x-0x%08x（%d 项）---' % (c[0], c[-1], len(c)))
    for a in c[:30]:
        print('   0x%08x -> %s' % (a, ptrs[a]))
    # ★ 紧邻表尾之后的 4 字节，看是不是 int 枚举
    tail = c[-1] + 4
    o = v2o(tail)
    if o and o + 64 <= len(d):
        vals = []
        for k in range(8):
            vals.append(struct.unpack_from('<i', d, o + k * 4)[0])
        print('   表尾后 8 个 int32: %s' % vals)
        # 也看表头之前
        o2 = v2o(c[0] - 4)
        if o2 and o2 >= 0:
            pre = []
            for k in range(8):
                pre.append(struct.unpack_from('<i', d, o2 - k * 4)[0])
            print('   表头前 8 个 int32: %s' % pre[::-1])
