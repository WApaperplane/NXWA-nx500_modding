# -*- coding: utf-8 -*-
"""epdump5 定位：分离"单次 write 大小"与"write 次数"两个变量
   ★ telnet 严格串行；每发一条等它跑完；跑完先断 telnet 再拉文件
用法: python ep_smoke5.py blk0_chunk4kblk0_chunk1k blk1_chunk4k
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minitel import MiniTel
import ftplib

HOST = '192.168.0.105'
X = '/mnt/mmc/_xfer'
BB = '/opt/usr/nx-ks/busybox'
HERE = os.path.dirname(os.path.abspath(__file__))
ARM = os.path.join(HERE, 'epdump5.arm')
OUT = os.path.join(HERE, 'raw7')

# (tag, blk, chunk)  —— 刻意设计成单变量对照
CASES = [
    ('c_b0_whole', 0, 0),    # 块0 7168B 一次 write      -> 若 OK，问题在 write 次数
    ('c_b0_1k',    0, 1024), # 块0 7168B 分 8 次 write   -> 对照
    ('c_b1_whole', 1, 0),    # 块1 4096B 一次 write      -> 尺寸减半对照
    ('c_b3_1k',    3, 1024), # 块3 4096B 分 4 次
    ('c_b9_1k',    9, 1024), # 块9 256B  分 1 次（已知 OK 的邻近点）
]

os.makedirs(OUT, exist_ok=True)

f = ftplib.FTP(HOST, timeout=30); f.login(); f.cwd('/_xfer')
with open(ARM, 'rb') as fh:
    f.storbinary('STOR epdump5.arm', fh)
f.quit()
print('uploaded %d bytes' % os.path.getsize(ARM))

t = MiniTel(HOST); t.read(3); t.send('root', 2); t.send('', 2)
t.send('{0} chmod 755 {0}/epdump5.arm'.format(X), 3)

for tag, blk, chunk in CASES:
    print('>>> %s (blk=%d chunk=%d)' % (tag, blk, chunk))
    t.send('{0}/epdump5.arm {1} {2} {3}; echo RC=$? > {0}/rc_{1}.txt'.format(
        X, tag, blk, chunk), 30)
    time.sleep(3)

t.close()
print('--- telnet closed, cooling 8s ---')
time.sleep(8)

f = ftplib.FTP(HOST, timeout=60); f.login(); f.cwd('/_xfer')
names = f.nlst()
for tag, blk, chunk in CASES:
    fn = '%s' % tag
    if fn not in names:
        print('  MISS %s' % fn); continue
    p = os.path.join(OUT, fn)
    with open(p, 'wb') as fh:
        f.retrbinary('RETR ' + fn, fh.write)
    rc = '?'
    rp = os.path.join(OUT, 'rc_%s.txt' % tag)
    if os.path.exists(rp):
        rc = open(rp).read().strip()
    print('  GOT  %-14s %7d bytes  %s' % (fn, os.path.getsize(p), rc))
f.quit()