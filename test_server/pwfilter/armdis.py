#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
armdis.py — 反汇编 libcapture-fw-prod.so 的指定函数（ARM Thumb/ARM）
最小实现：只处理最常见的指令模式，目标是看清【函数开头加载了什么常量】。

用法: python armdis.py <so> <vaddr_hex> [函数名]
"""
import struct, sys

path = sys.argv[1]
va = int(sys.argv[2], 16)
fname = sys.argv[3] if len(sys.argv) > 3 else ''

d = open(path, 'rb').read()
e_shoff, = struct.unpack_from('<I', d, 32)
e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<HHH', d, 46)
secs = []
for i in range(e_shnum):
    o = e_shoff + i * e_shentsize
    v = struct.unpack_from('<IIIIIIIIII', d, o)
    secs.append(dict(name=v[0], type=v[1], addr=v[3], off=v[4], size=v[5]))
st = secs[e_shstrndx]['off']
def nm(n):
    e = d.index(b'\0', st + n)
    return d[st + n:e].decode('utf-8', 'replace')

e_phoff, = struct.unpack_from('<I', d, 28)
e_phentsize, e_phnum = struct.unpack_from('<HH', d, 42)
loads = []
for i in range(e_phnum):
    o = e_phoff + i * e_phentsize
    p_type, p_off, p_va, p_pa, p_fsz, p_msz = struct.unpack_from('<IIIIII', d, o)
    if p_type == 1:
        loads.append((p_va, p_off, p_msz))
def v2o(v):
    for a, b, c in loads:
        if a <= v < a + c:
            return b + (v - a)
    return None

# ARM cond codes
CC = {0:'eq',1:'ne',2:'cs',3:'cc',4:'mi',5:'pl',6:'vs',7:'vc',
      8:'hi',9:'ls',10:'ge',11:'lt',12:'gt',13:'le',14:'',15:'nv'}

def disasm_arm(addr, n):
    o = v2o(addr)
    out = []
    for k in range(n):
        if o is None or o + 4 > len(d):
            break
        w = struct.unpack_from('<I', d, o)[0]
        cond = w >> 28
        op = (w >> 21) & 0xF
        # 只解几种常见模式
        txt = '???'
        if (w & 0x0FFFFFF0) == 0x012FFF10:
            txt = 'bx%s\t%s' % ('lr' if w & 0xF else 'r0', CC.get(cond,''))
        elif (w & 0x0F000000) == 0x0A000000:
            off = w & 0x00FFFFFF
            if off & 0x800000:
                off -= 0x1000000
            txt = 'b%s\t0x%08x' % (CC.get(cond,''), addr + 8 + off * 4)
        elif (w & 0x0FB00000) == 0x03000000:
            imm = w & 0xFF
            rd = (w >> 12) & 0xF
            opc = (w >> 20) & 0xFF
            names = {0xC0:'bic',0x40:'orr',0x20:'eor',0x00:'and',0x80:'add',0xA0:'sub'}
            txt = '%s%s\t#%d' % (names.get(opc,'?'), CC.get(cond,''), imm)
        elif (w & 0x0FBF0FFF) == 0x010F0000:
            rd = (w >> 12) & 0xF
            txt = 'mrs%s\tr%d, CPSR' % (CC.get(cond,''), rd)
        elif (w & 0x0E000000) == 0x08000000:
            imm = w & 0x00FFFFFF
            rd = (w >> 12) & 0xF
            pre = (w >> 24) & 0xF
            txt = 'ldm%s\tr%d%s' % (CC.get(cond,''), rd,
                                    {0xD:'db',0x1:'ia'}.get(pre,'?'))
        elif (w & 0x0E000000) == 0x0A000000:
            rd = (w >> 12) & 0xF
            txt = 'stm%s\tr%d' % (CC.get(cond,''), rd)
        elif (w & 0x0FF00000) == 0x03A00000:
            imm = w & 0xFF
            rd = (w >> 12) & 0xF
            rn = (w >> 16) & 0xF
            op = (w >> 21) & 3
            names = {0:'add',1:'sub',2:'rsb',3:'rsc'}
            txt = '%s%s\tr%d, r%d, #%d' % (names[op], CC.get(cond,''), rd, rn, imm)
        elif (w & 0x0FB00000) == 0x01000000:
            off = w & 0xFFF
            rn = (w >> 16) & 0xF
            rd = (w >> 12) & 0xF
            txt = 'ldr%s\tr%d, [r%d, #%d]' % (CC.get(cond,''), rd, rn, off)
        elif (w & 0x0E000000) == 0x04000000:
            imm = w & 0xFF
            rn = (w >> 16) & 0xF
            rd = (w >> 12) & 0xF
            op = (w >> 21) & 0xF
            load = (w >> 20) & 1
            names = {0:'and',1:'eor',2:'sub',3:'rsb',4:'add',5:'adc',8:'or',13:'bic'}
            if op in names:
                txt = '%s%s\tr%d, r%d, #%d' % (
                    ('ldr' if load else 'str'), CC.get(cond,''), rd, rn, imm)
        elif (w & 0x0F000000) == 0x0F000000:
            sw = (w >> 24) & 0xF
            rn = (w >> 16) & 0xF
            rd = (w >> 12) & 0xF
            rm = w & 0xF
            txt = 'swp%s\tr%d, r%d, [r%d]' % (CC.get(cond,''), rd, rm, rn)
        out.append((addr + k * 4, w, txt))
    return out

print('=== %s @ 0x%08x（反汇编 %d 条 ARM）===' % (fname, va, 40))
for a, w, t in disasm_arm(va, 40):
    mark = ''
    # ★ 注释：若这条是 PC 相对加载，标出可能的常量池地址
    if (w & 0x0F7F0000) == 0x051F0000 or (w & 0x0F7F0000) == 0x059F0000:
        off = w & 0xFFF
        if w & 0x00800000:
            off = -off
        mark = '   ; <- PC 相对量 %d' % off
    print('  0x%08x: %08x  %s%s' % (a, w, t, mark))
