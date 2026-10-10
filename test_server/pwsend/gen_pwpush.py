#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_pwpush.py — PW「一键滤镜」值编码器（PC 侧）

把 recipes.json 的 7 维人读值，编码为「SetVariableDataMCB 发送值」（4 字节低16位），
并反向验证（发送值 → 预期读回高16位 → 解码回值）。用于：

  1. 设计审计：展示 值→发送值→读回 的完整数学链（本文件可自测）
  2. 上机对照：`--write` 生成对照表，校准/一键实验时对着看（防 busybox 算术错）
  3. filmlab.sh 的 pw_direct 内联计算的参考实现

编码定义（依据 docs/current/ATTR_BUS_MCB_2026-10-09.md + PW_ID_MAP_FULL_2026-10-10.md）：
  ★ 发送值 = 完整 32 位「向导格式」（10-09 夜真机实证；裸值会被存但不被消费）：
  SCALAR (H/S/S/C)   : 发送 = (raw16<<16)|0xD80A;   raw16 = 16×(值-10)+15（有符号16位）
  R/G/B 编码          : 默认 "color" = (gain16<<16)|0x00FF，gain16 = ceil(值×2032/100)
                        （= 官方档位应用路径对 R/G/B 的编码）；rgb_enc="scalar" 可切回
                        0xD80A 同式（回归/备选用）。
  读回 = 发送值（逐位精确，0x005FD80A→0x005FD80A 实测）。

★ 与 scripts/filmlab.sh 的 pw_raw_code/pw_gain_code 逐值一致（对拍见 selftest）。
★ id 表（10-10 上机定案）：SAT/SHARP/CON = 0x110/0x111/0x112（已实测，三维回归通过）；
  R/G/B/HUE 内部 id = 0x130/0x131/0x132/0x133 —— ★ **无外部 MCB 通路**
  （probe3 负结论：rc=0 而 varlist 无变化；静态：外部归一化器只认 0x100-0x12e）
  ⇒ 保留 id 常量仅供 G4 后备用，默认不发送。

用法:
  python gen_pwpush.py                      # 全部配方 → 编码总表
  python gen_pwpush.py --recipe portra800   # 单配方详表
  python gen_pwpush.py --write out_dir      # 写 每配方.seq 文件（pwsend seq 参数形式）
  python gen_pwpush.py --selftest           # 往返自测
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
DEFAULT_RECIPES = os.path.join(REPO, "scripts", "filmlab", "recipes.json")

# ---- id 表（10-10 上机定案：PW_ID_MAP_FULL_2026-10-10.md §6）----
#   S/P/C = 已实测外部 id（经 p7 归一化 → 内部 SAT/SHARP/CON）。
#   R/G/B/HUE = 内部 id（0x130-0x133），★ 无外部 MCB 通路（probe3 负结论）⇒ 默认不发送。
IDS = {
    "R_COLOR":    0x130,   # 内部 id，无外部通路（G4 后可用）
    "G_COLOR":    0x131,   # 同上
    "B_COLOR":    0x132,   # 同上
    "HUE":        0x133,   # 同上
    "SATURATION": 0x110,   # 已实测（PWSATURATION）
    "SHARPNESS":  0x111,   # 已实测（PWSHARPNESS）
    "CONTRAST":   0x112,   # 已实测（PWCONTRAST）
}

ORDER = ["R_COLOR", "G_COLOR", "B_COLOR", "HUE", "SATURATION", "SHARPNESS", "CONTRAST"]
COLOR_KEYS = ("R_COLOR", "G_COLOR", "B_COLOR")
SCALAR_KEYS = ("HUE", "SATURATION", "SHARPNESS", "CONTRAST")


# ---------------------------------------------------------------- 编码

def v2gain16(v):
    """COLOR: 值 → gain16（发送值/读回高16位）。

    用【向上取整】而非四舍五入：让读回解码（整数截断 `g*100/2032`）严格回到配方值。
    依据：实测 app 链路是"截断+截断"⇒ 读回系统性 -1（109→108 等，仍在 check 容差内）；
    我们选 ceil 版让 check 判据严格对齐（渲染差异 ≤1/2032，可忽略）。
    """
    return (v * 2032 + 99) // 100


def v2raw16(v):
    """SCALAR: 值 → raw16（有符号；发送时取低 16 位）。"""
    return 16 * (v - 10) + 15


