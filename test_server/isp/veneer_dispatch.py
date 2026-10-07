#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p7 ARM 跳转表解码器（FUN_003f3fa4 = 20 字段访问器）。

★★★ 重要教训（2026-10-07）：
  先前把 0x3f3fa4 判成 "Thumb veneer 桩" 是【错的】—— 那是 Thumb 误读 ARM 的结果。
  p7 是 ARM/Thumb 混合代码；0x3f3fa4 附近是纯 ARM。
  正确形态是 ARM 经典的 `ldrls pc, [pc, r1, lsl #2]` 索引跳转表：

      FUN_003f3fa4(struct *r0, int id):
        0x3f3fa4  cmp     r1, #0x13               ; id <= 19 ?
        0x3f3fa8  ldrls   pc, [pc, r1, lsl #2]    ; 跳 table[r1]
        0x3f3fac  b       #0x3f40a0               ; 默认: return 0
        0x3f3fb0  .word   0x803f4098              ; table[0] (p7 VA, 基址 0x80000000)
        ...

  => table[i] = 0x80000000 + (0x3f4098 - i*8)
  => handler_i:  ldr r0, [r0, #0x14 + i*4] ; bx lr
  => 语义 = 读取 struct 的 20 个 u32 字段（+0x14 .. +0x60），id 越界返回 0

用法: python veneer_dispatch.py          # 解 0x3f3fa4 访问器
      python veneer_dispatch.py 0xXXXXXX # 解任意 ARM ldrls pc 表
"""
import sys
import capstone
from pathlib import Path

BIN = Path(__file__).resolve().parent.parent.parent / "raw8" / "p7" / "p7_full.bin"
if not BIN.exists():
    BIN = Path(r"D:\download\NX-KS2-88\raw8\p7\p7_full.bin")

ARM = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
ARM.detail = False

VA_BASE = 0x80000000        # p7 内核虚拟基址（MMU 开启）


def patch_addr(addr):
    """在 addr 处找 `cmp rX,#imm` + `ldrls pc,[pc,rX,lsl #2]` 的跳转表。"""
    b = BIN.read_bytes()
    ins = list(ARM.disasm(b[addr:addr + 12], addr))
    if len(ins) < 2:
        return None
    c, j = ins[0], ins[1]
    if not c.mnemonic.startswith("cmp"):
        return None
    if "pc" not in j.op_str or "lsl #2" not in j.op_str:
        return None
    maxid = int(c.op_str.split("#")[1], 0)
    # ARM `ldrls pc,[pc,rX,lsl#2]` 位于 addr+4，PC 基准 = (addr+4)+8 = addr+0xc
    tbl = addr + 0xC
    return maxid, tbl


def main():
    addr = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x3F3FA4
    b = BIN.read_bytes()
    info = patch_addr(addr)
    if not info:
        print(f"0x{addr:x} 处不是 `cmp+ldrls pc` 跳转表")
        sys.exit(1)
    maxid, tbl = info
    print(f"=== ARM 索引跳转表 ===")
    print(f"dispatcher @0x{addr:x} : cmp id,#0x{maxid:x}  => {maxid+1} 条目 (id 0..{maxid})")
    print(f"table @0x{tbl:x}")
    print()
    print("  %-5s %-12s %-12s %s" % ("id", "table_addr", "target(VA)", "handler"))
    rows = []
    for i in range(maxid + 1):
        a = tbl + i * 4
        w = int.from_bytes(b[a:a + 4], "little")
        fo = w - VA_BASE
        dis = ""
        if 0 <= fo < len(b):
            ins = list(ARM.disasm(b[fo:fo + 8], fo))
            dis = " ; ".join(f"{x.mnemonic} {x.op_str}" for x in ins[:2])
        rows.append((i, a, w, fo, dis))
        print("  %-5d 0x%-10x 0x%-10x %s" % (i, a, w, dis))

    out = Path(__file__).resolve().parent / "out" / "arm_jumptable.txt"
    out.parent.mkdir(exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        f.write(f"dispatcher=0x{addr:x} entries={maxid+1} table=0x{tbl:x}\n")
        for i, a, w, fo, dis in rows:
            f.write(f"id={i:2d} table=0x{a:08x} target=0x{w:08x} file=0x{fo:x} :: {dis}\n")
    print(f"\n写入 {out}")


if __name__ == "__main__":
    if not BIN.exists():
        print("找不到 p7_full.bin:", BIN)
        sys.exit(1)
    main()
