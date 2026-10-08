#!/usr/bin/env python3
"""p7「B 区」代码地图 · 硬证据覆盖率扩展 v2  (NX-KS2 / U01 扩展 IV · D5)

承接 p7_extend_map.py（v1，硬 48.21%）。★ 不改变判据纪律：

  · **硬证据** = 有直接引用证据的归属（字符串引用 / RTTI 三跳 / 指针表 / 序言回收）
  · **推断**   = 调用图传播（复用 p7_callgraph.py 的产物）—— 单列，**不计入**硬证据分子。

三条硬证据通道（每条可溯源到 p7 文件偏移/VA）：

  R 广义 RTTI（typeinfo 签名校验）
     v1 的 p7_class_map.py 只在 A 区（0x580000-0x600000）找「长度前缀自洽」的
     Itanium 类名，解出 565 类。本轮：
       (a) 搜索放到**全镜像**；
       (b) 加一道 **typeinfo 签名校验**：type_info 结构 = [vptr][name_ptr]，
           其 vptr 只应取极少数几个值。实测 910 个候选的 vptr 只落在 **3 个值**上
           ⇒ 签名自校验通过（这 3 个值就是 __class_type_info / __si_class_type_info /
           __vmi_class_type_info 的 vtable）。
       (c) 名字不再要求"长度前缀自洽"（那会漏掉**模板/嵌套**名，如
           `9SingletonI13C3AControllerE` = Singleton<C3AController>）—— 因为 vptr 签名
           已经是足够强的独立校验。

  P 函数指针表
     连续 ≥4 个「指向 Ghidra 函数起点（或 f-1）」的 4 字节指针 = 分发/跳转/方法表。
     被它指向的函数即"被代码以地址形式引用" ⇒ 存在且被登记（硬证据）。

  F 漏识别函数回收（★ 兼作对 v1「②Thumb」的更正）
     v1 的 "②Thumb 序言" 实为 **ARM 序言**：667 条全部 4 字节对齐、首指令
     `0xe92d....`（ARM `stmdb sp!,{..,lr}`）—— 它们是 **Ghidra 漏识别的 ARM 函数**，
     不是 Thumb。本轮把"被指针指向但不在 Ghidra 函数表里、且有 ARM 序言"的地址
     回收为函数（计入**统一口径**的分母与分子）。

用法  python p7_extend_map_v2.py
产物  raw8/p7/p7_extend_map_v2.txt / .tsv（保留 v1 的 p7_extend_map.tsv）
"""
from __future__ import annotations

import bisect
import collections
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
P7 = os.path.join(REPO, "raw8", "p7")
GH = os.path.join(P7, "ghidra")
IMG = os.path.join(P7, "p7_full.bin")
VA = 0x80000000

STRLEN = re.compile(r"^(\d{1,3})([A-Za-z_][A-Za-z0-9_:<>~]{2,80})$")


def load_strings(path):
    out = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            p = ln.rstrip("\r\n").split("\t", 2)
            if len(p) == 3 and len(p[0]) == 8:
                try:
                    out[int(p[0], 16)] = p[2]
                except ValueError:
                    pass
    return out


def load_functions(path):
    out = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            p = ln.rstrip("\r\n").split("\t")
            if len(p) >= 3 and p[0].startswith("0x"):
                try:
                    out.append((int(p[0], 16), int(p[1]), p[2]))
                except ValueError:
                    pass
    out.sort()
    return out


def load_tsv_col(path, col=0):
    out = set()
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", errors="replace") as fh:
        next(fh, None)
        for ln in fh:
            p = ln.rstrip("\r\n").split("\t")
            if len(p) > col and p[col]:
                out.add(p[col])
    return out


def arm_prologue(img, off):
    if off + 4 > len(img) or off % 4:
        return None
    w = struct.unpack_from("<I", img, off)[0]
    if (w & 0xFFFF0000) == 0xE92D0000 and (w & (1 << 14)):
        return "ARM stmdb sp!,{..,lr}=%#010x" % w
    return None


def thumb_prologue(img, off):
    if off + 2 > len(img) or off % 2:
        return None
    hw = struct.unpack_from("<H", img, off)[0]
    if (hw & 0xFF00) == 0xB500:
        return "Thumb push {..,lr}=%#06x" % hw
    return None


def methods_from(img, vs, n, cap=128):
    out = []
    for k in range(cap):
        if vs + k * 4 > n - 4:
            break
        w = struct.unpack_from("<I", img, vs + k * 4)[0]
        if not (VA <= w < VA + n):
            break
        out.append(w - VA)
    return out


