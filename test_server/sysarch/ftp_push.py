#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ftp_push.py —— 上传本地文件到 NX 相机 SD 卡（FTP 根 == SD 卡根）

用法:
  python ftp_push.py <local> <remote> [--host=192.168.0.106]
  remote 为 FTP 相对路径（如 /nx500.bin 或 nx500.bin）
"""
import ftplib
import os
import sys
import time

host = "192.168.0.106"
args = []
for a in sys.argv[1:]:
    if a.startswith("--host="):
        host = a.split("=", 1)[1]
    else:
        args.append(a)
local, remote = args[0], args[1]
if not remote.startswith("/"):
    remote = "/" + remote

size = os.path.getsize(local)
print(f"push {local} ({size} B) -> ftp://{host}{remote}", flush=True)
ftp = ftplib.FTP(host, timeout=60)
ftp.login("root", "")
ftp.set_pasv(True)
t0 = time.time()
done = [0]


def cb(block):
    done[0] += len(block)
    if done[0] % (16 << 20) < len(block):
        el = max(time.time() - t0, 1e-9)
        print(f"  {done[0]/1e6:7.1f} / {size/1e6:.1f} MB  {el:5.0f}s  {done[0]/1e6/el:5.2f} MB/s", flush=True)


with open(local, "rb") as f:
    ftp.storbinary(f"STOR {remote}", f, blocksize=1 << 16, callback=cb)
ftp.quit()
el = time.time() - t0
print(f"done in {el:.0f}s  avg {size/1e6/max(el,1e-9):.2f} MB/s", flush=True)
