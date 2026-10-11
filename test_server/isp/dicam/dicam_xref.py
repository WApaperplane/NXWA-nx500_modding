#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""di-camera-app 引用点定位器：
给定 (名称, 文件偏移) 的字符串表，扫描二进制里对该字符串虚拟地址的 4 字节小端引用。

地址映射（由 readelf -l 确认）：
  file_off <  0x4384ac           → vaddr = off + 0x8000   (R E 段: .text/.rodata/...)
  file_off >= 0x4384ac           → vaddr = off + 0x10000  (RW 段: .data/.bss)

输出：每个目标命中的 文件偏移、换算 vaddr、区域名。
区域边界（file offsets）:
  .plt     [0xa3600, 0xa6948)
  .text    [0xa6948, 0x360fd8)
  .rodata  [0x360fd8, 0x42de10)   # .rodata 0xc7e38 → ends 0x42de10 (incl extab)
  .data    [0x439c00, 0x48d0b0)
"""
import struct
import sys
from pathlib import Path

BIN = Path(r"E:/NXWA/fw/v1.12/extract/di-camera-app/com.samsung.di-camera-app/bin/di-camera-app")

REGIONS = [
    (0x000000, "elf-headers", "file [0,0x8000)"),
    (0x0a3600, ".plt", None),
    (0x0a6948, ".text", None),
    (0x360fd8, ".rodata", None),
    (0x42de10, ".ARM.extab/exidx", None),
    (0x4384ac, "gap/next-seg", None),
    (0x439c00, ".data", None),
    (0x48d0b0, ".bss(no file)", None),
]


def file_to_vaddr(off: int) -> int:
    if off < 0x4384ac:
        return off + 0x8000
    return off + 0x10000


def region_of(off: int) -> str:
    name = "?"
    for start, nm, _ in REGIONS:
        if off >= start:
            name = nm
        else:
            break
    return name


def find_refs(data: bytes, s_off: int, name: str, out) -> None:
    v = file_to_vaddr(s_off)
    pat = struct.pack("<I", v)
    hits = []
    start = 0
    while True:
        i = data.find(pat, start)
        if i < 0:
            break
        hits.append(i)
        start = i + 1
    out.append((name, s_off, v, hits))


def main() -> int:
    data = BIN.read_bytes()

    # 目标表：(名称, 文件偏移) —— 偏移来自 strings 提取
    targets = [
        # PW 菜单消息 id
        ("MSG_MENU_PW", 0x3F7E0C),
        ("MSG_MENU_PW_CUSTOM03", 0x3F80C0),
        ("MSG_MENU_PW_STANDARD", 0x3F938C),
        ("MSG_MENU_PW_PORTRAIT", 0x3F9A98),
        ("MSG_MENU_PW_COOL", 0x3F9BC8),
        ("MSG_MENU_PW_FOREST", 0x3F9BDC),
        ("MSG_MENU_PW_VIVID", 0x3F9F34),
        ("MSG_MENU_PW_LANDSCAPE", 0x3FA554),
        ("MSG_MENU_PW_OFF", 0x401E78),
        # PW 图标
        ("IMAGE_ICON_PW_CUSTOM01", 0x92FE5),
        ("IMAGE_ICON_PW_CUSTOM02", 0x95CC6),
        ("IMAGE_ICON_PW_CUSTOM03", 0x6C90F),
        ("IMAGE_ICON_PW_CUSTOM04", 0x6F47E),
        ("IMAGE_ICON_PW_STANDARD", 0x98B56),
        ("IMAGE_ICON_PW_VIVID", 0x93390),
        ("IMAGE_ICON_PW_PORTRAIT", 0x69DD4),
        ("IMAGE_ICON_PW_LANDSCAPE", 0x76150),
        ("IMAGE_ICON_PW_FOREST", 0x5B85A),
        ("IMAGE_ICON_PW_RETRO", 0x5F319),
        ("IMAGE_ICON_PW_COOL", 0x501CC),
        ("IMAGE_ICON_PW_CALM", 0x75D40),
        ("IMAGE_ICON_PW_CLASSIC", 0x7077A),
        ("IMAGE_ICON_PW_OFF", 0x95E93),
        # PW 快捷键图标
        ("IMAGE_08_HOTKEY_PW_CUSTOM1", 0x9B8CB),
        ("IMAGE_08_HOTKEY_PW_CUSTOM4", 0x6761A),
        ("IMAGE_08_HOTKEY_PW_STANDARD", 0x8890B),
    ]

    out = []
    for name, off in targets:
        find_refs(data, off, name, out)

    print("=" * 100)
    print("%-28s %-10s %-10s %s" % ("name", "stroff", "vaddr", "hits(file_off:region)"))
    print("=" * 100)
    for name, off, v, hits in out:
        hs = " ".join("%x:%s" % (h, region_of(h)) for h in hits)
        print("%-28s 0x%06x   0x%06x   %s" % (name, off, v, hs or "NONE"))

    # 详细输出到文件
    outfile = Path(r"E:/tmp/dicam_strings/xrefs.txt")
    with outfile.open("w") as f:
        for name, off, v, hits in out:
            f.write("### %s  str_off=0x%x vaddr=0x%x\n" % (name, off, v))
            for h in hits:
                f.write("    hit@0x%x region=%s vaddr_of_slot=0x%x\n" % (h, region_of(h), file_to_vaddr(h)))
    print("\n详细 →", outfile)
    return 0


if __name__ == "__main__":
    sys.exit(main())
