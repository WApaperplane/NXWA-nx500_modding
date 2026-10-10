#!/usr/bin/env python3
"""U6 结果收集/下发（PC 侧）

★ 与 u1_collect.py 同构（同一套 FTP 事实与分块策略）。

FTP 事实（本仓已确认）：
  * 相机 FTP 在 21 端口，root + 空密码，**FTP 根 = SD 卡**
  * 所以 /mnt/mmc/u6/out/xxx 在 FTP 里是 /u6/out/xxx
  * **单文件 >约 60KB 会 550/553** ⇒ 大文件必须分块 + md5 校验

用法:
  python u6_collect.py push --host 192.168.0.105   # 下发 U6 全部资产到 /mnt/mmc/u6/
  python u6_collect.py pull --host 192.168.0.105   # 拉回 /u6/out/ -> raw8/gates/u6/out/
  python u6_collect.py ls   --host 192.168.0.105
"""
from __future__ import annotations

import argparse
import hashlib
import ftplib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
DEST = os.path.join(REPO, "raw8", "gates", "u6", "out")
CHUNK = 32 * 1024
CAM_DIR = "/u6"          # FTP 相对路径（根 = SD 卡）
CAM_OUT = "/u6/out"

# (远端名, 本地相对路径) —— 相对 test_server/u6/
#   * .arm / .sh 全部自包含在 /mnt/mmc/u6/（不依赖 /opt 部署版本）
#   * 表文件从 raw8/gates/u6/ 取（R3 造表包产物）
PUSH = (
    ("u6_lut.sh", "u6_lut.sh"),
    ("u6_probe.sh", "u6_probe.sh"),
    ("cmasafe.arm", "cmasafe.arm"),
    ("cmapick2.arm", os.path.join("..", "sysarch", "cmapick2.arm")),
    ("lutapi.arm", os.path.join("..", "sysarch", "lutapi.arm")),
    ("lutload.arm", os.path.join("..", "sysarch", "lutload.arm")),
    ("runbook.txt", "runbook.txt"),
    ("md5sums.txt", os.path.join("..", "..", "raw8", "gates", "u6", "md5sums.txt")),
    ("r3_identity_slot.bin", os.path.join("..", "..", "raw8", "gates", "u6", "r3_identity_slot.bin")),
    ("r3_portra400_slot.bin", os.path.join("..", "..", "raw8", "gates", "u6", "r3_portra400_slot.bin")),
    ("r3_identity.bin", os.path.join("..", "..", "raw8", "gates", "u6", "r3_identity.bin")),
    ("r3_portra400.bin", os.path.join("..", "..", "raw8", "gates", "u6", "r3_portra400.bin")),
)

# 期望的源文件 md5（打包自检：推送前先验本地文件没被改动）
EXPECT = {
    "cmasafe.arm": "e616515a2d64650597fe427965aa3eaf",
    "lutapi.arm": "e769ae1c2cf84da2a8935b7986188bd6",
    "r3_identity_slot.bin": "235ad45324c042d0bd4233513e1fca52",
    "r3_portra400_slot.bin": "21074e36f1091cffde02539d7d9518f9",
    "r3_identity.bin": "66099183eda6a494db28e6a783eb940a",
    "r3_portra400.bin": "d5ff303fff05e8efeb7fd6393160afa3",
}


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


def md5f(p):
    h = hashlib.md5()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def do_push(a):
    f = conn(a.host)
    mkdirs(f, CAM_DIR)
    bad = 0
    for remote, rel in PUSH:
        src = os.path.normpath(os.path.join(HERE, rel))
        if not os.path.exists(src):
            print("  跳过（不存在）", remote, " <-", rel)
            bad += 1
            continue
        data = open(src, "rb").read()
        if remote.endswith(".sh"):
            assert b"\r\n" not in data, f"{remote} 含 CRLF（铁律 99）"
        md5 = md5f(src)
        exp = EXPECT.get(remote)
        flag = ""
        if exp and md5 != exp:
            flag = "  ★★ md5 与打包记录不符（期望 %s）" % exp
            bad += 1
        with open(src, "rb") as fh:
            f.storbinary("STOR %s/%s" % (CAM_DIR, remote), fh, blocksize=CHUNK)
        print("  推送 %-24s %7d B  md5=%s%s" % (remote, len(data), md5, flag))
    f.quit()
    print("★ 机上还需（一次）: ")
    print("   /opt/usr/nx-ks/busybox chmod 755 /mnt/mmc/u6/*.arm /mnt/mmc/u6/u6_lut.sh")
    return 1 if bad else 0


def _remote_files(f, path):
    """列远端目录 -> [(name, size)]。
    ★ 相机 busybox ftpd 不支持 MLSD，只支持 NLST / SIZE ⇒ NLST + SIZE 组合。"""
    out = []
    for name in f.nlst(path):
        if "/" in name:
            base = name.rsplit("/", 1)[-1]
            full = name if name.startswith("/") else "%s/%s" % (path, name)
        else:
            base = name
            full = "%s/%s" % (path, name)
        try:
            sz = int(f.size(full) or 0)
        except Exception:
            sz = 0
        out.append((base, sz))
    return out


def do_ls(a):
    f = conn(a.host)
    try:
        for name, size in _remote_files(f, CAM_OUT):
            print("  %-8s %10d  %s" % ("file", size, name))
    except Exception as e:
        print("  列目录失败（目录可能还没生成）:", e)
    f.quit()


def do_pull(a):
    os.makedirs(DEST, exist_ok=True)
    f = conn(a.host)
    try:
        files = _remote_files(f, CAM_OUT)
    except Exception as e:
        print("拉取失败：/u6/out 不存在或不可读 ->", e)
        return 1
    print("远端 %d 个文件" % len(files))
    for name, size in files:
        dst = os.path.join(DEST, name)
        # ★ >60KB 走分块（REST 续传），小文件一次拉完
        with open(dst, "wb") as fh:
            if size <= 60 * 1024:
                f.retrbinary("RETR %s/%s" % (CAM_OUT, name), fh.write, blocksize=CHUNK)
            else:
                got = 0
                while got < size:
                    def w(b):
                        fh.write(b)
                    f.retrbinary("RETR %s/%s" % (CAM_OUT, name), w, blocksize=CHUNK, rest=got)
                    got = fh.tell()
        got_size = os.path.getsize(dst)
        flag = "OK " if got_size == size else "!! "
        print("  %s%-28s %8d/%8d  md5=%s" % (flag, name, got_size, size, md5f(dst)))
    f.quit()
    print("落盘目录:", os.path.relpath(DEST, REPO))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["push", "pull", "ls"])
    ap.add_argument("--host", default="192.168.0.105")
    a = ap.parse_args()
    return {"push": do_push, "pull": do_pull, "ls": do_ls}[a.cmd](a) or 0


if __name__ == "__main__":
    sys.exit(main())
