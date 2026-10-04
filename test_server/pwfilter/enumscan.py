#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫 .rodata 里所有 E_CAP_CMD_* 枚举字符串 + 其上下文"""
import struct, sys, re

path = sys.argv[1] if len(sys.argv) > 1 else 'odd3l/libcapture-fw-prod.so'
d = open(path, 'rb').read()
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
ro = next(s for s in secs if nm(s['name']) == '.rodata')
blob = d[ro['off']:ro['off'] + ro['size']]
BASE = ro['addr']

# 抽全部字符串及偏移
strs = []
cur = bytearray(); start = 0
for i, b in enumerate(blob):
    if 32 <= b < 127:
        if not cur:
            start = i
        cur.append(b)
    else:
        if len(cur) >= 3:
            strs.append((start, bytes(cur).decode('ascii')))
        cur = bytearray()

print('=== ★ E_CAP_CMD_* 全部枚举字符串（%d 条）===' %
      len([s for s in strs if s[1].startswith('E_CAP_CMD')]))
for o, s in strs:
    if s.startswith('E_CAP_CMD'):
        print('  0x%08x  %s' % (BASE + o, s))

# ★ 找 E_* 枚举的整体范围
print('\n=== ★ 所有 E_* 开头的枚举字符串（按地址）===')
e_all = [(o, s) for o, s in strs if re.match(r'^E_[A-Z]', s)]
print('共 %d 条' % len(e_all))
# 只显示 PW/COLOR/BRACKET/CAPTURE 相关的
for o, s in e_all:
    if re.search(r'PW|BRACKET|COLOR|CAPTURE|SATUR|SHARP|CONTRA', s):
        print('  0x%08x  %s' % (BASE + o, s))

# ★ 关键：E_CAP_CMD_STL_PW_BRACKET 附近 512 字节的 hex dump
print('\n=== ★ E_CAP_CMD_STL_PW_BRACKET (0xa561c) 附近的原始数据 ===')
tgt = next((o for o, s in strs if s == 'E_CAP_CMD_STL_PW_BRACKET'), None)
if tgt is not None:
    a = max(0, tgt - 128)
    for k in range(a, min(len(blob), tgt + 256), 16):
        hexs = ' '.join('%02x' % blob[k + j] for j in range(min(16, len(blob) - k)))
        asc = ''.join(chr(blob[k + j]) if 32 <= blob[k + j] < 127 else '.'
                      for j in range(min(16, len(blob) - k)))
        print('  0x%08x  %-47s  %s' % (BASE + k, hexs, asc))
