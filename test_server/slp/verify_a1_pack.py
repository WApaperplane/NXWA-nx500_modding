#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_a1_pack.py —— A1 待刷包逐字节核验（离线，只读）。

★ 两个坑（第一版核验脚本踩过，记在这里）：
  1. **idx5 基址不要用"块位置反推"** —— 改用 p7 首 32 字节签名定位（唯一、可自证）。
     SLP 表里的 img_offset 就是**绝对文件偏移**（不含 304 字节头）。
  2. **0x510b0 的字节序**：设计文档写的 `ea 0000b7` 是**指令字**（LE 读作 0xEA0000B7），
     文件里实际字节是 `b7 00 00 ea`；补丁后字节 `13 01 ff ea`（字 0xEAFF0113）。

核验项：
  1. 两文件等长（否则必被 SLP 完整性检查拦）
  2. idx5 基址一致（签名定位 + 自证），且官方/待刷的 idx5 md5 分别等于 p7 原件/补丁件
  3. 0x510b0 原值 `b7 00 00 ea` → 新值 `13 01 ff ea`，分支目标解算 == 0x80011504
  4. 0x11504 处内容 == 对应档位的设计值；原值为 24B 全零
  5. 全库 diff 分解 == idx5 内 (3 + 块非零字节) + 库外 5B（version 1 + CRC32 4）
  6. 关键未改区抽查（跳转表头 / 共享收尾 / 拒收 handler）

用法: python verify_a1_pack.py <官方.bin> <待刷.bin> --p7 <p7原件.bin> [--variant step1|full]
"""
import argparse
import hashlib
import struct
import sys

P7_LEN = 12075648
P7_ORIG_MD5 = "5fc4824f5b6a6a3caca1f9104238b8ac"
B_OFF, B_OLD, B_NEW = 0x510B0, bytes.fromhex("b70000ea"), bytes.fromhex("1301ffea")
BLK_OFF = 0x11504
BLOCK_FULL = bytes.fromhex(
    "13 3e 40 e2 03 00 53 e3 a0 ff 00 8a 00 00 81 e5 00 00 a0 e3 17 ff 00 ea".replace(" ", ""))
_b = (0x80051394 - (0x80000000 + BLK_OFF + 8)) // 4
BLOCK_STEP1 = struct.pack("<I", 0xEA000000 | (_b & 0xFFFFFF))
VARIANTS = {"full": (BLOCK_FULL, "2ee98811a60059353a82c46ee2d836bc"),
            "step1": (BLOCK_STEP1, "1e0be7df0ed54c4b71cd6a6a0ea3b243")}
SAMPLES = [(0x510B4, "跳转表表头"), (0x5117C, "共享收尾"), (0x51394, "拒收 handler")]


def b_target(ins_le: bytes, va: int) -> int:
    """解算 ARM B 指令目标（ins_le 为 LE 文件字节）。"""
    w = int.from_bytes(ins_le, "little")
    imm = w & 0xFFFFFF
    if imm & 0x800000:
        imm -= 0x1000000
    return (va + 8 + imm * 4) & 0xFFFFFFFF


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("official")
    ap.add_argument("pack")
    ap.add_argument("--p7", required=True, help="p7 原件（chunk-05.bin / p7_full.bin）")
    ap.add_argument("--variant", default="full", choices=["step1", "full"])
    a = ap.parse_args()

    blk_expect, p7_patch_md5 = VARIANTS[a.variant]
    o = open(a.official, "rb").read()
    n = open(a.pack, "rb").read()
    oks = []

    def chk(cond, msg):
        oks.append(bool(cond))
        print("[%s] %s" % ("OK  " if cond else "FAIL", msg))
        return cond

    print("档位    : %s" % a.variant)
    print("官方件  : %s (%d B)" % (a.official, len(o)))
    print("待刷包  : %s (%d B)" % (a.pack, len(n)))
    print("待刷 md5: %s\n" % hashlib.md5(n).hexdigest())

    chk(len(o) == len(n), "两文件等长")

    base = o.find(open(a.p7, "rb").read()[:32])
    chk(base > 0 and base == n.find(open(a.p7, "rb").read()[:32]),
        "idx5 基址两文件一致 @ %#x（签名定位）" % base)

    chk(hashlib.md5(o[base:base + P7_LEN]).hexdigest() == P7_ORIG_MD5,
        "官方 idx5 md5 == p7 原件 %s…" % P7_ORIG_MD5[:8])
    chk(hashlib.md5(n[base:base + P7_LEN]).hexdigest() == p7_patch_md5,
        "待刷 idx5 md5 == 该档位补丁件 %s…" % p7_patch_md5[:8])

    got_old, got_new = o[base + B_OFF:base + B_OFF + 4], n[base + B_OFF:base + B_OFF + 4]
    chk(got_old == B_OLD, "0x510b0 原值 == %s（b 0x80051394 拒收）" % B_OLD.hex(" "))
    chk(got_new == B_NEW, "0x510b0 新值 == %s（期望）" % B_NEW.hex(" "))
    tgt = b_target(got_new, 0x800510B0)
    chk(tgt == 0x80011504, "分支目标解算 = %#x（期望 0x80011504）" % tgt)

    got_blk = n[base + BLK_OFF:base + BLK_OFF + len(blk_expect)]
    chk(got_blk == blk_expect, "0x11504 %dB 特判块 == 该档位设计值 %s"
        % (len(blk_expect), blk_expect.hex(" ")))
    chk(o[base + BLK_OFF:base + BLK_OFF + 24] == b"\x00" * 24, "0x11504 原值为 24B 全零（空闲区）")
    chk(tgt == 0x80000000 + BLK_OFF, "块物理偏移 %#x == 分支目标 - VA 基（自洽）" % BLK_OFF)
    if a.variant == "step1":
        t2 = b_target(got_blk, 0x80011504)
        chk(t2 == 0x80051394, "step1 中转目标解算 = %#x（应为原拒收 0x80051394）" % t2)

    d = [i for i in range(len(o)) if o[i] != n[i]]
    inside = [i for i in d if base <= i < base + P7_LEN]
    outside = [i for i in d if not (base <= i < base + P7_LEN)]
    nonzero_blk = sum(1 for b in blk_expect if b)
    expect_total = 3 + nonzero_blk + 5
    print("\ndiff 总数 %d B ｜ idx5 内 %d ｜ 库外 %d %s"
          % (len(d), len(inside), len(outside), [hex(i) for i in outside]))
    chk(len(d) == expect_total, "全库 diff == %d B（3 指令 + %d 块非零 + 1 version + 4 CRC）"
        % (expect_total, nonzero_blk))
    chk(set(outside) == {0x7, 0xBC, 0xBD, 0xBE, 0xBF},
        "库外 diff 恰为 version(0x7) + CRC32(0xbc..0xbf)")

    print()
    for off, why in SAMPLES:
        chk(o[base + off:base + off + 16] == n[base + off:base + off + 16],
            "%#x 未改动（%s）: %s" % (off, why, n[base + off:base + off + 8].hex(" ")))

    good = all(oks)
    print("\n==== 总体: %s （%d/%d 项通过）====" % ("PASS" if good else "FAIL", sum(oks), len(oks)))
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
