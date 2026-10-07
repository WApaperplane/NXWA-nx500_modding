# -*- coding: utf-8 -*-
"""Use the .reloc table to map each string VA -> all code sites referencing it."""
import pefile, re
from capstone import *
P='E:/iLauncher/firmwareUpgrader/FnA.dll'
pe=pefile.PE(P); IB=pe.OPTIONAL_HEADER.ImageBase
secs=[(s.Name.rstrip(b'\x00').decode(),s.VirtualAddress,s.Misc_VirtualSize,s.PointerToRawData,s.SizeOfRawData) for s in pe.sections]
d=open(P,'rb').read()
def rva2off(r):
    for n,va,vs,pr,rs in secs:
        if va<=r<va+max(vs,rs): return pr+(r-va)
def off2rva(o):
    for n,va,vs,pr,rs in secs:
        if pr<=o<pr+rs: return va+(o-pr)

# build reloc map: rva_of_dword -> target_va
rel={}
for b in getattr(pe,'DIRECTORY_ENTRY_BASERELOC',[]):
    for e in b.entries:
        if e.type in (3,):  # HIGHLOW
            rel[e.rva]=e.rva  # we'll compute target below
reltarget={}
for rva in list(rel):
    o=rva2off(rva)
    if o is None: continue
    delta=int.from_bytes(d[o:o+4],'little')
    reltarget[rva]=IB+delta

strs={}
for m in re.finditer(rb'[\x20-\x7e]{4,300}',d):
    va=off2rva(m.start())
    if va: strs[va]=m.group().decode('latin1')
def get_str(va):
    if va in strs: return strs[va]
    for s in sorted(strs):
        if s<=va<s+len(strs[s]): return strs[s][va-s:]

# invert: target_va -> [code rva of the dword]
inv={}
for rva,tv in reltarget.items():
    inv.setdefault(tv,[]).append(rva)

# disasm cache: for each ref site, disasm around
md=Cs(CS_ARCH_X86,CS_MODE_32); md.detail=True

def va2off(va): return rva2off(va-IB)

TARGETS=[0x52e1c,0x52e34,0x52ea8,0x533bc,0x53f3c,0x53f84,0x53fa0,0x53fb4,
         0x53fe4,0x5414c,0x54168,0x541c8,0x559cc,0x55a94,0x52de4,0x533a0]
for tv in TARGETS:
    s=get_str(tv)
    print('\n=== "%s"  (@%x)' % ((s or '?')[:60], tv))
    for rva in inv.get(tv,[]):
        va=IB+rva
        # find function start: scan back for CC CC or a prologue
        fo=va2off(va)
        if fo is None: continue
        print('   ref site %08x' % va)
