#!/usr/bin/env python
"""ARM PLT-aware annotated disassembler for libudd5.so (NX-KS2)
铁律67：读指令级结论必须用 capstone + 真实符号名，禁止手写反汇编。
用法: python udd5dis.py <func_addr> [size] | --sym <name>
"""
import sys, re
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

LIB = r"D:\download\NX-KS2-88\.uploads\nx1_open\rootfs_dev\standard-armv7l\usr\lib\libudd5.so"


def load():
    f = open(LIB, 'rb')
    e = ELFFile(f)
    segs = [(s['p_vaddr'], s['p_offset'], s['p_filesz'])
            for s in e.iter_segments() if s['p_type'] == 'PT_LOAD']

    def rd(va, n):
        for v, o, sz in segs:
            if v <= va < v + sz:
                f.seek(o + (va - v))
                return f.read(n)
        return b''

    ds = e.get_section_by_name('.dynsym')
    slots = {}
    rel = e.get_section_by_name('.rel.plt')
    if rel:
        for r in rel.iter_relocations():
            slots[r['r_offset']] = ds.get_symbol(r['r_info_sym']).name

    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)

    pltmap = {}
    if rel:
        for i in range(rel.num_relocations()):
            t = 0x8100 + 12 * (i + 1)
            ins = list(md.disasm(rd(t, 12), t))
            if len(ins) != 3:
                continue
            m = re.search(r'#(0x[0-9a-fA-F]+)\]', ins[2].op_str)
            if not m:
                continue
            pltmap[t] = slots.get(((t + 8) + 0x41000 + int(m.group(1), 16)) & ~3, '?')

    funcs = {}
    for sn in ('.dynsym', '.symtab'):
        s = e.get_section_by_name(sn)
        if not s:
            continue
        for x in s.iter_symbols():
            if x['st_value'] and x['st_info']['type'] == 'STT_FUNC':
                funcs.setdefault(x['st_value'], x.name)
    # plt stubs themselves are funcs;prefer real name
    for a, n in pltmap.items():
        if n and n != '?':
            funcs[a] = n + '@plt'
    return rd, funcs, md


def dump(va, size, rd, funcs, md):
    for ins in md.disasm(rd(va, size), va):
        ann = ''
        if ins.mnemonic in ('bl', 'blx'):
            try:
                tv = int(ins.op_str.lstrip('#'), 16)
                ann = '  ; ' + funcs.get(tv, hex(tv))
            except ValueError:
                pass
        print('%08x  %-8s %-32s%s' % (ins.address, ins.mnemonic, ins.op_str, ann))


if __name__ == '__main__':
    rd, funcs, md = load()
    if sys.argv[1] == '--sym':
        for a, n in sorted(funcs.items()):
            if sys.argv[2] in n:
                print(hex(a), n)
    else:
        va = int(sys.argv[1], 16)
        size = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x100
        print('=== %s @ %s ===' % (funcs.get(va, '?'), hex(va)))
        dump(va, size, rd, funcs, md)
