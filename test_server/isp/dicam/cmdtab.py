#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""App 命令表解析器（di-camera-app / NX500 v1.12）

表 @vaddr 0x449d28，8B/项 {name_ptr, handler_ptr}，遇零词或 name=='end' 停。
name_ptr 指向的串直接读文件字节（不依赖 all.txt，避免漏注解）。
"""
import struct
import sys
from pathlib import Path

BIN = Path(r"E:/NXWA/fw/v1.12/extract/di-camera-app/com.samsung.di-camera-app/bin/di-camera-app")

THRESH = 0x4484AC


def v2f(v):
    return v - (0x8000 if v < THRESH else 0x10000)


def f2v(f):
    return f + (0x8000 if f < 0x4384AC else 0x10000)


def cstr(data, vaddr, maxlen=48):
    off = v2f(vaddr)
    if off < 0 or off >= len(data):
        return "<out of file>"
    end = data.index(b"\x00", off) if b"\x00" in data[off:off + maxlen] else off + maxlen
    raw = data[off:end]
    try:
        return raw.decode("ascii")
    except UnicodeDecodeError:
        return "<non-ascii %s>" % raw.hex()


def main():
    data = BIN.read_bytes()
    lo = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x449D28
    hi = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x449E40
    off = v2f(lo)
    print("=== App 命令表 %#x..%#x (file %#x) ===" % (lo, hi, off))
    i = 0
    while off + 8 <= v2f(hi):
        name_v, handler_v = struct.unpack("<II", data[off:off + 8])
        if name_v == 0 or handler_v == 0:
            print("  [%02d] file %#x  -> 零词，表结束" % (i, off))
            break
        nm = cstr(data, name_v)
        print("  [%02d] name %#010x -> %-22r  handler %#010x (file %#x)"
              % (i, name_v, nm, handler_v, v2f(handler_v)))
        if nm == "end":
            print("       ^ 'end' 哨兵")
            break
        off += 8
        i += 1


if __name__ == "__main__":
    main()
