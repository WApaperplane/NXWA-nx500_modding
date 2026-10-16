#!/usr/bin/env python3
"""nx-put.py - 相机文件推送器（本地 → SD 卡，FTP STOR）

用法:
  python nx-put.py -d <远端目录> <本地文件...> [--as <远端名>]
  python nx-put.py -d stage/dicam scripts/dicam/*.sh
  python nx-put.py -d stage/dicam --as di-camera-app.c2 fw/v1.12/dicam/di-camera-app.c2.v2

约定:
  FTP 根 = /mnt/mmc（SD 卡），busybox ftpd 已 chroot ⇒ 远端路径一律**相对根**书写。
  --as 仅在单个源文件时有效（重命名上传）。
  上传后按 FTP SIZE 校验字节数（真正的 md5 校验走 telnet/nx-probe）。
  ⛔ 不执行任何远端命令（只 STOR），不触碰 /opt/usr/nx-ks。
"""
import ftplib
import os
import sys

HOST = "192.168.0.105"


def ensure_dir(f, path):
    """逐级 MKD（已存在时报错，忽略即可）。"""
    cur = ""
    for p in path.strip("/").split("/"):
        if not p:
            continue
        cur = (cur + "/" + p) if cur else p
        try:
            f.mkd(cur)
        except Exception:
            pass


def put_one(f, local, remote, verify=True):
    size = os.path.getsize(local)
    with open(local, "rb") as fh:
        f.storbinary("STOR " + remote, fh)
    ok = "?"
    if verify:
        try:
            rsize = f.size(remote)
            ok = "OK" if rsize == size else f"MISMATCH(remote={rsize})"
        except Exception as e:
            ok = f"SIZE?{type(e).__name__}"
    print(f"  PUT {local} -> {remote}  ({size} B)  verify={ok}")
    return ok == "OK" or ok.startswith("SIZE?")


def main():
    argv = sys.argv[1:]
    if "-d" not in argv:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    dest = argv[argv.index("-d") + 1]
    rename = None
    rest = list(argv)
    # 去掉 -d <dir> 与其值
    i = rest.index("-d")
    del rest[i:i + 2]
    if "--as" in rest:
        j = rest.index("--as")
        rename = rest[j + 1]
        del rest[j:j + 2]
    srcs = [a for a in rest if not a.startswith("--")]
    if not srcs:
        print("!! 无源文件", file=sys.stderr)
        sys.exit(2)
    if rename and len(srcs) != 1:
        print("!! --as 仅支持单个源文件", file=sys.stderr)
        sys.exit(2)

    print(f"[nx-put] host={HOST} dest={dest} files={len(srcs)}")
    f = ftplib.FTP()
    f.connect(HOST, 21, timeout=30)
    f.login("root", "")
    ensure_dir(f, dest)
    allok = True
    for s in srcs:
        if not os.path.isfile(s):
            print(f"  SKIP {s}（不是文件）")
            allok = False
            continue
        name = rename if rename else os.path.basename(s)
        remote = dest.rstrip("/") + "/" + name
        allok &= put_one(f, s, remote)
    f.quit()
    print("[nx-put] " + ("ALL OK" if allok else "有失败项（见上）"))
    sys.exit(0 if allok else 1)


if __name__ == "__main__":
    main()
