#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NOG 寄存器布局表（从 FUN_004aff08 反编译逐条提取，2026-10-06）。

`FUN_004aff08(param_1 /*u8[16+]*//, param_2 /*实例号*/)` 的完整语义：
  把param_1 的 16+ 字节按【4 字节一组】写进 NOG 的 4 个寄存器，
  每组先经过 0x10..0x1f 的中转结构（带激活/索引语义）。
  param_2==0 ⇒ 实例0（寄存器 0x20821c10/14/18/1c）
  param_2!=0 ⇒ 实例1（寄存器 0x20821c40/44/48/4c）★ 偏移差 0x30

**这张表就是魔灯"颗粒"三个旋钮的物理映射。**
"""

NOG_REGS = {
    0: {  # 实例 0
        "desc_base":  "DAT_004b0058",
        "desc_off":   "-0x20 (实例1 时)",
        "staging":    "+0x10 .. +0x1f  (16 字节中转区)",
        "regs": [
            # (寄存器, 源字节区间, 语义推断)
            ("0x20821c10", "param_1[0..3]",   "组0：第 1 个 32 位参数"),
            ("0x20821c14", "param_1[4..7]",   "组1：第 2 个 32 位参数"),
            ("0x20821c18", "param_1[8..11]",  "组2：第 3 个 32 位参数"),
            ("0x20821c1c", "param_1[12..15]", "组3：第 4 个 32 位参数"),
        ],
    },
    1: {  # 实例 1
        "desc_base":  "DAT_004b0058",
        "desc_off":   "+0",
        "staging":    "+0x10 .. +0x1f",
        "regs": [
            ("0x20821c40", "param_1[0..3]",   "组0（偏移 +0x30）"),
            ("0x20821c44", "param_1[4..7]",   "组1（偏移 +0x30）"),
            ("0x20821c48", "param_1[8..11]",  "组2（偏移 +0x30）"),
            ("0x20821c4c", "param_1[12..15]", "组3（偏移 +0x30）"),
        ],
    },
}

# 相关只读/间接寄存器（其它函数里出现）
NOG_EXTRA = {
    "0x20821c00": "FUN_004afe3c 写（3 字节/项 × 32 项表的下发口）",
    "0x20821c04": "FUN_004afe3c 写（同上，第 2 个）",
    "0x20821c08": "FUN_004afd58 读写",
    "0x20821c0c": "FUN_004afd58 读写",
}

CTRL_STRUCT = {
    "DAT_817d7e64": "NOG 实例0 控制结构（bit0/bit1 开关在此）",
    "DAT_817d7e84": "NOG 实例1 控制结构（= 实例0 + 0x20）",
}

SWITCH_FUNCS = {
    "FUN_004afdbc": "*p = (*p & 0xfd) | (v & 1) << 1   # bit1",
    "FUN_004afdfc": "*p = (*p & 0xfe) | (v & 1)       # bit0",
    "FUN_004afd2c": "memset 32 字节状态区（FUN_0050a114(base, 0, 0x20)）",
    "FUN_004afd58": "读/写 0x20821c08 / 0x20821c0c + 控制结构",
}

if __name__ == "__main__":
    print("=== NOG 硬件寄存器布局（2 个实例 × 4 个 32 位寄存器）===")
    for inst, d in NOG_REGS.items():
        print("\n实例 %d  (中转区 %s %s)" % (inst, d["staging"], d["desc_off"]))
        for reg, src, sem in d["regs"]:
            print("  %s  <- %-18s %s" % (reg, src, sem))
    print("\n=== 其它 NOG 相关寄存器 ===")
    for r, s in NOG_EXTRA.items():
        print("  %s  %s" % (r, s))
    print("\n=== 运行时控制结构 ===")
    for s, d in CTRL_STRUCT.items():
        print("  %s  %s" % (s, d))
    print("\n=== 开关/状态函数 ===")
    for f, s in SWITCH_FUNCS.items():
        print("  %-16s %s" % (f, s))
