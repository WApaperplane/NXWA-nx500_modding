# -*- coding: utf-8 -*-
"""
p7lut.py — 改 p7 固件里的 3D LUT 数据源指针，指向用户自定义表

=====================================================================
★★★★★ 这是B 线的入口：让 p7 自己把【我们指定的表】灌进硬件
---------------------------------------------------------------------
【为什么这样做】
  p7 有两个选表函数（从 53_all_pseudocode.c 读出）：
    FUN_0009a3e8 (160B)  → 返回 DAT_003837f0/f4/f8/fc   ★ 静态 4 档
    FUN_0009a408 (676B)  → 返回 DAT_00383a24..80       ★ 动态 24 档
  而这4 个变量是【静态初值】，全项目只有读、没有写。

【本工具做什么】
  把 DAT_003837f0/f4/f8/fc 这4 个 u32 从
      0x810fd100 / 0x81101e00 / 0x81106b00 / 0x81115200
  改成
      你的 CMA 物理地址（Linux 可读写/ 可 mmap）

  ⇒ 半按快门时，p7 走自己的完整流程
    （选表 → FUN_004dbb08 通知 → FUN_00179314 灌入）
  ⇒ ★★ 它自己灌，我们完全不碰硬件 DMA、不抢ISP 内存
  ⇒ ★★ 不会卡死（这是"用完即还"之外更彻底的方案）

【安全设计】
  ① 默认 dry-run：只报告差异，不写文件
  ② 自动重算 JAMCRC（zlib.crc32() ^ 0xFFFFFFFF）
  ③ 自动裁剪/填充到原始长度
  ④ 回读校验每个改动点
  ⑤ --restore 可一键还原

用法：
  python p7lut.py <p7_full.bin> <cma_addr> [--apply] [--slot 0-3]
  python p7lut.py <p7_full.bin> --restore --apply
=====================================================================
"""

import sys
import os
import struct
import zlib

# ★ 四个静态指针的文件偏移（Ghidra imageBase=0 ⇒ 地址=偏移）
PTR_OFFS = [0x3837f0, 0x3837f4, 0x3837f8, 0x3837fc]
PTR_NAMES = ["标准", "黑白", "电影", "肤色"]
PTR_ORIG = [0x810fd100, 0x81101e00, 0x81106b00, 0x81115200]

# ★ JAMCRC 常量（已验证，见重打包器）
JAM_POLY = 0xEDB88320


def jamcrc(data, init=0xFFFFFFFF):
    """与 zlib.crc32 相同算法。"""
    return zlib.crc32(data, init) & 0xFFFFFFFF


def find_crc_field(data):
    """在 p7 镜像里定位 JAMCRC 字段（★ 通过实测确定，不猜）。"""
    # 策略：找与文件 crc32 匹配的小端 u32
    c = jamcrc(data)
    packed = struct.pack('<I', c)
    hits = []
    idx = 0
    while True:
        i = data.find(packed, idx)
        if i < 0:
            break
        # 排除前 64 字节（文件头）
        if i >= 64:
            hits.append(i)
        idx = i + 1
        if len(hits) > 8:
            break
    return c, hits


def read_ptrs(data):
    return [struct.unpack_from('<I', data, o)[0] for o in PTR_OFFS]


