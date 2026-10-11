#!/usr/bin/env python3
"""di-camera-app 字符串提取：ASCII + UTF-16LE，带文件偏移。
输出到 E:/tmp/dicam_strings/all.txt（offset<TAB>encoding<TAB>string）。
后续用 Grep 工具过滤分析。"""
import re
import sys
from pathlib import Path

BIN = Path(r"E:/NXWA/fw/v1.12/extract/di-camera-app/com.samsung.di-camera-app/bin/di-camera-app")
OUT = Path(r"E:/tmp/dicam_strings/all.txt")

data = BIN.read_bytes()
rows = []

# ASCII strings
for m in re.finditer(rb"[\x20-\x7e]{4,}", data):
    rows.append((m.start(), "a", m.group().decode("ascii")))

# UTF-16LE strings
for m in re.finditer(rb"(?:[\x20-\x7e]\x00){4,}", data):
    rows.append((m.start(), "u", m.group().decode("utf-16-le")))

rows.sort(key=lambda r: r[0])
with OUT.open("w", encoding="utf-8") as f:
    for off, enc, s in rows:
        f.write("%08x\t%s\t%s\n" % (off, enc, s))

print("total strings:", len(rows))
print("ascii:", sum(1 for r in rows if r[1] == "a"))
print("utf16:", sum(1 for r in rows if r[1] == "u"))
