#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mk_a2_patch.py —— 生成 A2 p7 补丁镜像（5 处改动）+ 静态自检。

A2 = A1 全部改动（0x510b0 重定向；0x11504 特判块改扩至 0x130..0x13B）
   + 2 处新增（0x4cd30 改道 → A2 特判块 @0x11530；A2 块 80B）

输入：E:/NXWA/fw/v1.12/parts/chunk-05.bin（p7 原件）
     E:/NXWA/rea-tmp/a2/{blk1a2.bin, blk2.bin, redir2.bin}（WSL as 产物）
输出：E:/NXWA/fw/v1.12/a2/p7_a2.bin + a2_bytepatch.json
"""
import hashlib
import json
import os

SRC = r"E:/NXWA/fw/v1.12/parts/chunk-05.bin"
PARTS = r"E:/NXWA/rea-tmp/a2"
DST_DIR = r"E:/NXWA/fw/v1.12/a2"
DST = os.path.join(DST_DIR, "p7_a2.bin")
JSN = os.path.join(DST_DIR, "a2_bytepatch.json")

CHECKS = []


def chk(ok, msg):
    CHECKS.append((bool(ok), msg))
    print("[%s] %s" % ("OK  " if ok else "FAIL", msg))


def b_target(ins_le, va):
    """B/BL 目标解算（LE 文件字节）。"""
    w = int.from_bytes(ins_le, "little")
    imm = w & 0xFFFFFF
    if imm & 0x800000:
        imm -= 0x1000000
    return (va + 8 + imm * 4) & 0xFFFFFFFF


data = bytearray(open(SRC, "rb").read())
orig = bytes(data)

b1 = open(os.path.join(PARTS, "blk1a2.bin"), "rb").read()
b2 = open(os.path.join(PARTS, "blk2.bin"), "rb").read()
rd = open(os.path.join(PARTS, "redir2.bin"), "rb").read()

chk(len(b1) == 24, "blk1a2 长度 == 24B（实 %d）" % len(b1))
chk(len(b2) == 80, "blk2 长度 == 80B（实 %d）" % len(b2))
chk(len(rd) == 4, "redir2 长度 == 4B（实 %d）" % len(rd))

REDIR_OLD = bytes.fromhex("b70000ea")
REDIR_NEW = bytes.fromhex("1301ffea")
chk(bytes(data[0x510b0:0x510b4]) == REDIR_OLD, "0x510b0 原值 == b7 00 00 ea")
chk(bytes(data[0x11504:0x11504 + 24]) == b"\x00" * 24, "0x11504 原值 == 24B 零区")
chk(bytes(data[0x4cd30:0x4cd34]) == bytes.fromhex("7a2702eb"),
    "0x4cd30 原值 == bl 0xd6b20（7a 27 02 eb）")
chk(bytes(data[0x11530:0x11530 + 80]) == b"\x00" * 80, "0x11530 原值 == 80B 零区")

# 应用 4 处字节改动
data[0x510b0:0x510b4] = REDIR_NEW
data[0x11504:0x11504 + 24] = b1
data[0x4cd30:0x4cd34] = rd
data[0x11530:0x11530 + 80] = b2

# 静态解算复核
chk(b_target(REDIR_NEW, 0x800510B0) == 0x80011504, "0x510b0 目标解算 == 0x80011504")
b1_cmp = b1[4:8]
print("  blk1 cmp 字节 = %s（期望 0b 00 53 e3）" % b1_cmp.hex(" "))
chk(b1_cmp == bytes.fromhex("0b0053e3"), "blk1 已改扩（cmp #0xB）")
chk(b_target(b1[8:12], 0x8001150C) == 0x80051394, "blk1 bhi 目标 == 0x80051394")
chk(b_target(b1[20:24], 0x80011518) == 0x8005117C, "blk1 b 目标 == 0x8005117C")
chk(b_target(rd, 0x8004CD30) == 0x80011530, "0x4cd30 改道目标解算 == 0x80011530")
chk(b_target(b2[12:16], 0x8001153C) == 0x80011550, "blk2 bls → L_slot 0x80011550")
chk(b_target(b2[20:24], 0x80011544) == 0x80011568, "blk2 beq → L_commit 0x80011568")
chk(b_target(b2[28:32], 0x8001154C) == 0x800D6B20, "blk2 透传 → 0x800d6b20")
chk(b_target(b2[44:48], 0x8001155C) == 0x80064F0C, "blk2 slot 路径 bl → 0x80064f0c")
chk(b_target(b2[64:68], 0x80011570) == 0x80064F0C, "blk2 commit bl → 0x80064f0c")
chk(b_target(b2[68:72], 0x80011574) == 0x80051AB8, "blk2 commit bl → 0x80051ab8")

# diff 清单
diff = [i for i in range(len(data)) if data[i] != orig[i]]
print("\ndiff 总数 %d B" % len(diff))
for lo, ln, name in [(0x510b0, 4, "①重定向"), (0x11504, 24, "②A1块改扩"),
                     (0x4cd30, 4, "③改道"), (0x11530, 80, "④A2块")]:
    n = sum(1 for i in diff if lo <= i < lo + ln)
    nz = sum(1 for i in range(lo, lo + ln) if orig[i] != 0)
    print("  %s: %d B 变化" % (name, n))
chk(len(diff) > 0, "diff 非空")

os.makedirs(DST_DIR, exist_ok=True)
open(DST, "wb").write(data)
md5 = hashlib.md5(data).hexdigest()
print("\np7_a2.bin → %s" % DST)
print("md5 = %s" % md5)

json.dump({
    "src": SRC, "dst": DST, "md5": md5,
    "patches": [
        {"off": 0x510b0, "old": REDIR_OLD.hex(), "new": REDIR_NEW.hex()},
        {"off": 0x4cd30, "old": "7a2702eb", "new": rd.hex()},
    ],
    "block1": {"off": 0x11504, "len": 24, "bytes": b1.hex()},
    "block2": {"off": 0x11530, "len": 80, "bytes": b2.hex()},
}, open(JSN, "w"), indent=1)
print("bytepatch → %s" % JSN)

allok = all(c[0] for c in CHECKS)
print("\n==== %s（%d/%d）====" % ("全部 PASS" if allok else "存在 FAIL！",
                                   sum(c[0] for c in CHECKS), len(CHECKS)))
raise SystemExit(0 if allok else 1)
