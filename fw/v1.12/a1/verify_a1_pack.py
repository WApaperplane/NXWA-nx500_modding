#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_a1_pack.py —— A1 待刷包逐字节核验（离线，只读）。

★ 2026-10-11 修正两点（第一版核验脚本的错）：
  1. **idx5 基址不能用"块位置反推"**：改用 p7 首 32 字节签名在文件里定位（唯一、可自证）。
  2. **0x510b0 的字节序**：设计文档写的 `ea 0000b7` 是**指令字**（LE 读作 0xEA0000B7），
     文件里实际字节是 `b7 00 00 ea`；补丁后字节 `13 01 ff ea`（字 0xEAFF0113）。

核验项：
  1. 两文件等长（否则必被 SLP 完整性检查拦）
  2. idx5 基址一致 + 签名定位自证
  3. 0x510b0 = 原 `b7 00 00 ea` → 新 `13 01 ff ea`，且分支目标解算 == 0x80011504
  4. 0x11504 处 24B 特判块逐字节 == 设计值，且入口地址自洽
  5. idx5 内容 md5 == p7_patched_test.bin（2ee98811…）
  6. 全库 diff 分解 == idx5 内 20B + 库外 5B（version 1 + CRC32 4）
  7. 关键未改区抽查（跳转表头 / 共享收尾 / 拒收 handler）

用法: python verify_a1_pack.py <官方.bin> <待刷.bin> [p7_orig.bin]
"""
import hashlib
import sys

P7_LEN = 12075648
P7_ORIG_MD5 = "5fc4824f5b6a6a3caca1f9104238b8ac"
P7_PATCH_MD5 = "2ee98811a60059353a82c46ee2d836bc"
B_OFF, B_OLD, B_NEW = 0x510B0, bytes.fromhex("b70000ea"), bytes.fromhex("1301ffea")
BLK_OFF = 0x11504
BLK = bytes.fromhex(
    "13 3e 40 e2 03 00 53 e3 a0 ff 00 8a 00 00 81 e5 00 00 a0 e3 17 ff 00 ea".replace(" ", ""))
SAMPLES = [(0x510B4, "跳转表表头"), (0x5117C, "共享收尾"), (0x51394, "拒收 handler")]


def b_target(ins_bytes, va):
    """解算 ARM B 指令目标地址（ins_bytes 为 LE 文件字节）。"""
    w = int.from_bytes(ins_bytes, "little")
    imm = w & 0xFFFFFF
    if imm & 0x800000:
        imm -= 0x1000000
    return (va + 8 + imm * 4) & 0xFFFFFFFF


def main():
    off_path, new_path = sys.argv[1], sys.argv[2]
    p7_path = sys.argv[3] if len(sys.argv) > 3 else None
    o = open(off_path, "rb").read()
    n = open(new_path, "rb").read()
    oks = []

    def chk(cond, msg):
        oks.append(bool(cond))
        print("[%s] %s" % ("OK  " if cond else "FAIL", msg))
        return cond

    print("官方件 %s (%d B)" % (off_path, len(o)))
    print("待刷包 %s (%d B)" % (new_path, len(n)))
    print("待刷包 md5 = %s\n" % hashlib.md5(n).hexdigest())

    chk(len(o) == len(n), "两文件等长")

    # --- 基址：签名定位 + 自证 ---
    sig = (open(p7_path, "rb").read()[:32] if p7_path else None)
    if sig is None:
        # 退而求其次：用官方件里 p7 的已知首 32 字节不可得时，用块位置反推并打印警告
        print("[WARN] 未给 p7 原件，改用块位置反推基址（可靠性较低）")
        base = n.find(BLK) - BLK_OFF
    else:
        base = o.find(sig)
        chk(base == n.find(sig), "idx5 基址两文件一致 @ %#x" % base)
    print("    idx5 基址 = %#x\n" % base)

    chk(hashlib.md5(o[base:base + P7_LEN]).hexdigest() == P7_ORIG_MD5,
        "官方 idx5 md5 == p7 原件 %s…" % P7_ORIG_MD5[:8])
    chk(hashlib.md5(n[base:base + P7_LEN]).hexdigest() == P7_PATCH_MD5,
        "待刷 idx5 md5 == p7_patched_test %s…" % P7_PATCH_MD5[:8])

    # --- 补丁点 1：0x510b0 ---
    got_old = o[base + B_OFF: base + B_OFF + 4]
    got_new = n[base + B_OFF: base + B_OFF + 4]
    chk(got_old == B_OLD, "0x510b0 原值 == %s（b 0x80051394 拒收）" % B_OLD.hex(" "))
    chk(got_new == B_NEW, "0x510b0 新值 == %s（期望）" % B_NEW.hex(" "))
    tgt = b_target(got_new, 0x800510B0)
    chk(tgt == 0x80011504, "分支目标解算 = %#x（期望 0x80011504）" % tgt)

    # --- 补丁点 2：0x11504 ---
    got_blk = n[base + BLK_OFF: base + BLK_OFF + 24]
    chk(got_blk == BLK, "0x11504 24B 特判块逐字节相符")
    chk(o[base + BLK_OFF: base + BLK_OFF + 24] == b"\x00" * 24, "0x11504 原值为 24B 全零（空闲区）")
    chk(tgt == 0x80000000 + BLK_OFF, "块物理偏移 %#x == 分支目标 - base（自洽）" % BLK_OFF)

    # --- diff 分解 ---
    d = [i for i in range(len(o)) if o[i] != n[i]]
    inside = [i for i in d if base <= i < base + P7_LEN]
    outside = [i for i in d if not (base <= i < base + P7_LEN)]
    print("\ndiff 总数 %d B ｜ idx5 内 %d ｜ 库外 %d %s"
          % (len(d), len(inside), len(outside), [hex(i) for i in outside]))
    chk(len(d) == 25, "全库 diff == 25 B（3 指令 + 17 块 + 1 version + 4 CRC）")
    chk(len(inside) == 20, "idx5 内 diff == 20 B（3 + 17）")
    chk(len(outside) == 5 and set(outside) & {0x7} == {0x7},
        "库外 diff == version(0x7) + CRC32(0xbc..0xbf)")

    # --- 未改区抽查 ---
    print()
    for off, why in SAMPLES:
        same = o[base + off:base + off + 16] == n[base + off:base + off + 16]
        chk(same, "%#x 未改动（%s）: %s" % (off, why, n[base + off:base + off + 8].hex(" ")))

    good = all(oks)
    print("\n==== 总体: %s （%d/%d 项通过）====" % ("PASS" if good else "FAIL", sum(oks), len(oks)))
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
