#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deploy_recipes.py —— 配方库部署 + 菜单刷新 + 产物回收（PC 侧一条龙）

背景（2026-10-08 U2 定案）：
  · 引擎 filmlab.sh 读的是 **/mnt/mmc/filmlab/recipes.json**（对象式 JSON）
  · mod_gui 菜单 `gui_filmlab1b.NX500` 由 `filmlab.sh mkgui` 在机上现场生成
  · 菜单按钮数 = 配方数 + 2（返回/取消）；★ 标记位置由 cur.idx（0 基索引）决定

两步走（中间留人工核对位）：
  python deploy_recipes.py a            # 上传 recipes.json + 部署 + 侦察（不改菜单）
  python deploy_recipes.py b <idx>      # 修 cur.idx → mkgui 重建菜单 → 回收产物

铁律对照：
  · 88  危险 ∝ 循环长度 × 输出量 —— 本脚本全部是"小文件、短循环、小输出"
  · FTP 根 = SD 卡（/mnt/mmc），所以 /mnt/mmc/_xfer 在 FTP 里是 /_xfer
  · login = root + 空密码；telnet 串行，绝不同时开两会话
"""
from __future__ import annotations

import hashlib
import os
import socket
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "sysarch"))

from minitel import MiniTel  # noqa: E402  (test_server/sysarch/minitel.py)

HOST_DEFAULT = "192.168.0.105"
RECIPE_LOCAL = os.path.join(HERE, "recipes", "recipes.json")
MENU_PULLED = os.path.join(HERE, "recipes", "gui_filmlab1b.pulled.NX500")


def md5f(p):
    h = hashlib.md5()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def port_ok(host, p, tries=6, gap=4):
    for _ in range(tries):
        s = socket.socket(); s.settimeout(4)
        try:
            s.connect((host, p)); return True
        except Exception:
            time.sleep(gap)
        finally:
            try: s.close()
            except Exception: pass
    return False


def ftp_conn(host):
    import ftplib
    f = ftplib.FTP(host, timeout=60)
    f.login("root", "")
    return f


def t_conn(host):
    t = MiniTel(host, timeout=25)
    t.read(2)
    t.send("root", 2)
    t.send("", 2)
    time.sleep(1)
    return t


def step_a(host):
    """上传 + 部署 + 侦察"""
    data = open(RECIPE_LOCAL, "rb").read()
    assert b"\r\n" not in data, "recipes.json 含 CRLF（须为 LF）"
    local_md5 = md5f(RECIPE_LOCAL)
    print("[local] %s  %d B  md5=%s" % (RECIPE_LOCAL, len(data), local_md5))

    if not port_ok(host, 21):
        print("★ FTP 不可达"); return 1
    f = ftp_conn(host)
    try:
        f.mkd("/_xfer")
    except Exception:
        pass
    with open(RECIPE_LOCAL, "rb") as fh:
        f.storbinary("STOR /_xfer/recipes.json", fh, blocksize=32768)
    f.quit()
    print("[ftp] uploaded -> /_xfer/recipes.json")

    if not port_ok(host, 23, tries=4, gap=3):
        print("★ telnet 不可达"); return 1
    t = t_conn(host)
    CMD = (
        "cp -f /mnt/mmc/_xfer/recipes.json /mnt/mmc/filmlab/recipes.json; "
        "echo ==MD5==; md5sum /mnt/mmc/filmlab/recipes.json; "
        "echo ==OT==; [ /opt/usr/nx-ks/gui_filmlab1b.NX500 -ot /mnt/mmc/filmlab/recipes.json ] && echo OT-YES || echo OT-NO; "
        "echo ==MENUS==; ls /opt/usr/nx-ks/ | grep gui_filmlab; "
        "echo ==LAST==; cat /mnt/mmc/filmlab/last.log; "
        "echo ==CUR==; cat /mnt/mmc/filmlab/cur.idx 2>/dev/null; echo; "
        "echo ==LIST==; /opt/usr/nx-ks/filmlab.sh list"
    )
    out = t.send(CMD, 45)
    try:
        out += t.read(5)
    except Exception:
        pass
    t.close()
    print("----------- 机上输出 -----------")
    print(out.strip())
    print("-------------------------------")
    print("※ 比对：机上 recipes.json md5 应等于上面 [local] 的 md5")
    return 0


def step_b(host, idx):
    """修 cur.idx + mkgui + 回收（菜单 + 校数）"""
    if not port_ok(host, 23, tries=4, gap=3):
        print("★ telnet 不可达"); return 1
    t = t_conn(host)
    CMD = (
        "echo %d > /mnt/mmc/filmlab/cur.idx; "
        "echo ==IDX==; cat /mnt/mmc/filmlab/cur.idx; "
        "echo ==DUMP9==; /opt/usr/nx-ks/filmlab.sh dump x 9; "
        "/opt/usr/nx-ks/filmlab.sh mkgui; "
        "echo ==MENU==; cat /opt/usr/nx-ks/gui_filmlab1b.NX500; "
        "echo ==COPY==; cp -f /opt/usr/nx-ks/gui_filmlab1b.NX500 /mnt/mmc/_xfer/gui_filmlab1b.NX500; "
        "echo ==MD5==; md5sum /opt/usr/nx-ks/gui_filmlab1b.NX500 /mnt/mmc/filmlab/recipes.json"
    ) % idx
    out = t.send(CMD, 40)
    try:
        out += t.read(5)
    except Exception:
        pass
    t.close()
    print("----------- 机上输出 -----------")
    print(out.strip())
    print("-------------------------------")

    if not port_ok(host, 21):
        print("★ FTP 不可达（回收失败）"); return 1
    f = ftp_conn(host)
    with open(MENU_PULLED, "wb") as fh:
        f.retrbinary("RETR /_xfer/gui_filmlab1b.NX500", fh.write)
    f.quit()
    txt = open(MENU_PULLED, encoding="utf-8", errors="replace").read()
    nbtn = sum(1 for L in txt.splitlines() if L.startswith("button|"))
    print("[pull] %s  %d B  button 行 = %d（应 = 配方数+2）  md5=%s"
          % (MENU_PULLED, os.path.getsize(MENU_PULLED), nbtn, md5f(MENU_PULLED)))
    return 0


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if len(sys.argv) < 2:
        print(__doc__); return 2
    step = sys.argv[1]
    host = HOST_DEFAULT
    if step == "a":
        return step_a(host)
    if step == "b":
        if len(sys.argv) < 3:
            print("用法: python deploy_recipes.py b <cur.idx 0..N-1>"); return 2
        return step_b(host, int(sys.argv[2]))
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main())
