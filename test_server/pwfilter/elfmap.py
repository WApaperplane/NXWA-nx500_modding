#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
elfmap.py — 解析 di-camera-app 的 ELF 段布局，把运行期 eip 映射回文件偏移
"""
import struct, sys

PATH = sys.argv[1] if len(sys.argv) > 1 else 'odd3l/di-camera-app'
EIPS = [int(x, 16) for x in sys.argv[2:]] if len(sys.argv) > 2 else []

d = open(PATH, 'rb').read()
print('file: %s  size: %d' % (PATH, len(d)))

# ELF32 header
assert d[:4] == b'\x7fELF', 'not ELF'
e_type, e_machine = struct.unpack_from('<HH', d, 16)
e_entry, e_phoff, e_shoff = struct.unpack_from('<III', d, 24)
e_flags, e_ehsize, e_phentsize, e_phnum = struct.unpack_from('<IHHH', d, 36)
e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<HHH', d, 46)
print('type=%d machine=%d entry=0x%08x phnum=%d shnum=%d' % (
    e_type, e_machine, e_entry, e_phnum, e_shnum))

# section headers
secs = []
for i in range(e_shnum):
    off = e_shoff + i * e_shentsize
    sh_name, sh_type, sh_flags, sh_addr, sh_off, sh_size = \
        struct.unpack_from('<IIIIII', d, off)
    secs.append(dict(name=sh_name, type=sh_type, flags=sh_flags,
                     addr=sh_addr, off=sh_off, size=sh_size))
# 读字符串表
strtab_off = secs[e_shstrndx]['off']
def sname(n):
    e = d.index(b'\0', strtab_off + n)
    return d[strtab_off + n:e].decode('utf-8', 'replace')

print('\n=== 有分配内容的段（addr != 0） ===')
print('%-24s %-10s %-10s %-10s %-10s' % ('name', 'addr', 'off', 'size', 'flags'))
for s in secs:
    if s['addr'] and s['size']:
        print('%-24s 0x%08x 0x%08x %-10d 0x%x' % (
            sname(s['name']), s['addr'], s['off'], s['size'], s['flags']))

print('\n=== PT_LOAD 段（运行期映射用这个） ===')
loads = []
for i in range(e_phnum):
    off = e_phoff + i * e_phentsize
    p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_flags, p_align = \
        struct.unpack_from('<IIIIIIII', d, off)
    if p_type == 1:
        loads.append(dict(off=p_offset, vaddr=p_vaddr, filesz=p_filesz, memsz=p_memsz))
        print('LOAD vaddr=0x%08x off=0x%08x filesz=0x%x memsz=0x%x' % (
            p_vaddr, p_offset, p_filesz, p_memsz))

if EIPS:
    print('\n=== eip 映射 ===')
    for e in EIPS:
        hit = None
        for L in loads:
            if L['vaddr'] <= e < L['vaddr'] + L['memsz']:
                hit = L
                break
        if hit:
            fo = hit['off'] + (e - hit['vaddr'])
            print('  0x%08x -> file offset 0x%08x (vaddr 0x%08x, +0x%x)' % (
                e, fo, hit['vaddr'], e - hit['vaddr']))
        else:
            print('  0x%08x -> 不在任何 PT_LOAD 段（可能是 libc/其他 so）' % e)
