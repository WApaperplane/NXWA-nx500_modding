#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ftp_get.py — NX500 相机 FTP 拉取（单文件 / 批量）

FTP 已在听 21 端口（tcpsvd），root 空密码，**FTP 根 = SD 卡**（/opt/storage/sdcard）。
因此系统文件（/usr/lib/...）必须先在相机上 cp 到 /mnt/mmc/_xfer/ 才能拉。
★ `_` 开头目录在某些 FTP 实现里要单独 cwd —— 本脚本已自动处理。

用法:
  python ftp_get.py <远端路径> <本地路径>            # 单文件
  python ftp_get.py --batch <本地目录> <远端文件...> # 批量
  python ftp_get.py --ls <远端目录>                  # 列目录
"""
import ftplib
import os
import sys

HOST = '192.168.0.105'
XFER = '/mnt/mmc/_xfer'      # 相机端中转目录


def _connect():
    f = ftplib.FTP(HOST, timeout=60)
    f.login('root', '')
    return f


def ls(remote_dir):
    f = _connect()
    total = 0
    for name, facts in f.mlsd(remote_dir):
        size = int(facts.get('size', 0) or 0)
        kind = facts.get('type', '?')
        if kind == 'file':
            total += size
        print('  %-6s %10d  %s' % (kind, size, name))
    print('  合计 %d 字节' % total)
    f.quit()


def get(remote, local):
    """remote 若是 /mnt/mmc 下的绝对路径，转成 FTP 相对路径（FTP 根 = SD 卡）。"""
    if remote.startswith('/mnt/mmc'):
        rpath = remote[len('/mnt/mmc'):]      # -> /_xfer/xxx
        cwd = XFER
    else:
        rpath = remote
        cwd = '/'
    f = _connect()
    size = 0
    for try_cwd, try_rel in ((cwd, rpath), ('/', remote), ('/', rpath.lstrip('/'))):
        try:
            f.cwd(try_cwd)
            size = f.size(try_rel)
            cwd, rpath = try_cwd, try_rel
            break
        except Exception:
            continue
    else:
        raise RuntimeError('找不到 %s' % remote)
    print('  %s:%s%s  (%d 字节)' % (HOST, cwd, rpath, size))
    os.makedirs(os.path.dirname(os.path.abspath(local)), exist_ok=True)
    with open(local, 'wb') as fo:
        f.retrbinary('RETR ' + rpath, fo.write, 65536)
    f.quit()
    got = os.path.getsize(local)
    print('  %s 已保存 %d 字节 -> %s' % ('OK  ' if got == size else 'MISMATCH!', got, local))
    return got == size


def batch(localdir, remotes):
    ok = fail = 0
    for r in remotes:
        base = os.path.basename(r.rstrip('/')) or 'unnamed'
        try:
            if get(r, os.path.join(localdir, base)):
                ok += 1
            else:
                fail += 1
        except Exception as e:
            print('  FAIL %s : %s' % (r, e))
            fail += 1
    print('\n== 批量完成: 成功 %d, 失败 %d ==' % (ok, fail))
    return fail


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    if sys.argv[1] == '--ls':
        ls(sys.argv[2])
    elif sys.argv[1] == '--batch':
        batch(sys.argv[2], sys.argv[3:])
    else:
        get(sys.argv[1], sys.argv[2])
