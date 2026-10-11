#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用引用扫描：给定 vaddr 列表，找 LE32 引用并打印 [前1][本体][后1] 三词上下文（带字符串注解）。
用法: python findref.py 0x409eac 0x406974 ...
"""
import struct
import sys
from pathlib import Path

BIN = Path(r"E:/NXWA/fw/v1.12/extract/di-camera-app/com.samsung.di-camera-app/bin/di-camera-app")
STRTAB = Path(r"E:/tmp/dicam_strings/all.txt")


def file_to_vaddr(off: int) -> int:
    return off + (0x8000 if off < 0x4384AC else 0x10000)


def load_strings():
    tab = {}
    for line in STRTAB.open(encoding="utf-8"):
        parts = line.rstrip("\n").split("\t", 2)
        if len(parts) != 3:
            continue
        tab[file_to_vaddr(int(parts[0], 16))] = parts[2]
    return tab


def region_of(off: int) -> str:
    for start, nm in [(0xA3600, ".plt"), (0xA6948, ".text"), (0x360FD8, ".rodata"),
                      (0x42DE10, ".exidx"), (0x4384AC, "gap"), (0x439C00, ".data")]:
        if off >= start:
            name = nm
        else:
            break
    else:
        name = "?"
    return name


def ann(val, strs, file_off):
    if val in strs:
        return "STR \"%s\"" % strs[val][:70]
    # 指向字符串中段？
    for probe in (val, val - 2, val - 4, val - 6, val - 8):
        if probe in strs:
            return "(mid)STR@0x%x \"%s\"" % (probe, strs[probe][:50])
    if off_style(val):
        return "PTR 0x%x" % val
    return "val 0x%x" % val


def off_style(v):
    return 0x8000 <= v < 0x600000


def main() -> int:
    data = BIN.read_bytes()
    strs = load_strings()
    for arg in sys.argv[1:]:
        target = int(arg, 16)
        pat = struct.pack("<I", target)
        hits = []
        start = 0
        while True:
            i = data.find(pat, start)
            if i < 0:
                break
            hits.append(i)
            start = i + 1
        print("### target vaddr=0x%x  (%d hits)" % (target, len(hits)))
        for h in hits:
            ctx = []
            for d in (-4, 0, 4):
                o = h + d
                v = struct.unpack("<I", data[o:o + 4])[0]
                ctx.append("[%+d]%08x %s" % (d, v, ann(v, strs, o)))
            print("   hit@0x%06x (%s): %s" % (h, region_of(h), "  |  ".join(ctx)))
        print()


if __name__ == "__main__":
    sys.exit(main())
