#!/usr/bin/env python3
"""p7 归属覆盖率扩展 ①②③  (NX-KS2 / U01 扩展 III)

承接 docs/current/TIER1_AND_TIER3_OFFLINE_2026-10-08.md §8.4 列出的三条通道：

① A 区/带限定名的格式串：形如 `CBackendParameterMonitor::SetLiveviewParam2Monitor(%x, %p, %d)`
   引用它的函数**就是那个方法** ⇒ 类名与方法名直接得到。
② Thumb 函数：vtable 里有一批槽的目标不是 Ghidra 函数起点（多为 Thumb）。
   对每个未解析目标做 **Thumb 序言检测**（push {..,lr} / push.w / 常见首指令），
   命中则把它当函数，归属到该类。
③ A 区「类名被代码引用」（跳1 命中但跳2 为空）：
   那说明是**代码直接引用类名**（工厂注册/断言/日志），引用者归属到该类。

★ 三条都是**直接引用证据**（不是调用图传播的推断），因此计入 hard 一栏。
★ 判据纪律：每条归属都记录 evidence（字符串 / 指令地址 / 序言字节），可复核。

用法  python p7_extend_map.py
产物  raw8/p7/p7_extend_map.txt + raw8/p7/p7_extend_map.tsv
"""
from __future__ import annotations

import collections
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p7_code_map as pcm  # noqa: E402

P7 = pcm.P7DIR
IMG = os.path.join(P7, "p7_full.bin")
VA = 0x80000000
A_LO, A_HI = 0x580000, 0x600000

QUAL = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_]*::)+([A-Za-z_~][A-Za-z0-9_]*)")
CLSNAME = re.compile(r"^(\d{1,3})([A-Za-z_][A-Za-z0-9_:<>~]{2,80})$")


def thumb_prologue(img, off):
    """Thumb 函数序言检测 -> (bool, 描述)"""
    if off + 4 > len(img):
        return False, ""
    b0, b1 = img[off], img[off + 1]
    # 16-bit Thumb: push {...,lr} = 1011 010x xxxxxxxx  → 0xB5**
    if b1 == 0xB5:
        return True, f"push {{{b0:02x}}} lr  (0xB5{b0:02x})"
    if b1 == 0xB4:
        return True, f"push {{{b0:02x}}}     (0xB4{b0:02x})"
    if b1 == 0xB2:
        return True, "push (no lr)"
    # 32-bit Thumb prologue: push.w = 1110 1001 0010 1101 = 0xE92D
    hw = struct.unpack_from("<H", img, off)[0]
    if hw == 0xE92D:
        return True, "push.w (0xE92D)"
    # 常见：sub sp,#imm (0xB08x) 后跟 bl
    if b1 == 0xB0 and b0 in (0x80, 0x81, 0x82, 0x83, 0x84):
        return True, f"sub sp,#{b0*4} (0xB{b0:02x})"
    # ARM 序言（可能混编）: stmdb sp!,{...,lr} = 0xE92D****
    w = struct.unpack_from("<I", img, off)[0]
    if (w & 0xFFFF0000) == 0xE92D0000:
        return True, f"stmdb sp!,{{lr}} (0x{w:08x})"
    return False, ""


