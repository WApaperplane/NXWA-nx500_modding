#!/usr/bin/env python3
"""在无符号表的 ARM 固件里，用「字符串锚点」定位并反汇编函数。

为什么需要这个：
  p7 固件没有符号表（不是 ELF），但保留了 67,200 个可读标识符
  （C++ 符号被 strip 前的残留，常量池里保留了 mangled name / 日志串）。
  ⇒ 策略：先找到标识符字符串的位置，再沿 PC-relative 反查
  哪个 LDR 指令引用了它 —— 那个指令所在函数就是要找的函数。

★ 铁律 16 的延伸：解析器"零输出"和"目标不存在"必须能区分。
  本工具在找不到时明确报"字符串本身没找到"还是"找到但零引用"。

用法：
    python fnref.py <bin> <symbol>          # 定位并反汇编
    python fnref.py <bin> --find <regex>    # 按正则找标识符
"""
import re
import struct
import sys
from pathlib import Path

BL = 0xEB000000
B = 0xEA000000
LDR_LIT = 0x059F0000
STMFD = 0xE92D0000
BLX = 0xFA000000
BX = 0xE12FFF1E
POP = 0xE8BD0000
SUB_SP = 0xE24DD000
ADD_SP = 0xE28DD000
PUSH = 0xE92D0000
MOV_PC = 0xE1A0F00E


def find_strings(d, pattern, allow_space=False):
    """返回 [(offset, text)]，按 pattern 正则搜可读串。

    ★ 2026-10-06 补：allow_space=True 时允许匹配含空格的日志串
      （如 "CIQ_AWB_Test Func Start"）。
      原版用 [A-Za-z_][A-Za-z0-9_]{3,} 只匹标识符，
      导致日志串一律"未找到" —— 而日志串恰恰是定位函数的关键锚点
      （函数体内会printf("...Func Start")）。
    """
    out = []
    if allow_space:
        # 允许空格，但要求首尾是字母数字，且整体长度 >=4
        rx = rb"[A-Za-z0-9_][A-Za-z0-9_ ,.:%/\-]{2,}[A-Za-z0-9_.]"
    else:
        rx = rb"[A-Za-z_][A-Za-z0-9_]{3,}"
    for m in re.finditer(rx, d):
        s = m.group().decode("ascii", "replace")
        if re.search(pattern, s):
            out.append((m.start(), s))
    return out


def refs_to(d, target_off):
    """找所有 LDR-literal 引用了 target_off 的指令。

    LDR rX, [pc, #imm] => 池地址 = ((pc+8) & ~3) + imm
    目标可能也被 MOV/MOVW 间接引用，一并报告。
    """
    out = []
    lo = max(0, target_off - 0x20000)
    for i in range(lo, target_off, 4):
        w = struct.unpack_from("<I", d, i)[0]
        if (w & 0x0FFF0000) == LDR_LIT and (w & 0xF0000000) == 0xE0000000:
            imm = (w & 0xFFF) << 2
            at = ((i + 8) & ~3) + imm
            if at == target_off:
                out.append((i, (w >> 12) & 0xF, "LDR"))
    return out


def find_func_start(d, off, back=0x4000):
    """从 off 往前找函数入口：找 push {..,lr} 或 push {..}。"""
    lo = max(0, off - back)
    cands = []
    for i in range(off, lo, -4):
        w = struct.unpack_from("<I", d, i)[0]
        if (w & 0xFFFF0000) == STMFD:          # stmfd/push
            cands.append(i)
            if len(cands) >= 6:
                break
    return cands[0] if cands else None


def find_func_end(d, start, fwd=0x2000):
    """从 start 往后找 bx lr（ARM 模式）或 pop {..,pc}。"""
    n = min(len(d), start + fwd)
    for i in range(start, n - 4, 4):
        w = struct.unpack_from("<I", d, i)[0]
        if w == BX:                              # bx lr
            return i
        if (w & 0xFFFF0000) == 0xE8BD0000 and (w & 0x8000):   # pop {..,pc}
            return i
    return None


