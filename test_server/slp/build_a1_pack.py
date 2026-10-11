#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_a1_pack.py —— A1（方案 G）待刷 SLP 包构建器。

把 p7（SLP idx5）的两处补丁写进官方 1.12 容器，重算 JAMCRC，提升 version 到 1.16
（U4 实测：UI 层只放行"文件版本 > 设备版本"），产出可交付刷写的 nx500.bin。

两个档位（对应设计文档 §6.1 的灰度两步法）：
  step1 —— 仅把 0x510b0 重定向到 0x11504，而 0x11504 只放一条 `b 0x80051394`
           ⇒ 行为与改前**逐位等价**，用来探「0x11504 所属零区是否会被运行时覆盖」。
           若被覆盖 → p7 立刻出问题，损失最小。
  full  —— 写入 24B 恒等特判块（打通 0x130–0x133 外部直推）。

用法:
  python build_a1_pack.py <官方.bin> <p7原始.bin> <out目录> [--variant step1|full|both] [--version 1.16] [--write]

默认 dry-run（只报告不落盘）。产出文件名：
  slp_a1_p7_g_step1_v116.bin / slp_a1_p7_g_v116.bin
"""
from __future__ import annotations

import argparse
import hashlib
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slp_tool  # noqa: E402

P7_IDX = 5          # SLP 分区 5 = p7 = rtos = ISP 固件本体
B_OFF = 0x510B0     # 越界分支（原 b 0x80051394 拒收）
BLK_OFF = 0x11504   # 特判块落点（引导参数块尾部 254B 零区）

# 0x510b0 新值：b 0x80011504  （ARM B 指令字 0xEAFF0113，文件字节 LE）
REDIRECT = bytes.fromhex("1301ffea")

# full 档：24B 恒等特判块
BLOCK_FULL = bytes.fromhex(
    "13 3e 40 e2 03 00 53 e3 a0 ff 00 8a 00 00 81 e5 00 00 a0 e3 17 ff 00 ea".replace(" ", ""))

# step1 档：只放一条 `b 0x80051394`（= 原拒收路径）
_b = (0x80051394 - (0x80000000 + BLK_OFF + 8)) // 4
BLOCK_STEP1 = struct.pack("<I", 0xEA000000 | (_b & 0xFFFFFF))

VARIANTS = {
    "step1": ("slp_a1_p7_g_step1_v%s.bin", BLOCK_STEP1),
    "full": ("slp_a1_p7_g_v%s.bin", BLOCK_FULL),
}


def apply_patch(p7: bytes, block: bytes) -> bytes:
    """在 p7 镜像上打两处补丁（越界分支重定向 + 特判块）。"""
    buf = bytearray(p7)
    assert buf[B_OFF:B_OFF + 4] == bytes.fromhex("b70000ea"), "0x510b0 原值不是 b 0x80051394，基线不对"
    assert buf[BLK_OFF:BLK_OFF + 24] == b"\x00" * 24, "0x11504 不是 24B 全零空闲区，基线不对"
    buf[B_OFF:B_OFF + 4] = REDIRECT
    buf[BLK_OFF:BLK_OFF + len(block)] = block
    return bytes(buf)


def main():
    ap = argparse.ArgumentParser(description="A1 p7 补丁 SLP 构建（默认 dry-run）")
    ap.add_argument("official")
    ap.add_argument("p7")
    ap.add_argument("outdir")
    ap.add_argument("--variant", default="both", choices=["step1", "full", "both"])
    ap.add_argument("--version", default="1.16")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    meta, parts = slp_tool.parse(a.official, verbose=False)
    p7 = open(a.p7, "rb").read()
    print("官方容器 : %s" % a.official)
    print("  版本 %s / 项目 %s / 分区数 %d" % (meta["version"], meta["project"], len(parts)))
    print("p7 原始  : %s  (%d B, md5 %s)"
          % (a.p7, len(p7), hashlib.md5(p7).hexdigest()))
    print("  SLP[%d] 长度 = %d  一致=%s"
          % (P7_IDX, parts[P7_IDX]["img_len"], parts[P7_IDX]["img_len"] == len(p7)))

    if a.variant == "both":
        todo = ["step1", "full"]
    else:
        todo = [a.variant]

    os.makedirs(a.outdir, exist_ok=True)
    for v in todo:
        name = VARIANTS[v][0] % a.version.replace(".", "")
        out = os.path.join(a.outdir, name)
        newp7 = apply_patch(p7, VARIANTS[v][1])
        newparts = [dict(p) for p in parts]
        newparts[P7_IDX] = dict(newparts[P7_IDX])
        newparts[P7_IDX]["data"] = newp7

        newmeta = dict(meta)
        newmeta["version"] = a.version        # ★ UI 反降级判据；头不在分区内 ⇒ 不影响 JAMCRC
        buf, warn = slp_tool.build(newmeta, newparts, out, write=False)

        print("\n---- variant=%s ----" % v)
        print("  p7 补丁后 md5 = %s" % hashlib.md5(newp7).hexdigest())
        print("  容器 %d B  md5=%s" % (len(buf), hashlib.md5(buf).hexdigest()))
        print("  新 crc32[%d] = %08x (JAMCRC)" % (P7_IDX, slp_tool.crc_jamcrc(newp7)))
        for w in warn:
            print("  [warn] %s" % w)
        if a.write:
            open(out, "wb").write(buf)
            print("  ★ 已写 %s" % out)
        else:
            print("  (dry-run，未落盘；加 --write 才写)")


if __name__ == "__main__":
    sys.exit(main())
