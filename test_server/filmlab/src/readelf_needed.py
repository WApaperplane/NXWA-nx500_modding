"""从 ARM ELF 的 .dynamic 段读出 DT_NEEDED 全部依赖（真机 EFL 清单的权威来源）。

用途：不靠猜、不靠记忆，直接问「已经在真机上跑通的 mod_gui 到底链了哪些 .so」。
DT_NEEDED 里的 libecore*.so / libevas*.so / libelementary*.so 就是必须补取的文件名。

只解析 ELF32 little-endian ARM（本项目目标平台），够用即可，不引第三方库。
"""
import struct
import sys
from pathlib import Path

DT_NEEDED = 1
DT_STRTAB = 5
DT_STRSZ = 10
DT_SONAME = 14


def read_elf32_dyn(path: Path):
    d = path.read_bytes()
    if d[:4] != b"\x7fELF":
        raise SystemExit("not an ELF: %s" % path)
    if d[4] != 1:
        raise SystemExit("not ELF32: %s" % path)

    # 程序头 → 找 PT_DYNAMIC(=2)
    e_phoff = struct.unpack_from("<I", d, 28)[0]
    e_phentsize = struct.unpack_from("<H", d, 42)[0]
    e_phnum = struct.unpack_from("<H", d, 44)[0]

    dyn_off = dyn_sz = None
    loads = []
    for i in range(e_phnum):
        b = e_phoff + i * e_phentsize
        p_type = struct.unpack_from("<I", d, b)[0]
        p_offset = struct.unpack_from("<I", d, b + 4)[0]
        p_vaddr = struct.unpack_from("<I", d, b + 8)[0]
        p_filesz = struct.unpack_from("<I", d, b + 16)[0]
        if p_type == 2:  # PT_DYNAMIC
            dyn_off, dyn_sz = p_offset, p_filesz
        if p_type == 1:  # PT_LOAD
            loads.append((p_vaddr, p_offset, p_filesz))

    if dyn_off is None:
        raise SystemExit("no PT_DYNAMIC (statically linked?) : %s" % path)

    def v2o(vaddr):
        for va, off, sz in loads:
            if va <= vaddr < va + sz:
                return off + (vaddr - va)
        raise SystemExit("vaddr 0x%x not in any PT_LOAD" % vaddr)

    # 先扫一遍拿 DT_STRTAB 的 vaddr
    entries = []
    strtab_v = None
    p = dyn_off
    end = dyn_off + dyn_sz
    while p + 8 <= end:
        tag, val = struct.unpack_from("<iI", d, p)
        if tag == 0:
            break
        entries.append((tag, val))
        if tag == DT_STRTAB:
            strtab_v = val
        p += 8

    if strtab_v is None:
        raise SystemExit("no DT_STRTAB")

    # .dynsym 的 st_name 是 strtab 偏移，varlist 式索引需先拿 strtab 在文件里的位置
    strtab_o = v2o(strtab_v)

    def s(off):
        end_i = d.index(b"\x00", strtab_o + off)
        return d[strtab_o + off : end_i].decode("utf-8", "replace")

    needed, soname = [], None
    for tag, val in entries:
        if tag == DT_NEEDED:
            needed.append(s(val))
        elif tag == DT_SONAME:
            soname = s(val)
    return soname, needed


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: readelf_needed.py <elf> [elf...]")
        return 2
    for a in sys.argv[1:]:
        p = Path(a)
        if not p.is_file():
            print("!! 缺文件: %s" % p)
            continue
        soname, needed = read_elf32_dyn(p)
        print("=" * 70)
        print("%s   SONAME=%s" % (p.name, soname or "-"))
        print("-" * 70)
        for n in needed:
            print("  %s" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
