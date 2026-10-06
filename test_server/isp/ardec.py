#!/usr/bin/env python3
"""从 ARM32 共享库反汇编中提取「结构体字段偏移」与「寄存器偏移」。

背景：libudd5.so 的 NOG/3DLUT 访问是两层
    ep_nog_reg_base (全局 .bss，运行时 = mmap 后的 EP 虚拟基址)
      → _udd_ep_nog_regset0/1 (.bss，运行时填入 regset 结构指针)
        → 结构体 {void *reg_base; ...} → base + 字段偏移
所以「偏移」藏在两种地方：
  A. 立即数偏移：ADD rX, rY, #imm12 / LDR/STR [rX, #imm]
  B. 字面量池里的绝对偏移（我第一版只抓到 B 的 LDR-literal，且阈值卡太死）

本工具两种都抓，并按函数分组。只用标准库。

★ 教训：ARM 位域必须按规则解码，「猜编码必错」（记忆铁律 12）。
  这里用显式掩码+移位，不做任何语义假设。
"""
import struct
import sys
from pathlib import Path

SHT_SYMTAB = 2
SHT_DYNSYM = 11


def load_elf(path: Path):
    d = path.read_bytes()
    if d[:4] != b"\x7fELF" or d[4] != 1:
        raise SystemExit("need ELF32 LE")
    v = struct.unpack_from("<HHIIIIIHHHHHH", d, 16)
    (_t, mach, _ver, _entry, _phoff, shoff, _fl, _eh, _phe, _phn,
     shent, shnum, shstrndx) = v
    raw = []
    for i in range(shnum):
        b = shoff + i * shent
        raw.append(struct.unpack_from("<IIIIIIIIII", d, b))
    shstr = raw[shstrndx]

    def nm(off):
        p = shstr[4] + off
        return d[p:d.index(b"\0", p)].decode(errors="replace")

    secs = []
    for i, s in enumerate(raw):
        secs.append(dict(idx=i, name=nm(s[0]), type=s[1], addr=s[3],
                         off=s[4], size=s[5], link=s[6], entsize=s[9]))
    return d, secs, mach


def read_syms(d, secs):
    out = {}
    for s in secs:
        if s["type"] not in (SHT_SYMTAB, SHT_DYNSYM):
            continue
        st = secs[s["link"]]
        n = s["size"] // 16
        for i in range(n):
            b = s["off"] + i * 16
            nameoff, value, size, info, other, shndx = struct.unpack_from(
                "<IIIBBH", d, b)
            if nameoff == 0:
                continue
            p = st["off"] + nameoff
            name = d[p:d.index(b"\0", p)].decode(errors="replace")
            out[name] = (value, size, info >> 4, shndx)
    return out


def decode_offsets(body: bytes):
    """返回 [(类别, 立即数, 说明)]。

    ARM 数据处理立即数（ADD/SUB）:  cond 00 I 0101 S Rn Rd operand2
      imm12 = bits[11:0]（I=0）或 imm12 = 0x00000c00 | rot8*2（I=1）
    LDR/STR 立即数偏移:  cond 01 0 P U B W L Rn Rt imm12
    LDR 字面量:         0xE59F_nnnn
    """
    n = len(body) // 4
    words = struct.unpack_from("<%dI" % n, body, 0)
    out = []
    for i, w in enumerate(words):
        off = i * 4
        cond = (w >> 28) & 0xF
        if cond == 0xF:
            continue
        # ---- LDR rX, [pc, #imm] : 0xE59F0000 ----
        if (w & 0x0FFF0000) == 0x059F0000 and (w & 0xF0000000) == 0xE0000000:
            imm = (w & 0xFFF) << 2
            pc = (i + 2) * 4
            at = (pc & ~3) + imm
            if at + 4 <= len(body):
                val = struct.unpack_from("<I", body, at)[0]
                out.append(("LDRlit", val, "pc-relative literal"))
            continue
        # ---- LDR/STR imm12 offset ----
        if (w & 0x0E000000) == 0x04000000:
            I = (w >> 25) & 1
            P = (w >> 24) & 1
            U = (w >> 23) & 1
            B = (w >> 22) & 1
            W = (w >> 21) & 1
            L = (w >> 20) & 1
            Rn = (w >> 16) & 0xF
            Rt = (w >> 12) & 0xF
            imm = w & 0xFFF
            if I == 0 and P == 1 and W == 0 and B == 0:
                kind = "LDR" if L else "STR"
                sign = "" if U else "-"
                if imm:
                    out.append((kind, imm, "[r%d%s%s] r%d" % (Rn, sign, "", Rt)))
            continue
        # ---- ADD/SUB imm ----
        if (w & 0x0E000000) == 0x02000000:
            I = (w >> 25) & 1
            S = (w >> 20) & 1
            Rn = (w >> 16) & 0xF
            Rd = (w >> 12) & 0xF
            op = "ADD" if (w >> 21) & 1 else "SUB"
            if I == 0:
                imm = w & 0xFFF
            else:
                rot = ((w >> 8) & 0xF) * 2
                imm = (w & 0xFF) << rot
            if S == 0 and imm:
                out.append((op, imm, "r%d -> r%d" % (Rn, Rd)))
            continue
        # ---- MOV imm ----
        if (w & 0x0FE00000) == 0x03A00000:
            Rd = (w >> 12) & 0xF
            rot = ((w >> 8) & 0xF) * 2
            imm = ((w >> 4) & 0xF000) | (w & 0xFF)
            imm = ((imm >> rot) | (imm << (32 - rot))) & 0xFFFFFFFF if rot else imm
            if imm > 0x40:
                out.append(("MOV", imm, "-> r%d" % Rd))
            continue
    return out


def main():
    path = Path(sys.argv[1])
    d, secs, mach = load_elf(path)
    syms = read_syms(d, secs)
    if len(sys.argv) > 2 and sys.argv[2] == "--list":
        for nm in sorted(syms):
            v, sz, bind, shndx = syms[nm]
            sec = secs[shndx]["name"] if 0 < shndx < len(secs) else "UND"
            print("%-40s %08x sz=%-5d %-10s bind=%d" % (nm, v, sz, sec, bind))
        return

    pats = [p.lower() for p in sys.argv[2:]] or ["nog"]
    text = next(s for s in secs if s["name"] == ".text")
    tdata = d[text["off"]:text["off"] + text["size"]]
    print("# lib=%s  .text @%08x size=%d  machine=%d" % (
        path.name, text["addr"], text["size"], mach))
    for nm in sorted(syms):
        low = nm.lower()
        if not any(p in low for p in pats):
            continue
        v, sz, bind, shndx = syms[nm]
        if sz == 0 or not (0 < shndx < len(secs)) or secs[shndx]["name"] != ".text":
            continue
        st = v - text["addr"]
        if st < 0 or st + sz > len(tdata):
            continue
        items = decode_offsets(tdata[st:st + sz])
        seen = []
        for kind, val, note in items:
            seen.append("%s %s 0x%x  (%s)" % (kind, "", val, note))
        print("\n=== %s @%08x size=%d ===" % (nm, v, sz))
        for line in seen:
            print("    " + line)
        if not seen:
            print("    (no imm offsets)")


if __name__ == "__main__":
    main()
