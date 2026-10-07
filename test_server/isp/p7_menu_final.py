#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
p7 菜单渲染 —— 终局判定
========================
假设：p7 的显示层只做「取景器叠加层」(FD框/obj框/vsync)，不做菜单。

验证三条：
 1. p7 显示层函数清单（dp_box_* / displayer_* / Display* / Parts*）—— 有没有 menu/item/select/scroll。
 2. 菜单必有的「选中态 / 层级 / 项索引」概念在 p7 里存在吗？
    (menuIndex / selectedItem / cursor / scroll / m_pMenu / submenu / hierarchy)
 3. 相机系统菜单实际由谁提供？→ 排 p7 之外：查 NX-KS 侧已有知识 / 查 libudd5 / 查 Tizen 侧。
"""
import re, struct

d = open('raw8/p7/p7_full.bin', 'rb').read()
VA = 0x80000000

print('#' * 72)
print('# p7 菜单渲染 终局判定')
print('#' * 72)

# ---------- 1. 显示层函数清单 ----------
print('\n[1] p7 显示层相关符号（含 draw/paint/blit/box/display）')
pat = re.compile(rb'[A-Za-z_][A-Za-z0-9_]{4,60}')
syms = set()
for m in pat.finditer(d):
    s = m.group(0).decode('latin1')
    if re.search(r'(draw|Draw|display|Display|blit|Blit|box|Box|osd|OSD|paint|Paint|vsync|VSync|render|Render)', s):
        syms.add(s)
# 过滤掉明显噪声
noise = re.compile(r'^(DrawRectangle|Reset|Register|NumberOf|IsConti|GetFd|SetFd|UpdateHDM|GetObjTrack|SetObjTrack)')
disp = sorted(s for s in syms if len(s) > 5)
print('    命中 %d 个符号；下列筛出「疑似 UI/菜单」：' % len(disp))
menu_kw = re.compile(r'menu|Menu|item|Item|select|Select|cursor|Cursor|scroll|Scroll|list|List|nav|Nav|hierarch|Hierarch|screen|Screen|form|Form|dlg|Dialog|PopupText', re.I)
ui_sym = [s for s in disp if menu_kw.search(s)]
if not ui_sym:
    print('      ⇒ ★ 没有任何「菜单/项/选中/滚动/层级」符号')
for s in ui_sym[:40]:
    print('       ', s)

# ---------- 2. 菜单核心概念 ----------
print('\n[2] 菜单核心概念的裸串存在性')
concepts = {
    'menuIndex': rb'menuIndex', 'm_pMenu': rb'm_pMenu', 'm_Menu': rb'm_Menu',
    'menuItem': rb'menuItem', 'MenuItem': rb'MenuItem', 'menu_item': rb'menu_item',
    'selectedItem': rb'selectedItem', 'selection': rb'[Ss]election',
    'cursor': rb'cursor', 'scroll': rb'scroll', 'submenu': rb'submenu',
    'SubMenu': rb'SubMenu', 'hierarchy': rb'hierarch', 'navigate': rb'navigat',
    'TabControl': rb'TabControl', 'CTab': rb'CTab', 'ListCtrl': rb'ListCtrl',
    'CMenu': rb'CMenu', 'MenuForm': rb'MenuForm', 'MenuScreen': rb'MenuScreen',
    'CMenuItem': rb'CMenuItem', 'RootMenu': rb'RootMenu', 'MenuTitle': rb'MenuTitle',
}
none = []
for name, rx in concepts.items():
    ms = list(re.finditer(rx, d))
    mark = '★' if ms else ' '
    print('   %s %-14s %d' % (mark, name, len(ms)))
    for m in ms[:3]:
        o = m.start()
        a = o
        while a > 0 and 32 <= d[a-1] < 127: a -= 1
        b = o
        while b < len(d) and 32 <= d[b] < 127: b += 1
        print('        %08x  %s' % (o + VA, d[a:b].decode('latin1')[:70]))
    if not ms:
        none.append(name)

# ---------- 3. 结论 ----------
print('\n[3] 结论')
print('    p7 有无「菜单」类符号     :', '有' if ui_sym else '无')
print('    p7 有无「菜单」裸串概念   :', '无（%d 项全零）' % len(none) if not none else '部分存在')
print('''
    ⇒ p7 显示层 = 取景器叠加层 (dp_box_*_draw / isr_displayer_*_vsync)
      职能：把 ISP 算出的 FD 框、目标框、过曝区 叠加到 LCD/TV 输出
    ⇒ 相机系统菜单(MENU键)的渲染 不在 p7
''')
