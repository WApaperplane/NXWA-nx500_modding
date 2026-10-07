# -*- coding: utf-8 -*-
"""Dump all string refs + API refs for a set of FnA.dll functions."""
import pefile, re, sys
from capstone import *

P = 'E:/iLauncher/firmwareUpgrader/FnA.dll'
pe = pefile.PE(P); IB = pe.OPTIONAL_HEADER.ImageBase
secs = [(s.Name.rstrip(b'\x00').decode(), s.VirtualAddress, s.Misc_VirtualSize,
         s.PointerToRawData, s.SizeOfRawData) for s in pe.sections]
d = open(P, 'rb').read()

def rva2off(rva):
    for n, va, vs, pr, rs in secs:
        if va <= rva < va + max(vs, rs):
            return pr + (rva - va)
    return None

def off2rva(off):
    for n, va, vs, pr, rs in secs:
        if pr <= off < pr + rs:
            return va + (off - pr)
    return None

iat = {}
delay = {}
for e in getattr(pe, 'DIRECTORY_ENTRY_IMPORT', []):
    for im in e.imports:
        if im.name: iat[im.address] = '%s!%s' % (e.dll.decode(), im.name.decode())

strs = {}
for m in re.finditer(rb'[\x20-\x7e]{4,300}', d):
    va = off2rva(m.start())
    if va: strs[va] = m.group().decode('latin1')

def get_str(va):
    if va in strs: return strs[va]
    for sva in sorted(strs):
        if sva <= va < sva + len(strs[sva]):
            return strs[sva][va - sva:]
    return None

md = Cs(CS_ARCH_X86, CS_MODE_32); md.detail = True

def trace(va, size=0x600, label=''):
    fo = rva2off(va - IB)
    if fo is None: 
        print('!! no file off for %x' % va); return
    print('\n### %s @ %08x' % (label or 'sub', va))
    for ins in md.disasm(d[fo:fo+size], va):
        mn, op = ins.mnemonic, ins.op_str
        notes = []
        vals = []
        for tok in re.findall(r'0x[0-9a-fA-F]+', op):
            vals.append(int(tok, 16))
        # push imm
        if mn == 'push' and len(vals) == 1:
            v = vals[0]
            s = get_str(v)
            if s: notes.append('STR "%s"' % s[:110])
            elif v in iat: notes.append('API ' + iat[v])
        # mov/lea reg, imm32
        if mn in ('mov', 'lea', 'cmp') and len(vals) == 1 and not op.startswith(('dword', 'byte', 'word')):
            v = vals[0]
            s = get_str(v)
            if s: notes.append('STR "%s"' % s[:110])
        # mov dword ptr [x], imm32  (string stored to global)
        if mn == 'mov' and 'dword ptr [0x' in op and len(vals) == 2:
            s = get_str(vals[1])
            if s: notes.append('GLOBALSTR "%s"' % s[:110])
        if mn == 'call':
            if len(vals) == 1:
                t = vals[0]
                if IB <= t < IB + 0x100000: notes.append('-> sub_%x' % t)
            if 'dword ptr [0x' in op:
                tgt = vals[-1] if vals else 0
                if tgt in iat: notes.append('-> ' + iat[tgt])
        if notes:
            print('  %08x  %-7s %-40s ; %s' % (ins.address, mn, op, ' | '.join(notes)))

for a, l in [(0x10006140, 'do_modal_firmware_up_dlg'),
             (0x10006040, 'do_modal_lcd_anim_notice_dlg_if_needed'),
             (0x10005ef0, 'create_lcd_anim_window'),
             (0x100065f0, 'isLatestVersionAvailable')]:
    trace(a, 0x900, l)
