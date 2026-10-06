#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ftp_put.py — 通过 FTP 上传文件到 NX500（比 telnet base64 快 ~3 个数量级）

背景：FTP 已在听 21 端口（tcpsvd），root 空密码，**FTP 根 = SD 卡**（/opt/storage/sdcard）。
系统路径（/opt/usr/nx-ks/...）需要传两次：先传到 SD 的 _xfer/，再 telnet cp 到目标。

实测：telnet 传 320KB 会让相机过热重启；FTP 5MB/3.9s。
所以任何 ≥10KB 的文件都必须走 FTP。

用法:
  python ftp_put.py <本地路径> <SD内路径>
      例: python ftp_put.py out/lut3dl_probe.arm _pwtest/lut3dl_probe.arm
  → 完成后用 telnet cp 从 /mnt/mmc/<SD内路径> 搬到目标位置
"""
import ftplib
import os
import sys


def put(local, remote_sd, host='192.168.0.105'):
    data = open(local, 'rb').read()
    f = ftplib.FTP(host, timeout=60)
    f.login('root', '')
    # 确保目录存在
    d = os.path.dirname(remote_sd)
    if d:
        try:
            f.mkd(d)
        except Exception:
            pass
    # 目录切换（逐级，因为 _ 开头目录需绝对 cwd）
    parts = [p for p in remote_sd.split('/') if p]
    cur = '/'
    for p in parts[:-1]:
        cur = cur.rstrip('/') + '/' + p
        try:
            f.cwd(cur)
        except Exception:
            try:
                f.mkd(cur)
                f.cwd(cur)
            except Exception as e:
                print('  目录 %s 处理异常: %s' % (cur, e))
                f.cwd('/')
    import io
    buf = io.BytesIO(data)
    f.storbinary('STOR ' + parts[-1], buf, 65536)
    size = f.size(parts[-1])
    f.quit()
    ok = 'OK ' if size == len(data) else 'MISMATCH!'
    print('  %s 上传 %d 字节 -> %s%s' % (ok, size, cur + '/' if cur != '/' else '/', parts[-1]))
    return size == len(data)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    host = sys.argv[3] if len(sys.argv) > 3 else '192.168.0.105'
    put(sys.argv[1], sys.argv[2], host)
