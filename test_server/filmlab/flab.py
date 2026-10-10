#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""flab.py — FilmLab 配方 / 设置数据管理 + 一条龙部署（PC 侧）

= 便捷增删配方链路 =
  本地操作（add/edit/rm） → lint（引擎兼容性） → deploy（推 → 生效 → 菜单重建 → 回收）

= 设置数据导入路径 =
  `conf` 子命令管理 filmlab.conf（PWID 校准结果 / FILMLAB_PW 开关 / 其他设置）；
  deploy --conf 推送到相机 /mnt/mmc/filmlab/filmlab.conf，由 filmlab.sh 启动时 source。
  ⇒ 校准结果 = 数据文件，不再"改脚本重推"。

用法:
  python flab.py list
  python flab.py add <key> --label "Name" --r 106 --g 100 --b 93 --hue 11 --sat 9 --sharp 9 --con 8
  python flab.py edit <key> [--sat 10] [--label "..."] ...
  python flab.py rm <key>
  python flab.py lint
  python flab.py conf --set PWID_G=0x10f --set FILMLAB_PW=1 ...   # 累积编辑
  python flab.py conf --show
  python flab.py conf --unset PWID_G
  python flab.py deploy [--host H] [--conf] [--sync-filmsim] [--idx N]

引擎解析纪律（本工具保证生成物 100% 兼容 filmlab.sh 的 awk）：
  * `"recipes"` 段下配方键 **4 空格**缩进；配方内部字段 **8 空格**；配方结束 `}` **4 空格**
  * label 不得含 `"` 或 `|`（会破坏 awk/UI 解析）；字段顺序固定语义序
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "test_server", "sysarch"))
from minitel import MiniTel  # noqa: E402

RECIPES = os.path.join(REPO, "scripts", "filmlab", "recipes.json")
CONF_LOCAL = os.path.join(HERE, "filmlab.conf")
FILMSIM_COPY = os.path.join(REPO, "test_server", "filmsim", "recipes", "recipes.json")
HOST_DEFAULT = "192.168.0.105"

FIELDS = ["label", "R_COLOR", "G_COLOR", "B_COLOR", "HUE",
          "SATURATION", "SHARPNESS", "CONTRAST"]
NUM_FIELDS = FIELDS[1:]

# 值域（宽松哨兵；超出报 warn，不阻断）
COLOR_RANGE = (40, 220)
SCALAR_RANGE = (-10, 30)
# 菜单分页：每页配方数（mkgui 同步此值；18 + 上/下页 + 返回 + 取消 = 22 = mod_gui 上限）
PERPAGE = 18


# ---------------------------------------------------------------- 读写

def load():
    with open(RECIPES, encoding="utf-8") as f:
        d = json.load(f)
    return d


def render(d):
    """严格缩进渲染（引擎 awk 兼容；勿用 json.dumps(indent=4)）。"""
    L = ["{", '  "recipes": {']
    keys = list(d.get("recipes", {}).keys())
    for i, k in enumerate(keys):
        r = d["recipes"][k]
        L.append('    "%s": {' % k)
        fields = [(f, r.get(f)) for f in FIELDS if f in r]
        # 保留可能存在的额外字段（排在标准字段后）
        extra = [(f, v) for f, v in r.items() if f not in FIELDS]
        fields += extra
        for j, (f, v) in enumerate(fields):
            comma = "" if j == len(fields) - 1 else ","
            vv = json.dumps(v, ensure_ascii=False) if isinstance(v, str) else v
            L.append('        "%s": %s%s' % (f, vv, comma))
        L.append("    }%s" % ("," if i < len(keys) - 1 else ""))
    L.append("  },")
    L.append('  "presets": {')
    L.append("  }")
    L.append("}")
    return "\n".join(L) + "\n"


def save(d):
    data = render(d)
    with open(RECIPES, "w", encoding="utf-8", newline="\n") as f:
        f.write(data)
    return data


def md5f(p):
    h = hashlib.md5()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ---------------------------------------------------------------- lint（模拟引擎解析）

