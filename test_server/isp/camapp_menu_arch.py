#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
di-camera-app 菜单架构解包器
============================
从 test_server/appprobe/di-camera-app 抽出 CAPPGUIMenuView 全部符号 +
菜单结构体 + Edje 部件名 + 源文件路径，产出可读的菜单架构清单。

Itanium ABI demangle：只处理 _ZN...E 形式（嵌套名 + 限定 + 基本类型）。
"""
import re, sys

APP = 'test_server/appprobe/di-camera-app'
d = open(APP, 'rb').read()

# ---------- 极简 Itanium demangler（够用） ----------
BASE = {
    'v': 'void', 'b': 'bool', 'c': 'char', 'i': 'int', 'j': 'unsigned int',
    'l': 'long', 'm': 'unsigned long', 'x': 'long long', 'y': 'unsigned long long',
    'f': 'float', 'd': 'double', 'e': 'long double', 'h': 'unsigned char',
    's': 'short', 't': 'unsigned short', 'w': 'wchar_t', 'P': '*', 'R': '&',
    'K': 'const ', 'j': 'unsigned int'.split()[0],
}

def demangle(m):
    """处理 _Z <name> [<params>] 的常见形态"""
    if not m.startswith('_Z'):
        return m
    s = m[2:]
    # 跳过嵌套名 _ZN ... E
    if s.startswith('N'):
        s = s[1:]
        # 读 <len><name> 直到 E
        parts = []
        i = 0
        while i < len(s) and s[i] != 'E':
            j = i
            while j < len(s) and s[j].isdigit():
                j += 1
            if j == i:
                parts.append(s[i]); i += 1; continue
            n = int(s[i:j])
            parts.append(s[j:j+n])
            i = j + n
        rest = s[i+1:] if i < len(s) else ''
        return '::'.join(parts) + ('(' + demangle_params(rest) + ')' if rest else '')
    # 非嵌套
    i = 0
    while i < len(s) and s[i].isdigit():
        i += 1
    if i == 0:
        return m
    n = int(s[:i])
    name = s[i:i+n]
    rest = s[i+n:]
    return name + ('(' + demangle_params(rest) + ')' if rest else '')

def demangle_params(s):
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c in 'PKR':
            p = ''
            while i < len(s) and s[i] in 'PKR':
                p += {'P': '*', 'R': '&', 'K': 'const '}[s[i]]; i += 1
            out.append(p + (BASE.get(s[i], s[i]) if i < len(s) else ''))
            i += 1
        elif c.isdigit():
            j = i
            while j < len(s) and s[j].isdigit(): j += 1
            n = int(s[i:j]); out.append(s[j:j+n]); i = j + n
        else:
            out.append(BASE.get(c, c)); i += 1
    return ', '.join(x for x in out if x)

# ---------- 1. CAPPGUIMenuView 全符号 ----------
print('=' * 78)
print('【1】CAPPGUIMenuView 类 API 全表（相机系统菜单视图）')
print('=' * 78)
syms = set()
for m in re.finditer(rb'_ZN15CAPPGUIMenuView[0-9A-Za-z_]+', d):
    syms.add(m.group(0).decode())
for m in re.finditer(rb'_ZN[0-9]+CAPPGUI(Menu|HdmiMenu|MenuDepth1State|MenuDepth2State|MenuTopState|MenuState|MenuLicenseState|MenuHorizontalCalibrationState)[0-9A-Za-z_]+', d):
    syms.add(m.group(0).decode())
rows = sorted(set(demangle(x) for x in syms))
for r in rows:
    print('   ', r)
print('   共 %d 个' % len(rows))

# ---------- 2. 菜单状态类 / 源文件 ----------
print('\n' + '=' * 78)
print('【2】菜单状态机源文件（GUI/src/...）')
print('=' * 78)
srcs = set()
for m in re.finditer(rb'GUI/src/[A-Za-z0-9_./]+\.cpp', d):
    srcs.add(m.group(0).decode())
for s in sorted(srcs):
    print('   ', s)

# ---------- 3. Edje 主题 + 部件名 ----------
print('\n' + '=' * 78)
print('【3】Edje 主题文件（菜单外观来源，可用 edje_decc 解开）')
print('=' * 78)
edj = set()
for m in re.finditer(rb'/usr/apps/com\.samsung\.di-camera-app/res/edje/[A-Za-z0-9_.]+\.edj', d):
    edj.add(m.group(0).decode())
for e in sorted(edj):
    print('   ', e)

print('\n   菜单用到的 Edje 部件名（menu_/depth 前缀）:')
parts = set()
for m in re.finditer(rb'[a-z][a-z0-9_]{4,40}', d):
    t = m.group(0).decode()
    if re.match(r'(menu_|depth[0-9]_)', t):
        parts.add(t)
for p in sorted(parts):
    print('      ', p)

# ---------- 4. 菜单项结构体 menu_item ----------
print('\n' + '=' * 78)
print('【4】menu_item 结构体相关知识')
print('=' * 78)
for kw in [b'tag_MENU_INFO', b'menu_item', b'curr_menu_item', b'tag_MENU_INFO.list']:
    n = d.count(kw)
    print('   %-22s %d 处' % (kw.decode(), n))
# 抽含 menu_item 的完整 mangled（找成员访问）
for m in re.finditer(rb'_ZN1[0-9A-Za-z_]*[0-9]{1,2}menu_item[0-9A-Za-z_]*', d):
    print('   mangled:', m.group(0).decode())

# ---------- 5. 菜单刷新 / 绘制入口 ----------
print('\n' + '=' * 78)
print('【5】菜单刷新与绘制关键函数（去 mangled）')
print('=' * 78)
keys = ['setMenuList', 'getMenuItem', 'getInfoList', 'getInfoData',
        'SetDrawInfo', 'DrawMenuSmart', 'displayTop', 'displaySub',
        'DrawUpInfo', 'SetMenuListStyle', 'SetMenuTitle', 'setFocusCursor',
        'depth3_list_update', 'menu_depth1_list', 'menu_depth2_list',
        'menu_depth3_list', 'MENU_REFRESH', 'MENU_FIRST_ENTER', 'MENU_TOP_NUM',
        '_rotate_list', 'get_select_menu_string', 'UI_Get_Item_Addr']
for k in keys:
    hit = [r for r in rows if k in r]
    print('   %-22s %s' % (k, hit if hit else '（见成员变量）'))
