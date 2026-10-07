#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""快速 veneer 表扫描器（纯字节匹配，不用 capstone 逐条反汇编）。

veneer 形状（Thumb，4 字节定长）：
  word = [2B 前半指令][2B b <target>]
  - `movs Rd, Ra`  Thumb16 编码 = 0x0000 | (Rm<<3) | Rd，即 imm5==0 的 16-bit MOV
    实际常见 `movs r3, r2` -> 0x0013 (小端 13 00)
  - `b <target>`   Thumb16 条件/无条件 B = 0xE000 | (off11)   高 5 位 = 11100
  - 填充 `0x1eff`(nop) / `0x2fe1`(nop.w)

本脚本按 4 字节对齐扫全镜像，用位掩码快速判定，比 capstone 快约 100 倍。
"""
import sys
from pathlib import Path
from collections import defaultdict

BIN = Path(__file__).resolve().parent.parent.parent / "raw8" / "p7" / "p7_full.bin"
if not BIN.exists():
    BIN = Path(r"D:\download\NX-KS2-88\raw8\p7\p7_full.bin")

NOP16 = 0x1EFF
NOP32 = 0x2FE1


def is_mov_reg(h):
    """Thumb16 MOV(reg) 且 imm5==0：高 6 位必须 = 000000。"""
    return (h & 0xFFC0) == 0x0000


def is_b(h):
    """Thumb16 无条件 B：高 5 位 = 11100。"""
    return (h & 0xF800) == 0xE000


def decode_b_target(h, addr):
    off = h & 0x07FF
    if off & 0x0400:
        off -= 0x0800
    return (addr + 4 + off * 2) & 0xFFFFFFFF


def main():
    b = BIN.read_bytes()
    n = len(b)
    print(f"image = {BIN} ({n} bytes)")
    a = 0
    runs = []
    cur = []
    while a + 4 <= n:
        h0 = int.from_bytes(b[a:a+2], "little")
        h1 = int.from_bytes(b[a+2:a+4], "little")
        if h1 == NOP32:
            a += 4
            continue
        if is_mov_reg(h0) and is_b(h1):
            dst = h0 & 7
            src = (h0 >> 3) & 7
            tgt = decode_b_target(h1, a + 2)
            cur.append((a, dst, src, tgt))
            a += 4
        else:
            if len(cur) >= 4:
                runs.append(cur)
            cur = []
            a += 4
    if len(cur) >= 4:
        runs.append(cur)

    print(f"veneer 段数(>=4 连续) = {len(runs)}")
    total = sum(len(r) for r in runs)
    print(f"veneer 条目总数 = {total}")
    if runs:
        lens = sorted((len(r) for r in runs), reverse=True)
        print(f"段长分布(top10) = {lens[:10]}")

    by_target = defaultdict(list)
    for run in runs:
        for addr, dst, src, tgt in run:
            by_target[tgt].append(addr)
    print(f"不同目标实现数 = {len(by_target)}")

    # 输出最大的几个段
    print()
    print("--- 最大的 6 个 veneer 段 ---")
    for run in sorted(runs, key=lambda r: -len(r))[:6]:
        s, e = run[0][0], run[-1][0]
        print(f"  段 @0x{s:x}..0x{e:x}  条目 {len(run)}  "
              f"目标范围 0x{min(t for _,_,_,t in run):x}..0x{max(t for _,_,_,t in run):x}")

    out = Path(__file__).resolve().parent / "out" / "veneer_fast.txt"
    out.parent.mkdir(exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        f.write(f"runs={len(runs)} total={total} targets={len(by_target)}\n\n")
        for run in sorted(runs, key=lambda r: -len(r)):
            f.write(f"=== 段 @0x{run[0][0]:x} ({len(run)} 条) ===\n")
            for addr, dst, src, tgt in run:
                f.write(f"  0x{addr:08x}  movs r{dst},r{src}  -> 0x{tgt:08x}\n")
            f.write("\n")
    print(f"\n详情写入 {out}")


if __name__ == "__main__":
    if not BIN.exists():
        print("找不到 p7_full.bin:", BIN)
        sys.exit(1)
    main()
