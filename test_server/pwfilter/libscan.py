#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
libscan.py — 扫一个 .so 的符号表，按关键词分组输出

用法: python libscan.py <so文件> [关键词...]
"""
import struct, sys

def load(path):
    d = open(path, 'rb').read()
    e_shoff, = struct.unpack_from('<I', d, 32)
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<HHH', d, 46)
    secs = []
    for i in range(e_shnum):
        o = e_shoff + i * e_shentsize
        v = struct.unpack_from('<IIIIIIIIII', d, o)
        secs.append(dict(name=v[0], type=v[1], flags=v[2], addr=v[3], off=v[4],
                         size=v[5], link=v[6], entsize=v[9]))
    st = secs[e_shstrndx]['off']
    def nm(n):
        e = d.index(b'\0', st + n)
        return d[st + n:e].decode('utf-8', 'replace')
    syms = []
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
            syms.append((st_value, st_size,
                         d[strt + st_name:e].decode('utf-8', 'replace'),
                         nm(s['name'])))
    # 节名
    names = {}
    for s in secs:
        names[s['addr']] = nm(s['name'])
    return d, syms, names, secs

if __name__ == '__main__':
    path = sys.argv[1]
    kws = [k.lower() for k in sys.argv[2:]]
    d, syms, names, secs = load(path)
    print('=== %s  (%d 字节) ===' % (path, len(d)))
    print('段:')
    for a in sorted(names):
        for s in secs:
            if s['addr'] == a and s['size']:
                print('  %-20s 0x%08x size 0x%-8x' % (names[a], a, s['size']))
    print('\n符号总数: %d' % len(syms))
    if not kws:
        # 无关键词：按长度排前 40（长名字通常是函数）
        print('\n=== 最长的 40 个符号（可能是 API）===')
        for v, sz, n, tab in sorted(syms, key=lambda x: -len(x[2]))[:40]:
            print('  0x%08x %-50s %s' % (v, n, tab))
    else:
        hit = [(v, sz, n, tab) for v, sz, n, tab in syms
               if any(k in n.lower() for k in kws)]
        print('\n=== 命中 %d 个符号（关键词: %s）===' % (len(hit), ','.join(kws)))
        for v, sz, n, tab in sorted(hit):
            print('  0x%08x %-52s %s' % (v, n, tab))
