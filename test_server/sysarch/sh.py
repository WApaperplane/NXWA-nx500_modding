#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""通用：在相机上跑任意 shell 命令，输出经文件重定向再 FTP 拉回。

★ 为什么不用 telnet 直接读输出：相机对已登录会话静默回显（实测输出为空），
  run_arm.py 的"重定向到文件再拉回"是本项目已验证的唯一可靠读出方式。

用法: python sh.py "<shell 命令>" [outname]
"""
import ftplib
import os
import socket
import sys
import time

from minitel import MiniTel

HOST = "192.168.0.105"
X = "/mnt/mmc/_xfer"
HERE = os.path.dirname(os.path.abspath(__file__))


def pull(name):
    f = ftplib.FTP(HOST, timeout=30)
    f.login()
    f.cwd("/_xfer")
    data = b""
    import io
    buf = io.BytesIO()
    f.retrbinary("RETR " + name, buf.write)
    f.quit()
    return buf.getvalue().decode("utf-8", "replace")


def main():
    cmd = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 else "sh_out.txt"
    t = MiniTel(HOST, timeout=60)
    t.read(3)
    t.send("root", 2)
    t.send("", 2)
    # 分号包在 { } 里；2>&1 合并错误；不用 find/xargs 等重活
    line = '{ echo "=== cmd ==="; %s; echo "=== exit=$? ==="; } > %s/%s 2>&1' % (
        cmd, X, name)
    t.send(line, 25)
    t.close()
    time.sleep(2.5)
    out = pull(name)
    print(out.replace("\r\n", "\n").strip())
    # 存一份本地
    with open(os.path.join(HERE, "raw5", name), "w", encoding="utf-8",
              errors="replace") as f:
        os.makedirs(os.path.join(HERE, "raw5"), exist_ok=True)
        f.write(out)


if __name__ == "__main__":
    main()