#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C++ 符号反修饰（Itanium ABI 子集）+ 类结构统计"""
import re, sys
from collections import Counter

def load_syms(path):
    import struct
    d = open(path, 'rb').read()
    e_shoff, = struct.unpack_from('<I', d, 32)
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<HHH', d, 46)
    secs = []
    for i in range(e_shnum):
        o = e_shoff + i * e_shentsize
        v = struct.unpack_from('<IIIIIIIIII', d, o)
        secs.append(dict(type=v[1], addr=v[3], off=v[4], size=v[5], link=v[6], entsize=v[9]))
    st = secs[e_shstrndx]['off']
    out = []
    for s in secs:
        if s['type'] not in (2, 11) or s['entsize'] != 16:
            continue
        strt = secs[s['link']]['off']
        for i in range(s['size'] // 16):
            o = s['off'] + i * 16
            st_name, st_value, st_size = struct.unpack_from('<III', d, o)
            if st_value == 0:
                continue
            e = d.index(b'\0', strt + st_name)
            out.append((st_value, st_size, d[strt + st_name:e].decode('utf-8', 'replace')))
    return out

def parse_mangled(n):
    """_ZN4DscImage8StopFileSaveEv -> (['DscImage'], 'StopFileSave')"""
    if not n.startswith('_ZN'):
        return None, n
    i = 2
    parts = []
    cls = None
    while i < len(n):
        if not n[i].isdigit():
            break
        j = i
        while n[j].isdigit():
            j += 1
        ln = int(n[i:j])
        word = n[j:j + ln]
        if cls is None:
            cls = word
        else:
            parts.append(word)
        i = j + ln
        if i < len(n) and n[i] == 'E':
            continue
        if i < len(n) and n[i] == 'I':
            parts.append('[' + parse_mangled(n[i:])[1] + ']')
            break
    return cls, '::'.join(parts)

if __name__ == '__main__':
    path = sys.argv[1]
    syms = load_syms(path)
    cls = Counter()
    methods = {}
    for v, sz, n in syms:
        c, m = parse_mangled(n)
        if c:
            cls[c] += 1
            methods.setdefault(c, set()).add(m)
    print('=== %s: %d 符号, %d 个类 ===' % (path, len(syms), len(cls)))
    for c, k in cls.most_common(40):
        print('  %-26s %3d 符号' % (c, k))
    # 关键词过滤
    if len(sys.argv) > 2:
        kws = [k.lower() for k in sys.argv[2:]]
        print('\n=== 命中细节 ===')
        for v, sz, n in syms:
            if any(k in n.lower() for k in kws):
                c, m = parse_mangled(n)
                print('  0x%08x %-46s  %s' % (v, (c or '') + '::' + m, n[:60]))
