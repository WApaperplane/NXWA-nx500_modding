"""提取 ARM ELF32 的 .dynsym：区分【已定义=导出】与【未定义=需要别人提供】。

★ 核心用法（真机符号白名单）：
  mod_gui 是在 NX500 真机上跑通的可执行文件，它 .dynsym 里的 UNDEF 符号
  按前缀天然归属到某个库：
      ecore_*  → libecore.so.1
      ecore_evas_* → libecore_evas.so.1
      ecore_input_* → libecore_input.so.1
      evas_*  → libevas.so.1
      eina_*  → libeina.so.1
      elm_*   → libelementary.so.1
  所以「mod_gui 用到了 ecore_event_handler_add」就是**该符号存在于真机
  libecore.so.1 的直接证据**——比凭 EFL 版本记忆推断可靠得多。

不引第三方库，只处理 ELF32 little-endian。
"""
import struct
import sys
from pathlib import Path

SHN_UNDEF = 0
STB_GLOBAL = 1
STB_WEAK = 2


def dynsym(path: Path):
    """返回 (defined, undefined)：[(name, bind)]，已排序。"""
    d = path.read_bytes()
    if d[:4] != b"\x7fELF" or d[4] != 1:
        raise SystemExit("need ELF32 LE: %s" % path)

    e_shoff = struct.unpack_from("<I", d, 32)[0]
    e_shentsize = struct.unpack_from("<H", d, 46)[0]
    e_shnum = struct.unpack_from("<H", d, 48)[0]
    e_shstrndx = struct.unpack_from("<H", d, 50)[0]

    secs = []
    for i in range(e_shnum):
        b = e_shoff + i * e_shentsize
        nameoff, stype, flags, addr, off, size, link, info, align, entsize = struct.unpack_from(
            "<10I", d, b
        )
        secs.append(dict(nameoff=nameoff, type=stype, off=off, size=size,
                         link=link, entsize=entsize))

    # 节名表
    shstr = secs[e_shstrndx]
    def sname(off):
        end = d.index(b"\x00", shstr["off"] + off)
        return d[shstr["off"] + off : end].decode("ascii", "replace")

    for s in secs:
        s["name"] = sname(s["nameoff"])

    dynsym_sect = None
    for s in secs:
        if s["name"] == ".dynsym":
            dynsym_sect = s
            break
    if not dynsym_sect:
        raise SystemExit("no .dynsym in %s" % path)

    # 关联的字符串表（link 指向 .dynstr）
    strtab = secs[dynsym_sect["link"]]

    def s(off):
        base = strtab["off"] + off
        end = d.index(b"\x00", base)
        return d[base:end].decode("utf-8", "replace")

    defined, undefined = [], []
    n = dynsym_sect["size"] // 16  # Elf32_Sym = 16 bytes
    off = dynsym_sect["off"]
    for i in range(n):
        st_name, st_value, st_size = struct.unpack_from("<3I", d, off)
        st_info = d[off + 12]
        if st_name == 0:
            off += 16
            continue
        nm = s(st_name)
        bind = st_info >> 4
        shndx = struct.unpack_from("<H", d, off + 14)[0]
        if shndx == SHN_UNDEF:
            if nm not in ("", "_init", "_fini", "__gmon_start__", "_ITM_deregisterTMCloneTable",
                          "__cxa_finalize", "__gmon_start", "_Jv_RegisterClasses",
                          "_ITM_registerTMCloneTable"):
                undefined.append(nm)
        else:
            defined.append(nm)
        off += 16
    return sorted(set(defined)), sorted(set(undefined))


PREFIX_LIB = [
    ("elm_", "libelementary.so.1"),
    ("evas_", "libevas.so.1"),
    ("ecore_evas_", "libecore_evas.so.1"),
    ("ecore_input_", "libecore_input.so.1"),
    ("ecore_file_", "libecore_file.so.1"),
    ("ecore_", "libecore.so.1"),
    ("eina_", "libeina.so.1"),
    ("edje_", "libedje.so.1"),
]


def owner(nm):
    for p, lib in PREFIX_LIB:
        if nm.startswith(p):
            return lib
    return None


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: dynsym.py <elf> [--libs]")
        return 2
    libs_mode = "--libs" in sys.argv
    for a in sys.argv[1:]:
        if a.startswith("--"):
            continue
        p = Path(a)
        if not p.is_file():
            print("!! 缺文件: %s" % p)
            continue
        defined, undefined = dynsym(p)
        print("=" * 72)
        print("%s   导出 %d  需外部提供 %d" % (p.name, len(defined), len(undefined)))
        print("=" * 72)
        if libs_mode:
            buckets = {}
            for nm in undefined:
                lib = owner(nm) or "(非 EFL)"
                buckets.setdefault(lib, []).append(nm)
            for lib in sorted(buckets):
                names = buckets[lib]
                print("\n--- %s : %d 个 ---" % (lib, len(names)))
                for nm in names:
                    print("  %s" % nm)
        else:
            print("--- 需外部提供 ---")
            for nm in undefined:
                print("  %s" % nm)
    return 0


if __name__ == "__main__":
    sys.exit(main())