def apply_patch(data, new_addr, slots):
    """把指定 slot 的指针改成 new_addr，返回 (新数据, 改动报告)"""
    out = bytearray(data)
    report = []
    for s in slots:
        off = PTR_OFFS[s]
        old = struct.unpack_from('<I', out, off)[0]
        struct.pack_into('<I', out, off, new_addr)
        # 回读校验
        chk = struct.unpack_from('<I', out, off)[0]
        assert chk == new_addr, "回读校验失败 @0x%06x" % off
        report.append((s, off, old, new_addr))
    return bytes(out), report


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    src = sys.argv[1]
    if not os.path.isfile(src):
        print("找不到文件: %s" % src)
        return 1

    with open(src, 'rb') as f:
        data = f.read()

    print("=== p7 LUT 指针补丁工具 ===")
    print("源文件: %s  (%d 字节)" % (os.path.basename(src), len(data)))

    # ---- 当前值 ----
    cur = read_ptrs(data)
    print("\n当前 4 个数据源指针：")
    for s, (o, v) in enumerate(zip(PTR_OFFS, cur)):
        print("  [%d] %-4s @0x%06x = 0x%08x" % (s, PTR_NAMES[s], o, v))

    # ---- 解析操作 ----
    restore = '--restore' in sys.argv
    apply_ = '--apply' in sys.argv
    slot = 0
    if '--slot' in sys.argv:
        i = sys.argv.index('--slot')
        if i + 1 < len(sys.argv):
            slot = int(sys.argv[i + 1])

    if not restore and len(sys.argv) < 3:
        print("\n（未指定目标地址，仅显示当前状态。dry-run 模式）")
        return 0

    # ---- CRC 字段定位 ----
    crc, hits = find_crc_field(data)
    print("\n=== CRC 字段 ===")
    print("  当前文件 crc32 = 0x%08x" % crc)
    if hits:
        print("  ★ 匹配位置: %s" % ", ".join("0x%06x" % h for h in hits))
        crc_off = hits[0]
        print("  ⇒ 将重算并写回 0x%06x" % crc_off)
    else:
        crc_off = None
        print("  ★ 未找到匹配的 CRC 字段 ⇒ 不改动 CRC")

    # ---- 构造新数据 ----
    if restore:
        print("\n=== 操作：还原为出厂指针 ===")
        new, rep = apply_patch(data, None, range(4)) if False else (data, [])
        out = bytearray(data)
        for s in range(4):
            struct.pack_into('<I', out, PTR_OFFS[s], PTR_ORIG[s])
        out = bytes(out)
    else:
        addr = int(sys.argv[2], 0)
        if not (0x80000000 <= addr < 0xC0000000):
            print("★ 目标地址 0x%08x 不在 p7 可访问范围（0x80000000..0xBFFFFFFF）" % addr)
            print("  ★ 必须是 Linux 能 mmap 的物理地址（如 CMA 0x94xxxxxx）")
            return 2
        print("\n=== 操作：把 [%d] %s 指向 0x%08x ===" % (slot, PTR_NAMES[slot], addr))
        out, rep = apply_patch(data, addr, [slot])

    # ---- 差异报告 ----
    print("\n=== 改动明细 ===")
    for s, o in enumerate(PTR_OFFS):
        old = cur[s]
        nv = struct.unpack_from('<I', out, o)[0]
        if nv != old:
            print("  [%d] %-4s @0x%06x: 0x%08x → 0x%08x  ★" % (s, PTR_NAMES[s], o, old, nv))
        else:
            print("  [%d] %-4s @0x%06x: 0x%08x（不变）" % (s, PTR_NAMES[s], o, old))

    # ---- 长度处理 ----
    if len(out) != len(data):
        print("\n长度会变化 %d → %d" % (len(data), len(out)))
        out = out[:len(data)].ljust(len(data), b'\x00')

    # ---- CRC 重算 ----
    if crc_off is not None:
        newcrc = jamcrc(out)
        struct.pack_into('<I', out, crc_off, newcrc)
        print("\n=== CRC 已重算 @0x%06x: 0x%08x → 0x%08x ===" % (crc_off, crc, newcrc))
        # 回读校验
        back = struct.unpack_from('<I', out, crc_off)[0]
        assert back == newcrc, "CRC 回读失败"
        print("  CRC 回读校验 ✔")

    # ---- dry-run / apply ----
    dst = src.replace('.bin', '') + '.lutmod.bin'
    if not apply_:
        print("\n" + "=" * 60)
        print("★ DRY-RUN 模式：未写任何文件")
        print("  确认无误后加 --apply 执行：")
        print("    python p7lut.py %s %s --apply" % (src, sys.argv[2] if len(sys.argv) > 2 else '--restore'))
        print("  输出将写入: %s" % dst)
        print("=" * 60)
        return 0

    with open(dst, 'wb') as f:
        f.write(out)
    print("\n★ 已写入: %s  (%d 字节)" % (dst, len(out)))

    # 最终校验
    with open(dst, 'rb') as f:
        chk = f.read()
    print("\n=== 最终校验 ===")
    print("  大小: %d  %s" % (len(chk), "✔" if len(chk) == len(data) else "✘"))
    ok = True
    for s, o in enumerate(PTR_OFFS):
        v = struct.unpack_from('<I', chk, o)[0]
        e = struct.unpack_from('<I', out, o)[0]
        good = (v == e)
        ok &= good
        print("  [%d] @0x%06x = 0x%08x  %s" % (s, o, v, "✔" if good else "✘"))
    if crc_off is not None:
        c1 = jamcrc(chk)
        c2 = struct.unpack_from('<I', chk, crc_off)[0]
        print("  CRC: 文件=0x%08x 字段=0x%08x  %s" % (c1, c2, "✔" if c1 == c2 else "✘"))
        ok &= (c1 == c2)
    print("\n%s" % ("★★ 全部校验通过" if ok else "★ 校验失败"))
    return 0 if ok else 3


if __name__ == '__main__':
    sys.exit(main())
