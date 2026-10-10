#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pwsend_deploy.py — PW 直推包部署（PC 侧）

推送「一键滤镜」资产到相机：
  /mnt/mmc/filmlab/pwsend.arm    ← POC/生产工具（seq 模式）
  /mnt/mmc/filmlab/pwcalib.sh    ← 校准脚本
  /opt/usr/nx-ks/filmlab.sh      ←（可选 --with-filmlab）新版引擎（带 pwpush）
  另推 runbook.txt 备查。

用法:
  python pwsend_deploy.py push  --host 192.168.0.105 [--with-filmlab]
  python pwsend_deploy.py ls    --host 192.168.0.105
"""
from __future__ import annotations

import argparse
import ftplib
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
CHUNK = 32 * 1024

# (远端目录, 远端名, 本地路径)
#   /filmlab/  = /mnt/mmc/filmlab/（FTP 根 == SD 卡）
FILES = [
    ("/filmlab", "pwsend.arm", os.path.join(HERE, "pwsend.arm")),
    ("/filmlab", "pwcalib.sh", os.path.join(HERE, "pwcalib.sh")),
    ("/filmlab", "runbook.txt", os.path.join(HERE, "runbook.txt")),
    ("/filmlab", "gen_pwpush.py", os.path.join(HERE, "gen_pwpush.py")),
]
FILMLAB_SH = os.path.join(REPO, "scripts", "filmlab.sh")
EXPECT = {
    "pwsend.arm": None,   # 在推送时现算现印（工具迭代频繁，不强绑旧 md5）
    "pwcalib.sh": None,
}


def conn(host):
    f = ftplib.FTP(host, timeout=60)
    f.login("root", "")
    return f


def mkdirs(f, path):
    cur = ""
    for p in [x for x in path.split("/") if x]:
        cur += "/" + p
        try:
            f.mkd(cur)
        except Exception:
            pass


def md5f(p):
    h = hashlib.md5()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def do_push(a):
    f = conn(a.host)
    for d, _, _ in FILES:
        mkdirs(f, d)
    for d, remote, src in FILES:
        if not os.path.exists(src):
            print("  跳过（缺）", src)
            continue
        data = open(src, "rb").read()
        if remote.endswith(".sh"):
            assert b"\r\n" not in data, "%s 含 CRLF（铁律 99）" % remote
        with open(src, "rb") as fh:
            f.storbinary("STOR %s/%s" % (d, remote), fh, blocksize=CHUNK)
        print("  推送 %-20s %7d B  md5=%s" % (remote, len(data), md5f(src)))
    if a.with_filmlab:
        mkdirs(f, "/_xfer")
        data = open(FILMLAB_SH, "rb").read()
        assert b"\r\n" not in data, "filmlab.sh 含 CRLF"
        with open(FILMLAB_SH, "rb") as fh:
            f.storbinary("STOR /_xfer/filmlab.sh", fh, blocksize=CHUNK)
        print("  推送 filmlab.sh → /_xfer/（需机上 cp 到 /opt/usr/nx-ks/）")
    f.quit()
    print("★ 机上 chmod（一次）:")
    print("   /opt/usr/nx-ks/busybox chmod 755 /mnt/mmc/filmlab/pwsend.arm /mnt/mmc/filmlab/pwcalib.sh")
    if a.with_filmlab:
        print("   /opt/usr/nx-ks/busybox cp -f /mnt/mmc/_xfer/filmlab.sh /opt/usr/nx-ks/filmlab.sh")
        print("   /opt/usr/nx-ks/busybox chmod 755 /opt/usr/nx-ks/filmlab.sh")
    print("★ 进门检查：/opt/usr/nx-ks/busybox grep pwpush /opt/usr/nx-ks/filmlab.sh")
    return 0


def do_ls(a):
    f = conn(a.host)
    try:
        for name in f.nlst("/filmlab"):
            base = name.rsplit("/", 1)[-1]
            try:
                sz = f.size("/filmlab/" + base)
            except Exception:
                sz = -1
            print("  %-24s %s" % (base, sz))
    except Exception as e:
        print("列目录失败:", e)
    f.quit()
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["push", "ls"])
    ap.add_argument("--host", default="192.168.0.105")
    ap.add_argument("--with-filmlab", action="store_true",
                    help="同时推新版 filmlab.sh（到 _xfer，需机内 cp）")
    a = ap.parse_args()
    return {"push": do_push, "ls": do_ls}[a.cmd](a) or 0


if __name__ == "__main__":
    sys.exit(main())
