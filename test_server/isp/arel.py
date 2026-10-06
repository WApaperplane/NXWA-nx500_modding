#!/usr/bin/env python3
"""ARM32 ELF：把重定位条目解析成「哪个函数引用了哪个符号」。

用途：定位某个全局变量（如 ep_nog_reg_base）到底被**哪些函数**写/读，
从而确认「谁负责初始化它」——这是「找入口」的关键一步。

踩过的坑：
  1. 共享库只有 .dynsym(type=11)，只判 type==2 会全跳过。
  2. 符号名表用 sh_link 指向的 strtab；按 nameoff 直接切会越界，
     必须先检查 nameoff < strtab.size。
  3. R_ARM_ABS32(2) / R_ARM_GLOB_DAT(21) / R_ARM_JUMP_SLOT(22) 都可能出现，
     过滤时不能只认一种。
"""
import struct
import sys
from pathlib import Path

SHT_REL = 9
SHT_RELA = 4
SHT_SYMTAB = 2
SHT_DYNSYM = 11

R_ARM_ABS32 = 2
R_ARM_GLOB_DAT = 21
R_ARM_JUMP_SLOT = 22
R_ARM_RELATIVE = 23
R_ARM_COPY = 20


def load(path):
    d = path.read_bytes()
    if d[:4] != b"\x7fELF" or d[4] != 1:
        raise SystemExit("need ELF32 LE: %s" % path)
    (_t, mach, _v, _e, _ph, shoff, _f, _eh, _pe, _pn,
     shent, shnum, shstrndx) = struct.unpack_from("<HHIIIIIHHHHHH", d, 16)
    raw = [struct.unpack_from("<IIIIIIIIII", d, shoff + i * shent)
           for i in range(shnum)]
    shstr = raw[shstrndx]

    def nm(off):
        p = shstr[4] + off
        e = d.find(b"\0", p)
        return d[p:e if e >= 0 else len(d)].decode(errors="replace")

    secs = []
    for s in raw:
        secs.append(dict(name=nm(s[0]), type=s[1], addr=s[3], off=s[4],
                         size=s[5], link=s[6], entsize=s[9]))
    return d, secs, mach, shstr


def sym_name(d, secs, sec, idx):
    st = secs[sec["link"]]
    p = sec["off"] + idx * 16
    if p + 16 > len(d):
        return None, 0
    nameoff, value, size, info, other, shndx = struct.unpack_from(
        "<IIIBBH", d, p)
    if nameoff == 0 or nameoff >= st["size"]:
        return None, value
    q = st["off"] + nameoff
    e = d.find(b"\0", q)
    if e < 0:
        return None, value
    return d[q:e].decode(errors="replace"), value


def func_of_addr(secs, addr, syms_sorted):
    lo, hi = 0, len(syms_sorted) - 1
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        nm, st, sz = syms_sorted[mid]
        if st <= addr:
            best = (nm, st, sz)
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def main():
    path = Path(sys.argv[1])
    want = [a.lower() for a in sys.argv[2:]]
    if not want:
        raise SystemExit("usage: arel.py <lib.so> <sym-substr>...")
    d, secs, mach, shstr = load(path)

    # 收集 FUNC 符号（用于 reloc offset -> 函数名）
    funcs = []
    for s in secs:
        if s["type"] not in (SHT_SYMTAB, SHT_DYNSYM):
            continue
        n = s["size"] // 16
        for i in range(n):
            name, val = sym_name(d, secs, s, i)
            if not name:
                continue
            p = s["off"] + i * 16
            _no, _v, sz, info, _o, shndx = struct.unpack_from("<IIIBBH", d, p)
            if (info & 0xF) == 2 and sz > 0:  # STT_FUNC=2（低 4 位是 type，
                # 高 4 位是 binding —— 踩过：用 >>4 判 type 会得到 funcs=0）
                funcs.append((name, val, sz))
    funcs.sort(key=lambda x: x[1])
    print("# %s  funcs=%d  machine=%d" % (path.name, len(funcs), mach))

    found = False
    for s in secs:
        if s["type"] not in (SHT_REL, SHT_RELA):
            continue
        step = 8 if s["type"] == SHT_REL else 12
        cnt = s["size"] // step
        for i in range(cnt):
            base = s["off"] + i * step
            r_offset, r_info = struct.unpack_from("<II", d, base)
            sym = r_info >> 8
            rtype = r_info & 0xFF
            if sym == 0:
                if rtype != R_ARM_RELATIVE:
                    continue
                name = None
            else:
                name, _ = sym_name(d, secs, s, sym)
            if not name:
                continue
            low = name.lower()
            if not any(w in low for w in want):
                continue
            fn = func_of_addr(secs, s["addr"] + r_offset, funcs)
            found = True
            print("%-14s off=0x%08x type=%-3d  sym=%-28s  in %s" % (
                s["name"], s["addr"] + r_offset, rtype, name,
                ("%s+0x%x" % (fn[0], r_offset - fn[1])) if fn else "?"))
    if not found:
        print("(no relocation matches %s)" % want)


if __name__ == "__main__":
    main()
