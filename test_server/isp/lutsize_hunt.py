#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lutsize_hunt.py  —  用 E:/nxks2-re 环境，定位 p7 里 LUT 长度校验点

目标字符串:
  0x73c398  "lut size error too large~ (%d) > %d"

思路:
  1. 在 p7_full.bin 里搜该字符串，得到 file offset = VA - 0x80000000
  2. 计算 VA，然后在整个镜像里搜「引用该 VA 的代码」
     - ARM:  movw/movt 立即数装载
     - 也搜 裸 4 字节字面量（Ghidra 风格的 DAT_ 常量池）
  3. 反汇编引用点前后的指令，用 capstone 读算术（上界立即数）
"""
import sys, struct
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_LITTLE_ENDIAN

HERE = Path(__file__).resolve().parent
IMG = HERE.parent.parent / "raw8" / "p7" / "p7_full.bin"
VA_BASE = 0x80000000

data = IMG.read_bytes()
print(f"[i] image = {IMG}")
print(f"[i] size  = {len(data)} (0x{len(data):X})")

# ---- 1. 找字符串 ----
needle = b"lut size error too large"
offs = []
i = data.find(needle)
while i != -1:
    offs.append(i)
    i = data.find(needle, i + 1)
print(f"\n[1] string hits: {[hex(o) for o in offs]}")

if not offs:
    print("!! 字符串不在镜像里（可能被压缩/在别的分区）")
    sys.exit(1)

str_off = offs[0]
str_va = str_off + VA_BASE
print(f"    first: file=0x{str_off:X}  VA=0x{str_va:X}")

# 打印字符串尾部（含 %d > %d）
tail = data[str_off:str_off + 48]
end = tail.find(b"\x00")
print(f"    text: {tail[:end if end>0 else 48]!r}")

# ---- 2. 搜引用 ----
targets = {str_va + o for o in [0]}
# 把字符串起点以及内部偏移都作为可能引用点
for o in offs:
    for extra in range(0, 48):
        if data[o + extra] == 0:
            break
        targets.add(o + extra + VA_BASE)

print(f"\n[2] target VA count = {len(targets)}")

# 2a. 裸 4 字节小端字面量
hits_raw = []
tb = struct.pack
for va in sorted(targets):
    pat = struct.pack("<I", va)
    j = data.find(pat)
    while j != -1:
        hits_raw.append((va, j))
        j = data.find(pat, j + 1)
print(f"[2a] raw 4-byte literal refs = {len(hits_raw)}")
for va, j in hits_raw[:30]:
    print(f"     0x{va:X} <- file 0x{j:X}")

# 2b. movw/movt 立即数装载（ARM: E30?XXXX ... E34?YYYY）
md = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)
md.detail = False
hits_mov = []
step = 4
for j in range(0, len(data) - 8, step):
    w1 = struct.unpack_from("<I", data, j)[0]
    # movw rX, #imm16 : cond 0011 0000 imm4 Rd imm12
    if (w1 & 0x0FF00000) != 0x03000000:
        continue
    rd = (w1 >> 12) & 0xF
    imm4 = (w1 >> 16) & 0xF
    imm12 = w1 & 0xFFF
    imm16 = (imm4 << 12) | imm12
    # 看下一条是否 movt 同一 Rd
    w2 = struct.unpack_from("<I", data, j + 4)[0]
    if (w2 & 0x0FF00000) != 0x03400000:
        continue
    rd2 = (w2 >> 12) & 0xF
    if rd2 != rd:
        continue
    imm4b = (w2 >> 16) & 0xF
    imm12b = w2 & 0xFFF
    hi = (imm4b << 12) | imm12b
    val = (hi << 16) | imm16
    if val in targets:
        hits_mov.append((val, j))
print(f"[2b] movw/movt refs = {len(hits_mov)}")
for va, j in hits_mov[:40]:
    print(f"     0x{va:X} <- file 0x{j:X}  (VA 0x{j+VA_BASE:X})")

# ---- 3. 反汇编每个引用点附近 ----
def disasm_around(off, back=32, fwd=64, label=""):
    s = max(0, off - back)
    e = min(len(data), off + fwd)
    print(f"\n--- disasm @ file 0x{off:X} (VA 0x{off+VA_BASE:X}) {label} ---")
    for ins in md.disasm(data[s:e], s + VA_BASE):
        mark = " <==" if s + (ins.address - VA_BASE) == off else ""
        print(f"  {ins.address:08X}: {ins.mnemonic:<8} {ins.op_str}{mark}")

seen = set()
for va, j in hits_mov[:12]:
    if j in seen: continue
    seen.add(j)
    disasm_around(j, 48, 96, f"ref to 0x{va:X}")

print("\n[done]")