def gain16_2v(g):
    """COLOR 解码（与 filmlab.sh check 同式）：gain16 → 值（整数近似）。"""
    return g * 100 // 2032


def raw16_2v(r):
    """SCALAR 解码：raw16（可负，补码输入用 &0xFFFF 的整数）→ 值。"""
    if r >= 0x8000:
        r -= 0x10000
    return 10 + (r - 15) // 16    # Python 地板除，负数向下——与 ash 的整数除略有差
                                   # （ash 截断向零）；此函数仅为人读对照，判据在相机端


def encode(key, v, rgb_enc="color"):
    """返回 (完整发送值(32 位), 说明)。

    完整格式 = (数据16 << 16) | 格式标记：SCALAR 0xD80A / COLOR 0x00FF。
    ★ rgb_enc：R/G/B 默认 "color"（= 官方档位应用路径编码，(gain<<16)|0x00FF）；
      "scalar" 可切回 0xD80A 同式（回归/备选）。
    """
    if key in COLOR_KEYS and rgb_enc == "color":
        g = v2gain16(v)
        return ((g & 0xFFFF) << 16) | 0x00FF, "gain16=%d" % g
    r = v2raw16(v)
    return ((r & 0xFFFF) << 16) | 0xD80A, "raw16=%d%s" % (r, "（负→补码）" if r < 0 else "")


def decode_expected(key, sv, rgb_enc="color"):
    """完整发送值 sv → 「预期读回高16位 → 解码值」——用于上机对照。"""
    hi = (sv >> 16) & 0xFFFF
    if key in COLOR_KEYS and rgb_enc == "color":
        return gain16_2v(hi)
    return raw16_2v(hi)


# ---------------------------------------------------------------- 主逻辑

