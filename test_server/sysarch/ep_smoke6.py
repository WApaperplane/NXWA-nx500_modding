# -*- coding: utf-8 -*-
"""epdump6 逐 256B 扫块 0，定位不可读起始偏移
   ★ telnet 串行；单块扫描，负载极小
用法: python ep_smoke6.py [blk] [step]
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minitel import MiniTel
import ftplib

HOST = '192.168.0.105'
X = '/mnt/mmc/_xfer'
HERE = os.path.dirname(os.path.abspath(__file__))
ARM = os.path.join(HERE, 'epdump6.arm')
OUT = os.path.join(HERE, 'raw7')
BLK = sys.argv[1] if len(sys.argv) > 1 else '0'
STEP = sys.argv[2] if len(sys.argv) > 2 else '256'
TAG = 'scan_b%s_%s' % (BLK, STEP)

os.makedirs(OUT, exist_ok=True)

f = ftplib.FTP(HOST, timeout=30); f.login(); f.cwd('/_xfer')
with open(ARM, 'rb') as fh:
    f.storbinary('STOR epdump6.arm', fh)
f.quit()
print('uploaded %d bytes; scan blk=%s step=%s' % (os.path.getsize(ARM), BLK, STEP))

t = MiniTel(HOST); t.read(3); t.send('root', 2); t.send('', 2)
t.send('{0} chmod 755 {0}/epdump6.arm'.format(X), 3)
t.send('{0}/epdump6.arm {1} {2} {3}; echo RC=$? > {0}/rc_{1}.txt'.format(
    X, TAG, BLK, STEP), 40)
time.sleep(2)
t.close()
print('--- closed, cooling 6s ---')
time.sleep(6)

f = ftplib.FTP(HOST, timeout=60); f.login(); f.cwd('/_xfer')
names = f.nlst()
got = False
if TAG in names:
    p = os.path.join(OUT, TAG)
    with open(p, 'wb') as fh:
        f.retrbinary('RETR ' + TAG, fh.write)
    print('  GOT  %-22s %d bytes' % (TAG, os.path.getsize(p)))
    got = True
else:
    print('  MISS %s' % TAG)
if ('rc_%s.txt' % TAG) in names:
    rp = os.path.join(OUT, 'rc_%s.txt' % TAG)
    with open(rp, 'wb') as fh:
        f.retrbinary('RETR rc_%s.txt' % TAG, fh.write)
    print('  RC =', open(rp).read().strip())
f.quit()

# ---- 本地解析 ----
if got:
    import struct
    d = open(os.path.join(OUT, TAG), 'rb').read()
    w = struct.unpack('<%dI' % (len(d)//4), d[:len(d)//4*4])
    print('\nheader: magic=%08x base=0x%08x size=0x%x step=%d' % w[:4])
    i = 4
    s = 0
    while i < len(w):
        if w[i] & 0xF0000000 == 0xB0000000:
            s = w[i] & 0xFFFF
            if i+1 >= len(w):
                print('  step %2d off=0x%04x  -> FAULT (读后标记缺失)' % (s, s*int(STEP)))
                break
            val = w[i+1] & 0x0FFFFFFF
            print('  step %2d off=0x%04x  first_word=0x%08x' % (s, s*STEP, val))
            i += 2
        elif w[i] & 0xF0000000 == 0xA0000000:
            print('  (stray A marker at %d)' % i); i += 1
        elif w[i] & 0x60000000 == 0x60000000:
            print('  DONE nsteps=%d' % (w[i] & 0xfff)); i += 1
        else:
            i += 1
