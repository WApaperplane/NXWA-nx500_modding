# -*- coding: utf-8 -*-
"""单发验证：epdump2 能否在实机跑通并拉回（先证工具，再跑整轮）
   ★ 只读，不写任何 EP 寄存器
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minitel import MiniTel
import ftplib

HOST = '192.168.0.105'
X = '/mnt/mmc/_xfer'
BB = '/opt/usr/nx-ks/busybox'
HERE = os.path.dirname(os.path.abspath(__file__))
ARM = os.path.join(HERE, 'epdump2.arm')
OUT = os.path.join(HERE, 'raw7')
TAG = sys.argv[1] if len(sys.argv) > 1 else 'smoke'

os.makedirs(OUT, exist_ok=True)

f = ftplib.FTP(HOST, timeout=30); f.login(); f.cwd('/_xfer')
with open(ARM, 'rb') as fh:
    f.storbinary('STOR epdump2.arm', fh)
f.quit()
print('uploaded %d bytes' % os.path.getsize(ARM))

t = MiniTel(HOST); t.read(3); t.send('root', 2); t.send('', 2)
r = t.send('ls -l %s/epdump2.arm' % X, 6)
print('ls:', ' '.join(r.split())[:200])

r = t.send('time nice -n 19 %s/epdump2.arm %s 256 2>%s/err_%s.txt; echo RC=$?'
           % (X, TAG, X, TAG), 40)
print('run:', ' '.join(r.split())[-300:])
time.sleep(2)

t.send('ls -l %s/ep_%s.txt; cat %s/err_%s.txt; echo ---HEAD---; head -14 %s/ep_%s.txt; echo ---TAIL---; tail -3 %s/ep_%s.txt'
       % (X, TAG, X, TAG, X, TAG, X, TAG), 25)
time.sleep(2)
t.close()
print('\npulling ...')
time.sleep(1)

f = ftplib.FTP(HOST, timeout=60); f.login(); f.cwd('/_xfer')
names = f.nlst()
for fn in ('ep_%s.txt' % TAG, 'err_%s.txt' % TAG):
    if fn not in names:
        print('  MISS %s' % fn); continue
    p = os.path.join(OUT, fn)
    with open(p, 'wb') as fh:
        f.retrbinary('RETR ' + fn, fh.write)
    print('  GOT  %-24s %d bytes' % (fn, os.path.getsize(p)))
f.quit()