def awk_sim_jlist(text):
    """模拟 filmlab.sh jlist：recipes 段内 4 空格缩进的配方键。"""
    keys, inr = [], False
    for line in text.split("\n"):
        if '"recipes"' in line:
            inr = True
            continue
        if '"presets"' in line:
            inr = False
            continue
        if inr:
            m = line.startswith('    "') and line.rstrip().endswith("{")
            if m:
                k = line.strip().strip('": {')
                keys.append(k)
    return keys


def awk_sim_jval(text, key, field):
    """模拟 filmlab.sh jval：找到 `"key": ` 行后，向下取 `"field":` 的数字。"""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if ('"%s": ' % key) in line:
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("    }"):
                    break
                if ('"%s":' % field) in lines[j]:
                    s = lines[j].split('"%s":' % field, 1)[1]
                    if field == "label":
                        s = s.strip().strip(",").strip().strip('"')
                        return s
                    import re
                    m = re.search(r"-?\d+", s)
                    return m.group(0) if m else None
    return None


def lint(d, text):
    fails, warns = [], []
    keys = awk_sim_jlist(text)
    recipes = d.get("recipes", {})
    if len(keys) != len(recipes):
        fails.append("jlist 模拟读到 %d 个键，JSON 有 %d 个（缩进不符）"
                     % (len(keys), len(recipes)))
    for k in keys:
        for f in FIELDS:
            v = awk_sim_jval(text, k, f)
            if v is None:
                fails.append("%s: 字段 %s 引擎读不到" % (k, f))
        lab = awk_sim_jval(text, k, "label")
        if lab and ('"' in lab or "|" in lab):
            fails.append("%s: label 含引号或竖线（破坏解析）" % k)
        r = recipes.get(k, {})
        for f in NUM_FIELDS:
            v = r.get(f)
            if not isinstance(v, int):
                fails.append("%s.%s = %r 不是整数" % (k, f, v))
                continue
            lo, hi = COLOR_RANGE if f.endswith("COLOR") else SCALAR_RANGE
            if not (lo <= v <= hi):
                warns.append("%s.%s = %d 超出建议域 [%d,%d]" % (k, f, v, lo, hi))
    if len(recipes) > PERPAGE:
        pages = (len(recipes) + PERPAGE - 1) // PERPAGE
        warns.append("配方数 %d > %d：菜单将分 %d 页（mkgui 自动分页）"
                     % (len(recipes), PERPAGE, pages))
    return fails, warns


# ---------------------------------------------------------------- conf（设置数据）

