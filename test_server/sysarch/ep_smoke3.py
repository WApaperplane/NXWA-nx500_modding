# -*- coding: utf-8 -*-
"""epdump3 单发验证：只跑一次，立刻拉回，立刻断开
   ★ 上次 v2 文本版 324KB 输出把相机打死。本版二进制 44KB。
   ★ 单核铁律：一个脚本最多 3 条 telnet 命令，跑完就撤。
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minitel import MiniTel
import ftplib

HOST = '192.168.0.105'
X = '/mnt/mmc/_xfer'
BB = '/opt/usr/nx-ks/busybox'
HERE = os.path.dirname(os.path.abspath(__file__))
ARM = os.path.join(HERE, 'epdump3.arm')
OUT = os.path.join(HERE, 'raw7')
TAG = sys.argv[1] if len(sys.argv) > 1 else 'smoke'

os.makedirs(OUT, exist_ok=True)

f = ftplib.FTP(HOST, timeout=30); f.login(); f.cwd('/_xfer')
with open(ARM, 'rb') as fh:
    f.storbinary('STOR epdump3.arm', fh)
f.quit()
print('uploaded %d bytes' % os.path.getsize(ARM))

t = MiniTel(HOST); t.read(3); t.send('root', 2); t.send('', 2)
t.send('%s chmod 755 %s/epdump3.arm' % (BB, X), 3)
# 只跑一次，立刻计时
t.send('S=$(date +%s); {0}/epdump3.arm {1}; R=$?; E=$(date +%s); '
       'echo RC=$R > {0}/t_{1}.txt; echo SEC=$((E-S)) >> {0}/t_{1}.txt'.format(X, TAG), 45)
time.sleep(1)
t.send('cat %s/t_%s.txt; ls -l %s/ep_%s.bin' % (X, TAG, X, TAG), 12)
time.sleep(1)
t.close()
print('--- telnet closed, cooling 5s ---')
time.sleep(5)

f = ftplib.FTP(HOST, timeout=60); f.login(); f.cwd('/_xfer')
names = f.nlst()
for fn in ('ep_%s.bin' % TAG, 't_%s.txt' % TAG):
    if fn not in names:
        print('  MISS %s' % fn); continue
    p = os.path.join(OUT, fn)
    with open(p, 'wb') as fh:
        f.retrbinary('RETR ' + fn, fh.write)
    print('  GOT  %-22s %d bytes' % (fn, os.path.getsize(p)))
f.quit()