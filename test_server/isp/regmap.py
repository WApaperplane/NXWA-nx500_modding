#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ EP 寄存器偏移全表自动提取（libudd5.so）

对每个 _udd_ep_*_reg_* 函数：
  1. 找`ldr rX,[pc,#N]` -> `add rX,pc,rX` 模式解出 GOT 基准
  2. 找 `ldr rY,[GOT+off]` -> 得到全局符号（如 ep_3dlut_reg_base）
  3. 扫函数体内所有 `[rX, #imm]` 累加 -> 得到该符号基址下的寄存器偏移
  4. 输出 (符号, 偏移, 该函数做了什么)

产出 = 『哪个 API 写 EP 哪个寄存器的第几字节』的完整映射，
可直接与实机 /dev/mem 读到的 0x2082b000 等块交叉验证。
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from udd5 import Elf, Dis, LIB, CS_OP_IMM, CS_OP_MEM  # noqa

REG_KW = re.compile(r"^_udd_ep_(3dl|nog|mc|lvr|top|fd|jpeg|rsz|ldc|bblt)_reg")


def analyze(elf, dis):
    gotb = elf.got_base()
    rows = []
    for v, name, sz in elf.funcs:
        if not REG_KW.match(name):
            continue
        base = v & ~1
        size = elf.func_size(base)
        ins = dis.decode(base, size)
        if not ins:
            continue
        # (1) 全函数扫 ldr rY,[rX,#imm] 形式：rX 是寄存器变量（来自 GOT）
        #     我们记录 (基址符号集合, 偏移集合, 出现的 mov/orr 立即数)
        offs = set()
        imms = set()
        strs = set()
        regs_touched = set()
        for x in ins:
            mn = x.mnemonic
            try:
                ops = x.operands
            except Exception:
                continue
            # ldr rA, [rB, #imm]  -> 记录 imm（EP 块内寄存器偏移）
            if mn in ("ldr", "str", "strb", "ldrb") and len(ops) >= 2:
                m = ops[1]
                if m.type == CS_OP_MEM and m.mem.disp:
                    if abs(m.mem.disp) < 0x2000:
                        offs.add(m.mem.disp)
                        regs_touched.add(x.reg_name(m.mem.base))
            if mn in ("mov", "orr", "bic", "and", "add", "bfc", "bfi", "mvn"):
                for o in ops:
                    if o.type == CS_OP_IMM:
                        v2 = o.imm & 0xFFFFFFFF
                        if v2 < 0x400:
                            imms.add(v2)
            for n in dis.annotate(x):
                strs.add(n)
        # (2) 该函数引用了哪些全局符号（GOT 槽）
        base_syms = set()
        for a, nm in elf.relsym.items():
            if nm in strs or ("->%s" % nm) in strs:
                base_syms.add(nm)
        rows.append(dict(name=name, va=base, size=size,
                         offs=sorted(offs), imms=sorted(imms),
                         calls=sorted(n for n in strs if n.startswith("->")),
                         syms=sorted(s for s in strs if not n_ok(s))))
    return rows


def n_ok(s):
    return s.startswith("->")


def main():
    elf = Elf(LIB)
    dis = Dis(elf)
    rows = analyze(elf, dis)
    print("=" * 78)
    print("EP 寄存器偏移全表（%d 个 reg 层函数）" % len(rows))
    print("=" * 78)
    for r in rows:
        print("\n--- %s @0x%06x (%d B)" % (r["name"], r["va"], r["size"]))
        if r["syms"]:
            print("    全局   : %s" % ", ".join(r["syms"][:6]))
        if r["calls"]:
            print("    调用   : %s" % ", ".join(c.lstrip("->@plt ") for c in r["calls"][:8]))
        if r["offs"]:
            print("    偏移   : %s" % " ".join(
                ("+0x%x" % o if o > 0 else "-0x%x" % -o) for o in r["offs"][:16]))
        if r["imms"]:
            print("    立即数 : %s" % " ".join(str(i) for i in r["imms"][:16]))


if __name__ == "__main__":
    main()