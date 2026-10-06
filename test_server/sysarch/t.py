#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""telnet 串行执行器 v2 —— 复用已验证的 minitel.MiniTel（已处理 IAC 协商）

★ 铁律：telnet 必须串行，一次只跑一条命令，绝不并发。
★ 铁律：CRLF 是本项目头号坑 —— 一律用带标记的 echo 精确切分。

用法: python t.py "<shell 命令>"
"""
import sys
import time

from minitel import MiniTel

HOST = "192.168.0.105"
M1 = "zZbGaN"
M2 = "zZeNdD"


def run(cmd, timeout=30.0):
    t = MiniTel(HOST, 23, timeout=int(timeout) + 10)
    try:
        t.read(3.0)                 # 等 login 提示
        t.send("root", wait=2.0)     # telnet root 空密码
        t.read(1.5)
        t.send("echo READY", wait=1.5)
        txt = t.read(2.0)
        if "READY" not in txt:
            # 有些情况第一句就进去了
            pass
        t.send("echo %s" % M1, wait=0.8)
        t.send(cmd, wait=timeout)      # ★ 等命令跑完
        t.send("echo %s" % M2, wait=1.5)
        out = t.read(2.5)
        i = out.rfind(M1)
        j = out.rfind(M2)
        if i >= 0 and j > i:
            return out[i + len(M1):j].replace("\r\n", "\n").strip("\n").strip()
        return out.replace("\r\n", "\n").strip()
    finally:
        t.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('用法: t.py "<cmd>"')
        sys.exit(1)
    print(run(sys.argv[1]))