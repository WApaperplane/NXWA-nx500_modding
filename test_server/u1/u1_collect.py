#!/usr/bin/env python3
"""U1 结果收集/下发（PC 侧）

★ 生成物，勿手改：python test_server/tools/gate_pack_u1.py

FTP 事实（本仓已确认）：
  * 相机 FTP 在 21 端口，root + 空密码，**FTP 根 = SD 卡**（/opt/storage/sdcard）
  * 所以 /mnt/mmc/u1/out/xxx 在 FTP 里是 /u1/out/xxx
  * **单文件 >约 60KB 会 550/553** ⇒ 大文件必须 32KB 分块 + md5sum 拼合校验

用法:
  python u1_collect.py push --host 192.168.0.105        # 把本目录脚本推到相机 /mnt/mmc/u1/
  python u1_collect.py pull --host 192.168.0.105        # 把 u1/out/ 全部拉回 raw8/gates/u1/
  python u1_collect.py ls   --host 192.168.0.105
"""
from __future__ import annotations

import argparse
import hashlib
import ftplib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
DEST = os.path.join(REPO, "raw8", "gates", "u1")
CHUNK = 32 * 1024
CAM_DIR = "/u1"          # FTP 相对路径（根 = SD 卡）
CAM_OUT = "/u1/out"
# (远端名, 本地相对路径) —— 相对 test_server/u1/
# ★ epmc.arm 是唯一需要的裸 ELF：u1_epmc.sh 直接 exec 它 ⇒ 必须 x 位，
#   而 FTP 上传不带 x 位 ⇒ 上传后必须机上 chmod（do_push 末尾会提示）。
PUSH = (
    ("u1_probe.sh", "u1_probe.sh"),
    ("u1_rd.sh", "u1_rd.sh"),
    ("u1_input.sh", "u1_input.sh"),
    ("u1_iqr.sh", "u1_iqr.sh"),
    ("u1_epmc.sh", "u1_epmc.sh"),
    ("runbook.txt", "runbook.txt"),
    ("epmc.arm", os.path.join("..", "sysarch", "epmc.arm")),
)


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
    for remote, rel in PUSH:
        src = os.path.normpath(os.path.join(HERE, rel))
        if not os.path.exists(src):
            print("  跳过（不存在）", remote)
            continue
        data = open(src, "rb").read()
        if remote.endswith(".sh"):
            assert b"\r\n" not in data, f"{remote} 含 CRLF（铁律 99）"
        with open(src, "rb") as fh:
            f.storbinary("STOR %s/%s" % (CAM_DIR, remote), fh, blocksize=CHUNK)
        print("  推送 %-16s %7d B  md5=%s" % (remote, len(data), md5f(src)))
    f.quit()
    print("★ 机上还需: chmod +x /mnt/mmc/u1/epmc.arm （FTP 不带 x 位）")


def _remote_files(f, path):
    """列远端目录 -> [(name, size)]。
    ★ 相机 busybox ftpd 不支持 MLSD（实测回 500 Unknown command），
    只支持 NLST / SIZE / LIST ⇒ 必须用 NLST + SIZE 组合，否则 pull 永远失败。"""
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
        print("拉取失败：/u1/out 不存在或不可读 ->", e)
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