def main():
    img = open(IMG, "rb").read()
    funcs = pcm.load_functions(pcm.F_FUNCS)
    strings = pcm.load_strings(pcm.F_STRINGS)
    fidx = pcm.FuncIndex(funcs)

    # 现有硬证据标签
    hard = {}
    tsv = os.path.join(P7, "p7_code_map.tsv")
    if os.path.exists(tsv):
        with open(tsv, encoding="utf-8", errors="replace") as fh:
            next(fh, None)
            for ln in fh:
                p = ln.rstrip("\r\n").split("\t")
                if len(p) >= 2 and p[0]:
                    hard[p[0]] = "mod:" + p[1]
    ctsv = os.path.join(P7, "p7_class_map.tsv")
    if os.path.exists(ctsv):
        with open(ctsv, encoding="utf-8", errors="replace") as fh:
            next(fh, None)
            for ln in fh:
                p = ln.rstrip("\r\n").split("\t")
                if len(p) >= 4 and p[3] and p[3] not in hard:
                    hard[p[3]] = "cls:" + p[0]
    base_hard = len(hard)
    print(f"baseline hard labels = {base_hard}")

    # 引用扫描（复用 U01 的扫描器：必须解引用池槽 + 加 0x80000000）
    va2file = {s + VA: s for s in strings}
    xrefs_va = pcm.scan_literal_pool_xrefs(img, set(va2file))
    xrefs = collections.defaultdict(list)
    for va, instrs in xrefs_va.items():
        xrefs[va2file[va]].extend(instrs)
    print(f"referenced strings = {len(xrefs)}")

    added = {}          # func -> (label, channel, evidence)

    # ---- 通道 ①：限定名格式串 ----
    # 注：这类串多在 B 区（0x710000+），引用它的函数**多半已被 U01 的模块通道覆盖**
    #     ⇒ 本通道的真正价值是「把 mod: 标签精化为 cls:Class::Method」，单独记为 refine
    n1 = 0
    refine = {}
    for saddr, instrs in xrefs.items():
        t = strings.get(saddr, (0, ""))[1]
        m = QUAL.match(t)
        if not m:
            continue
        qual = t.split("::")[:-1]
        if not qual:
            continue
        cls, meth = qual[-1], m.group(1)
        for ia in instrs:
            o = fidx.owner(ia)
            if not o:
                continue
            if o[2] not in hard and o[2] not in added:
                added[o[2]] = (f"cls:{cls}", "①限定名串", f"{t[:52]!r} @insn {ia:#x} [{meth}]")
                n1 += 1
            elif o[2] in hard and not hard[o[2]].startswith("cls:"):
                refine.setdefault(o[2], (f"{cls}::{meth}", f"{t[:52]!r}"))
    print(f"channel ①  qualified-name strings -> new +{n1}, refined {len(refine)}")

    # ---- 通道 ③：A 区类名被代码直接引用（typeinfo 跳2 为空的那些）----
    inv = collections.defaultdict(list)
    n = len(img)
    for off in range(0, n - 4, 4):
        v = struct.unpack_from("<I", img, off)[0]
        if VA <= v < VA + n:
            inv[v].append(off)
    n3 = 0
    for saddr, instrs in xrefs.items():
        if not (A_LO <= saddr < A_HI):
            continue
        t = strings.get(saddr, (0, ""))[1]
        m = CLSNAME.match(t)
        if not m or int(m.group(1)) != len(m.group(2)):
            continue
        cls = m.group(2)
        for ia in instrs:
            o = fidx.owner(ia)
            if not o or o[2] in hard or o[2] in added:
                continue
            # 只要"代码直接引用"这一条（这是日志/注册/断言形态）
            added[o[2]] = (f"cls:{cls}", "③类名被代码引用", f"{t[:52]!r} @insn {ia:#x}")
            n3 += 1
    print(f"channel ③  class names referenced from code -> +{n3}")

    # ---- 通道 ②：Thumb 函数（vtable 未解析目标）----
    funcstarts = {f[0] for f in funcs}
    n2 = 0
    thumb_found = []
    if os.path.exists(ctsv):
        with open(ctsv, encoding="utf-8", errors="replace") as fh:
            next(fh, None)
            for ln in fh:
                p = ln.rstrip("\r\n").split("\t")
                if len(p) < 4:
                    continue
                f = p[3]
                if f.startswith("FUN_") or f == "Reset" or f.startswith("0x"):
                    pass
                if not f.startswith("0x"):
                    continue
                off = int(f, 16)
                if off in funcstarts:
                    continue
                ok, desc = thumb_prologue(img, off)
                if ok:
                    thumb_found.append((off, desc, p[0]))
    seen = {}
    for off, desc, cls in thumb_found:
        if off not in seen:
            seen[off] = (f"cls:{cls}", "②Thumb 序言", desc)
            n2 += 1
    added.update({k: v for k, v in seen.items() if k not in added})
    print(f"channel ②  Thumb prologues at unresolved vtable targets -> +{n2}")

    total = len(funcs)
    new_hard = collections.defaultdict(list)
    for f, (lab, ch, ev) in added.items():
        new_hard[ch].append((f, lab, ev))

    comb = len(set(hard) | set(added))
    print(f"\nbaseline hard={base_hard}  added={len(added)}  hard now={comb}/{total} "
          f"({100.0*comb/total:.2f}%)")

    lines = []
    lines.append("=" * 96)
    lines.append("p7 · 归属覆盖率扩展 ①②③（直接引用证据，计入 hard）  (NX-KS2 / U01 扩展 III)")
    lines.append("=" * 96)
    lines.append(f"函数总数            : {total}")
    lines.append(f"基线 hard 标签      : {base_hard}")
    lines.append(f"① 限定名格式串      : +{n1} 新增 / ★ {len(refine)} 条标签精化（mod: → Class::Method）")
    lines.append(f"③ 类名被代码引用    : +{n3}")
    lines.append(f"② Thumb 序言命中    : +{n2}")
    lines.append(f"新增合计            : +{len(added)}")
    lines.append(f"★ 扩充后 hard       : {comb} / {total} ({100.0*comb/total:.2f}%)")
    lines.append("")
    lines.append("★ 三条都是「直接引用证据」（字符串被某指令引用 / vtable 指向该地址并有序言），")
    lines.append("  不是调用图传播的推断 ⇒ 计入 hard 一栏。每条附证据可复核。")
    lines.append("")
    lines.append("-" * 96)
    lines.append(f"## ★ 通道① 的副产品：{len(refine)} 条「模块 → 具体方法」精化")
    lines.append("-" * 96)
    lines.append("（函数本来已有 mod: 标签，现在拿到了 `Class::Method` —— 这是 p7 第一批**真实方法名**）")
    lines.append("")
    for f in sorted(refine):
        mn, ev = refine[f]
        lines.append(f"  {f:<22} {hard.get(f,'?'):<44} = {mn:<46} {ev}")
    lines.append("")
    lines.append("-" * 96)
    lines.append("## 新增按通道与标签聚合")
    lines.append("-" * 96)
    for ch in ("①限定名串", "③类名被代码引用", "②Thumb 序言"):
        rows = new_hard.get(ch, [])
        if not rows:
            continue
        lines.append("")
        lines.append(f"### {ch}  （{len(rows)} 条）")
        agg = collections.Counter(lab for _, lab, _ in rows)
        for lab, c in agg.most_common(40):
            lines.append(f"    {c:>4}  {lab}")
    lines.append("")
    lines.append("-" * 96)
    lines.append("## 明细（函数 / 标签 / 通道 / 证据）")
    lines.append("-" * 96)
    for ch in ("①限定名串", "③类名被代码引用", "②Thumb 序言"):
        for f, lab, ev in sorted(new_hard.get(ch, [])):
            lines.append(f"  {f:<22} {lab:<46} {ch}  {ev}")

    with open(os.path.join(P7, "p7_extend_map.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    with open(os.path.join(P7, "p7_extend_map.tsv"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("func\tlabel\tchannel\tevidence\n")
        for f, (lab, ch, ev) in sorted(added.items()):
            fh.write(f"{f}\t{lab}\t{ch}\t{ev}\n")
    print(f"wrote {P7}/p7_extend_map.txt + .tsv")

    print("\n--- 通道 ① 命中样本 ---")
    for f, lab, ev in new_hard.get("①限定名串", [])[:12]:
        print(f"  {f:<22} {lab:<44} {ev[:70]}")


if __name__ == "__main__":
    sys.exit(main())
