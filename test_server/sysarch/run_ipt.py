# -*- coding: utf-8 -*-
"""IPCC ioctl 逐格探测：每次进程只调一个 ioctl，崩了也知道崩在哪格。
   用法: python run_ipt.py 3 4 5 20 21 ...   （3|16|bit 表示 size8，3 表示 size4）
   ★ telnet 串行，一次只跑一个进程，绝不并发。
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minitel import MiniTel
import ftplib

HOST = '192.168.0.105'
X    = '/mnt/mmc/_xfer'
HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, 'raw5')


def main():
    args = sys.argv[1:]
    if not args:
        print('need nr list, e.g. 3 4 5 19 20 21'); return 1
    src = os.path.join(HERE, 'probe_src', 'ipt.arm')
    os.makedirs(OUT, exist_ok=True)

    f = ftplib.FTP(HOST, timeout=30); f.login(); f.cwd('/_xfer')
    with open(src, 'rb') as fh:
        f.storbinary('STOR ipt.arm', fh)
    f.quit()
    print('uploaded ipt.arm')

    results = {}
    for a in args:
        tag = 'ipt_%s' % a
        t = MiniTel(HOST)
        t.read(3); t.send('root', 2); t.send('', 2)
        t.send('chmod 755 %s/ipt.arm' % X, 1.5)
        t.send('{ /%s/ipt.arm %s; echo "EXIT=$?"; } > %s/%s 2>&1' % (X, a, X, tag), 6)
        t.close()
        time.sleep(1.5)
        try:
            f = ftplib.FTP(HOST, timeout=30); f.login(); f.cwd('/_xfer')
            p = os.path.join(OUT, tag)
            with open(p, 'wb') as fh:
                f.retrbinary('RETR ' + tag, fh.write)
            f.quit()
            txt = open(p, encoding='utf-8', errors='replace').read()
            results[a] = txt
            alive = 'SURVIVED' in txt
            print('--- nr=%s  %s' % (a, 'ALIVE' if alive else '*** DIED ***'))
            print(txt.strip())
        except Exception as e:
            print('--- nr=%s PULL FAIL %s' % (a, e))
    return 0


if __name__ == '__main__':
    sys.exit(main())