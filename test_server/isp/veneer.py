#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p7 veneer thunk 表解调器（抓主干工具）。

背景：p7 是一堆 4 字节定长 veneer：`[2B movs Rd, Ra][2B b <real_impl>]`，
中间用 `0x1eff2fe1`（Thumb `nop; nop.w`）补齐。Ghidra 常把它们建成
"20 字节的坏函数"，反编译出 `halt_baddata()`。本工具直接解出 veneer 表。

用法:
  python veneer.py scan 0x3f3f64 0x40      # 扫 [start, start+size) 的 veneer 表
  python veneer.py dis   0x3f3a8a         # 解某个真实实现的反汇编
  python veneer.py all                    # 扫全镜像, 找所有 veneer 表(>=4 连续)
"""
import sys
import capstone
from pathlib import Path
from collections import defaultdict

BIN = Path(__file__).resolve().parent.parent.parent / "raw8" / "p7" / "p7_full.bin"
if not BIN.exists():
    BIN = Path(r"D:\download\NX-KS2-88\raw8\p7\p7_full.bin")

THUMB = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
THUMB.detail = False

# Thumb: 0x1eff = nop, 0x2fe1 = nop.w (补齐用的填充)
NOP16 = 0x1EFF
NOP32 = 0x2FE1


def disasm(addr, n=64):
    b = BIN.read_bytes()
    return list(THUMB.disasm(b[addr:addr + n], addr))


def veneer_at(addr):
    """若 addr 处是一个 veneer，返回 (dst_reg, src_reg, target)；否则 None。"""
    ins = disasm(addr, 4)
    if len(ins) != 2:
        return None
    a, c = ins
    if a.mnemonic != "movs" or c.mnemonic != "b":
        return None
    try:
        dst = a.op_str.split(",")[0].strip()
        src = a.op_str.split(",")[1].strip()
        tgt = int(c.op_str.replace("#", ""), 0)
    except Exception:
        return None
    return dst, src, tgt


def cmd_scan(start, size):
    b = BIN.read_bytes()
    print(f"=== veneer 表 @ 0x{start:x} (size {size}) ===")
    print("  %-10s %-8s %-8s %s" % ("addr", "dst", "src", "-> target"))
    n = 0
    a = start
    while a < start + size:
        w = int.from_bytes(b[a + 2:a + 4], "little")
        if w == NOP32:          # 填充，跳过
            a += 4
            continue
        v = veneer_at(a)
        if v:
            dst, src, tgt = v
            print("  0x%-8x %-8s %-8s 0x%x" % (a, dst, src, tgt))
            n += 1
        a += 4
    print(f"  total veneers = {n}")


def cmd_dis(addr, n=80):
    print(f"=== 反汇编 0x{addr:x} ===")
    for i in disasm(addr, n):
        print("  0x%-8x %-10s %s" % (i.address, i.mnemonic, i.op_str))


def cmd_all(minrun=4):
    """扫全镜像找所有连续 veneer 段。"""
    b = BIN.read_bytes()
    n = len(b)
    print("=== 扫描全镜像的 veneer 段 (>=%d 连续) ===" % minrun)
    runs = []
    a = 0
    cur = []
    while a + 4 <= n:
        v = veneer_at(a)
        if v:
            cur.append((a, v))
            a += 4
        else:
            if len(cur) >= minrun:
                runs.append(cur)
            cur = []
            a += 4
    if len(cur) >= minrun:
        runs.append(cur)
    print(f"veneer 段数 = {len(runs)}")
    # 按目标地址聚类: 同一实现被多个 veneer 指向 = 参数访问器
    by_target = defaultdict(list)
    for run in runs:
        for addr, (_, _, tgt) in run:
            by_target[tgt].append(addr)
    print(f"不同实现目标数 = {len(by_target)}")
    print()
    print("--- 被 >=3 个 veneer 指向的实现（= 参数访问器/字段选择器）---")
    for tgt, srcs in sorted(by_target.items(), key=lambda x: -len(x[1]))[:25]:
        print(f"  0x{tgt:x}  <- {len(srcs)} 个 veneer: {[hex(s) for s in srcs[:6]]}")


if __name__ == "__main__":
    if not BIN.exists():
        print("找不到 p7_full.bin:", BIN)
        sys.exit(1)
    c = sys.argv[1] if len(sys.argv) > 1 else "all"
    if c == "scan":
        cmd_scan(int(sys.argv[2], 0), int(sys.argv[3], 0) if len(sys.argv) > 3 else 64)
    elif c == "dis":
        cmd_dis(int(sys.argv[2], 0), int(sys.argv[3], 0) if len(sys.argv) > 3 else 80)
    else:
        cmd_all()
