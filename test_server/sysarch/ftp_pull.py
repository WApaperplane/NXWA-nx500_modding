#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ftp_pull.py —— 从 NX 相机批量拉取文件（带重试，应对不稳网络）

用法:
  python ftp_pull.py <outdir> <remote1> [remote2 ...] [--host=192.168.0.106]
  remote 为 FTP 绝对路径（如 /emmcbak/p7.bin）
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
outdir, remotes = args[0], args[1:]
os.makedirs(outdir, exist_ok=True)

for remote in remotes:
    name = os.path.basename(remote)
    local = os.path.join(outdir, name)
    if os.path.exists(local) and os.path.getsize(local) > 0:
        print(f"skip {name} (exists)", flush=True)
        continue
    ok = False
    for attempt in range(1, 4):
        try:
            t0 = time.time()
            ftp = ftplib.FTP(host, timeout=60)
            ftp.login("root", "")
            ftp.set_pasv(True)
            done = [0]

            def cb(block):
                done[0] += len(block)

            with open(local, "wb") as f:
                ftp.retrbinary(f"RETR {remote}", f.write, blocksize=1 << 16)
            ftp.quit()
            el = max(time.time() - t0, 1e-9)
            print(f"OK  {name}  {done[0]/1e6:.1f} MB  {el:.0f}s  {done[0]/1e6/el:.2f} MB/s", flush=True)
            ok = True
            break
        except Exception as e:  # noqa: BLE001
            print(f"retry {name} (attempt {attempt}): {e}", flush=True)
            try:
                os.remove(local)
            except OSError:
                pass
            time.sleep(3)
    if not ok:
        print(f"FAIL {name}", flush=True)
