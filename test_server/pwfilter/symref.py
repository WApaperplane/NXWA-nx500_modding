#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
symref.py — 从运行期 maps + 库文件建立「eip → 库内符号」解析器

用法:
  python symref.py maps.txt                       # 列出所有 r-xp 映射
  python symref.py maps.txt 0xb32b2afc            # 解析单个 eip
  python symref.py maps.txt --lib libc 0xb32b2afc # 指定库

原理: eip 落在某个 so 的 r-xp 段内 → 减去该段起始 vaddr → 得到库内偏移
      → 在该库的 .dynsym/.symtab 里按 st_value 找最近的符号
"""
import struct, sys, os

def load_syms(path):
    """返回 [(value, size, name), ...]，来自 .dynsym 和 .symtab"""
    d = open(path, 'rb').read()
    out = []
    e_shoff, = struct.unpack_from('<I', d, 32)
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<HHH', d, 46)
    secs = []
    for i in range(e_shnum):
        off = e_shoff + i * e_shentsize
        sh_name, sh_type, sh_flags, sh_addr, sh_off, sh_size, sh_link, \
            sh_info, sh_align, sh_entsize = struct.unpack_from('<IIIIIIIIII', d, off)
        secs.append(dict(name=sh_name, type=sh_type, addr=sh_addr, off=sh_off,
                         size=sh_size, link=sh_link, entsize=sh_entsize))
    st = secs[e_shstrndx]['off']
    def nm(n):
        e = d.index(b'\0', st + n)
        return d[st + n:e].decode('utf-8', 'replace')
    for s in secs:
        if s['type'] not in (2, 11):   # SHT_SYMTAB / SHT_DYNSYM
            continue
        if s['entsize'] != 16:        # Elf32_Sym
            continue
        strt = secs[s['link']]['off']
        n = s['size'] // 16
        for i in range(n):
            o = s['off'] + i * 16
            st_name, st_value, st_size = struct.unpack_from('<III', d, o)
            if st_value == 0:
                continue
            e = d.index(b'\0', strt + st_name)
            name = d[strt + st_name:e].decode('utf-8', 'replace')
            out.append((st_value, st_size, name, nm(s['name'])))
    out.sort()
    return out

def parse_maps(path):
    maps = []
    for ln in open(path, encoding='utf-8', errors='replace'):
        p = ln.split()
        if len(p) < 5 or '-' not in p[0]:
            continue
        a, b = p[0].split('-')
        try:
            maps.append(dict(s=int(a, 16), e=int(b, 16), perms=p[1],
                             off=int(p[2], 16), path=p[-1] if len(p) >= 6 else ''))
        except ValueError:
            pass
    return maps

def find_symbol(syms, off):
    """找 off 落在哪个符号里（取最近的 <= off）"""
    best = None
    for v, sz, n, tab in syms:
        if v > off:
            break
        if sz and off < v + sz:
            return n, v, tab
        if not sz:
            best = best or (n, v, tab)
    return (best[0], best[1], best[2]) if best else (None, None, None)

if __name__ == '__main__':
    mp = sys.argv[1]
    maps = parse_maps(mp)
    if len(sys.argv) == 2:
        print('=== r-xp 映射 ===')
        for m in maps:
            if m['perms'].startswith('r-x') and m['path']:
                print('  0x%08x-0x%08x off=0x%08x %s' % (m['s'], m['e'], m['off'], m['path']))
        sys.exit(0)

    # 解析 eip
    libcache = {}
    for a in sys.argv[2:]:
        v = int(a, 16)
        host = None
        for m in maps:
            if m['s'] <= v < m['e']:
                host = m
                break
        if not host:
            print('0x%08x  ★ 不在任何映射' % v)
            continue
        path = host['path']
        # maps 里是绝对路径（/lib/libc-2.13.so），本机只有 sysroot/lib/...
        cands = [path, os.path.join('sysroot', path.lstrip('/'))]
        real = next((c for c in cands if c and os.path.exists(c)), None)
        if not real:
            print('0x%08x  %s  (库文件不在本机: %s)' % (v, host['perms'], path or 'anonymous'))
            continue
        if real not in libcache:
            try:
                libcache[real] = load_syms(real)
            except Exception as ex:
                libcache[real] = []
                print('  解析 %s 失败: %s' % (real, ex))
        syms = libcache[real]
        off = v - host['s'] + host['off']
        n, sv, tab = find_symbol(syms, off)
        print('0x%08x  %s' % (v, path))
        print('     库内偏移 = 0x%08x (段 off 0x%x + 0x%x)' % (off, host['off'], v - host['s']))
        if n:
            print('     符号: %s  (值 0x%x, %s)' % (n, sv, tab))
        else:
            print('     符号: 未找到')
