#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 run_arm 拉回来的 hexdump 文本转成 ARM 指令并反汇编。

用法: python dishex.py <raw5/d5epopen.txt> [base_addr]
"""
import re
import sys
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM


def parse(path):
    """从 hexdump 文本提取 (addr, bytes)"""
    out = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").split("\n"):
        m = re.match(r"^([0-9a-f]{8})\s+((?:[0-9a-f]{2}\s+){1,16})", line)
        if not m:
            continue
        addr = int(m.group(1), 16)
        bs = [int(x, 16) for x in m.group(2).split()]
        out.append((addr, bs))
    return out


def main():
    path = sys.argv[1]
    rows = parse(path)
    if not rows:
        raise SystemExit("no hexdump rows parsed from " + path)
    data = bytearray()
    base = rows[0][0]
    for a, bs in rows:
        assert a == base + len(data), "gap at 0x%x" % a
        data += bytes(bs)
    print("/* %s : %d bytes @ 0x%08x */" % (Path(path).name, len(data), base))

    cs = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    for i in cs.disasm(bytes(data), base):
        print("  %08x:  %-10s %s" % (i.address, i.mnemonic, i.op_str))


if __name__ == "__main__":
    main()