# -*- coding: utf-8 -*-
"""epdump9 全量 dump（纯二进制 44KB）+ 校验
   ★ telnet 只跑一次，跑完立刻断开
用法: python ep_dump7.py <tag>
"""
import sys, os, time, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minitel import MiniTel
import ftplib

HOST = '192.168.0.105'
X = '/mnt/mmc/_xfer'
HERE = os.path.dirname(os.path.abspath(__file__))
ARM = os.path.join(HERE, 'epdump9.arm')
OUT = os.path.join(HERE, 'raw7')
TAG = sys.argv[1] if len(sys.argv) > 1 else 'v7'

BLK_NAME = ['top','ldc','mc','rsz','lvr','bblt','fd','jpeg','3dlut','nog']
os.makedirs(OUT, exist_ok=True)

f = ftplib.FTP(HOST, timeout=30); f.login(); f.cwd('/_xfer')
with open(ARM, 'rb') as fh:
    f.storbinary('STOR epdump9.arm', fh)
f.quit()
print('uploaded %d bytes' % os.path.getsize(ARM))

t = MiniTel(HOST); t.read(3); t.send('root', 2); t.send('', 2)
t.send('{0} chmod 755 {0}/epdump9.arm'.format(X), 3)
r = t.send('{0}/epdump9.arm {1}; echo RC=$? > {0}/rc9_{1}.txt'.format(X, TAG), 45)
print('telnet:', ' '.join((r or '').split())[-120:])
time.sleep(2)
t.close()
print('--- closed, cooling 6s ---')
time.sleep(6)

f = ftplib.FTP(HOST, timeout=60); f.login(); f.cwd('/_xfer')
names = f.nlst()
fn = 'ep_%s.bin' % TAG
if fn not in names:
    print('  MISS %s' % fn); f.quit(); sys.exit(1)
p = os.path.join(OUT, fn)
with open(p, 'wb') as fh:
    f.retrbinary('RETR ' + fn, fh.write)
print('  GOT  %-22s %d bytes' % (fn, os.path.getsize(p)))
if ('rc9_%s.txt' % TAG) in names:
    rp = os.path.join(OUT, 'rc9_%s.txt' % TAG)
    with open(rp, 'wb') as fh:
        f.retrbinary('RETR rc9_%s.txt' % TAG, fh.write)
    print('  RC =', open(rp).read().strip())
f.quit()

# ---- 校验 ----
d = open(p, 'rb').read()
w = list(struct.unpack('<%dI' % (len(d)//4), d[:len(d)//4*4]))
magic, ver, nblk, tot = w[0], w[1], w[2], w[3]
starts = w[4:14]
sizes = w[14:24]
print('\nmagic=%08x ver=%d nblk=%d total=0x%x filesize=%d' % (magic, ver, nblk, tot, len(d)))
expect = 0
for i in range(10):
    print('  %-6s start=0x%08x size=0x%04x' % (BLK_NAME[i], starts[i], sizes[i]))
    expect += sizes[i]
print('payload expect=%d  header=96  tail=44  total=%d' % (expect, 96+expect+44))

off = 96
for i in range(10):
    chunk = d[off:off+sizes[i]]
    nz = sum(1 for k in range(0, len(chunk)-3, 4)
             if chunk[k:k+4] != b'\0\0\0\0' and chunk[k:k+4] != b'\xff\xff\xff\xff')
    if len(chunk) < 32:
        print('  %-6s off=%6d  *** BLOCK TOO SMALL (%d B) - dump aborted early' % (
            BLK_NAME[i], off, len(chunk)))
        break
    print('  %-6s off=%6d first8=%s nonzero/nonFF=%d/%d' % (
        BLK_NAME[i], off,
        ' '.join('%08x' % x for x in struct.unpack_from('<8I', chunk, 0)),
        nz, sizes[i]//4))
    off += sizes[i]
print('tail:', ' '.join('%08x' % x for x in w[off//4:]))