def conf_read():
    if not os.path.exists(CONF_LOCAL):
        return {}
    out = {}
    for line in open(CONF_LOCAL, encoding="utf-8"):
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def conf_write(c):
    lines = ["# FilmLab 外置设置数据（由 flab.py conf 管理；相机端 filmlab.sh source）",
             "#",
             "# 校准完成后（见 test_server/pwsend/runbook.txt），用实测值写入：",
             "#   python flab.py conf --set PWID_G=0x10f --set PWID_B=0x113 \\",
             "#        --set PWID_H=0x114 --set FILMLAB_PW=1",
             "#   python flab.py deploy --conf",
             "#",
             "# 支持的键（与 filmlab.sh 变量同名）：FILMLAB_PW / FILMLAB_SAVE / FILMLAB_MID",
             "#   PWSEND / PWID_R / PWID_G / PWID_B / PWID_H / PWID_S / PWID_P / PWID_C",
             ""]
    for k in sorted(c):
        lines.append("%s=%s" % (k, c[k]))
    with open(CONF_LOCAL, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("已写 %s（%d 项）" % (CONF_LOCAL, len(c)))


# ---------------------------------------------------------------- 部署

def ftp_conn(host):
    import ftplib
    f = ftplib.FTP(host, timeout=60)
    f.login("root", "")
    return f


def port_ok(host, p, tries=4, gap=3):
    import time
    for _ in range(tries):
        s = socket.socket()
        s.settimeout(4)
        try:
            s.connect((host, p))
            return True
        except Exception:
            time.sleep(gap)
        finally:
            try:
                s.close()
            except Exception:
                pass
    return False


def deploy(host, with_conf, sync_filmsim, idx=None):
    d = load()
    text = render(d)
    fails, warns = lint(d, text)
    for w in warns:
        print("  warn:", w)
    if fails:
        for x in fails:
            print("  FAIL:", x)
        print("★ lint 未过 —— 拒绝部署（修完再来）")
        return 1

    if sync_filmsim:
        with open(FILMSIM_COPY, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("[sync] -> %s" % os.path.relpath(FILMSIM_COPY, REPO))

    if not port_ok(host, 21):
        print("★ FTP 不可达"); return 1
    f = ftp_conn(host)
    try:
        f.mkd("/_xfer")
    except Exception:
        pass
    with open(RECIPES, "rb") as fh:
        f.storbinary("STOR /_xfer/recipes.json", fh, blocksize=32768)
    print("[ftp] recipes.json -> /_xfer/  md5=%s" % md5f(RECIPES))
    if with_conf and os.path.exists(CONF_LOCAL):
        with open(CONF_LOCAL, "rb") as fh:
            f.storbinary("STOR /_xfer/filmlab.conf", fh, blocksize=32768)
        print("[ftp] filmlab.conf -> /_xfer/  md5=%s" % md5f(CONF_LOCAL))
    f.quit()

    if not port_ok(host, 23):
        print("★ telnet 不可达（JSON 已到 _xfer，稍后可手动 cp）"); return 1
    t = MiniTel(host, timeout=25)
    t.send("root", 2)
    t.send("", 2)
    cmds = [
        "cp -f /mnt/mmc/_xfer/recipes.json /mnt/mmc/filmlab/recipes.json",
    ]
    if with_conf and os.path.exists(CONF_LOCAL):
        cmds.append("cp -f /mnt/mmc/_xfer/filmlab.conf /mnt/mmc/filmlab/filmlab.conf")
    if idx is not None:
        cmds.append("echo %d > /mnt/mmc/filmlab/cur.idx" % idx)
    cmds += [
        # cur.idx 越界归一（删配方后）
        "CUR=$(cat /mnt/mmc/filmlab/cur.idx 2>/dev/null || echo 0)",
        "N=$(grep -c '\"label\"' /mnt/mmc/filmlab/recipes.json)",
        "[ \"$CUR\" -ge \"$N\" ] 2>/dev/null && { echo 0 > /mnt/mmc/filmlab/cur.idx; echo IDX-FIXED; }",
        "echo ==MD5==; md5sum /mnt/mmc/filmlab/recipes.json",
        "echo ==CONF==; cat /mnt/mmc/filmlab/filmlab.conf 2>/dev/null | head -20",
        "echo ==EXPORT==; /opt/usr/nx-ks/filmlab.sh export",
        "echo ==MKGUI==; /opt/usr/nx-ks/filmlab.sh mkgui",
        "echo ==CUR==; cat /mnt/mmc/filmlab/cur.idx; echo",
        "echo ==LIST==; /opt/usr/nx-ks/filmlab.sh list | head -30",
        "echo ==COPY==; cp -f /opt/usr/nx-ks/gui_filmlab1b.NX500 /mnt/mmc/_xfer/gui_filmlab1b.NX500",
    ]
    out = t.send("; ".join(cmds), 60)
    try:
        out += t.read(5)
    except Exception:
        pass
    t.close()
    print("----------- 机上输出 -----------")
    print(out.strip())
    print("-------------------------------")

    # 回收菜单核对
    if port_ok(host, 21, tries=2, gap=2):
        f = ftp_conn(host)
        dst = os.path.join(HERE, "gui_filmlab1b.pulled.NX500")
        try:
            with open(dst, "wb") as fh:
                f.retrbinary("RETR /_xfer/gui_filmlab1b.NX500", fh.write)
            nbtn = sum(1 for L in open(dst, encoding="utf-8", errors="replace")
                       if L.startswith("button|"))
            print("[pull] 菜单 %d B, button 行 = %d（应 = 配方数 %d + 2）"
                  % (os.path.getsize(dst), nbtn, len(d["recipes"])))
        except Exception as e:
            print("[pull] 菜单回收失败:", e)
        f.quit()
    return 0


# ---------------------------------------------------------------- main

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "add", "edit", "rm", "lint", "conf", "deploy"])
    ap.add_argument("key", nargs="?")
    ap.add_argument("--label")
    for f in ("r", "g", "b", "hue", "sat", "sharp", "con"):
        ap.add_argument("--" + f, type=int)
    ap.add_argument("--set", action="append", default=[], metavar="K=V")
    ap.add_argument("--unset", action="append", default=[])
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--host", default=HOST_DEFAULT)
    ap.add_argument("--conf", action="store_true")
    ap.add_argument("--sync-filmsim", action="store_true")
    ap.add_argument("--idx", type=int)
    return ap.parse_args()


