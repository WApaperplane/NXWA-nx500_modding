# -*- coding: utf-8 -*-
"""实验③：不同 ISO 下的 NOG / EP 全块dump
★ ISO 枚举已由iso_enum.py 5 实测回读确认（不是猜的）：
    n=0  ISO_AUTO     0x00050000
    n=1  ISO_100      0x00050001
    ...
    n=8  ISO_6400x00050009
    n=10 ISO_800      0x0005000a
    n=14 ISO_20000x0005000e
设计（唯一变量 + 漂移基线 + 复原）：
    n0(ISO_200) ─ n1(ISO_6400) ─ n2(ISO_2000) ─ n3(回到 ISO_200)
判据：
    J1 n0==n3（ISO 可逆，dump 无漂移）
    J2 n0 != n1 或 n0 != n2（ISO 档位真的在 EP 留痕）
    ★ 若 n1 与 n0 的 NOG 完全相同 ⇒ NOG 不是 ISO 的落点，需要换块看。
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minitel import MiniTel
import ftplib, hashlib

HOST = '192.168.0.105'
X = '/mnt/mmc/_xfer'
BB = '/opt/usr/nx-ks/busybox'
HERE = os.path.dirname(os.path.abspath(__file__))
ARM = os.path.join(HERE, 'epdump2.arm')
OUT = os.path.join(HERE, 'raw7')

ISO = {200: 0x00050004, 640: 0x00050009, 800: 0x0005000a,
       1250: 0x0005000c, 2000: 0x0005000e}
AUTO = 0x00050000

# (tag, ISO 档位, 回读)
PLAN = [
    ('i0_iso200', 200, None),
    ('i1_iso640', 640, None),
    ('i2_iso2000', 2000, None),
    ('i3_back200', 200, None),
]


def sh(t, cmd, wait=8, tag='_last.txt'):
    t.send('{ %s; } > %s/%s 2>&1; echo "RC=$?" >> %s/%s' % (cmd, X, tag, X, tag), wait)
    time.sleep(1)


def main():
    os.makedirs(OUT, exist_ok=True)
    f = ftplib.FTP(HOST, timeout=30); f.login(); f.cwd('/_xfer')
    with open(ARM, 'rb') as fh:
        f.storbinary('STOR epdump2.arm', fh)
    f.quit()
    print('uploaded %d bytes' % os.path.getsize(ARM))

    t = MiniTel(HOST); t.read(3); t.send('root', 2); t.send('', 2)
    t.send('%s chmod 755 %s/epdump2.arm' % (BB, X), 5)
    t.send('st app mode a', 12)
    time.sleep(3)
    t.send('{ st cap capdtm getusr 5; } > %s/i_env0.txt 2>&1' % X, 8)

    for tag, iso, _ in PLAN:
        v = ISO[iso]
        print('>>> %s  ISO%d=0x%08x' % (tag, iso, v))
        sh(t, 'st cap capdtm setusr 5 0x%08x' % v, 10, '%s_w.txt' % tag)
        time.sleep(3)                    # ★ 给 ISP 充分的自动曝光/降噪重算时间
        sh(t, 'st cap capdtm getusr 5', 10, '%s_r.txt' % tag)
        sh(t, 'nice -n 19 %s/epdump2.arm %s 256' % (X, tag), 25, '%s_d.txt' % tag)
        time.sleep(3)

    # 恢复 AUTO
    sh(t, 'st cap capdtm setusr 5 0x%08x' % AUTO, 10, 'i_restore_w.txt')
    time.sleep(2)
    sh(t, 'st cap capdtm getusr 5', 10, 'i_restore_r.txt')
    t.close()
    print('\npulling ...')
    time.sleep(1)

    f = ftplib.FTP(HOST, timeout=120); f.login(); f.cwd('/_xfer')
    names = set(f.nlst())

    def rd(fn):
        if fn not in names:
            return '(missing)'
        buf = []
        f.retrbinary('RETR ' + fn, lambda b: buf.append(b))
        return ' '.join(b''.join(buf).decode('utf-8', 'replace').split())

    print('\n===== 自证 =====')
    print('  初始 : %s' % rd('i_env0.txt')[:70])
    for tag, iso, _ in PLAN:
        print('  %-12s w=%-20s r=%s' % (tag, rd('%s_w.txt' % tag)[:20],
                                        rd('%s_r.txt' % tag)[:46]))
    print('  恢复  : %s' % rd('i_restore_r.txt')[:70])

    print('\n===== 拉回与md5 =====')
    h = {}
    for tag, _, _ in PLAN:
        fn = 'ep_%s.txt' % tag
        if fn in names:
            p = os.path.join(OUT, fn)
            with open(p, 'wb') as fh:
                f.retrbinary('RETR ' + fn, fh.write)
            h[tag] = hashlib.md5(open(p, 'rb').read()).hexdigest()
            print('  %-12s %d B  %s' % (tag, os.path.getsize(p), h[tag]))
    f.quit()

    if len(h) == 4:
        print('\n  J1 可逆(i0==i3): %s' % ('PASS' if h['i0_iso200'] == h['i3_back200'] else 'FAIL'))
        print('  J2 有变化(200 vs 6400): %s' % ('DIFF' if h['i0_iso200'] != h['i1_iso640'] else 'SAME'))
        print('     200 vs 2000        : %s' % ('DIFF' if h['i0_iso200'] != h['i2_iso2000'] else 'SAME'))
    return 0


if __name__ == '__main__':
    sys.exit(main())