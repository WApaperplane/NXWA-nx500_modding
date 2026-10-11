#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""add_batch2_recipes.py —— FilmLab 配方库第二批（+27 条）幂等追加器

背景（2026-10-11）：
  首批 68 条配方随 release `v2.88.0-nxwa.1` 交付。本次按用户诉求
  「进一步增加滤镜配方」，聚焦 **经典彩色负片全谱 + 反转片 E-6 / 电影卷**，
  再补 27 条（68 → 95，菜单自动分 6 页）。

设计纪律：
  · 幂等：已存在的 key 一律跳过（重复跑不产生副本、不重排）
  · 渲染/写盘全部走 flab.py 的 render()（← 与相机端 filmlab.sh 的 awk 严格对齐）
  · 追加顺序固定：先彩色负片、后反转片/电影卷（菜单里成组，便于翻页找）
  · 取值域沿用既有配方：R/G/B 88–125（100 中性）、HUE 9–15（10 中性）、
    SAT 0–16（0=纯黑白）、SHARP 7–13、CON 3–16

用法:
  python test_server/filmlab/add_batch2_recipes.py            # 干跑（只报差异）
  python test_server/filmlab/add_batch2_recipes.py --apply    # 落盘
  python test_server/filmlab/add_batch2_recipes.py --apply --sync-filmsim
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import flab  # noqa: E402

# (key, label, R, G, B, HUE, SAT, SHARP, CON)
NEGATIVES = [
    ("portra400nc",        "Portra 400NC",    104, 100,  95, 10,  8,  9,  7),
    ("portra400vc",        "Portra 400VC",    107, 100,  92, 11, 12,  9,  9),
    ("portra800_push",     "Portra 800 推1600", 110, 102, 95, 11, 10,  8,  9),
    ("kodak_max400",       "Kodak Max 400",   110, 101,  90, 12, 12,  8, 10),
    ("fuji_xtra400",       "Fuji X-TRA 400",   99, 102, 104, 12, 11,  9,  9),
    ("fuji_venus800",      "Fuji Venus 800",  101, 100, 103, 12, 12,  8, 10),
    ("fuji_superia1600",   "Superia 1600",    100, 100, 105, 13, 12,  8, 11),
    ("fuji_natura1600",    "Natura 1600",     103, 101, 104, 12, 11,  8, 10),
    ("agfa_vista100",      "Agfa Vista 100",  104, 100,  99, 11, 12, 10, 10),
    ("ferrania_solaris400", "Solaris 400",    103, 100,  99, 12, 13,  9, 11),
    ("lomography_color100", "Lomo Color 100", 105, 101,  97, 13, 13,  9, 11),
    ("konica_centuria400", "Centuria 400",    102, 102,  98, 12, 12,  9, 10),
    ("kodak_colorplus400", "ColorPlus 400",   108, 101,  89, 12, 12,  8, 10),
    ("rollei_cn200",       "Rollei CN 200",   101, 101, 101, 11, 11, 10, 10),
]

SLIDES_CINE = [
    ("kodak_ektachrome64", "Ektachrome 64",   100, 102, 104, 11, 12, 11, 12),
    ("kodachrome25",       "Kodachrome 25",   108,  99,  91, 12, 13, 13, 14),
    ("kodachrome200",      "Kodachrome 200",  107,  99,  91, 12, 12, 11, 13),
    ("fuji_sensia200",     "Sensia 200",      101, 102, 105, 11, 11, 10, 10),
    ("fuji_sensia400",     "Sensia 400",      100, 102, 106, 11, 12, 10, 11),
    ("fuji_fortia",        "Fortia SP",       102, 110, 109, 10, 15, 12, 14),
    ("agfachrome_ct100",   "Agfachrome CT100", 102, 100, 101, 11, 12, 11, 12),
    ("agfachrome_rsx100",  "Agfachrome RSX100", 103,  99,  99, 12, 13, 12, 13),
    ("ektachrome100d",     "Ektachrome 100D",  99, 102, 106, 11, 12, 10, 11),
    ("vision3_50d",        "Vision3 50D",     103, 101, 100, 11, 11, 10, 10),
    ("vision3_200t",       "Vision3 200T",     96, 102, 111, 13, 12,  8, 10),
    ("fuji_eterna500",     "Eterna 500T",      97, 101, 108, 12,  9,  7,  8),
    ("cinestill_400d",     "CineStill 400D",  104, 101,  99, 11, 12,  9, 10),
]

BATCH = NEGATIVES + SLIDES_CINE


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正落盘（否则干跑）")
    ap.add_argument("--sync-filmsim", action="store_true",
                    help="同时同步一份到 test_server/filmsim/recipes/recipes.json")
    args = ap.parse_args()

    d = flab.load()
    recipes = d.setdefault("recipes", {})
    before = len(recipes)

    added, skipped = [], []
    for row in BATCH:
        key, label, r, g, b, hue, sat, sharp, con = row
        if key in recipes:
            skipped.append(key)
            continue
        recipes[key] = {
            "label": label,
            "R_COLOR": r, "G_COLOR": g, "B_COLOR": b,
            "HUE": hue, "SATURATION": sat,
            "SHARPNESS": sharp, "CONTRAST": con,
        }
        added.append((key, label))

    print("批次：负片 %d + 反转/电影 %d = %d 条" % (len(NEGATIVES), len(SLIDES_CINE), len(BATCH)))
    print("新增 %d 条；跳过（已存在）%d 条" % (len(added), len(skipped)))
    for k, lab in added:
        print("  + %-20s %s" % (k, lab))
    if skipped:
        print("  跳过：%s" % ", ".join(skipped))
    print("配方数 %d -> %d（菜单 %d 页）"
          % (before, len(recipes),
             max(1, (len(recipes) + flab.PERPAGE - 1) // flab.PERPAGE)))

    text = flab.render(d)
    fails, warns = flab.lint(d, text)
    for x in fails:
        print("  FAIL:", x)
    print("lint: %s（%d FAIL / %d warn）"
          % ("PASS" if not fails else "FAIL", len(fails), len(warns)))
    if fails:
        print("★ lint 未过 —— 不落盘")
        return 1

    if not args.apply:
        print("（干跑，未写盘。加 --apply 落盘）")
        return 0

    if not added:
        print("无新增，跳过写盘。")
        return 0

    flab.save(d)
    print("已写 %s  md5=%s" % (flab.RECIPES, flab.md5f(flab.RECIPES)))

    if args.sync_filmsim:
        with open(flab.FILMSIM_COPY, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("已同步 -> %s" % os.path.relpath(flab.FILMSIM_COPY, flab.REPO))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