def main():
    img = open(IMG, "rb").read()
    n = len(img)
    strings = load_strings(os.path.join(GH, "04_strings.txt"))
    funcs = load_functions(os.path.join(GH, "52_pseudocode_index.txt"))
    starts = [f[0] for f in funcs]
    fstart = {f[0] for f in funcs}
    name_of = {f[0]: f[2] for f in funcs}
    total = len(funcs)

    def owner(a):
        i = bisect.bisect_right(starts, a) - 1
        if i < 0:
            return None
        s, sz, nm = funcs[i]
        end = s + sz if sz else (funcs[i + 1][0] if i + 1 < len(funcs) else s + 0x10000)
        return funcs[i] if s <= a < max(end, s + 4) else None

    def ident(tgt):
        if tgt in fstart:
            return name_of[tgt], "fun"
        if (tgt - 1) in fstart:
            return name_of[tgt - 1], "fun"
        return "@%x" % tgt, "addr"

    # -------- 逆索引 + 串指针位点
    inv = collections.defaultdict(list)
    ptr2str = []
    for off in range(0, n - 4, 4):
        v = struct.unpack_from("<I", img, off)[0]
        if VA <= v < VA + n:
            inv[v].append(off)
            if (v - VA) in strings:
                ptr2str.append((off, v - VA))
    print(f"inverse-index values = {len(inv)}   string-pointer sites = {len(ptr2str)}")

    # =================================================== R：广义 RTTI
    # 第一遍：用「长度前缀自洽」的保守子集确定规范 typeinfo vptr 集合
    strict_cand = []
    for P, soff in ptr2str:
        t = strings.get(soff, "")
        m = STRLEN.match(t)
        if not m or int(m.group(1)) != len(m.group(2)):
            continue
        ti = P - 4
        if ti < 0 or not inv.get(ti + VA):
            continue
        strict_cand.append((t, soff, ti, struct.unpack_from("<I", img, ti)[0]))
    vpc = collections.Counter(vp for *_, vp in strict_cand)
    canon = {v for v, c in vpc.items() if c >= 20 and VA <= v < VA + n}
    print(f"typeinfo 候选(保守子集) = {len(strict_cand)}   规范 typeinfo vptr = "
          f"{[hex(v) for v in sorted(canon)]}")

    # 第二遍：全镜像，只要 vptr 命中签名 + typeinfo 被指向 + vtable ≥2 槽
    classes = {}                       # name -> list[(vt_off, str_off, ti_off, [slots], is_strict)]
    for P, soff in ptr2str:
        t = strings.get(soff, "")
        if len(t) < 3 or not re.search(r"[A-Za-z_]", t) or len(t) > 120:
            continue
        ti = P - 4
        if ti < 0 or not inv.get(ti + VA):
            continue
        if struct.unpack_from("<I", img, ti)[0] not in canon:
            continue                       # ★ typeinfo 签名
        m = STRLEN.match(t)
        is_strict = bool(m and int(m.group(1)) == len(m.group(2)))
        for M in inv.get(ti + VA, ()):
            meth = methods_from(img, M + 4, n)
            if len(meth) >= 2:
                classes.setdefault(t, []).append((M, soff, ti, meth, is_strict))
    n_strict_cls = sum(1 for t, v in classes.items() if all(x[4] for x in v))
    print(f"[R] classes(typeinfo-signature) = {len(classes)}  "
          f"(其中严格长度前缀名 = {n_strict_cls})")

    # =================================================== P：函数指针表
    def is_funcptr(v):
        if not (VA <= v < VA + n):
            return False
        f = v - VA
        return (f in fstart) or (f - 1) in fstart

    runs = []
    off = 0
    while off <= n - 16:
        if is_funcptr(struct.unpack_from("<I", img, off)[0]):
            j, cnt = off, 0
            while j <= n - 4 and is_funcptr(struct.unpack_from("<I", img, j)[0]):
                cnt += 1
                j += 4
            if cnt >= 4:
                runs.append((off, cnt))
                off = j
                continue
        off += 4
    ptbl = {}
    for o, c in runs:
        for k in range(c):
            f = struct.unpack_from("<I", img, o + k * 4)[0] - VA
            tgt = f if f in fstart else f - 1
            ptbl.setdefault(name_of[tgt], (o, k, tgt))
    print(f"[P] pointer-table runs = {len(runs)}   distinct funcs = {len(ptbl)}")

    # =================================================== F：序言回收
    referenced = set()
    for t, vts in classes.items():
        for M, soff, ti, meth, st in vts:
            referenced.update(meth)
    for o, c in runs:
        for k in range(c):
            referenced.add(struct.unpack_from("<I", img, o + k * 4)[0] - VA)
    recovered = {}
    for r in referenced:
        if r in fstart or (r - 1) in fstart or owner(r):
            continue
        d = arm_prologue(img, r) or thumb_prologue(img, r)
        if d:
            recovered[r] = d
    n_arm = sum(1 for d in recovered.values() if d.startswith("ARM"))
    print(f"[F] recovered funcs = {len(recovered)}  (ARM {n_arm} / Thumb {len(recovered)-n_arm})")

    # =================================================== 身份集合
    modFUN = {k for k in load_tsv_col(os.path.join(P7, "p7_code_map.tsv"), 0)
              if k and k != "func"}
    cls_v1 = load_tsv_col(os.path.join(P7, "p7_class_map.tsv"), 3)
    ext_v1 = load_tsv_col(os.path.join(P7, "p7_extend_map.tsv"), 0)          # 十进制串
    extADDR = {int(x) for x in ext_v1 if x.isdigit()}

    clsFUN_v2, clsADDR_v2, clsALL_keys_v2 = set(), set(), set()
    for t, vts in classes.items():
        for M, soff, ti, meth, st in vts:
            for f in meth:
                k, kind = ident(f)
                if kind == "fun":
                    clsFUN_v2.add(k)
                    clsALL_keys_v2.add(k)
                else:
                    clsADDR_v2.add(f)
                    clsALL_keys_v2.add("0x%x" % f)

    # 口径 O（旧/文档口径，原样保留其键空间，含 v1 的 667 重复）
    o_v1 = set(modFUN) | set(cls_v1) | set(ext_v1)
    o_v2 = set(modFUN) | clsALL_keys_v2 | set(ext_v1) | set(ptbl)
    # 口径 D（去重：统一身份键）
    d_v1 = set(modFUN) | {k for k in cls_v1 if k.startswith("FUN_") or k == "Reset"} \
        | {"@%x" % a for a in (extADDR | {int(k, 16) for k in cls_v1 if k.startswith("0x")})}
    d_v2 = set(modFUN) | clsFUN_v2 | {"@%x" % a for a in (clsADDR_v2 | extADDR)} | set(ptbl)
    # 口径 S（严格：仅 Ghidra 函数）
    s_v1 = set(modFUN) | {k for k in cls_v1 if k.startswith("FUN_") or k == "Reset"}
    s_v2 = set(modFUN) | clsFUN_v2 | set(ptbl)

    # =================================================== 推断（复用 callgraph）
    inferred = {}
    cg = os.path.join(P7, "p7_callgraph.txt")
    if os.path.exists(cg):
        on = False
        for ln in open(cg, encoding="utf-8", errors="replace"):
            if ln.startswith("## 推断明细"):
                on = True
                continue
            if on and ln.startswith("## "):
                break
            if on:
                m = re.match(r"^\s+(FUN_[0-9a-f]{8})\s+(\S+)\s+conf=(\S+)\s+support=(\S+)", ln)
                if m:
                    inferred[m.group(1)] = (m.group(2), float(m.group(3)), int(m.group(4)))

    def pc(x, d=total):
        return 100.0 * x / d

    R = len(recovered)
    uni = len(s_v2) + R
    d_v2_noP = set(modFUN) | clsFUN_v2 | {"@%x" % a for a in (clsADDR_v2 | extADDR)}
    all_inf = len(set(d_v2) | set(inferred))
    all_inf_O = len(set(o_v2) | set(inferred))
    print("\n--- 覆盖率（/16466）---")
    print(f"口径O 旧(串键,含重复667) v1 : {len(o_v1)} = {pc(len(o_v1)):.2f}%")
    print(f"口径O 旧(串键,含重复667) v2 : {len(o_v2)} = {pc(len(o_v2)):.2f}%")
    print(f"口径D 去重               v1 : {len(d_v1)} = {pc(len(d_v1)):.2f}%")
    print(f"   + R(广义RTTI)            : {len(d_v2_noP)} = {pc(len(d_v2_noP)):.2f}%")
    print(f"   + P(指针表)   [=v2 硬]   : {len(d_v2)} = {pc(len(d_v2)):.2f}%")
    print(f"口径S 严格(仅Ghidra函数) v1 : {len(s_v1)} = {pc(len(s_v1)):.2f}%")
    print(f"口径S 严格(仅Ghidra函数) v2 : {len(s_v2)} = {pc(len(s_v2)):.2f}%")
    print(f"口径U 统一(含回收 {R}) v2    : {uni}/{total+R} = {100.0*uni/(total+R):.2f}%")
    print(f"含推断(口径D ∪ callgraph {len(inferred)}) : {all_inf} = {pc(all_inf):.2f}%")
    print(f"含推断(口径O ∪ callgraph {len(inferred)}) : {all_inf_O} = {pc(all_inf_O):.2f}%")

    # =================================================== 落盘
    rows = []
    for t, vts in classes.items():
        for M, soff, ti, meth, st in vts:
            for i, f in enumerate(meth):
                k, kind = ident(f)
                crit = "strict" if st else "wide"
                rows.append((k, "cls:" + t, "R-RTTI", kind, crit,
                             f"name@{soff:#x} ti@{ti:#x} vt@{M:#x} slot{i}"))
    for name, (o, k, tgt) in ptbl.items():
        rows.append((name, "ptr-table", "P-fptbl", "fun", "strict", f"tbl@{o:#x} slot{k}"))
    for a, d in recovered.items():
        rows.append(("@%x" % a, "recovered", "F-prologue", "addr", "strict",
                     f"off={a:#x} {d}"))
    with open(os.path.join(P7, "p7_extend_map_v2.tsv"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write("identity\tlabel\tchannel\tkind\tcriterion\tevidence\n")
        for r in sorted(rows):
            fh.write("\t".join(str(x) for x in r) + "\n")
    print(f"wrote {P7}/p7_extend_map_v2.tsv  ({len(rows)} rows)")

    L = []
    A = L.append
    A("=" * 96)
    A("p7「B 区」代码地图 · 硬证据覆盖率扩展 v2  (NX-KS2 / U01 扩展 IV · D5)")
    A("=" * 96)
    A(f"函数总数(=Ghidra 索引)        : {total}")
    A(f"typeinfo 签名校验             : 保守子集 {len(strict_cand)} 个 -> 规范 vptr "
      f"{[hex(v) for v in sorted(canon)]}")
    A(f"[R] 类(typeinfo 签名)         : {len(classes)}  (严格长度前缀名 {n_strict_cls})")
    A(f"[P] 指针表 runs / 函数        : {len(runs)} / {len(ptbl)}")
    A(f"[F] 回收函数(被指针指向+序言) : {len(recovered)}  (ARM {n_arm} / Thumb "
      f"{len(recovered)-n_arm})")
    A("")
    A("--- 覆盖率（分子/分母 = /16466）---")
    A(f"口径O 旧(串键,含重复667) v1   : {len(o_v1)} = {pc(len(o_v1)):.2f}%")
    A(f"★ 口径O 旧(串键,含重复667) v2 : {len(o_v2)} = {pc(len(o_v2)):.2f}%")
    A(f"口径D 去重               v1   : {len(d_v1)} = {pc(len(d_v1)):.2f}%")
    A(f"   + R(广义 RTTI)              : {len(d_v2_noP)} = {pc(len(d_v2_noP)):.2f}%")
    A(f"★ 口径D 去重(硬)         v2   : {len(d_v2)} = {pc(len(d_v2)):.2f}%   (+P 指针表)")
    A(f"口径S 严格(仅Ghidra函数) v1   : {len(s_v1)} = {pc(len(s_v1)):.2f}%")
    A(f"口径S 严格(仅Ghidra函数) v2   : {len(s_v2)} = {pc(len(s_v2)):.2f}%")
    A(f"口径U 统一(含回收 {R}) v2      : {uni}/{total+R} = {100.0*uni/(total+R):.2f}%")
    A(f"含推断(口径D ∪ callgraph)     : {all_inf} = {pc(all_inf):.2f}%")
    A(f"含推断(口径O ∪ callgraph)     : {all_inf_O} = {pc(all_inf_O):.2f}%")
    A("")
    A("★ 硬证据 = R/P/F 三通道的直接引用证据；推断(调用图传播)单列，不计入硬证据。")
    A("★ v1 旧口径把 ext 的 667 条（十进制键）与 cls 的 667 条（0x 键）——**同一批地址**")
    A("  ——重复计了一次 ⇒ 去重后基线是 7272(44.16%)，不是 7939(48.21%)。")
    with open(os.path.join(P7, "p7_extend_map_v2.txt"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"wrote {P7}/p7_extend_map_v2.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
