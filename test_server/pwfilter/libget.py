#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量 FTP 拉取（相机 tcpsvd 只支持相对根的路径，用 cwd 逐层进）"""
import ftplib, os, sys

HOST = '192.168.0.105'
RPARTS = ['_fl2', 'lib']
LOCAL = sys.argv[1] if len(sys.argv) > 1 else 'sysroot/lib'

f = ftplib.FTP(HOST, timeout=90)
f.login('root', '')
for p in RPARTS[:-1]:
    f.cwd('/' + p)          # 相机 FTP 对绝对路径会 550
names = f.nlst(RPARTS[-1])
f.quit()
print('远端 %d 个文件' % len(names))

f = ftplib.FTP(HOST, timeout=90)
f.login('root', '')
for p in RPARTS[:-1]:
    f.cwd('/' + p)
ok = fail = 0
for n in names:
    bn = n.strip().split('/')[-1]
    if not bn or bn in ('.', '..'):
        continue
    try:
        data = bytearray()
        f.retrbinary('RETR ' + n, data.extend)
        open(os.path.join(LOCAL, bn), 'wb').write(bytes(data))
        print('  OK   %-40s %9d' % (bn, len(data)))
        ok += 1
    except Exception as e:
        print('  FAIL %-40s %s' % (bn, e))
        fail += 1
f.quit()
print('成功 %d  失败 %d  -> %s' % (ok, fail, LOCAL))
