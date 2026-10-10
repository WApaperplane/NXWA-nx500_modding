#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deploy_luts.py — LUT 一键部署（PC 侧）★ LUT 链路的「可导入」环节

流程：.cube → nx3dlut.py import（按硬件格点采样）→ 19712B 整槽表 → FTP 推相机。

用法:
  python deploy_luts.py build                          # 扫描 .cube → build/（含 _identity + 清单）
  python deploy_luts.py build --cubes <dir>[,...]      # 追加密目录（用户自己的 .cube）
  python deploy_luts.py push  --host 192.168.0.105     # 推送 build/ → 相机 /mnt/mmc/filmlab/
  python deploy_luts.py build-push --host 192.168.0.105
  python deploy_luts.py list                           # 看构建集

相机端落点（FTP 根 == SD 卡）：
  /filmlab/luts/<Name>.bin        ← 表（lutpick.sh apply <Name>）
  /filmlab/{cmasafe,cmapick2,lutapi,lutload}.arm + lutpick.sh   ← 工具
"""

from __future__ import annotations

import argparse
import ftplib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
def _py():
    """优先 E 盘 venv（与项目惯例一致），退回当前解释器。"""
    p = r"E:\nxks2-re\Scripts\python.exe"
    return p if os.path.exists(p) else sys.executable

NX3DLUT = os.path.join(REPO, "test_server", "isp", "nx3dlut.py")
DEFAULT_CUBES = [os.path.join(REPO, "test_server", "filmsim", "luts")]
BUILD = os.path.join(HERE, "build")

# 工具来源（单一来源原则：从既有位置取材，不复制维护）
TOOLS = [
    ("cmasafe.arm", os.path.join(REPO, "test_server", "u6", "cmasafe.arm")),
    ("cmapick2.arm", os.path.join(REPO, "test_server", "sysarch", "cmapick2.arm")),
    ("lutapi.arm", os.path.join(REPO, "test_server", "sysarch", "lutapi.arm")),
    ("lutload.arm", os.path.join(REPO, "test_server", "sysarch", "lutload.arm")),
    ("lutpick.sh", os.path.join(HERE, "lutpick.sh")),
    ("lutsentinel.arm", os.path.join(HERE, "lutsentinel.arm")),
]

CAM_DIR = "/filmlab"          # FTP 相对路径（根 = SD 卡 = /mnt/mmc）
CAM_LUTS = "/filmlab/luts"
CHUNK = 32 * 1024


def sanitize(name):
    """.cube 文件名 → 安全表名（[A-Za-z0-9_.-]，空格→_）。"""
    n = os.path.splitext(os.path.basename(name))[0]
    n = re.sub(r"[^A-Za-z0-9_.-]+", "_", n).strip("_")
    return n or "unnamed"


def md5f(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("★ 命令失败(%d): %s" % (r.returncode, " ".join(cmd)))
        print(r.stdout[-800:])
        print(r.stderr[-400:])
    return r.returncode == 0, r.stdout


def build(cube_dirs):
    if not os.path.exists(NX3DLUT):
        print("★ 缺 nx3dlut.py：", NX3DLUT)
        return 1
    os.makedirs(os.path.join(BUILD, "luts"), exist_ok=True)
    manifest = []

    # 1) identity（离/开启用）
    idp = os.path.join(BUILD, "luts", "_identity.bin")
    ok, out = run([_py(), NX3DLUT, "identity", idp, "--slot"])
    if ok:
        manifest.append(dict(name="_identity", src="(generated)", bin="_identity.bin",
                             md5=md5f(idp), size=os.path.getsize(idp)))
        print("  OK  _identity.bin (%d B)" % os.path.getsize(idp))

    # 2) 扫描 .cube
    seen = set()
    for d in cube_dirs:
        if not os.path.isdir(d):
            print("  跳过（不存在）:", d)
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.lower().endswith(".cube"):
                continue
            src = os.path.join(d, fn)
            name = sanitize(fn)
            if name in seen:
                print("  跳过（重名）:", fn)
                continue
            seen.add(name)
            dst = os.path.join(BUILD, "luts", name + ".bin")
            ok, out = run([_py(), NX3DLUT, "import", src, dst, "--slot"])
            if not ok:
                continue
            manifest.append(dict(name=name, src=fn, bin=name + ".bin",
                                 md5=md5f(dst), size=os.path.getsize(dst)))
            print("  OK  %-28s <- %s (%d B)" % (name + ".bin", fn, os.path.getsize(dst)))

    with open(os.path.join(BUILD, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(dict(luts=manifest), f, ensure_ascii=False, indent=2)
    print("构建完成：%d 表 → %s" % (len(manifest), BUILD))
    return 0


def conn(host):
    f = ftplib.FTP(host, timeout=60)
    f.login("root", "")
    return f


def mkdirs(f, path):
    cur = ""
    for part in [p for p in path.split("/") if p]:
        cur += "/" + part
        try:
            f.mkd(cur)
        except Exception:
            pass


def push(host):
    mf = os.path.join(BUILD, "manifest.json")
    if not os.path.exists(mf):
        print("★ 先 build：", BUILD)
        return 1
    man = json.load(open(mf, encoding="utf-8"))
    f = conn(host)
    mkdirs(f, CAM_LUTS)
    n = 0
    for it in man["luts"]:
        p = os.path.join(BUILD, "luts", it["bin"])
        with open(p, "rb") as fh:
            f.storbinary("STOR %s/%s" % (CAM_LUTS, it["bin"]), fh, blocksize=CHUNK)
        print("  推送 %-28s %7d B" % (it["bin"], it["size"]))
        n += 1
    for remote, src in TOOLS:
        if not os.path.exists(src):
            print("  跳过（缺）", src)
            continue
        data = open(src, "rb").read()
        if remote.endswith(".sh"):
            assert b"\r\n" not in data, "%s 含 CRLF（铁律 99）" % remote
        with open(src, "rb") as fh:
            f.storbinary("STOR %s/%s" % (CAM_DIR, remote), fh, blocksize=CHUNK)
        print("  推送工具 %-20s %7d B" % (remote, len(data)))
    f.quit()
    print("推送完成：%d 表 + 工具 → %s" % (n, CAM_DIR))
    print("★ 机上 chmod（一次）：")
    print("   /opt/usr/nx-ks/busybox chmod 755 /mnt/mmc/filmlab/*.arm /mnt/mmc/filmlab/lutpick.sh")
    print("★ 试运行：/opt/usr/nx-ks/busybox sh /mnt/mmc/filmlab/lutpick.sh list")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "push", "build-push", "list"])
    ap.add_argument("--cubes", default="", help="追加 .cube 目录（逗号分隔）")
    ap.add_argument("--host", default="192.168.0.105")
    a = ap.parse_args()

    dirs = list(DEFAULT_CUBES)
    if a.cubes:
        dirs += [d for d in a.cubes.split(",") if d]

    if a.cmd == "list":
        mf = os.path.join(BUILD, "manifest.json")
        if not os.path.exists(mf):
            print("（未构建）")
            return 0
        man = json.load(open(mf, encoding="utf-8"))
        for it in man["luts"]:
            print("  %-28s %8d B  md5=%s  <- %s"
                  % (it["bin"], it["size"], it["md5"][:8], it["src"]))
        return 0
    if a.cmd in ("build", "build-push"):
        rc = build(dirs)
        if rc != 0 or a.cmd == "build":
            return rc
    return push(a.host)


if __name__ == "__main__":
    sys.exit(main())
