#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mk_recipes_json.py —— 从 nx500_recipes.txt 生成引擎要的 recipes.json

★ 背景（2026-10-08，U2 上机排障时发现）：
  引擎 `filmlab-apply.sh` 读的是 **`/mnt/mmc/filmlab/recipes.json`**，格式是【对象式】：
      { "recipes": { "<key>": { "label": ..., "R_COLOR": ... }, ... }, "presets": { ... } }
  而仓库里另一份 `nx500_filmlab.json` 是【数组式】（`"recipes": [ {"id": ...} ]`）—— **两者不兼容**。
  原本该做入库源的 `nx500_filmlab_sd.json` 已被清成 **0 字节** ⇒ 相机上 recipes.json 从未生成
  ⇒ mod_gui 菜单点按钮调 `filmlab.sh apply` 时 `jval` 取不到值 ⇒ **点了没反应**（用户实测）。

★ 缩进必须严格（引擎用 awk 按行首缩进切分）：
  * `"recipes"` 段下每个配方键 **4 空格**缩进（`jlist` 匹配 `^    "`）
  * 配方字段 **8 空格**
  * 配方对象结束的 `}` **4 空格**（`jval` 遇 `^    \\}` 退出）

用法: python test_server/filmsim/mk_recipes_json.py
产物: test_server/filmsim/recipes/recipes.json
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "recipes", "nx500_recipes.txt")
DST = os.path.join(HERE, "recipes", "recipes.json")

# recipes.txt 的列序: key|label|R|G|B|HUE|SAT|SHARP|CON
FIELDS = ["R_COLOR", "G_COLOR", "B_COLOR", "HUE", "SATURATION", "SHARPNESS", "CONTRAST"]


def main():
    rows = []
    with open(SRC, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 2 + len(FIELDS):   # key + label + 7 个数值 = 9 列
                continue
            key, label = parts[0], parts[1]
            vals = []
            for x in parts[2:2 + len(FIELDS)]:
                try:
                    vals.append(int(x))
                except ValueError:
                    vals.append(None)
            rows.append((key, label, vals))

    if not rows:
        print("★ 源配方表为空:", SRC)
        return 1

    L = []
    A = L.append
    A("{")
    A('  "recipes": {')
    for i, (key, label, vals) in enumerate(rows):
        last = (i == len(rows) - 1)
        A('    "%s": {' % key)
        A('        "label": "%s",' % label)
        for j, (fn, v) in enumerate(zip(FIELDS, vals)):
            comma = "" if j == len(FIELDS) - 1 else ","
            A('        "%s": %s%s' % (fn, v if v is not None else 0, comma))
        A('    }%s' % ("" if last else ","))
    A('  },')
    A('  "presets": {')
    A('  }')
    A('}')
    txt = "\n".join(L) + "\n"

    with open(DST, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(txt)

    # 自检：能被 python 的 json 解析（说明语法合法）
    with open(DST, encoding="utf-8") as fh:
        back = json.load(fh)
    n = len(back.get("recipes", {}))

    print("读入 %d 条配方 -> %s" % (len(rows), os.path.relpath(DST, os.path.dirname(HERE))))
    print("json 校验: recipes = %d 条" % n)
    for k, v in list(back["recipes"].items())[:3]:
        print("   %-16s %s" % (k, v.get("label")))
    print("   ...")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
