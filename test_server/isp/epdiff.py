#!/usr/bin/env python3
"""
epdiff.py —— EP 寄存器差分分析器（NX500 / p7 ISP）

用途
----
1. `epdiff.py struct  <file> [<base>]`  解析 0x80 stride 的 DMA 描述符记录数组
2. `epdiff.py diff   <A> <B> [...]`      两个采样文件做 word 级差分
3. `epdiff.py stable <f1> <f2> <f3>`     多次采样区分「稳定非零 / 波动 / 恒零」
4. `epdiff.py survey`                    打印已知的 EP 块清单与语义

背景（2026-10-06 实测）
---------------------
`0x20821700` 不是「ISP 调参寄存器」，而是 **0x80 字节 stride 的 DMA 描述符表**：
    +0x00 buf0（物理地址）    +0x08 尺寸/格式
    +0x04 buf1（物理地址）    +0x0c 权限标志（恒 0x08000000）
    +0x10 类型/通道          +0x20/+0x24/+0x28 宽/高/步长
已见到 rec3 = `0x94000000`（SMA 共享区）⇒ ISP 配方经 SMA 传递。
"""

import re
import sys
from collections import defaultdict

# ── EP 块清单（实测非零 word 数来自 2026-10-06 采样）────────────────────────
EP_BLOCKS = {
    0x20820000: ("EP_top",20, "9 个函数写入；顶层控制"),
    0x20821300: ("ISP_param_A", 4, "FUN_004b6894(760B, 28 调用者)"),
    0x20821700: ("DMA_desc",   56, "FUN_004b6b98(688B, 27 调用者)｜0x80 stride 描述符表"),
    0x20821C00: ("NOG",         1, "FUN_004afe3c/004aff08｜硬件颗粒，当前未配置"),
    0x20824000: ("EP_mc",       4, ""),
    0x20826000: ("EP_unk",    143, "非零最多，功能待定"),
    0x20829000: ("EP_fd",       1, ""),
    0x2082A000: ("EP_jpeg",   130, "读到 0x195010e0 帧数据"),
    0x2082B000: ("EP_3DLUT",   16, "3D LUT"),
}

LINE = re.compile(r"^W([0-9a-fA-F]{4})=([0-9a-fA-F]{8})")


def load(path):
    """读 epfull.arm 的输出 → {偏移: 值}"""
    d = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = LINE.match(line)
            if m:
                d[int(m.group(1), 16)] = int(m.group(2), 16)
    return d


def ann(v):
    """给地址值加注释"""
    if v == 0:
        return ""
    if 0xBB000000 <= v < 0xBD000000:
        return "liveview帧"
    if 0xBF000000 <= v < 0xC0000000:
        return "浮点常量区"
    if 0x94000000 <= v < 0x9E000000:
        return "★SMA共享区"
    if 0x9B000000 <= v < 0x9D000000:
        return "SRAM"
    if 0x20800000 <= v < 0x20900000:
        return "EP寄存器"
    return ""


def cmd_survey():
    print("=== EP 块清单（2026-10-06 实测非零统计）===")
    print("%-12s %-14s %-8s %s" % ("地址", "名称", "非零word", "说明"))
    for a in sorted(EP_BLOCKS):
        n, nz, desc = EP_BLOCKS[a]
        print("0x%08x  %-14s %-8d %s" % (a, n, nz, desc))


def cmd_struct(path, base=0x700):
    """解析 0x80 stride 描述符数组"""
    d = load(path)
    if not d:
        print("!! 没解析到 Wxxxx=yyyy 记录")
        return 1
    print("=== 0x80 stride 描述符记录（起始偏移 0x%x）===" % base)
    print("每条 0x80 = 32 个 u32 word\n")
    for r in range(16):
        o = base + r * 0x80
        if o not in d:
            break
        vals = [d.get(o + k * 4, 0) for k in range(32)]
        if not any(vals):
            print("── record %d @ 0x%03x : 全零" % (r, o))
            continue
        print("── record %d @ 偏移 0x%03x" % (r, o))
        print("   buf0=0x%08x %-12s buf1=0x%08x %s"
              % (vals[0], ann(vals[0]), vals[1], ann(vals[1])))
        print("   fmt =0x%08xperm=0x%08x  type=0x%08x"
              % (vals[2], vals[3], vals[4]))
        print("   dim =0x%08x / 0x%08x / 0x%08x   (宽/高/步长?)"
              % (vals[8], vals[9], vals[10]))
        # 打印该记录内所有非零
        nz = [(k * 4, v) for k, v in enumerate(vals) if v and k not in (0, 1, 2, 3, 4, 8, 9, 10)]
        if nz:
            print("   其他非零:", "  ".join("+0x%02x=0x%x" % (o, v) for o, v in nz[:8]))
        print()
    return 0


def cmd_diff(pa, pb):
    a, b = load(pa), load(pb)
    keys = sorted(set(a) | set(b))
    print("=== 差分: %s  vs  %s ===" % (pa, pb))
    print("  A: %d word   B: %d word\n" % (len(a), len(b)))
    n = 0
    for k in keys:
        va, vb = a.get(k, 0), b.get(k, 0)
        if va != vb:
            n += 1
            print("  0x%03x: 0x%08x -> 0x%08x   (%d -> %d)  %s"
                  % (k, va, vb, va, vb, ann(vb) if vb else ""))
    if n == 0:
        print("  ★ 完全相同")
    else:
        print("\n共 %d 个 word 变化" % n)
    return 0


def cmd_stable(*paths):
    if len(paths) < 2:
        print("需要至少 2 个采样文件")
        return 1
    S = [load(p) for p in paths]
    keys = sorted(set().union(*[set(s) for s in S]))
    stable_nz, fluc = [], []
    for k in keys:
        vs = [s.get(k, 0) for s in S]
        if vs[0] and len(set(vs)) == 1:
            stable_nz.append((k, vs[0]))
        elif len(set(vs)) > 1:
            fluc.append((k, vs))
    zeros = [k for k in keys if all(s.get(k, 0) == 0 for s in S)]

    print("=== %d 次采样稳定性分析 ===" % len(S))
    for i, p in enumerate(paths):
        print("  [%d] %s" % (i + 1, p))
    print()
    print("稳定非零: %d    波动: %d    恒零: %d\n" % (len(stable_nz), len(fluc), len(zeros)))

    print("--- 稳定非零 ---")
    for k, v in stable_nz:
        print("  0x%03x: 0x%08x  %10d  %s" % (k, v, v, ann(v)))
    if fluc:
        print("\n--- 波动（这些是「活」的参数）---")
        for k, vs in fluc:
            rng = max(vs) - min(vs)
            print("  0x%03x: %s  range=%d" % (k, " ".join("0x%08x" % v for v in vs), rng))
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    if cmd == "survey":
        return cmd_survey()
    if cmd == "struct":
        if len(sys.argv) < 3:
            print("用法: epdiff.py struct <file> [base]")
            return 1
        base = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x700
        return cmd_struct(sys.argv[2], base)
    if cmd == "diff":
        if len(sys.argv) < 4:
            print("用法: epdiff.py diff <A> <B>")
            return 1
        return cmd_diff(sys.argv[2], sys.argv[3])
    if cmd == "stable":
        return cmd_stable(*sys.argv[2:])
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
