import re
from collections import Counter

txt = open(r'D:\download\NX-KS2-88\test_server\pwfilter\prefman_info_full.txt', encoding='utf-8').read()
rows = []
for m in re.finditer(r'^\s*(0x[0-9a-fA-F]+)\s+([0-9a-fA-Fx]+)\s+([A-Za-z_][A-Za-z0-9_]*)\s*$', txt, re.M):
    rows.append((int(m.group(1), 16), int(m.group(2), 16), m.group(3)))

print('总字段 %d, 偏移 0x%x..0x%x' % (len(rows), rows[0][0], rows[-1][0]))
print()

# ★ 关键: 找「独立调节域」——已知的 PW/SmartFilter 之外的色彩/曝光/曲线
KNOWN = {
    'EFFECT': '已知 PW/SmartFilter',
    'PWBRK': '已知 PW 标志位',
    'WB': '已知白平衡',
    'COLORSPACE': '已知色彩空间',
}

# 按语义分组找候选
GROUPS = {
    '伽马/曲线/色调':r'GAMMA|CURVE|TONE|GAMUT|RANGE|SCALE|LEVEL_?BIAS|OFFSET|LUT|TABLE',
    '曝光/高光/阴影':r'EXPOS|HIGHLIGHT|SHADOW|DRANGE|DYNAMIC|BRIGHT|EXPOSURE',
    '饱和/彩度/色相': r'SATURAT|CHROMA|HUE|COLOR|COLOUR|GAIN|BALANCE|DESAT',
    '降噪/锐化/细节': r'NOISE|NR_|DENOISE|SHARP|DETAIL|CLARITY|SHARPNESS|LUMA',
    '白平衡': r'WB_|AWB|KEVIN|WHITE|TINT|BRACKET|AWB',
    '滤镜/效果': r'FILTER|EFFECT|ART|STYLE|LOOK|MODE_?EF',
    '编码/输出': r'JPEG|CODEC|BIT_|RAW|SHARP|CAPT|STILL|MOVIE|PHOTO',
    '人像/检测': r'FACE|SKIN|PORTRAIT|PERSON|RECOG',
}

print('=== 语义域扫描（排除已知 EFFECT/PWBRK 块）===')
for zh, pat in GROUPS.items():
    hits = [(o, sz, n) for (o, sz, n) in rows
            if re.search(pat, n, re.I) and not n.startswith(('APPPREF_EFFECT_', 'APPPREF_PWBRK'))]
    if hits:
        print()
        print('--- %s (%d 项) ---' % (zh, len(hits)))
        for o, sz, n in hits:
            print('  0x%06x%-4s %s' % (o, sz, n))

# 前缀分布
print()
print('=== 前缀分布（找大块）===')
c = Counter()
for o, sz, n in rows:
    m = re.search(r'APPPREF_([A-Z0-9]+)_', n)
    if m:
        c[m.group(1)] += 1
for k, v in c.most_common(40):
    print('  %-16s %d' % (k, v))
