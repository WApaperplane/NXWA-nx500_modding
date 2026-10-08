#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deploy_entry.py —— FilmLab 入口/菜单上机部署（PC 侧）

用途（2026-10-08 发布打包同步）：
  1) 补部署菜单 2/3/4 页（主菜单 gui_filmlab.NX500 的「预设槽 / 诊断」按钮指向它们）
  2) 部署新版 EV_AEL.sh（含 -ot 菜单自动重建守卫 + NX1 回退）
  3) 部署 EV_AEL.community.sh（NX1 回退用的社区原版，NX500 上不执行）

全部小文件（<3KB each），符合铁律 88。
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

from minitel import MiniTel  # noqa: E402

HOST = "192.168.0.105"
D = "/opt/usr/nx-ks"

# (本地文件, 远端名)
FILES = [
    (os.path.join(REPO, "scripts", "gui_filmlab2.NX500"), "gui_filmlab2.NX500"),
    (os.path.join(REPO, "scripts", "gui_filmlab3.NX500"), "gui_filmlab3.NX500"),
    (os.path.join(REPO, "scripts", "gui_filmlab4.NX500"), "gui_filmlab4.NX500"),
    (os.path.join(REPO, "scripts", "EV_AEL.sh"), "EV_AEL.sh"),
    (os.path.join(REPO, "scripts", "EV_AEL.community.sh"), "EV_AEL.community.sh"),
]


def md5f(p):
    h = hashlib.md5()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def port_ok(p, tries=6, gap=4):
    for _ in range(tries):
        s = socket.socket(); s.settimeout(4)
        try:
            s.connect((HOST, p)); return True
        except Exception:
            time.sleep(gap)
        finally:
            try: s.close()
            except Exception: pass
    return False


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    for src, _ in FILES:
        d = open(src, "rb").read()
        if src.endswith(".sh"):
            assert b"\r\n" not in d, "%s 含 CRLF（铁律 99）" % src
        print("[local] %-28s %6d B  md5=%s" % (os.path.basename(src), len(d), md5f(src)))

    if not port_ok(21):
        print("★ FTP 不可达"); return 1
    import ftplib
    f = ftplib.FTP(HOST, timeout=60); f.login("root", "")
    try:
        f.mkd("/_xfer")
    except Exception:
        pass
    for src, name in FILES:
        with open(src, "rb") as fh:
            f.storbinary("STOR /_xfer/%s" % name, fh, blocksize=32768)
    f.quit()
    print("[ftp] uploaded %d files -> /_xfer/" % len(FILES))

    if not port_ok(23, tries=4, gap=3):
        print("★ telnet 不可达"); return 1
    t = MiniTel(HOST, timeout=25)
    t.read(2); t.send("root", 2); t.send("", 2); time.sleep(1)
    CMD = (
        "cp -f /mnt/mmc/_xfer/gui_filmlab2.NX500 /mnt/mmc/_xfer/gui_filmlab3.NX500 "
        "/mnt/mmc/_xfer/gui_filmlab4.NX500 /opt/usr/nx-ks/; "
        "cp -f /mnt/mmc/_xfer/EV_AEL.sh /mnt/mmc/_xfer/EV_AEL.community.sh /opt/usr/nx-ks/; "
        "chmod +x /opt/usr/nx-ks/EV_AEL.sh /opt/usr/nx-ks/EV_AEL.community.sh; "
        "echo ==SYNTAX==; sh -n /opt/usr/nx-ks/EV_AEL.sh && echo EV_AEL-SYNTAX-OK; "
        "sh -n /opt/usr/nx-ks/EV_AEL.community.sh && echo COMMUNITY-SYNTAX-OK; "
        "echo ==LS==; ls /opt/usr/nx-ks/ | grep -E 'gui_filmlab|EV_AEL'; "
        "echo ==MD5==; md5sum /opt/usr/nx-ks/EV_AEL.sh /opt/usr/nx-ks/EV_AEL.community.sh "
        "/opt/usr/nx-ks/gui_filmlab2.NX500 /opt/usr/nx-ks/gui_filmlab3.NX500 /opt/usr/nx-ks/gui_filmlab4.NX500; "
        "echo ==OT==; [ /opt/usr/nx-ks/gui_filmlab1b.NX500 -ot /mnt/mmc/filmlab/recipes.json ] && echo OT-YES || echo OT-NO-fresh"
    )
    out = t.send(CMD, 30)
    try:
        out += t.read(4)
    except Exception:
        pass
    t.close()
    print("----------- 机上输出 -----------")
    print(out.strip())
    print("-------------------------------")
    return 0


if __name__ == "__main__":
    sys.exit(main())
