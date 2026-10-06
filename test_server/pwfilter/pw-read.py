#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pw-read.py - 通过 telnet 读取 NX500 app 区 Picture Wizard 13x7 参数矩阵

用法: python pw-read.py [IP]
"""
import socket, sys, time, re

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.0.105"
STYLES = ['STANDARD', 'VIVID', 'PORTRAIT', 'LANDSCAPE', 'FOREST', 'RETRO', 'COOL',
          'CALM', 'CLASSIC', 'CUSTOM_1', 'CUSTOM_2', 'CUSTOM_3', 'CUSTOM_4']
PARAMS = ['R_COLOR', 'G_COLOR', 'B_COLOR', 'HUE', 'SATURATION', 'SHARPNESS', 'CONTRAST']
BASE = 0x0a3ec


def off(pi, si):
    return BASE + pi * 52 + si * 4


def telnet(cmds, wait=1.2):
    s = socket.create_connection((HOST, 23), timeout=10)
    s.settimeout(1.0)
    buf = b""

    def drain(t):
        nonlocal buf
        end = time.time() + t
        while time.time() < end:
            try:
                c = s.recv(8192)
                if not c:
                    break
                buf += c
            except socket.timeout:
                pass

    drain(2.0)
    s.sendall(b"root\n")
    drain(1.5)
    for c in cmds:
        buf = b""
        s.sendall((c + "\n").encode())
        drain(wait)
        txt = buf.decode("utf-8", "replace")
        txt = re.sub(r"[\x00-\x08\x0b-\x1f]", "", txt)
        yield c, txt
    s.close()


# 每行一个参数：13 次 prefman get，用 awk 抽取 value
rows = []
for pi, p in enumerate(PARAMS):
    parts = []
    for si in range(13):
        parts.append("prefman get 0 0x%05x l" % off(pi, si))
    # 用 grep -o 一次抽多个
    cmd = ";".join(parts) + "|grep -o 'value = [-0-9]*'"
    rows.append((p, cmd))

print("=== NX500 Picture Wizard 13x7 参数矩阵 (app 区) ===")
print("偏移: base=0x%05x, 参数步进=52(0x34), 风格步进=4\n" % BASE)

for (p, cmd), (c, txt) in zip(rows, telnet([r[1] for r in rows], wait=3.0)):
    vals = re.findall(r"value = (-?\d+)", txt)
    if len(vals) != 13:
        print("%-11s  !! 只读到 %d 个: %s" % (p, len(vals), vals))
    else:
        print("%-11s  %s" % (p, "  ".join("%4s" % v for v in vals)))
print()
print("风格顺序: " + "  ".join("%9s" % s for s in STYLES))