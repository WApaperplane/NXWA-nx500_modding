#!/usr/bin/env python3
"""st 命令表猎人 v2 —— 解出 p7 的 st shell 命令分发表（8B 条目 {name, handler}）。

dispatcher = FUN_00046f70 @ 0x80046f70
  walker: ldr r4,[r6, r5, lsl #3]      ; 取 name 指针（8B 步长）
          bl  strcmp                   ; 0x8050bea4
          ldr r3,[r5, #4] ; blx r3     ; 命中则调 handler

表基址在调用者里用 `ldr rN,[pc,#imm]` 或 movw/movt 装入。
本脚本解析两类装载，dump 表内容。
"""
import struct, re
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_LITTLE_ENDIAN

BIN = 'raw8/p7/p7_full.bin'
VA = 0x80000000
d = open(BIN, 'rb').read()
md = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)
md.detail = True


def rd32(off):
    return struct.unpack('<I', d[off:off + 4])[0]


def rdstr(va):
    off = va - VA
    if off < 0 or off >= len(d):
        return None
    e = d.find(b'\x00', off)
    if e < 0:
        return None
    try:
        return d[off:e].decode('latin1')
    except Exception:
        return None


def disasm(va, nbytes):
    off = va - VA
    return list(md.disasm(d[off:off + nbytes], va))


def resolve_pc_literal(ins):
    """ldr rX,[pc,#imm] -> (reg, target_va, value)"""
    if ins.mnemonic != 'ldr' or 'pc' not in ins.op_str:
        return None
    m = re.search(r'#(-?0x[0-9a-f]+)', ins.op_str)
    if not m:
        return None
    addr = ins.address + 8 + int(m.group(1), 16)
    if addr < VA or addr + 4 > VA + len(d):
        return None
    mreg = re.match(r'(r\d+|sl|fp|ip|sp|lr|pc)', ins.op_str)
    reg = mreg.group(1) if mreg else '?'
    return (reg, addr, rd32(addr - VA))


def find_tables(va, span=0x100):
    """在 [va-span, va] 里找所有可能装入的 32 位指针（literal 或 movw/movt）。"""
    found = []
    insns = disasm(va - span, span + 4)
    mv = {}
    for ins in insns:
        lit = resolve_pc_literal(ins)
        if lit and VA <= lit[2] < VA + len(d):
            found.append((ins.address, 'lit', lit[2]))
        if ins.mnemonic == 'movw' and len(ins.operands) == 2:
            mv[ins.operands[0].reg] = ins.operands[1].imm & 0xFFFF
        elif ins.mnemonic == 'movt' and len(ins.operands) == 2:
            r = ins.operands[0].reg
            v = ((ins.operands[1].imm & 0xFFFF) << 16) | mv.get(r, 0)
            if VA <= v < VA + len(d):
                found.append((ins.address, 'mwmt', v))
    return found


def looks_like_table(base_va, min_entries=3):
    """8B 条目 {char* name; fn}，至少 min_entries 个合法名字。"""
    off = base_va - VA
    n = 0
    for k in range(64):
        nv = rd32(off + 8 * k)
        fv = rd32(off + 8 * k + 4)
        if nv == 0:
            break
        s = rdstr(nv)
        if not s or len(s) > 40 or not all(32 <= ord(c) < 127 for c in s):
            break
        if not (VA <= fv < VA + len(d)):
            break
        n += 1
    return n if n >= min_entries else 0


def dump_table(base_va):
    off = base_va - VA
    rows = []
    for k in range(256):
        nv = rd32(off + 8 * k)
        fv = rd32(off + 8 * k + 4)
        if nv == 0:
            break
        s = rdstr(nv)
        if not s or len(s) > 40 or not all(32 <= ord(c) < 127 for c in s):
            break
        rows.append((k, s, fv))
    return rows


if __name__ == '__main__':
    callers = [0x8004765c, 0x80047978, 0x80047a2c, 0x80047bf8, 0x80047d20]
    seen = {}
    for c in callers:
        print(f'\n=== caller @{c:#x} 的候选表指针 ===')
        cands = find_tables(c, span=0x100)
        for addr, kind, v in cands:
            n = looks_like_table(v)
            tag = f'★ TABLE({n} entries)' if n else ''
            print(f'  {addr:#010x} {kind} -> {v:#010x}  {tag}')
            if n:
                seen[v] = n
    print('\n' + '=' * 60)
    for base, n in seen.items():
        print(f'\n### 命令表 @ {base:#010x}  ({n} 条)')
        for k, s, fn in dump_table(base):
            print(f'  [{k:2d}] {s:24s} -> {fn:#010x}')
