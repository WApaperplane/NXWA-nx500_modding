#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extract_variants.py —— 从 SLP 成品包提取 p7 镜像与 QEMU 测试区段。

「包级真字节」测试的一级输入：测试对象 = **将要刷入相机的字节**，
即从 slp_a1_p7_g(*).bin 里解出的 idx5（p7 镜像），而非重新打补丁的中间产物。

用法（WSL 或 Windows 均可，纯标准库）:
    python3 extract_variants.py <官方包> <step1包> <full包> <输出目录>

产出（输出目录下）:
    p7_orig.bin / p7_step1.bin / p7_full.bin    各包 idx5（12,075,648 B）
    seg_norm_<v>.bin   p7[0x51090..0x513e0]   归一化器全链（入口+47项表+handler+拒收）0x350 B
    seg_blk_<v>.bin    p7[0x11504..0x1151c]   特判块 / step1 中转区                 0x18 B

自检（任一失败 → 非零退出）:
    1. idx5 md5 == 5fc4824f…(orig) / 1e0be7df…(step1) / 2ee98811…(full)
    2. seg_norm 三版本差异仅限 0x510b0（4 B），其余逐字节相同
    3. 0x510b0: orig = b7 00 00 ea（b 0x80051394）; step1/full = 13 01 ff ea（b 0x80011504）
    4. seg_blk: orig = 24B 全零; step1 = 单条 b 0x80051394; full = 24B 恒等特判块
"""
from __future__ import annotations

import hashlib
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))       # 找同层
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))  # 找 slp_tool
import slp_tool  # noqa: E402

P7_LEN = 12075648
P7_IDX = 5
NORM_OFF, NORM_LEN = 0x51090, 0x350
BLK_OFF, BLK_LEN = 0x11504, 0x18
B_OFF = 0x510B0

MD5_EXPECT = {
    "orig":  "5fc4824f5b6a6a3caca1f9104238b8ac",
    "step1": "1e0be7df0ed54c4b71cd6a6a0ea3b243",
    "full":  "2ee98811a60059353a82c46ee2d836bc",
}
B_OLD = bytes.fromhex("b70000ea")
B_NEW = bytes.fromhex("1301ffea")
BLOCK_FULL = bytes.fromhex(
    "13 3e 40 e2 03 00 53 e3 a0 ff 00 8a 00 00 81 e5 00 00 a0 e3 17 ff 00 ea".replace(" ", ""))
_b = (0x80051394 - (0x80000000 + BLK_OFF + 8)) // 4
BLOCK_STEP1 = struct.pack("<I", 0xEA000000 | (_b & 0xFFFFFF)) + b"\x00" * (BLK_LEN - 4)

fails = []


def chk(cond, msg):
    print("[%s] %s" % ("OK  " if cond else "FAIL", msg))
    if not cond:
        fails.append(msg)
    return cond


def main():
    if len(sys.argv) != 5:
        print(__doc__)
        return 2
    pkgs = {"orig": sys.argv[1], "step1": sys.argv[2], "full": sys.argv[3]}
    outdir = sys.argv[4]
    os.makedirs(outdir, exist_ok=True)

    norm_segs, blk_segs = {}, {}
    for v in ("orig", "step1", "full"):
        meta, parts = slp_tool.parse(pkgs[v], verbose=False)
        p7 = parts[P7_IDX]["data"]
        md5 = hashlib.md5(p7).hexdigest()
        print("== %-5s %s" % (v, pkgs[v]))
        print("   version=%s  idx5=%d B  md5=%s" % (meta["version"], len(p7), md5))
        chk(len(p7) == P7_LEN, "%s: idx5 长度 == %d" % (v, P7_LEN))
        chk(md5 == MD5_EXPECT[v], "%s: idx5 md5 == %s…" % (v, MD5_EXPECT[v][:8]))
        open(os.path.join(outdir, "p7_%s.bin" % v), "wb").write(p7)
        norm_segs[v] = p7[NORM_OFF:NORM_OFF + NORM_LEN]
        blk_segs[v] = p7[BLK_OFF:BLK_OFF + BLK_LEN]
        open(os.path.join(outdir, "seg_norm_%s.bin" % v), "wb").write(norm_segs[v])
        open(os.path.join(outdir, "seg_blk_%s.bin" % v), "wb").write(blk_segs[v])

    print("\n-- 区段自检 --")
    # seg_norm: 三版本差异仅限 0x510b0
    for a, b in (("orig", "step1"), ("orig", "full")):
        diffs = [i for i in range(NORM_LEN)
                 if norm_segs[a][i] != norm_segs[b][i]]
        chk(diffs and all(B_OFF - NORM_OFF <= i < B_OFF - NORM_OFF + 4 for i in diffs),
            "seg_norm %s vs %s: 差异仅限 0x510b0 指令内（%d 字节: %s）"
            % (a, b, len(diffs), [hex(i + NORM_OFF) for i in diffs[:6]]))
    chk(norm_segs["step1"] == norm_segs["full"], "seg_norm step1 == full（逐字节）")

    bpos = B_OFF - NORM_OFF
    chk(norm_segs["orig"][bpos:bpos + 4] == B_OLD, "0x510b0 orig  == %s" % B_OLD.hex(" "))
    chk(norm_segs["step1"][bpos:bpos + 4] == B_NEW, "0x510b0 step1 == %s" % B_NEW.hex(" "))
    chk(norm_segs["full"][bpos:bpos + 4] == B_NEW, "0x510b0 full  == %s" % B_NEW.hex(" "))

    # seg_blk: 三种形态
    chk(blk_segs["orig"] == b"\x00" * BLK_LEN, "seg_blk orig == 24B 全零")
    chk(blk_segs["step1"] == BLOCK_STEP1,
        "seg_blk step1 == 单条 b 0x80051394 + 零（%s）" % blk_segs["step1"][:4].hex(" "))
    chk(blk_segs["full"] == BLOCK_FULL,
        "seg_blk full == 24B 恒等特判块")

    print()
    if fails:
        print("==== 提取自检: FAIL（%d 项） ====" % len(fails))
        return 1
    print("==== 提取自检: PASS —— 产物已写入 %s ====" % outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
