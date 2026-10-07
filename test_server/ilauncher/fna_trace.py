# -*- coding: utf-8 -*-
"""Trace FnA.dll do_modal_firmware_up_dlg: which API string args are used,
   and whether the flow can be fed a local firmware file."""
import pefile
from capstone import *

P = 'E:/iLauncher/firmwareUpgrader/FnA.dll'
pe = pefile.PE(P)
IB = pe.OPTIONAL_HEADER.ImageBase
secs = [(s.Name.rstrip(b'\x00').decode(), s.VirtualAddress, s.Misc_VirtualSize,
         s.PointerToRawData, s.SizeOfRawData) for s in pe.sections]


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


d = open(P, 'rb').read()

# --- imports per IAT slot ---
iat = {}
for e in getattr(pe, 'DIRECTORY_ENTRY_IMPORT', []):
    for im in e.imports:
        if im.name:
            iat[im.address] = (e.dll.decode(), im.name.decode())


def rd(off, n):
    return d[off:off + n]


def rd32(off):
    return int.from_bytes(d[off:off + 4], 'little')


def foff(rva):
    o = rva2off(rva)
    return o


md = Cs(CS_ARCH_X86, CS_MODE_32)
md.detail = True

# --- read .rdata strings with VA ---
strs = {}
for m in __import__('re').finditer(rb'[\x20-\x7e]{4,200}', d):
    va = off2rva(m.start())
    if va:
        strs[va] = m.group().decode('latin1')


def get_str(va):
    # exact start or walk back to a string start
    if va in strs:
        return strs[va]
    for sva in sorted(strs):
        if sva <= va < sva + len(strs[sva]):
            return strs[sva][va - sva:]
    return None


# --- disassemble function and collect push imm32 / mov reg,imm32 that point at strings/APIs ---
def trace(name, va):
    fo = foff(va - IB)
    print('\n' + '=' * 78)
    print('FUNC %s @ VA %08x (file 0x%x)' % (name, va, fo))
    print('=' * 78)
    code = d[fo:fo + 0x1400]
    insns = list(md.disasm(code, va))
    for i, ins in enumerate(insns):
        mn, op = ins.mnemonic, ins.op_str
        mark = ''
        # push imm32 that resolves to string
        if mn == 'push' and op.startswith('0x'):
            v = int(op, 16)
            s = get_str(v)
            if s:
                mark = '   ; STR "%s"' % s.replace('\n', ' ')[:90]
            elif v in iat:
                mark = '   ; API %s!%s' % iat[v]
        # mov eax, imm32 -> string ; call
        if mn in ('mov', 'lea') and ',' in op and op.split(',')[1].strip().startswith('0x'):
            v = int(op.split(',')[1].strip(), 16)
            s = get_str(v)
            if s:
                mark = '   ; STR "%s"' % s.replace('\n', ' ')[:90]
        if mn == 'call':
            if op.startswith('0x'):
                t = int(op, 16)
                # direct call inside image
                if IB <= t < IB + 0x100000:
                    sub = pe.get_symbol_at_rva(t - IB) if hasattr(pe, 'get_symbol_at_rva') else None
                    mark = '   ; -> sub_%x' % t
            elif 'dword ptr [0x' in op:
                try:
                    tgt = int(op.split('[')[1].rstrip(']'), 16)
                    if tgt in iat:
                        mark = '   ; -> %s!%s' % iat[tgt]
                except Exception:
                    pass
        if mark:
            print('  %08x  %-8s %-42s%s' % (ins.address, mn, op, mark))


trace('do_modal_firmware_up_dlg', 0x10006140)
