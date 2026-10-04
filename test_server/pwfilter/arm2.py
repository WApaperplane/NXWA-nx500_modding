#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ARM (32-bit, little-endian) 轻量反汇编器 —— 专攻 libudd5.so
★ 教训：之前用if-elif 猜指令类型，LDR/STR/STM/LDM 全解错。
   正确做法：先按位域判断类别，再解码。
"""
import struct
import sys


def load(path):
    return open(path, 'rb').read()


# ---- 条件码 ----
COND = ['eq', 'ne', 'cs', 'cc', 'mi', 'pl', 'vs', 'vc',
        'hi', 'ls', 'ge', 'lt', 'gt', 'le', '', 'nv']
COND_AL = ''


def cond_str(c):
    return COND[c] if c < 15 else ('al' if c == 14 else 'nv')


def disasm_one(w, addr):
    """返回 (长度字节, 文本)"""
    cond = (w >> 28) & 0xF
    cs = cond_str(cond)
    op = (w >> 21) & 0xF

    # ===== 立即数/数据处理 (op = 00I opcode S Rn Rd operand2) =====
    if (w & 0x0C000000) == 0x00000000:
        I = (w >> 25) & 1
        opcode = (w >> 21) & 0xF
        S = (w >> 20) & 1
        Rn = (w >> 16) & 0xF
        Rd = (w >> 12) & 0xF
        names = ['and', 'eor', 'sub', 'rsb', 'add', 'adc', 'sbc', 'rsc',
                 'tst', 'teq', 'cmp', 'cmn', 'orr', 'mov', 'bic', 'mvn']
        nm = names[opcode]
        if I:
            rot = ((w >> 8) & 0xF) * 2
            imm8 = w & 0xFF
            val = (imm8 >> rot) | (imm8 << (32 - rot)) & 0xFFFFFFFF if rot else imm8
            op2 = '#%d' % val
        else:
            Rm = w & 0xF
            sh = (w >> 4) & 0xFF
            if sh:
                st = ['lsl', 'lsr', 'asr', 'ror'][sh >> 5]
                op2 = 'r%d, %s #%d' % (Rm, st, sh & 0x1F)
            else:
                op2 = 'r%d' % Rm
        if S and nm not in ('cmp', 'cmn', 'tst', 'teq'):
            return 4, '%s%s%s%s r%d, %s, %s' % (nm, cs, S and 's' or '', '', Rd, 'r%d' % Rn, op2)
        if nm in ('cmp', 'cmn', 'tst', 'teq'):
            return 4, '%s%s r%d, %s' % (nm, cs, Rn, op2)
        if nm in ('mov', 'mvn'):
            return 4, '%s%s r%d, %s' % (nm, cs, Rd, op2)
        return 4, '%s%s r%d, r%d, %s' % (nm, cs, Rd, Rn, op2)

    # ===== 乘法/长乘 (op = 01) =====
    if (w & 0x0FC000F0) == 0x00000090:
        A = (w >> 21) & 0xF
        Rd = (w >> 16) & 0xF
        Rm = (w >> 8) & 0xF
        names = ['mul', 'mla', 'umlal', 'smlal', 'muls', 'mlas', 'umuls', 'smlals']
        return 4, '%s%s r%d, r%d, r%d' % (names[A], cs, Rd, Rd, Rm)

    # ===== 加载/存储 (op = 01, I=1) =====
    if (w & 0x0E000000) == 0x04000000:
        I = (w >> 25) & 1
        P = (w >> 24) & 1
        U = (w >> 23) & 1
        B = (w >> 22) & 1
        W = (w >> 21) & 1
        L = (w >> 20) & 1
        Rn = (w >> 16) & 0xF
        Rd = (w >> 12) & 0xF
        kind = 'ldr' if L else 'str'
        b = 'b' if B else ''
        if I:
            off = w & 0xFFF
            u = '+' if U else '-'
            if off:
                return 4, '%s%s%s r%d, [r%d, #%s%d]' % (kind, b, cs, Rd, Rn, u, off)
            return 4, '%s%s%s r%d, [r%d]' % (kind, b, cs, Rd, Rn)
        else:
            return 4, '%s%s%s r%d, [r%d, r%d]%s' % (kind, b, cs, Rd, Rn, w & 0xF,
                                                     '!' if W else '')

    # ===== 块加载/存储 (op = 10) =====
    if (w & 0x0E000000) == 0x08000000:
        P = (w >> 24) & 1
        U = (w >> 23) & 1
        S = (w >> 22) & 1
        W = (w >> 21) & 1
        L = (w >> 20) & 1
        Rn = (w >> 16) & 0xF
        reglist = w & 0xFFFF
        rl = ','.join('r%d' % i for i in range(16) if (reglist >> i) & 1)
        kind = 'ldm' if L else 'stm'
        return 4, '%s%s%s r%d%s, {%s}' % (kind, cs, 'db' if P else 'ia',
                                          Rn, '!' if W else '', rl)

    # ===== 分支 (op = 10, 101) =====
    if (w & 0x0E000000) == 0x0A000000:
        L = (w >> 24) & 1
        off = w & 0xFFFFFF
        if off & 0x800000:
            off -= 0x1000000
        tgt = addr + 8 + (off << 2)
        return 4, 'b%s%s 0x%08x' % ('l' if L else '', cs, tgt & 0xFFFFFFFF)

    # ===== 协处理/软中断 =====
    if (w & 0x0F000000) == 0x0F000000:
        op2 = (w >> 4) & 0xF
        if op2 == 1:
            return 4, 'svc%s #%d' % (cs, w & 0xFFFFFF)
        if op2 == 0:
            return 4, 'mcr%s #%d, %d, %d, %d, %d' % (cs, (w >> 21) & 7, Rd_of(w),
                                                     (w >> 8) & 0xF, (w >> 5) & 7, w & 0xF)

    return 4, '.word 0x%08x' % w


def Rd_of(w):
    return (w >> 12) & 0xF


def disasm_range(d, va, count, label=''):
    if label:
        print('=== %s @ 0x%05x ===' % (label, va))
    for k in range(count):
        a = va + k * 4
        if a + 4 > len(d):
            break
        w = struct.unpack_from('<I', d, a)[0]
        n, txt = disasm_one(w, a)
        print('  0x%05x: %08x  %s' % (a, w, txt))
    print()


if __name__ == '__main__':
    d = load(sys.argv[1])
    va = int(sys.argv[2], 16)
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 24
    lbl = sys.argv[4] if len(sys.argv) > 4 else ''
    disasm_range(d, va, n, lbl)
