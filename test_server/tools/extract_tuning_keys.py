#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extract_tuning_keys.py —— 从 p7 固件字符串面重建键名全表（G5 判据件）。

★ 背景（2026-10-11）：`raw8/p7/tuning_keys.txt` 原件的生成脚本随
  `D:/download/NX-KS2-88` 一起丢失（D 盘已并入 C 盘）；原件 12916 键 / 780KB 不可复原。
  本脚本产出的是**重建件**，用于恢复 `gate_flow.py` G5-1 的判据来源，**不等同于原件**。
  重建方法（写死，可复现）：
    1. 取 p7 字符串面区 0x6f3710 .. 0x800000（capdtm 字符串区，eIQ_ID_* 表坐落于此）；
    2. 抽 `[A-Za-z_][A-Za-z0-9_]{3,}` 标识符（长度 >= 4）；
    3. 去重 + 排序，一行一键，UTF-8/LF。
  实测：184 个 `eIQ_ID_*` 全部覆盖（= gate_flow.EIQ_MIN_IDS）。

用法: python extract_tuning_keys.py <p7_full.bin|chunk-05.bin> [out=raw8/p7/tuning_keys.txt]
"""
import os
import re
import sys

REGION_START = 0x6F3710
REGION_END = 0x800000
IDENT = re.compile(rb"[A-Za-z_][A-Za-z0-9_]{3,}")


def main():
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join("raw8", "p7", "tuning_keys.txt")
    d = open(src, "rb").read()
    seg = d[REGION_START:REGION_END]
    keys = sorted({m.decode("ascii") for m in IDENT.findall(seg)})
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(keys) + "\n")
    n_eiq = sum(1 for k in keys if k.startswith("eIQ_ID_"))
    print("源文件 %s (%d B)" % (src, len(d)))
    print("区间   %#x..%#x" % (REGION_START, REGION_END))
    print("写入   %s" % out)
    print("键数   %d  (其中 eIQ_ID_* = %d, 门控要求 >=184)" % (len(keys), n_eiq))


if __name__ == "__main__":
    main()