def disasm(d, start, end):
    """最小 ARM 反汇编：只标注分支/字面量/栈操作，够定位用。"""
    lines = []
    i = start
    while i < end and i < len(d) - 4:
        w = struct.unpack_from("<I", d, i)[0]
        ann = ""
        top = w & 0xFF000000
        if (w & 0x0FFF0000) == LDR_LIT and (w & 0xF0000000) == 0xE0000000:
            rt = (w >> 12) & 0xF
            imm = (w & 0xFFF) << 2
            at = ((i + 8) & ~3) + imm
            if 0 <= at < len(d) - 4:
                v = struct.unpack_from("<I", d, at)[0]
                s = ""
                if at < len(d):
                    frag = d[at:at + 44].split(b"\x00")[0]
                    if len(frag) > 2 and all(32 <= c < 127 for c in frag):
                        s = '  ; "%s"' % frag.decode("ascii", "replace")
                ann = "      ; ldr r%d, =0x%08x%s" % (rt, v, s)
        elif top == BL:
            imm = w & 0xFFFFFF
            if imm & 0x800000:
                imm -= 0x1000000
            ann = "      ; bl 0x%08x" % (i + 8 + imm * 4)
        elif top == B:
            imm = w & 0xFFFFFF
            if imm & 0x800000:
                imm -= 0x1000000
            t = i + 8 + imm * 4
            ann = "      ; b  0x%08x%s" % (t, "  (loop)" if t <= start else "")
        elif w == BX:
            ann = "      ; bx  lr   <== 函数返回"
        elif (w & 0x0E000000) == 0x0A000000:      # cmp
            ann = "      ; cmp"
        elif (w & 0x0FFF0000) == 0x03500000:      # cmp imm
            ann = "      ; cmp #%d" % (w & 0xFF)
        elif (w & 0x0E000000) == 0x02000000:      # add/sub imm
            I = (w >> 25) & 1
            imm = (w & 0xFFF) if I == 0 else ((w & 0xFF) << (((w >> 8) & 0xF) * 2))
            if imm:
                op = "add" if (w >> 21) & 1 else "sub"
                rn = (w >> 16) & 0xF
                rd = (w >> 12) & 0xF
                ann = "      ; %s r%d, r%d, #%d (0x%x)" % (op, rd, rn, imm, imm)
        elif (w & 0x0FFF0000) in (0x05900000, 0x05100000, 0x05200000, 0x05400000,
                                  0x05500000, 0x05600000, 0x05700000, 0x05800000):
            L = (w >> 20) & 1
            U = (w >> 23) & 1
            rn = (w >> 16) & 0xF
            rd = (w >> 12) & 0xF
            imm = w & 0xFFF
            op = "ldr" if L else "str"
            if imm:
                ann = "      ; %s r%d, [r%d, #%s%d]  (off 0x%x)" % (
                    op, rd, rn, "" if U else "-", imm, imm)
        lines.append("  0x%06x: %08x%s" % (i, w, ann))
        i += 4
    return "\n".join(lines)


def main():
    path = Path(sys.argv[1])
    d = path.read_bytes()
    N = len(d)
    if len(sys.argv) > 2 and sys.argv[2] == "--find":
        pat = sys.argv[3]
        hits = find_strings(d, pat)
        print("# 匹配 %r 的标识符: %d 条" % (pat, len(hits)))
        for o, s in hits[:60]:
            print("  0x%06x  %s" % (o, s))
        return

    sym = sys.argv[2]
    # 含空格则自动启用 allow_space（日志串锚点）
    allow_space = (" " in sym) or ("--space" in sys.argv)
    hits = find_strings(d, re.escape(sym), allow_space=allow_space)
    print("# 目标符号: %s%s" % (sym, "  [含空格模式]" if allow_space else ""))
    if not hits:
        print("!! 字符串本身【未找到】—— 目标可能不存在（区别于『找到但零引用』）")
        sys.exit(2)
    print("# 字符串位置 %d 处" % len(hits))
    # ★ 对照组自证：若所有命中都是零引用，结论不可信（铁律 20）
    total_refs = 0
    for so, stext in hits:
        print("\n" + "=" * 70)
        print("# 字符串 @ 0x%06x : %s" % (so, stext))
        refs = refs_to(d, so)
        total_refs += len(refs)
        if not refs:
            print("!! 找到字符串，但【零 LDR-literal 引用】")
            print("   ⇒ 可能通过 MOV/MOVW 间接引用，或通过表指针间接访问")
            print("   ⇒ 也可能是【本工具的解码方式不适用该固件】——")
            print("      必须用一个已知有引用的串做对照，才能判定这一条的可信度")
            continue
        print("# LDR 引用 %d 处" % len(refs))
        for ri, rt, kind in refs:
            fs = find_func_start(d, ri)
            fe = find_func_end(d, fs if fs else ri)
            print("\n-- 引用点 @ 0x%06x (r%d, %s)" % (ri, rt, kind))
            if fs:
                print("   函数起点估计 @ 0x%06x" % fs)
            else:
                print("   函数起点未找到（往前 16KB 无 push）")
                fs = ri - 0x40
            end = min((fe if fe else fs + 0x200) + 8, N)
            print(disasm(d, fs, end))

    if total_refs == 0:
        print("\n" + "!" * 70)
        print("!! 全部 %d 处命中均为零引用。" % len(hits))
        print("!! ★ 这不是结论，是【工具失效】的信号。")
        print("!! 自证方法：换一个已知必然被代码引用的串跑同样的流程，")
        print("!!   若它也是零引用 ⇒ 本工具对该固件不适用，别把零引用当结论。")
        sys.exit(3)


if __name__ == "__main__":
    main()
