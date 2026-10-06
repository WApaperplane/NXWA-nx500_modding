#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p7 ISP 参数 schema 提取器（抓主干 v3）。

从 veneer 链的**末端实现**里抽"字段偏移 + 位域"，
这些偏移就是魔灯配方 JSON 的物理 schema。

原理：p7 的参数访问器 veneer 末端实现形如
    adds r0, #0x68      ; 取结构体 +0x68 字段
    movs r0, #0xb       ; 宽度/枚举常量
    b<common_epilogue> ; 统一出口
⇒ 每个 veneer 对应一个 (字段偏移, 宽度) 组合。

用法:
  python schema.py 0x3f3f64 0x200# 解一段 veneer 表=> 字段偏移表
  python schema.py --scan           # 全镜像扫 veneer 表, 汇总字段偏移
"""
import sys
import re
import capstone
from pathlib import Path
from collections import defaultdict, Counter

ROOT = Path(__file__).resolve().parent.parent.parent
BIN = ROOT / "raw8" / "p7" / "p7_full.bin"

THUMB = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
THUMB.detail = False
B = None
NOP32 = 0x2FE1


def load():
    global B
    if B is None:
        B = BIN.read_bytes()
    return B


def ins2(a):
    o = list(THUMB.disasm(load()[a:a + 2], a))
    return o[0] if o else None


def veneer_at(a):
    i1, i2 = ins2(a), ins2(a + 2)
    if not i1 or not i2:
        return None
    if i1.mnemonic != "movs" or i2.mnemonic != "b":
        return None
    try:
        d, s = [x.strip() for x in i1.op_str.split(",")]
        t = int(i2.op_str.replace("#", ""), 0)
    except Exception:
        return None
    return d, s, t


def follow(start, maxhop=8):
    """追 veneer 链，返回 [(addr, is_veneer, ins_text), ...]"""
    out = []
    cur = start
    seen = set()
    for _ in range(maxhop):
        if cur in seen:
            break
        seen.add(cur)
        v = veneer_at(cur)
        i = ins2(cur)
        if i:
            out.append((cur, v is not None, i.mnemonic + " " + i.op_str))
        if v is None:
            break
        cur = v[2]
    return out


def fields_at(addr, span=0x40):
    """在 addr 起的实现里抽: 结构体偏移 / 立即数 / 位掩码 / 内存槽位。"""
    load()
    end = min(len(B), addr + span)
    offs, imms, masks, mems = [], [], [], []
    for i in THUMB.disasm(B[addr:end], addr):
        t = i.mnemonic + " " + i.op_str
        m = re.search(r"\badds?\s+r\d+,\s*#(0x[0-9a-f]+|\d+)", t)
        if m:
            v = int(m.group(1), 0)
            if 4 <= v <= 0x2000:
                offs.append(v)
        m = re.search(r"\bmovs\s+r\d+,\s*#(0x[0-9a-f]+|\d+)$", t)
        if m:
            imms.append(int(m.group(1), 0))
        m = re.search(r"&\s*(0x[0-9a-f]+)", t)
        if m:
            masks.append(int(m.group(1), 0))
        m = re.search(r"\[\s*(r\d+|sp)\s*,\s*#(0x[0-9a-f]+|\d+)\s*\]", t)
        if m:
            mems.append(int(m.group(2), 0))
    return offs, imms, masks, mems


def cmd_table(start, size):
    print("=== veneer 表 @ 0x%x  →  参数 schema ===" % start)
    a = start
    rows = []
    while a < start + size:
        if int.from_bytes(load()[a + 2:a + 4], "little") == NOP32:
            a += 4
            continue
        v = veneer_at(a)
        if v:
            d, s, t = v
            hops = follow(a)
            end = hops[-1][0] if hops else t
            offs, imms, masks, mems = fields_at(end, 0x50)
            rows.append((a, "%s,%s" % (d, s), t, end, len(hops), offs, imms, masks, mems))
        a += 4
    print("  %-9s %-8s %-9s %-9s %-5s %-22s %-14s %-16s" %
          ("veneer", "mov", "hop1", "impl", "hop", "结构体偏移", "立即数", "位掩码"))
    for r in rows:
        print("  0x%-7x %-8s 0x%-7x 0x%-7x %-5d %-22s %-14s %-16s" %
              (r[0], r[1], r[2], r[3], r[4],
               str([hex(x) for x in r[5][:6]]), str(r[6][:4]), str([hex(x) for x in r[7][:4]])))
    # 汇总
    allo = Counter()
    for r in rows:
        for o in r[5]:
            allo[o] += 1
    print()
    print("  === 字段偏移汇总（出现次数）===")
    for o, c in sorted(allo.items()):
        print("    +0x%-6x %d 次" % (o, c))
    return rows


def cmd_scan(minrun=4):
    load()
    n = len(load())
    print("=== 全镜像扫 veneer 表 (>=%d 连续) ===" % minrun)
    runs = []
    cur = []
    a = 0
    while a + 4 <= n:
        v = veneer_at(a)
        if v:
            cur.append(a)
            a += 4
        else:
            if len(cur) >= minrun:
                runs.append(cur)
            cur = []
            a += 4
    if len(cur) >= minrun:
        runs.append(cur)
    print("veneer 段数 = %d" % len(runs))
    # 段内的 veneer 收集其末端实现的结构体偏移
    allo = Counter()
    segs = []
    for run in runs:
        seg = []
        for va in run:
            hops = follow(va)
            if not hops:
                continue
            end = hops[-1][0]
            offs, imms, masks, mems = fields_at(end, 0x50)
            if offs:
                seg.append((va, end, offs))
                for o in offs:
                    allo[o] += 1
        if seg:
            segs.append((run[0], run[-1], seg))
    print("含字段偏移的段 = %d" % len(segs))
    print()
    print("--- 段清单（>=3 个字段）---")
    for s, e, seg in segs:
        if len(seg) >= 3:
            allf = sorted(set(x for _, _, os_ in seg for x in os_))
            print("  0x%x-0x%x  %d veneers, 字段: %s" %
                  (s, e, len(seg), [hex(x) for x in allf[:10]]))
    print()
    print("--- 全镜像字段偏移 top 30 ---")
    for o, c in allo.most_common(30):
        print("    +0x%-6x %d 次" % (o, c))


if __name__ == "__main__":
    if not BIN.exists():
        print("缺", BIN)
        sys.exit(1)
    if sys.argv[1] == "--scan":
        cmd_scan()
    else:
        cmd_table(int(sys.argv[1], 0), int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x200)
