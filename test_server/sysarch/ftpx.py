# -*- coding: utf-8 -*-
"""FTP 拉取器（stdlib ftplib，不引第三方）。

铁律：
  - FTP 根 = SD 卡，root 空密码。
  - 流程固定 ftp_put → 一次 telnet → ftp_get（不在 FTP 里嵌 telnet 命令）。
  - 单文件大（>10KB）必须走 FTP，telnet 传不动。
"""
import ftplib
import sys
from pathlib import Path


def ftp_get(host, remote, local, timeout=40):
    """失败返回 None，不抛到调用方。"""
    local = Path(local)
    local.parent.mkdir(parents=True, exist_ok=True)
    try:
        ft = ftplib.FTP()
        ft.connect(host, 21, timeout=timeout)
        ft.login("root", "")
        ft.set_pasv(True)
        ft.voidcmd("TYPE I")
        with open(local, "wb") as f:
            ft.retrbinary("RETR " + remote, f.write, 8192)
        size = local.stat().st_size
        ft.quit()
        return size
    except Exception as e:
        print("  FTP FAIL %s -> %s : %s" % (remote, local, e))
        return None


def ftp_put(host, local, remote, timeout=40):
    local = Path(local)
    try:
        ft = ftplib.FTP()
        ft.connect(host, 21, timeout=timeout)
        ft.login("root", "")
        ft.set_pasv(True)
        with open(local, "rb") as f:
            ft.storbinary("STOR " + remote, f, 8192)
        ft.quit()
        return local.stat().st_size
    except Exception as e:
        print("  FTP PUT FAIL %s -> %s : %s" % (local, remote, e))
        return None


def ftp_list(host, path=".", timeout=30):
    try:
        ft = ftplib.FTP()
        ft.connect(host, 21, timeout=timeout)
        ft.login("root", "")
        lines = []
        ft.retrlines("LIST " + path, lines.append)
        ft.quit()
        return lines
    except Exception as e:
        return ["FTP LIST FAIL: %s" % e]


if __name__ == "__main__":
    host = sys.argv[1]
    mode = sys.argv[2]
    if mode == "get":
        print(ftp_get(host, sys.argv[3], sys.argv[4]))
    elif mode == "put":
        print(ftp_put(host, sys.argv[3], sys.argv[4]))
    elif mode == "ls":
        for l in ftp_list(host, sys.argv[3] if len(sys.argv) > 3 else "."):
            print(l)
