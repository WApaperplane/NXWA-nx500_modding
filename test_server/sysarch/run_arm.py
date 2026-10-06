# -*- coding: utf-8 -*-
"""通用：投递任意 .arm 到相机并运行、拉回输出
   用法: python run_arm.py <local.arm> <mode-args|-> [outname]
   ★ telnet 串行，一次只跑一个。
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
    src    = sys.argv[1]
    outnam = sys.argv[-1]
    args   = ' '.join(sys.argv[2:-1])
    if not args:
        args = '-'
    if not os.path.exists(src):
        print('MISSING', src); return 1
    base = os.path.basename(src)
    os.makedirs(OUT, exist_ok=True)

    f = ftplib.FTP(HOST, timeout=30); f.login(); f.cwd('/_xfer')
    with open(src, 'rb') as fh:
        f.storbinary('STOR ' + base, fh)
    f.quit()
    print('uploaded %s (%d bytes)' % (base, os.path.getsize(src)))

    t = MiniTel(HOST)
    t.read(3); t.send('root', 2); t.send('', 2)
    cmdline = '{ echo "=== run ==="; %s/%s %s; echo "EXIT=$?"; } > %s/%s 2>&1' % (
        X, base, ('' if args == '-' else args), X, outnam)
    t.send('chmod 755 %s/%s' % (X, base), 2)
    out = t.send(cmdline, 30)
    print('tail:', (out or '')[-200:])
    t.close()
    time.sleep(3)

    f = ftplib.FTP(HOST, timeout=30); f.login(); f.cwd('/_xfer')
    p = os.path.join(OUT, outnam)
    try:
        with open(p, 'wb') as fh:
            f.retrbinary('RETR ' + outnam, fh.write)
    except Exception as e:
        print('PULL FAIL', e); return 1
    f.quit()
    print('\n============ %s ============' % outnam)
    print(open(p, encoding='utf-8', errors='replace').read())
    return 0


if __name__ == '__main__':
    sys.exit(main())