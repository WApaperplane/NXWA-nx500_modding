#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
p7 相机系统菜单渲染 —— 存在性判定工具
=====================================
问题：p7 固件里到底有没有「相机系统菜单(MENU键)」的渲染/构建代码？

判据链：
  A. 源码树里有没有 UI/Menu/GUI/OSD/Draw/Font 源文件？
  B. p7 里有没有 UI 工具包原语（字体/绘制/对话框/控件类）？
  C. 所有 UI 疑似标识符字符串，有多少个真的被代码引用（xref>0）？

任何一条成立 ⇒ 菜单在本固件里。三条全不成立 ⇒ 菜单不在 p7。
"""
import re, struct, sys, os

BIN = 'raw8/p7/p7_full.bin'
VA = 0x80000000
d = open(BIN, 'rb').read()

print('=' * 72)
print('p7 固件 %s  (%d B / 0x%X)' % (BIN, len(d), len(d)))
print('=' * 72)

# ---------- A. 源码树 ----------
print('\n[A] 源码树 .cpp 路径里的 UI 关键词')
tree = open('raw8/p7/source_tree.txt', 'r', encoding='latin1').read()
paths = re.findall(r'0x[0-9a-f]+  (\S+\.cpp)', tree)
print('    源文件总数: %d' % len(paths))
ui_pat = re.compile(r'menu|gui|osd|draw|font|dialog|widget|render|screen|form', re.I)
hits = [p for p in paths if ui_pat.search(p)]
print('    命中 UI 关键词: %d' % len(hits))
for p in hits:
    print('       ', p)
if not hits:
    print('    ⇒ ★ 零个 UI/菜单源文件')

# ---------- B. UI 原语 ----------
print('\n[B] UI 工具包原语（全二进制裸串搜索）')
prims = ['Font', 'DrawStr', 'DrawText', 'DrawChar', 'RenderText', 'Dialog',
         'Popup', 'Widget', 'Canvas', 'Bitmap', 'Blit', 'MenuItem',
         'MenuBar', 'SubMenu', 'UIObject', 'ScreenMgr', 'Viewport',
         'Sprite', 'Icon', 'Layer', 'Compositor']
def all_strs():
    for m in re.finditer(rb'[ -~]{4,80}', d):
        yield m.start(), m.group(0).decode('latin1')
strs = list(all_strs())
def count(kw):
    return [(o, s) for o, s in strs if kw.lower() in s.lower()]
for k in prims:
    c = count(k)
    mark = '★' if c else ' '
    print('   %s %-12s %d' % (mark, k, len(c)))
    for o, s in c[:4]:
        print('        %08x  %s' % (o + VA, s))

# ---------- C. 字符串 xref 计数 ----------
print('\n[C] UI 疑似标识符的 xref 计数（字面量 + pc-rel ldr）')
# 收集候选：含 UI/Menu/OSD/GUI/Disp/Font 的字符串
cands = [(o, s) for o, s in strs
         if re.search(r'UI|Menu|OSD|GUI|Font|Draw', s)]
# 去重
seen = set(); uniq = []
for o, s in cands:
    if s not in seen:
        seen.add(s); uniq.append((o, s))
print('    候选字符串: %d 条' % len(uniq))

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_LITTLE_ENDIAN
md = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)
md.detail = True
# 预扫所有 pc-rel ldr 目标
pcrel = {}
pm = re.compile(r'#(-?0x[0-9a-f]+)')
for j in range(0, len(d) - 4, 4):
    ins = next(md.disasm(d[j:j + 4], VA + j), None)
    if ins and ins.mnemonic == 'ldr' and 'pc' in ins.op_str:
        mm = pm.search(ins.op_str)
        if mm:
            t = ins.address + 8 + int(mm.group(1), 16)
            pcrel[t] = pcrel.get(t, 0) + 1
print('    pc-rel 字面量池: %d 个目标' % len(pcrel))

referenced = 0
for o, s in uniq:
    va = o + VA
    lit = struct.pack('<I', va)
    lit_hits = 0
    i = 0
    while True:
        j = d.find(lit, i)
        if j < 0: break
        lit_hits += 1; i = j + 1
    n = lit_hits + pcrel.get(va, 0)
    if n > 0:
        referenced += 1
        print('    [%2d] %-42s %08x' % (n, s[:42], va))
print('    → 被引用的 UI 候选: %d / %d' % (referenced, len(uniq)))
if referenced == 0:
    print('    ⇒ ★ 全部为孤儿字符串，零代码引用')
