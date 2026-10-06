"""提取 libudd5.so 的全部 FUNC 符号，筛出色彩/画质相关"""
import struct
import re
import sys

path = r'D:\download\NX-KS2-88\test_server\pwfilter\libudd5.so'
d = open(path, 'rb').read()
e_shoff, = struct.unpack_from('<I', d, 32)
e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<HHH', d, 46)

secs = []
for i in range(e_shnum):
    o = e_shoff + i * e_shentsize
    nm, ty, fl, ad, of, sz = struct.unpack_from('<IIIIII', d, o)
    link, inf, ent2 = struct.unpack_from('<III', d, o + 24)
    secs.append(dict(nm=nm, ty=ty, ad=ad, of=of, sz=sz, link=link, ent=ent2))


def sec_name(i):
    off = secs[i]['nm']
    s = secs[e_shstrndx]
    tab = d[s['of']:s['of'] + s['sz']]
    end = tab.find(b'\x00', off)
    return tab[off:end].decode('ascii', 'replace')


def strtab_of(sec):
    s = secs[sec['link']]
    return d[s['of']:s['of'] + s['sz']]


def sname(tab, off):
    if off >= len(tab):
        return '<bad:%d>' % off
    end = tab.find(b'\x00', off)
    if end < 0:
        return '<unterm>'
    return tab[off:end].decode('ascii', 'replace')


syms = []
objs = []
for i, s in enumerate(secs):
    if s['ty'] in (2, 11):          # SYMTAB / DYNSYM
        tab = strtab_of(s)
        ent = s['ent'] or 16
        for k in range(s['sz'] // ent):
            p = s['of'] + k * ent
            n, val, sz, info, oth, sh = struct.unpack_from('<IIIBBH', d, p)
            if n == 0 or val == 0:
                continue
            nm = sname(tab, n)
            t = info & 0xF
            if t == 2:
                syms.append((val, nm))
            elif t == 1:
                objs.append((val, nm, sh, sec_name(i)))

syms.sort()
objs.sort()
print('FUNC 符号(有地址): %d' % len(syms))
print('OBJECT 符号(全局数据): %d' % len(objs))

kw = re.compile(r'(?i)ccm|color|gamma|tone|curve|sat|hue|_pw|csc|wb|awb|sharp|contrast|lut|histo|drc|histeq|white|black|face|skin')

print()
print('=== 色彩/画质 FUNC (%d) ===' % len([1 for v, n in syms if kw.search(n)]))
for v, n in syms:
    if kw.search(n):
        print('  0x%06x  %s' % (v, n))

print()
print('=== 色彩/画质 OBJECT (%d) ===' % len([1 for o in objs if kw.search(o[1])]))
for v, n, sh, sn in objs:
    if kw.search(n):
        print('  0x%06x  %s' % (v, n))

print()
print('=== 全局 OBJECT 全部 ===')
for v, n, sh, sn in objs:
    print('  0x%06x  %s' % (v, n))
