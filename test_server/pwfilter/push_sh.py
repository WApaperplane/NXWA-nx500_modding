#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""push_sh.py — 上传 shell 脚本到 NX500（base64 整块直传，规避 echo 对中文的破坏）
用法: python push_sh.py <本地路径> [相机端路径]
"""
import base64
import socket
import sys
import time

HOST = sys.argv[3] if len(sys.argv) > 3 else '192.168.0.105'
LOCAL = sys.argv[1]
DEST = sys.argv[2] if len(sys.argv) > 2 else '/opt/storage/sdcard/_pwtest/filmlab-apply.sh'

raw = open(LOCAL, 'rb').read()
# ★ 强制 CRLF -> LF。Windows 端写文件默认 CRLF，而相机 busybox ash 会把 \r
#   当命令一部分 → 空行变": command not found"、函数定义变 "syntax error near '{'"。
#   这是踩过的坑，转换放在上传器里统一做。
if b'\r\n' in raw:
    raw = raw.replace(b'\r\n', b'\n')
b64 = base64.b64encode(raw).decode()
lines = [b64[i:i + 76] for i in range(0, len(b64), 76)]

s = socket.create_connection((HOST, 23), timeout=10)
s.settimeout(2.0)


def drain(t=1.0):
    end = time.time() + t
    out = b''
    while time.time() < end:
        try:
            c = s.recv(8192)
        except socket.timeout:
            continue
        if not c:
            break
        out += c
    cl = bytearray()
    i = 0
    while i < len(out):
        if out[i] == 0xFF and i + 2 < len(out):
            i += 3
            continue
        cl.append(out[i])
        i += 1
    return bytes(cl).decode('utf-8', 'replace')


drain(2.0)
s.sendall(b'root\n')
drain(2.0)

s.sendall(b'rm -f /tmp/pp.b64\n')
time.sleep(0.4)
drain(0.4)

# ★ 整块base64 分行 echo，每行 76 字符（base64 纯 ASCII，echo 安全）
for ln in lines:
    s.sendall(('echo %s >> /tmp/pp.b64\n' % ln).encode())
    time.sleep(0.07)
drain(1.5)

s.sendall(b'/opt/usr/nx-ks/busybox base64 -d /tmp/pp.b64 > %s\n' % DEST.encode())
time.sleep(1.5)
drain(1.0)
s.sendall(b'chmod +x %s; ls -la %s; md5sum %s\n' % (DEST.encode(), DEST.encode(), DEST.encode()))
time.sleep(1.2)
print(drain(1.8))
s.close()