def load_recipes(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    return d.get("recipes", {})


def table_one(name, rec, detail=True, rgb_enc="color"):
    lines = []
    label = rec.get("label", name)
    lines.append("── %s (%s)" % (name, label))
    for k in ORDER:
        v = rec.get(k)
        if v is None:
            lines.append("   %-11s = ?" % k)
            continue
        sv, note = encode(k, v, rgb_enc)
        back = decode_expected(k, sv, rgb_enc)
        idt = IDS.get(k)
        idtxt = ("0x%03x" % idt) if idt else "  ?  "
        lines.append("   %-11s 值=%-4s id=%s → 发送 0x%08X [%s] → 预期读回解码 ≈ %s"
                     % (k, v, idtxt, sv, note, back))
    return "\n".join(lines)


def write_seq(outdir, name, rec, rgb_enc="color"):
    """写 pwsend seq 参数文件（每行 'id value'；id 未定项注释掉）。"""
    os.makedirs(outdir, exist_ok=True)
    p = os.path.join(outdir, "%s.seq" % name)
    with open(p, "w", encoding="utf-8") as f:
        f.write("# %s (%s) — 发送值表；id 未校准项已注释，校准后启用\n"
                % (name, rec.get("label", "")))
        for k in ORDER:
            v = rec.get(k)
            if v is None:
                continue
            sv, note = encode(k, v, rgb_enc)
            idt = IDS.get(k)
            if idt:
                f.write("0x%03x 0x%08X   # %s 值=%s %s\n" % (idt, sv, k, v, note))
            else:
                f.write("# 0x??? 0x%08X   # %s 值=%s %s（id 待校准）\n"
                        % (sv, k, v, note))
    return p


def selftest():
    ok = True
    # 往返：COLOR —— ceil 版应精确往返（解码截断回原值）
    for v in (0, 1, 10, 88, 100, 101, 106, 109, 111, 125, 150, 255):
        g = v2gain16(v)
        b = gain16_2v(g)
        if b != v:
            ok = False
            print("FAIL color v=%s g=%d back=%d" % (v, g, b))
    # 往返：SCALAR（精确往返应成立）
    for v in range(0, 21):
        r = v2raw16(v)
        back = raw16_2v(r & 0xFFFF)
        if back != v:
            ok = False
            print("FAIL scalar v=%s raw=%d back=%s" % (v, r, back))
    # 已知实测对照（PW_PARAM_CHANNEL 实测：SAT=9 → 0xFFFF；PWHUE=0x003F ↔ 值13）
    if v2raw16(9) & 0xFFFF != 0xFFFF:
        ok = False
        print("FAIL SAT=9 应得 0xFFFF")
    if v2raw16(13) != 0x3F:
        ok = False
        print("FAIL HUE=13 应得 0x3F (63)")
    # 实测对照 2：R=88.2 读回 0x0700 (gain16=1792)；ceil(88×20.32)=1789（±3，
    # 属"实测是连续量 88.19 的四舍五入"而非整数 88——不影响判定）
    # ---- 完整 32 位格式断言 + bash 公式对拍（10-09 夜实证；对拍源 = filmlab.sh 217/218 行）----
    # 真机锚点：SAT=15 → 0x005FD80A（发送=读回逐位精确）
    sv, _ = encode("SATURATION", 15)
    if sv != 0x005FD80A:
        ok = False
        print("FAIL SAT=15 完整值应为 0x005FD80A，得 0x%08X" % sv)
    # bash 对拍 · SCALAR：U=$(( (v*16 - 145) & 0xFFFF )); 值 = "0x%04x%04x" U 0xD80A
    for v in range(0, 21):
        u = (v * 16 - 145) & 0xFFFF
        bash_sv = (u << 16) | 0xD80A
        py_sv, _ = encode("SATURATION", v)
        if py_sv != bash_sv:
            ok = False
            print("FAIL bash对拍(scalar) v=%s bash=0x%08X py=0x%08X" % (v, bash_sv, py_sv))
    # ★ 10-10 上机定案：R/G/B/HUE 无外部 MCB 通路（probe3 负结论）。
    #   默认编码按官方档位应用路径 = COLOR（(gain<<16)|0x00FF）；SCALAR 仍可显式选择（回归用）。
    # bash 对拍 · COLOR（默认）：G=$(( (v*2032 + 99)/100 )); 值 = "0x%04x%04x" G 0x00FF
    for v in (0, 1, 50, 88, 100, 109, 150, 255):
        g = (v * 2032 + 99) // 100
        bash_sv = ((g & 0xFFFF) << 16) | 0x00FF
        py_sv, _ = encode("R_COLOR", v)
        if py_sv != bash_sv:
            ok = False
            print("FAIL bash对拍(color/默认) v=%s bash=0x%08X py=0x%08X" % (v, bash_sv, py_sv))
    # SCALAR 显式（回归用）—— 与 pw_raw_code 同式
    for v in (0, 9, 10, 15, 20, 100, 106, 255):
        r = v2raw16(v)
        want = ((r & 0xFFFF) << 16) | 0xD80A
        py_sv, _ = encode("R_COLOR", v, rgb_enc="scalar")
        if py_sv != want:
            ok = False
            print("FAIL rgb-scalar(显式) v=%s 期望 0x%08X 得 0x%08X" % (v, want, py_sv))
        py_sv2, _ = encode("SATURATION", v)
        if py_sv != py_sv2:
            ok = False
            print("FAIL rgb-scalar 与 scalar 公式不一致 v=%s" % v)
    print("selftest:", "OK" if ok else "FAIL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipes", default=DEFAULT_RECIPES)
    ap.add_argument("--recipe", help="只显示单个配方")
    ap.add_argument("--write", help="输出目录（生成每配方 .seq）")
    ap.add_argument("--rgb-enc", default="color", choices=("scalar", "color"),
                    help="R/G/B 编码模式（默认 color = 官方档位应用路径；scalar=0xD80A 同式）")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return selftest()

    recs = load_recipes(a.recipes)
    if not recs:
        print("★ 读不到配方：", a.recipes)
        return 1

    if a.recipe:
        rec = recs.get(a.recipe)
        if not rec:
            print("★ 配方不存在：%s（可用：%s）" % (a.recipe, ", ".join(sorted(recs))))
            return 1
        print(table_one(a.recipe, rec, rgb_enc=a.rgb_enc))
        return 0

    for name in sorted(recs):
        print(table_one(name, recs[name], rgb_enc=a.rgb_enc))
        print()
    if a.write:
        for name in sorted(recs):
            p = write_seq(a.write, name, recs[name], rgb_enc=a.rgb_enc)
        print("已写 %d 个 .seq → %s" % (len(recs), a.write))
    return 0


if __name__ == "__main__":
    sys.exit(main())
