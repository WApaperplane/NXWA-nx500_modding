#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p7 ISP 模块描述符表提取器（魔灯的模块清单）。

从全量伪代码里提取 p7 内置的"ISP 子模块 → EP 通道"映射。
这些模块就是魔灯要挂的粒度：每个模块 = 一个 base + 若干 channel。

模块描述符的固定形态（Ghidra 伪代码）：
    iVar1 = DAT_xxxxxxxx;                        // 模块状态结构体基址
    if (*(char *)(DAT_xxxxxxxx + 0xNN) == '\0') // +NN   = 激活标志
       *(u32 *)(DAT_xxxxxxxx + 0xNN+4) = *(u32 *)(*(u8 *)(DAT_xxxxxxxx + 0xNN+1) + 0x2083xxxx);
    *(u32 *)(*(u8 *)(iVar1 + 0xNN+1) + 0x2083xxxx) = *(u32 *)(iVar1 + 0xNN+4);
                    ↑ +NN+1 = 通道索引        ↑ EP 通道寄存器阵列基址

用法:
  python modules.py            # 提取模块表
  python modules.py 0x2083     # 只看某EP 段的模块
"""
import re
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent.parent
PSEUDO = ROOT / "raw8" / "p7" / "ghidra" / "53_all_pseudocode.c"

HDR = re.compile(r"// ==== (\S+) @ (0x[0-9a-f]+) size=(\d+) ====")
RE_FLAG = re.compile(r"\(char \*\)\((DAT_[0-9a-f]+) \+ (0x[0-9a-f]+)\)")
RE_CH = re.compile(r"\(byte \*\)\((?:iVar|uVar|pcVar|iVar1|aVar)\w* \+ (0x[0-9a-f]+)\) \+ (0x208[0-9a-f]+)")
RE_CH2 = re.compile(r"\(byte \*\)\(\w+ \+ (0x[0-9a-f]+)\) \+ (0x208[0-9a-f]+)")
RE_EP = re.compile(r"\+ (0x208[0-9a-f]+)\)")


def extract():
    mods = {}
    fn = None
    for line in PSEUDO.open(encoding="utf-8", errors="replace"):
        m = HDR.match(line)
        if m:
            fn = (m.group(1), int(m.group(2), 16), int(m.group(3)))
            continue
        s = line.strip()
        a = RE_FLAG.search(s)
        if a and "==" in s:
            k = a.group(1)
            e = mods.setdefault(k, {"fn": fn, "chans": set()})
            e["flag"] = int(a.group(2), 16)
        c = RE_CH.search(s) or RE_CH2.search(s)
        if c:
            # 找当前函数对应的模块（该函数里的 flag）
            for k, e in mods.items():
                if e.get("fn") and e["fn"][0] == fn[0]:
                    off = int(c.group(1), 16)
                    if e.get("flag") is not None and off == e["flag"] + 1:
                        e["chans"].add((off, c.group(2)))
    return mods


def main():
    filt = sys.argv[1] if len(sys.argv) > 1 else None
    mods = extract()
    rows = []
    for k, e in mods.items():
        if "flag" not in e or not e["chans"]:
            continue
        eps = sorted(set(c[1] for c in e["chans"]))
        offs = sorted(set(c[0] for c in e["chans"]))
        if filt and not any(filt in x for x in eps):
            continue
        rows.append((min(offs), k, e["flag"], offs, eps, e["fn"]))
    rows.sort()
    print("=== p7 ISP 模块描述符表（%d 个模块）===" % len(rows))
    print("  %-6s %-16s %-8s %-14s %-14s %s" %
          ("ch", "模块基址标号", "flag", "通道索引偏移", "EP 阵列", "函数"))
    for _, k, flag, offs, eps, fn in rows:
        print("  0x%-4x %-16s +0x%-6x %-14s %-14s %s @ 0x%x/%dB" %
              (offs[0] if offs else 0, k, flag,
               ",".join(hex(x) for x in offs), ",".join(eps), fn[0], fn[1], fn[2]))
    print()
    # 按 EP 段汇总
    print("=== 按 EP 通道阵列汇总 ===")
    byep = defaultdict(list)
    for _, k, flag, offs, eps, fn in rows:
        for e in eps:
            byep[e].append((k, flag, offs, fn[0]))
    for ep in sorted(byep, key=lambda x: -len(byep[x])):
        print("  %s  (%d 个模块)" % (ep, len(byep[ep])))
        for k, flag, offs, f in byep[ep]:
            print("      %-16s flag=+0x%-5x ch=%s  %s" % (k, flag, offs, f))
    print()
    # 值偏移 = flag+4
    print("=== 值字段偏移（flag+4）分布 ===")
    cnt = defaultdict(int)
    for _, k, flag, offs, eps, fn in rows:
        cnt[flag + 4] += 1
    for o, c in sorted(cnt.items()):
        print("  +0x%-6x %d 个模块" % (o, c))


if __name__ == "__main__":
    main()
