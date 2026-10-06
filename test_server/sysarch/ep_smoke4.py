# -*- coding: utf-8 -*-
"""epdump4 单发定位：先只 dump 1 个块（NOG 最小），确认不崩再全量
   ★ 单核铁律：一个脚本最多 3 条 telnet 命令
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minitel import MiniTel
import ftplib

HOST = '192.168.0.105'
X = '/mnt/mmc/_xfer'
BB = '/opt/usr/nx-ks/busybox'
HERE = os.path.dirname(os.path.abspath(__file__))
ARM = os.path.join(HERE, 'epdump4.arm')
OUT = os.path.join(HERE, 'raw7')
TAG = sys.argv[1] if len(sys.argv) > 1 else 'p1'
FIRST = sys.argv[2] if len(sys.argv) > 2 else '0'
CNT = sys.argv[3] if len(sys.argv) > 3 else '1'

os.makedirs(OUT, exist_ok=True)

f = ftplib.FTP(HOST, timeout=30); f.login(); f.cwd('/_xfer')
with open(ARM, 'rb') as fh:
    f.storbinary('STOR epdump4.arm', fh)
f.quit()
print('uploaded %d bytes; dump blocks [%s,+%s)' % (
    os.path.getsize(ARM), FIRST, CNT))

t = MiniTel(HOST); t.read(3); t.send('root', 2); t.send('', 2)
t.send('{0} chmod 755 {0}/epdump4.arm'.format(X), 3)
t.send('{0}/epdump4.arm {1} {2} {3}; echo RC=$? > {0}/r_{1}.txt'.format(
    X, TAG, FIRST, CNT), 40)
time.sleep(1)
t.send('cat {0}/r_{1}.txt; ls -l {0}/ep_{1}.bin'.format(X, TAG), 12)
time.sleep(1)
t.close()
print('--- closed, cooling 5s ---')
time.sleep(5)

f = ftplib.FTP(HOST, timeout=60); f.login(); f.cwd('/_xfer')
names = f.nlst()
for fn in ('ep_%s.bin' % TAG, 'r_%s.txt' % TAG):
    if fn not in names:
        print('  MISS %s' % fn); continue
    p = os.path.join(OUT, fn)
    with open(p, 'wb') as fh:
        f.retrbinary('RETR ' + fn, fh.write)
    print('  GOT  %-22s %d bytes' % (fn, os.path.getsize(p)))
f.quit()