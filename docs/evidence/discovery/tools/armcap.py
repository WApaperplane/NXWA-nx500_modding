#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
capstone ARM 工具集 —— NX500 p7 固件静态分析
铁律: 所有指令级结论必须走本文件, 禁止手写十六进制解码。

地址约定: Ghidra 地址 == 文件偏移; VA = 0x80000000 + 文件偏移
"""
import sys, os, struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_LITTLE_ENDIAN

FW = r"D:/download/NX-KS2-88/raw8/p7/p7_full.bin"
VA_BASE = 0x80000000
_cache = {}


def fw():
    if "d" not in _cache:
        with open(FW, "rb") as f:
            _cache["d"] = f.read()
    return _cache["d"]


def va(off):
    return off + VA_BASE


def off(v):
    return v - VA_BASE


def disasm(vaddr, size=0x60, detail=False):
    """从虚拟地址反汇编 size 字节, 返回 capstone 指令列表。"""
    o = off(vaddr)
    d = fw()[o:o + size]
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)
    md.detail = detail
    return list(md.disasm(d, vaddr))


def p(text=""):
    print(text)


def show(vaddr, size=0x60, hdr=True):
    """打印反汇编, 并解析 ldr 的字面池值。"""
    if hdr:
        p("=" * 78)
        p("  VA 0x%08x  (file off 0x%06x)  len=%d" % (vaddr, off(vaddr), size))
        p("=" * 78)
    ins = disasm(vaddr, size)
    _dump(ins)
    return ins


def _pool(vaddr):
    """读 ARM 字面池 4 字节 (VA) -> int, 同时尝试解字符串。"""
    o = off(vaddr)
    d = fw()
    if o < 0 or o + 4 > len(d):
        return None, None
    val = struct.unpack_from("<I", d, o)[0]
    s = None
    so = off(val)
    if 0 <= so < len(d) - 4:
        raw = d[so:so + 200]
        end = raw.find(b"\x00")
        if 2 < end < 190:
            try:
                cand = raw[:end].decode("ascii")
                if all(32 <= ord(c) < 127 for c in cand):
                    s = cand
            except Exception:
                pass
    return val, s


def _dump(ins):
    for i in ins:
        extra = ""
        m = i.mnemonic
        op = i.op_str
        if m in ("ldr",) and "[pc" in op:
            # PC = ins.address + 8 (ARM)
            pc = i.address + 8
            try:
                imm = int(op.split("#")[1].rstrip("]"), 0)
                pool = pc + imm
                val, s = _pool(pool)
                if val is None:
                    extra = "   ; pool@0x%08x -> OUT OF RANGE" % pool
                else:
                    extra = "   ; pool@0x%08x -> 0x%08x" % (pool, val)
                    if s:
                        extra += " '%s'" % s
            except Exception:
                pass
        p("0x%08x: %-10s %-34s%s" % (i.address, m, op, extra))


def func_pseudo(name):
    """从 Ghidra 全量伪代码里抽出某个 FUN 的函数体。"""
    pc_path = r"D:/download/NX-KS2-88/raw8/p7/ghidra/53_all_pseudocode.c"
    if not os.path.exists(pc_path):
        p("[warn] pseudocode missing: " + pc_path)
        return
    with open(pc_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    start = None
    for idx, ln in enumerate(lines):
        if name in ln and ("(" in ln) and ln.rstrip().endswith("{"):
            start = idx
            break
    if start is None:
        p("[warn] function not found: " + name)
        return
    p("### %s  (line %d)" % (name, start + 1))
    depth = 0
    for ln in lines[start:]:
        p(ln.rstrip())
        depth += ln.count("{") - ln.count("}")
        if depth <= 0 and "}" in ln:
            break


if __name__ == "__main__":
    a = sys.argv[1]
    n = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x60
    show(int(a, 0), n)