#!/usr/bin/env python3
"""从 ARM32 ELF32 共享库里提取「函数 → PC-relative 字面量池常量」。

动机：三星 libudd5.so 里 NOG/3DLUT 寄存器偏移是**编译期常量**，
写进 .text 末尾的字面量池（ldr rX, =0x...），再用 base+offset 寻址。
所以只要把每个函数体后面的字面量池全 dump 出来，就能拿到**真实寄存器偏移**，
而不是靠读 ep_type.h 猜（记忆铁律：能自证就别猜）。

只用标准库。同时给出 rodata 里的字符串，方便确认函数语义。
"""
import struct
import sys
from pathlib import Path

SHT_PROGBITS = 1
SHT_SYMTAB = 2
SHT_NOBITS = 8
# ★ 共享库只有 .dynsym(type=11=SHT_DYNSYM)，没有 .symtab(2)。
#   只判 type==2 会把整个符号表跳过（踩过：--list 输出 0 行）。
SHT_DYNSYM = 11


def load_elf(path: Path):
    d = path.read_bytes()
    if d[:4] != b"\x7fELF" or d[4] != 1:
        raise SystemExit("need ELF32 LE")
    (e_type, e_machine, e_version, e_entry, e_phoff, e_shoff, e_flags,
     e_ehsize, e_phentsize, e_phnum, e_shentsize, e_shnum,
     e_shstrndx) = struct.unpack_from("<HHIIIIIHHHHHH", d, 16)

    secs = []
    for i in range(e_shnum):
        b = e_shoff + i * e_shentsize
        (name, stype, flags, addr, off, size, link, info,
         align, entsize) = struct.unpack_from("<IIIIIIIIII", d, b)
        secs.append(dict(name_off=name, type=stype, flags=flags, addr=addr,
                         off=off, size=size, link=link, info=info,
                         entsize=entsize))
    shstr = secs[e_shstrndx]
    for s in secs:
        b = shstr["off"] + s["name_off"]
        s["name"] = d[b:d.index(b"\0", b)].decode()
    return d, secs, e_machine


def read_syms(d, secs):
    out = {}
    for s in secs:
        if s["type"] not in (SHT_SYMTAB, SHT_DYNSYM):
            continue
        strt = secs[s["link"]]
        n = s["size"] // 16
        for i in range(n):
            b = s["off"] + i * 16
            nameoff, value, size, info, other, shndx = struct.unpack_from(
                "<IIIBBH", d, b)
            if nameoff == 0:
                continue
            p = strt["off"] + nameoff
            name = d[p:d.index(b"\0", p)].decode(errors="replace")
            out[name] = (value, size, info >> 4, shndx, s)
    return out


def arm_pool_consts(code: bytes):
    """扫 ARM 字面量池：返回 (offset, value)。

    两种模式：
      LDR rX, [pc, #imm]  → imm8*4 + (pc&~3) + 8
      LDR rX, =label      → 编码 0xe5..0101111，值在后面连续字里
    简化：直接把所有「看起来像偏移/常量」的字按顺序列出，交给人判断。
    这里做的是字面量池的粗提取：连续的非指令字（>=0x1000 或高位 0x0/0x1 稀疏值）。
    """
    n = len(code) // 4
    words = struct.unpack_from("<%dI" % n, code, 0)
    hits = []
    # 找 ldr rX,[pc,#imm] = 0xe59f_nnnn
    for i, w in enumerate(words):
        if (w & 0xFFFF0000) == 0xE59F0000:
            imm = (w & 0xFFF) << 2
            pc = (i + 2) * 4
            addr = ((pc) & ~3) + imm
            if addr + 4 <= len(code):
                val = struct.unpack_from("<I", code, addr)[0]
                if val > 0x60:
                    hits.append((i * 4, val, "LDR-literal"))
    return hits


def main():
    path = Path(sys.argv[1])
    d, secs, mach = load_elf(path)
    syms = read_syms(d, secs)
    if len(sys.argv) > 1 and sys.argv[2] == "--list":
        for n in sorted(syms):
            v, sz, bind, shndx, s = syms[n]
            sec = secs[shndx]["name"] if shndx < len(secs) else "?"
            print("%-40s %08x sz=%-5d %-8s %s" % (n, v, sz, sec, bind))
        return

    pats = sys.argv[2:] or ["nog", "3dl"]
    print("machine=%d (40=ARM)" % mach)
    text = next((s for s in secs if s["name"] == ".text"), None)
    if not text:
        raise SystemExit("no .text")
    print(".text addr=%08x off=%d size=%d" % (text["addr"], text["off"], text["size"]))
    tdata = d[text["off"]:text["off"] + text["size"]]

    for name in sorted(syms):
        low = name.lower()
        if not any(p in low for p in pats):
            continue
        v, sz, bind, shndx, s = syms[name]
        if shndx != text["name_off"] and secs[shndx]["name"] != ".text":
            continue
        if sz == 0:
            continue
        start = v - text["addr"]
        if start < 0 or start + sz > len(tdata):
            continue
        body = tdata[start:start + sz]
        hits = arm_pool_consts(body)
        print("\n=== %s @ %08x  size=%d ===" % (name, v, sz))
        for off, val, kind in hits:
            print("    +0x%04x  %08x  %s" % (off, val, kind))
        # 同时给出函数末尾的字面量池原始内容
        tail = body[-64:]
        tailw = struct.unpack_from("<%dI" % (len(tail) // 4), tail, 0)
        print("    tail: " + " ".join("%08x" % x for x in tailw))


if __name__ == "__main__":
    main()
