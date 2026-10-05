# -*- coding: utf-8 -*-
"""ISO 枚举实测：一次 telnet 会话内逐个试写 + 逐个回读，结果各存独立文件
★ 为什么不用覆盖写同一个文件：那样只能拿到最后一份。
★ 为什么必须回读：`UserData is not set` 只说明参数格式/取值非法，
  不能替代「回读值确实变成我写的那个」。
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minitel import MiniTel
import ftplib

HOST = '192.168.0.105'
X = '/mnt/mmc/_xfer'
BB = '/opt/usr/nx-ks/busybox'
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw7')

IDX = int(sys.argv[1]) if len(sys.argv) > 1 else 5
PREFIX = {5: 0x00050000, 30: 0x001E0000, 60: 0x003C0000}[IDX]
NMAX = 14
LO, HI = 0, NMAX


def main():
    os.makedirs(OUT, exist_ok=True)
    t = MiniTel(HOST); t.read(3); t.send('root', 2); t.send('', 2)
    t.send('st app mode a', 10)
    time.sleep(3)

    fns = []
    # 初值
    t.send('{ st cap capdtm getusr %d; } > %s/iso_%d_n00.txt 2>&1' % (IDX, X, IDX), 8)
    fns.append('iso_%d_n00.txt' % IDX)

    for n in range(LO, HI + 1):
        v = PREFIX | n
        t.send('{ st cap capdtm setusr %d 0x%08x; } > %s/iso_%d_n%02d_w.txt 2>&1'
               % (IDX, v, X, IDX, n), 7)
        time.sleep(1.0)
        t.send('{ st cap capdtm getusr %d; } > %s/iso_%d_n%02d_r.txt 2>&1'
               % (IDX, X, IDX, n), 7)
        time.sleep(0.7)

    # 恢复初值（ISO_AUTO / ISONR_MID等，n=0 即原值）
    t.send('{ st cap capdtm setusr %d 0x%08x; } > %s/iso_%d_restore_w.txt 2>&1'
           % (IDX, PREFIX, X, IDX), 8)
    time.sleep(2)
    t.send('{ st cap capdtm getusr %d; } > %s/iso_%d_restore_r.txt 2>&1' % (IDX, X, IDX), 8)
    time.sleep(1)
    t.close()
    print('session done, pulling ...')
    time.sleep(1)

    f = ftplib.FTP(HOST, timeout=90); f.login(); f.cwd('/_xfer')
    names = set(f.nlst())

    def rd(fn):
        if fn not in names:
            return '(missing)'
        buf = []
        f.retrbinary('RETR ' + fn, lambda b: buf.append(b))
        return ' '.join(b''.join(buf).decode('utf-8', 'replace').split())

    print('\nidx %d  prefix=0x%08x' % (IDX, PREFIX))
    print('  原始: %s' % rd('iso_%d_n00.txt' % IDX))
    print('\n  n    写入值写入结果                 回读')
    ok_list = []
    for n in range(LO, HI + 1):
        w = rd('iso_%d_n%02d_w.txt' % (IDX, n))
        r = rd('iso_%d_n%02d_r.txt' % (IDX, n))
        v = PREFIX | n
        good = ('0x%x' % v) in r.replace('0x', '0x').lower() or \
               ('%x' % v) in r.lower().replace('0x', '')
        mark = 'OK ' if good else '   '
        if good:
            ok_list.append((n, v, r))
        print('  %s%-3d 0x%08x  %-22s %s' % (mark, n, v, w[:22], r[:52]))
    print('\n  恢复后: %s' % rd('iso_%d_restore_r.txt' % IDX))
    print('\n  == 生效枚举 ==')
    for n, v, r in ok_list:
        print('    n=%-3d 0x%08x  %s' % (n, v, r[:60]))
    f.quit()

    with open(os.path.join(OUT, 'iso_enum_%d.txt' % IDX), 'w',
              encoding='utf-8') as fh:
        for n, v, r in ok_list:
            fh.write('0x%08x\t%s\n' % (v, r))
    return 0


if __name__ == '__main__':
    sys.exit(main())