#!/usr/bin/env python3
"""扫固件镜像里对某个物理地址段的【真实寄存器访问点】。

为什么不能直接搜字面量：
  Cortex-M 访问外设寄存器几乎都用「基址寄存器 + 偏移」间接寻址
  （ldr rX, =0x08060000 ; ldr rY, [rX, #0x1c]），基址只出现在字面量池里。
  所以必须走：LDR rX,[pc,#imm] 取字面量 → 追踪该寄存器后续被用作基址。
本工具做两步：
  1) 扫出所有 LDR-literal，取出字面量值，标注所在函数
  2) 把落在目标段的字面量按「引用它的指令位置」聚类 ⇒ 得到访问点
只读，不改任何东西。
"""
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

SHT_SYMTAB, SHT_DYNSYM = 2, 11


def load_funcs(d):
    """返回排序的 (start, end, name) —— 固件无符号表时返回空。"""
    return []


def scan_literals(d, lo, hi):
    """扫 LDR rX,[pc,#imm] (=0xE59F_nnnn)，返回 [(pc_off, rt, value)]。"""
    N = len(d)
    out = []
    for i in range(0, N - 4, 4):
        w = struct.unpack_from("<I", d, i)[0]
        if (w & 0x0FFF0000) == 0x059F0000 and (w & 0xF0000000) == 0xE0000000:
            rt = (w >> 12) & 0xF
            imm = (w & 0xFFF) << 2
            at = ((i + 8) & ~3) + imm
            if at + 4 <= N:
                v = struct.unpack_from("<I", d, at)[0]
                if lo <= v < hi:
                    out.append((i, rt, v, at))
    return out


def main():
    path = Path(sys.argv[1])
    lo = int(sys.argv[2], 0)
    hi = int(sys.argv[3], 0)
    d = path.read_bytes()
    N = len(d)
    print("# %s  size=%d  目标段 0x%08x-0x%08x" % (path.name, N, lo, hi))

    hits = scan_literals(d, lo, hi)
    print("# LDR-literal 命中 %d 处" % len(hits))

    if not hits:
        print("(无)")
        return

    # 按被载入的基址值聚类
    byval = defaultdict(list)
    for pc, rt, v, pool in hits:
        byval[v].append(pc)

    print("\n==== 被引用的基址值（按引用次数） ====")
    for v, pcs in sorted(byval.items(), key=lambda kv: -len(kv[1]))[:40]:
        pc = pcs[0]
        print("  0x%08x  引用 %2d 次  首在镜像偏移 0x%06x  (池 0x%06x)"
              % (v, len(pcs), pc, (pc + 8) & ~3))
        if len(pcs) <= 6:
            print("        位置: " + " ".join("0x%06x" % x for x in sorted(pcs)))

    # 引用的代码区域分布（哪些函数在访问）
    print("\n==== 访问点所在代码区（4KB 桶） ====")
    b = Counter(pc >> 12 for pc, _, _, _ in hits)
    for k, v in b.most_common(20):
        print("  0x%06x-0x%06x  %4d 处" % (k * 4096, (k + 1) * 4096, v))

    # 偏移推断：看每个基址附近被引用的字面量（可能是寄存器表）
    print("\n==== 基址附近的其它字面量（同池连续 ⇒ 寄存器表） ====")
    for v, pcs in sorted(byval.items(), key=lambda kv: -len(kv[1]))[:6]:
        pc = pcs[0]
        pool = (pc + 8) & ~3
        # 读该字面量池前后各 8 个字
        ctx = []
        for k in range(-6, 7):
            a = pool + k * 4
            if 0 <= a <= N - 4:
                val = struct.unpack_from("<I", d, a)[0]
                mark = " <== 基址" if k == 0 else ""
                if lo <= val < hi or k == 0:
                    ctx.append("0x%08x%s" % (val, mark))
        if len(ctx) > 1:
            print("  基址 0x%08x 池 @0x%06x:" % (v, pool))
            print("      " + " ".join(ctx))


if __name__ == "__main__":
    main()
