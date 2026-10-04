#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pltscan.py —— 扫 ELF 里的 PLT/GOT 映射，定位某个函数的调用入口

用法: pltscan.py <elf> [函数名关键字 ...]
输出: 该函数在 PLT 中的槽位、对应 GOT 偏移、以及反汇编调用点
"""
import struct
import sys


def load(path):
    return open(path, 'rb').read()


def sections(d):
    e_shoff, = struct.unpack_from('<I', d, 32)
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<HHH', d, 46)
    o = e_shoff + e_shstrndx * e_shentsize
    _, _, _, _, stro, _ = struct.unpack_from('<IIIIII', d, o)

    def nm(idx):
        e = d.find(b'\x00', stro + idx)
        return d[stro + idx:e].decode('ascii', 'replace')

    out = {}
    for i in range(e_shnum):
        o = e_shoff + i * e_shentsize
        n, typ, fl, ad, off, sz = struct.unpack_from('<IIIIII', d, o)
        out[nm(n)] = (typ, ad, off, sz)
    return out


def dynsym_reader(d, SEC):
    _, _, doff, dsz = SEC['.dynsym']
    _, _, stro, _ = SEC['.dynstr']

    def sym(i):
        o = doff + i * 16
        name, val, sz, info, other, shndx = struct.unpack_from('<IIIBBH', d, o)
        if name == 0:
            return ''
        e = d.find(b'\x00', stro + name)
        return d[stro + name:e].decode('ascii', 'replace')
    return sym


def main():
    path = sys.argv[1]
    kws = sys.argv[2:]
    d = load(path)
    SEC = sections(d)
    sym = dynsym_reader(d, SEC)

    # PLT 段
    if '.plt' not in SEC:
        print('无 .plt 段')
        return
    _, plt_ad, plt_off, plt_sz = SEC['.plt']
    # ARM PLT：每条 12 字节，第 0 条是 PLT0
    PLT0 = plt_ad
    entry = 12

    # .rel.plt：每条 8 字节（offset, info）
    _, _, rel_off, rel_sz = SEC['.rel.plt']

    # 收集 PLT -> (GOT, 符号名)
    pltmap = []
    for i in range(rel_sz // 8):
        got, info = struct.unpack_from('<II', d, rel_off + i * 8)
        symidx = info >> 8
        plt = PLT0 + (i + 1) * entry
        pltmap.append((plt, got, sym(symidx)))

    print('=== PLT 总数: %d ===' % len(pltmap))

    if not kws:
        for plt, got, nm in pltmap[:20]:
            print('  0x%05x -> GOT 0x%08x  %s' % (plt, got, nm))
        return

    # 按关键字过滤
    hits = []
    for plt, got, nm in pltmap:
        if any(k in nm for k in kws):
            hits.append((plt, got, nm))

    print('')
    print('=== 命中 %d 条（关键字: %s）===' % (len(hits), ', '.join(kws)))
    for plt, got, nm in hits:
        print('')
        print('  %s' % nm)
        print('    PLT 静态地址 = 0x%05x' % plt)
        print('    GOT 偏移     = 0x%08x' % got)

        # 找 .text 里所有 bl/blx 到这个 PLT 槽的调用点
        if '.text' in SEC:
            _, text_ad, text_off, text_sz = SEC['.text']
            callers = []
            for a in range(text_ad, text_ad + text_sz, 4):
                w = struct.unpack_from('<I', d, a - text_ad + text_off)[0]
                # BL: cond 1011 offset24
                if (w & 0x0F000000) == 0x0B000000:
                    off24 = w & 0xFFFFFF
                    if off24 & 0x800000:
                        off24 -= 0x1000000
                    tgt = a + 8 + (off24 << 2)
                    if tgt == plt:
                        callers.append(a)
                # BLX(reg) 不查
            if callers:
                print('    调用点 (%d 个):' % len(callers))
                for c in callers[:12]:
                    print('0x%05x' % c)
                if len(callers) > 12:
                    print('      ... 还有 %d 个' % (len(callers) - 12))
            else:
                print('    调用点: 无（★可能通过函数指针间接调用）')


if __name__ == '__main__':
    main()
