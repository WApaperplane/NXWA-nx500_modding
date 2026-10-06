#!/usr/bin/env python3
"""解析 Prefman_tool.md 里 NX500 app 区的 EFFECT(Picture Wizard) 字段，
推导出 13 种风格 x 7 参数的完整偏移表。"""
import re
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "Prefman_tool.md"
txt = open(SRC, encoding="utf-8", errors="replace").read()

rows = re.findall(r"(0x[0-9a-f]{8})\s+0004\s+APPPREF_(EFFECT_\w+)", txt, re.M)
print("EFFECT 字段总数:", len(rows))
if not rows:
    sys.exit("没匹配到，检查正则")

d = {}
for o, n in rows:
    d.setdefault(n, int(o, 16))

base = d["EFFECT_STANDARD_R_COLOR"]
PARAMS = ["R_COLOR", "G_COLOR", "B_COLOR", "HUE", "SATURATION", "SHARPNESS", "CONTRAST"]
MODES = ["STANDARD", "VIVID", "PORTRAIT", "LANDSCAPE", "FOREST", "RETRO", "COOL",
         "CALM", "CLASSIC", "CUSTOM_1", "CUSTOM_2", "CUSTOM_3", "CUSTOM_4"]

print("STANDARD_R_COLOR = 0x%05x" % base)
print("块大小 = 13 x 7 x 4 = %d 字节" % (13 * 7 * 4))
tail = base + 13 * 7 * 4 - 4
print("块尾 = 0x%05x -> %s" % (tail, [n for n, o in d.items() if o == tail]))

print()
print("| 参数 | 起始 | 范围 | 每模式步进 |")
print("|---|---|---|---|")
for i, p in enumerate(PARAMS):
    o = base + i * 13 * 4
    print("| %-11s | 0x%05x | 0x%05x-0x%05x | +52 |" % (p, o, o, o + 12 * 4))

print()
print("交叉验证（实际解析出的偏移，应与推算一致）：")
for m in MODES:
    cells = []
    for p in PARAMS:
        k = "EFFECT_%s_%s" % (m, p)
        cells.append("0x%05x" % d[k] if k in d else "??")
    print("  %-9s %s" % (m, " ".join(cells)))

print()
print("入口字段：")
for k in ["EFFECT_SMART_FILTER", "EFFECT_PW_TYPE", "EFFECT_OFF_COLOR",
          "EFFECT_OFF_SATURATION", "EFFECT_OFF_SHARPNESS",
          "EFFECT_OFF_CONTRAST", "EFFECT_OFF_HUE"]:
    if k in d:
        print("  0x%05x  APPPREF_%s" % (d[k], k))

print()
print("全局锚点：")
for k in ["SIGNATURE", "CHECKSUM"]:
    for o, n in re.findall(r"(0x[0-9a-f]{8})\s+0004\s+APPPREF_(\w+)", txt, re.M):
        if n == k:
            print("  0x%05x  APPPREF_%s" % (int(o, 16), n))
            break

# 生成可直接粘贴的 prefman 命令
print()
print("=" * 60)
print("NX500 胶片配方写入模板（把<val> 换成实机读到的值域内整数）")
print("=" * 60)
print("# 切到 CUSTOM_1")
print("prefman set 0 0x%05xl 9" % d["EFFECT_PW_TYPE"])
for i, p in enumerate(PARAMS):
    o = base + i * 13 * 4
    for m in ["CUSTOM_1"]:
        print("prefman set 0 0x%05x l <val>   # %s_%s" % (o, m, p))
print("prefman save 0&& sync")
