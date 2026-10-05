# -*- coding: utf-8 -*-
"""实验② 决定性版本：漂移对照 + 快门响应，一次跑完
★★ 为什么要对照：上一轮 before→after 有 19 处 ldc 变化，但那之间
   还执行了 `st app mode a`（DIALMODE 回读 = DIALMODE_APERTURE，确实切到 A 档了）
   ⇒ 变量不唯一，"ldc 变化" 既可能是快门也可能是切档，不能下结论。

本轮设计（唯一变量原则）：
  t0 ──无输入── t1 ──无输入── t2 ──快门── t3 ──无输入── t4
     ↑ 漂移基线↑ 漂移基线   ↑ 响应点    ↑ 保持性

判据（缺一不可，全部满足才算成立）：
  J1  t0==t1==t2（无输入时 EP 完全稳定，dump 本身不引入噪声）
  J2  t2 != t3（快门后有变化）
  J3  自证：DCIM 出现比拍摄时间更新的文件（快门真的响了）
  J1 不成立 ⇒ 前面看到的差异全是漂移，实验作废。
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
GAP = 7          # 每个 dump 之间的固定间隔（秒），必须一致


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

    # 模式与控制面自证
    sh(t, 'st app mode a', 12, 'r00_setmode.txt')
    time.sleep(4)
    sh(t, 'st cap capdtm getusr 0', 10, 'r01_dial.txt')
    sh(t, 'st cap capdtm getusr 20', 10, 'r02_pw.txt')
    sh(t, '{ date; ls -lt /mnt/mmc/DCIM/*/ 2>/dev/null | head -3; } > %s/r03_dcim_pre.txt 2>&1' % X, 12)

    tags = ['t0', 't1', 't2', 't3', 't4']
    for i, tg in enumerate(tags):
        if i == 3:
            print('>>> 快门')
            sh(t, 'st cap sh', 35, 'r10_shot.txt')
            time.sleep(GAP)
            sh(t, '{ date; ls -lt /mnt/mmc/DCIM/*/ 2>/dev/null | head -3; } '
                  '> %s/r04_dcim_post.txt 2>&1' % X, 12)
        print('>>> dump %s' % tg)
        sh(t, 'nice -n 19 %s/epdump2.arm r%s 256' % (X, tg), 25, 'r_%s.txt' % tg)
        time.sleep(GAP)

    t.close()
    print('\npulling ...')
    time.sleep(1)

    f = ftplib.FTP(HOST, timeout=120); f.login(); f.cwd('/_xfer')
    names = f.nlst()
    for tg in tags:
        fn = 'ep_r%s.txt' % tg
        if fn not in names:
            print('  MISS %s' % fn); continue
        p = os.path.join(OUT, fn)
        with open(p, 'wb') as fh:
            f.retrbinary('RETR ' + fn, fh.write)
        print('  GOT  %-16s %d B' % (fn, os.path.getsize(p)))
    for fn in ('r00_setmode.txt', 'r01_dial.txt', 'r02_pw.txt',
               'r03_dcim_pre.txt', 'r04_dcim_post.txt', 'r10_shot.txt'):
        if fn in names:
            with open(os.path.join(OUT, fn), 'wb') as fh:
                f.retrbinary('RETR ' + fn, fh.write)
    f.quit()

    def rd(fn):
        p = os.path.join(OUT, fn)
        return ' '.join(open(p, encoding='utf-8', errors='replace').read().split()) \
            if os.path.exists(p) else '(missing)'

    print('\n===== 自证 =====')
    print('  setmode : %s' % rd('r00_setmode.txt')[:90])
    print('  DIAL    : %s' % rd('r01_dial.txt')[:90])
    print('  PW      : %s' % rd('r02_pw.txt')[:90])
    print('  shot rc : %s' % rd('r10_shot.txt')[:60])
    print('  dcim pre : %s' % rd('r03_dcim_pre.txt')[:120])
    print('  dcim post: %s' % rd('r04_dcim_post.txt')[:120])

    print('\n===== md5 =====')
    h = {}
    for tg in tags:
        p = os.path.join(OUT, 'ep_r%s.txt' % tg)
        if os.path.exists(p):
            h[tg] = hashlib.md5(open(p, 'rb').read()).hexdigest()
            print('  %-4s %s' % (tg, h[tg]))
    if len(h) == 5:
        drift_ok = h['t0'] == h['t1'] == h['t2']
        resp = h['t2'] != h['t3']
        print('\n  J1 无输入时稳定(t0==t1==t2) : %s' % ('PASS' if drift_ok else 'FAIL'))
        print('  J2 快门后变化  (t2 != t3)   : %s' % ('PASS' if resp else 'FAIL'))
        if not drift_ok:
            print('\n  【作废】dump 本身不稳定 ⇒ 之前所有单点 diff 都不可信。')
        elif not resp:
            print('\n  【结论】快门后 EP 无变化 ⇒需J3 确认快门是否真的响了。')
    return 0


if __name__ == '__main__':
    sys.exit(main())