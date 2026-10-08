#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cam.py —— 相机上机通用小工具（一个会话一条命令，输出尽量小）

用法:
  python cam.py probe                     探 21/23 端口（REFUSED/TIMEOUT 判定口诀）
  python cam.py run "cmd1; cmd2"          跑一条（含 ; 的）命令，回车断行
  python cam.py put  <local> <remote>     FTP 传到相机 <remote>（远端须在 SD 卡上）
  python cam.py deploy <local> <remote>   put 之后按需 cp+chmod+sh -n+md5 自证
                                          （remote 以 /opt/usr/nx-ks/ 开头时用 cp 落位）

纪律（本项目铁律）:
  * 绝不并发两个 telnet 会话（相机单核，会打挂）
  * 单次运行的循环长度 × 输出量要小（铁律 88）
  * 要落位的 .sh 必须 `sh -n` + md5 三方互证，别信 storbinary 的返回码
  * Windows 写的 .sh 先 assert 无 CRLF（铁律 99）
"""
from __future__ import annotations

import hashlib
import ftplib
import os
import socket
import sys
import time

HOST = os.environ.get("NXHOST", "192.168.0.105")
# ★ FTP 根 = SD 卡根（/mnt/mmc）⇒ FTP 侧路径与机上路径不是一回事，别混用：
#   历史坑：把机上路径 "/mnt/mmc/_xfer/x" 直接丢给 STOR ⇒ busybox ftpd 回 553 Error
FTP_XFER = "/_xfer"
FS_XFER = "/mnt/mmc/_xfer"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sysarch"))
from minitel import MiniTel  # noqa: E402


def md5f(p):
    h = hashlib.md5()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def port_ok(p, tries=3, gap=3):
    for _ in range(tries):
        s = socket.socket()
        s.settimeout(4)
        try:
            s.connect((HOST, p))
            return True
        except Exception:
            time.sleep(gap)
        finally:
            try:
                s.close()
            except Exception:
                pass
    return False


def telnet(cmd, wait=12.0):
    t = MiniTel(HOST, timeout=25)
    t.read(2)
    t.send("root", 2)
    t.send("", 2)
    time.sleep(0.6)
    out = t.send(cmd, wait)
    try:
        out += t.read(2)
    except Exception:
        pass
    t.close()
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    a = sys.argv[1]

    if a == "probe":
        for p in (21, 23):
            print("%-6s %s" % ("%d" % p, "OPEN" if port_ok(p, tries=1) else "CLOSED"))
        return 0

    if a == "run":
        if len(sys.argv) < 3:
            print('用法: cam.py run "cmd"')
            return 2
        if not port_ok(23, tries=3, gap=3):
            print("★ telnet 不可达（整机离线？）")
            return 1
        print("----------- 机上输出 -----------")
        print(telnet(sys.argv[2], wait=float(os.environ.get("NXWAIT", "12"))).strip())
        print("-------------------------------")
        return 0

    if a in ("put", "deploy"):
        if len(sys.argv) < 4:
            print("用法: cam.py %s <local> <remote>" % a)
            return 2
        local, remote = sys.argv[2], sys.argv[3]
        d = open(local, "rb").read()
        if local.endswith(".sh"):
            assert b"\r\n" not in d, "%s 含 CRLF（铁律 99）" % local
        print("[local] %-30s %7d B  md5=%s" % (os.path.basename(local), len(d), md5f(local)))
        if not port_ok(21):
            print("★ FTP 不可达")
            return 1
        f = ftplib.FTP(HOST, timeout=60)
        f.login("root", "")
        try:
            f.mkd(FTP_XFER)
        except Exception:
            pass
        name = os.path.basename(remote)
        with open(local, "rb") as fh:
            f.storbinary("STOR %s/%s" % (FTP_XFER, name), fh, blocksize=32768)
        f.quit()
        print("[ftp] -> %s/%s" % (FTP_XFER, name))

        if a == "put":
            return 0

        cmd = "cp -f %s/%s %s; " % (FS_XFER, name, remote)
        if remote.endswith(".sh"):
            cmd += "chmod +x %s; sh -n %s && echo SYNTAX-OK; " % (remote, remote)
        cmd += "md5sum %s; ls -la %s" % (remote, remote)
        if not port_ok(23, tries=3, gap=3):
            print("★ telnet 不可达，文件已在 %s/%s，可稍后手动 cp" % (FS_XFER, name))
            return 1
        print("----------- 机上自证 -----------")
        print(telnet(cmd, wait=15).strip())
        print("[want] md5=%s" % md5f(local))
        print("-------------------------------")
        return 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
