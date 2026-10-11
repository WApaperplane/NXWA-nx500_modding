#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""di-camera-app .data 区转储器：以 4 字节为单位，指针自动注解为字符串。
用法: python dumpdata.py 0x46f850 0x46fb50 [更多范围...]
"""
import struct
import sys
from pathlib import Path

BIN = Path(r"E:/NXWA/fw/v1.12/extract/di-camera-app/com.samsung.di-camera-app/bin/di-camera-app")
STRTAB = Path(r"E:/tmp/dicam_strings/all.txt")


def file_to_vaddr(off: int) -> int:
    return off + (0x8000 if off < 0x4384AC else 0x10000)


def vaddr_to_file(v: int) -> int:
    return v - (0x8000 if v < 0x4484AC else 0x10000)


def load_strings():
    tab = {}
    for line in STRTAB.open(encoding="utf-8"):
        parts = line.rstrip("\n").split("\t", 2)
        if len(parts) != 3:
            continue
        off = int(parts[0], 16)
        tab[file_to_vaddr(off)] = parts[2]
    return tab


def main() -> int:
    data = BIN.read_bytes()
    strs = load_strings()
    ranges = []
    for a in sys.argv[1:]:
        ranges.append(a)
    # 两两一组
    pairs = [(int(ranges[i], 16), int(ranges[i + 1], 16)) for i in range(0, len(ranges) - 1, 2)]
    for lo, hi in pairs:
        print("=" * 96)
        print("range file[0x%x..0x%x)  vaddr[0x%x..0x%x)" % (lo, hi, file_to_vaddr(lo), file_to_vaddr(hi)))
        print("=" * 96)
        off = lo
        zerorun = 0
        while off + 4 <= hi:
            val = struct.unpack("<I", data[off:off + 4])[0]
            if val == 0:
                zerorun += 1
                off += 4
                continue
            if zerorun:
                print("  ... (%d zero words skipped, next @0x%x)" % (zerorun, off))
                zerorun = 0
            ann = ""
            if val in strs:
                ann = "-> STR \"%s\"" % strs[val][:80]
            elif 0x8000 <= val < 0x800000 and val < 0x600000:
                for probe in (val, val - 4, val - 8):
                    if probe in strs:
                        ann = "-> ptr STR \"%s\" (v=0x%x)" % (strs[probe][:60], probe)
                        break
                else:
                    ann = "-> ptr? 0x%x" % val
            elif 0 < val < 0x10000:
                ann = "int %d / 0x%x" % (val, val)
            print("  0x%06x  v:0x%06x  %08x  %s" % (off, file_to_vaddr(off), val, ann))
            off += 4


if __name__ == "__main__":
    sys.exit(main())