def main():
    a = parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if a.cmd == "list":
        d = load()
        for k, r in d["recipes"].items():
            print("  %-14s %-14s R/G/B=%s/%s/%s HUE=%s SAT=%s SHARP=%s CON=%s"
                  % (k, r.get("label", ""), r.get("R_COLOR"), r.get("G_COLOR"),
                     r.get("B_COLOR"), r.get("HUE"), r.get("SATURATION"),
                     r.get("SHARPNESS"), r.get("CONTRAST")))
        n = len(d["recipes"])
        pages = max(1, (n + PERPAGE - 1) // PERPAGE)
        print("  共 %d 配方（每页 %d，菜单 %d 页）" % (n, PERPAGE, pages))
        return 0

    if a.cmd in ("add", "edit"):
        if not a.key:
            print("用法: add <key> --label ... --r.. --g.. --b.. --hue.. --sat.. --sharp.. --con..")
            return 1
        d = load()
        r = d["recipes"].get(a.key, {})
        pairs = [("label", a.label), ("R_COLOR", a.r), ("G_COLOR", a.g), ("B_COLOR", a.b),
                 ("HUE", a.hue), ("SATURATION", a.sat), ("SHARPNESS", a.sharp),
                 ("CONTRAST", a.con)]
        for f, v in pairs:
            if v is not None:
                r[f] = v
        missing = [f for f in FIELDS if f not in r]
        if missing:
            print("★ 缺字段：%s（add 需给全 7+1 个；edit 只补差异）" % missing)
            return 1
        d["recipes"][a.key] = r
        save(d)
        print("已保存 %s（%d 配方）" % (a.key, len(d["recipes"])))
        return 0

    if a.cmd == "rm":
        if not a.key:
            print("用法: rm <key>"); return 1
        d = load()
        if a.key not in d["recipes"]:
            print("★ 不存在：%s" % a.key); return 1
        del d["recipes"][a.key]
        save(d)
        print("已删除 %s（剩 %d 配方）★ 记得 deploy（deploy 会自动归一 cur.idx）"
              % (a.key, len(d["recipes"])))
        return 0

    if a.cmd == "lint":
        d = load()
        text = open(RECIPES, encoding="utf-8").read()
        fails, warns = lint(d, text)
        for x in fails:
            print("  FAIL:", x)
        for x in warns:
            print("  warn:", x)
        print("lint: %s（%d FAIL / %d warn）" % ("PASS" if not fails else "FAIL",
                                                len(fails), len(warns)))
        return 1 if fails else 0

    if a.cmd == "conf":
        c = conf_read()
        if a.show or (not a.set and not a.unset):
            print("== %s ==" % CONF_LOCAL)
            for k in sorted(c):
                print("  %s=%s" % (k, c[k]))
            return 0
        for kv in a.set:
            if "=" not in kv:
                print("★ --set 需要 K=V：", kv); return 1
            k, v = kv.split("=", 1)
            c[k.strip()] = v.strip()
        for k in a.unset:
            c.pop(k, None)
        conf_write(c)
        print("★ 相机端生效：python flab.py deploy --conf（推 filmlab.conf）")
        return 0

    if a.cmd == "deploy":
        return deploy(a.host, a.conf, a.sync_filmsim, a.idx)

    return 0


if __name__ == "__main__":
    sys.exit(main())
