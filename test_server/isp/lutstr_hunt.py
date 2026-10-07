#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lutstr_hunt.py — 批量定位 p7 里 LUT/3DLUT 相关字符串的引用点
用法: python lutstr_hunt.py <substr> [...]
"""
import sys, struct
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_LITTLE_ENDIAN

HERE = Path(__file__).resolve().parent
IMG = HERE.parent.parent / "raw8" / "p7" / "p7_full.bin"
VA_BASE = 0x80000000

data = IMG.read_bytes()
md = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)

def find_refs(va):
    """返回引用 va 的 file offset 列表（裸 4 字节 + movw/movt）"""
    hits = []
    pat = struct.pack("<I", va)
    j = data.find(pat)
    while j != -1:
        hits.append(("raw", j))
        j = data.find(pat, j + 1)
    # movw/movt
    for j in range(0, len(data) - 8, 4):
        w1 = struct.unpack_from("<I", data, j)[0]
        if (w1 & 0x0FF00000) != 0x03000000:
            continue
        rd = (w1 >> 12) & 0xF
        imm16 = ((w1 >> 16) & 0xF) << 12 | (w1 & 0xFFF)
        w2 = struct.unpack_from("<I", data, j + 4)[0]
        if (w2 & 0x0FF00000) != 0x03400000 or ((w2 >> 12) & 0xF) != rd:
            continue
        hi = ((w2 >> 16) & 0xF) << 12 | (w2 & 0xFFF)
        if ((hi << 16) | imm16) == va:
            hits.append(("movw/movt", j))
    return hits

def func_start(off):
    """往回找 func 起点 —— 简化：找最近的前置 push {..,lr}"""
    for j in range(off & ~3, max(0, off - 0x2000), -4):
        w = struct.unpack_from("<I", data, j)[0]
        # push {...lr} : 0xE92Dxxxx with bit14 set
        if (w & 0xFFFF0000) == 0xE92D0000 and (w & 0x4000):
            return j
        if (w & 0xFFFF0000) == 0xE52D0000:  # push {lr}
            return j
    return None

def disasm(off, back=8, fwd=40):
    s = max(0, off - back)
    e = min(len(data), off + fwd)
    out = []
    for ins in md.disasm(data[s:e], s + VA_BASE):
        out.append(f"    {ins.address:08X}: {ins.mnemonic:<8} {ins.op_str}")
    return "\n".join(out)

for sub in sys.argv[1:]:
    nb = sub.encode()
    print(f"\n{'='*70}\n### \"{sub}\"")
    i = data.find(nb)
    cnt = 0
    while i != -1:
        va = i + VA_BASE
        refs = find_refs(va)
        end = data.find(b"\x00", i)
        txt = data[i:end].decode("latin1")
        print(f"\n  STR @ file 0x{i:X} VA 0x{va:X}: {txt!r}")
        if not refs:
            print("    (no refs)")
        for kind, j in refs:
            fs = func_start(j)
            print(f"    ref[{kind}] @ file 0x{j:X} (VA 0x{j+VA_BASE:X}) func_start={'0x%X'%fs if fs else '?'}")
            print(disasm(j, 12, 48))
        i = data.find(nb, i + 1)
        cnt += 1
        if cnt > 8:
            break
