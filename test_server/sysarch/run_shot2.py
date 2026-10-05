# -*- coding: utf-8 -*-
"""实验② 重做：先切A 档拍摄模式，再快门
★★为什么必须重做：v1 里 `st cap sh` 返回 RC=0，但 DCIM 快照前后完全一致
   （最新的还是 17:14 的 SAM_3201.JPG）⇒ 快门根本没响。
   RC=0 只证明命令被接收，不证明拍照动作发生。
   ⇒ 「拍照前后 EP 无变化」这个结论是无效的，不能写成「EP 不参与成像」。
   记忆里setusr 通道的前置条件就是「A 档 + 拍摄模式」。

自证链（缺一不可）：
  ① getusr 20 有值               → 控制面活着
  ② st app mode a回读 DIALMODE→ 真的在 A 档
  ③ DCIM 出现比拍摄时间更新的文件 → 快门真的响了（唯一客观判据）
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

    # ---- 0. 环境与模式自证 ----
    print('>>> [0] 模式自证')
    sh(t, 'st app mode a', 12, 'm00_setmode.txt')
    time.sleep(3)
    sh(t, 'st cap capdtm getusr 20', 10, 'm01_getusr.txt')
    sh(t, 'st cap capdtm getusr 0', 10, 'm02_dial.txt')   # 索引0 = DIALMODE
    sh(t, '{ ls -lt /mnt/mmc/DCIM/*/ 2>/dev/null | head -3; date; } > %s/m03_dcim0.txt 2>&1' % X, 12)

    # ---- 1. 拍照前 dump ----
    print('>>> [1] before dump')
    sh(t, 'nice -n 19 %s/epdump2.arm q01_before 256' % X, 25, 'q01_dump.txt')
    time.sleep(2)

    # ---- 2. 快门×2，中间留间隔 ----
    for i in (1, 2):
        print('>>> [2.%d] shutter' % i)
        sh(t, 'st cap sh', 35, 'q02_shot%d.txt' % i)
        time.sleep(8)
        sh(t, '{ ls -lt /mnt/mmc/DCIM/*/ 2>/dev/null | head -3; date; } '
              '> %s/m04_dcim%d.txt 2>&1' % (X, i), 12)
        time.sleep(2)

    # ---- 3. 拍照后 dump×2（区分「快门瞬间」与「持续状态」）----
    print('>>> [3] after dumps')
    sh(t, 'nice -n 19 %s/epdump2.arm q03_after 256' % X, 25, 'q03_dump.txt')
    time.sleep(2)
    sh(t, 'nice -n 19 %s/epdump2.arm q04_after2 256' % X, 25, 'q04_dump.txt')

    t.close()
    print('\npulling ...')
    time.sleep(1)

    f = ftplib.FTP(HOST, timeout=90); f.login(); f.cwd('/_xfer')
    names = f.nlst()
    want = ['ep_q01_before.txt', 'ep_q03_after.txt', 'ep_q04_after2.txt',
            'm00_setmode.txt', 'm01_getusr.txt', 'm02_dial.txt',
            'm03_dcim0.txt', 'm04_dcim1.txt', 'm04_dcim2.txt',
            'q02_shot1.txt', 'q02_shot2.txt']
    for fn in want:
        if fn not in names:
            print('  MISS %s' % fn); continue
        p = os.path.join(OUT, fn)
        with open(p, 'wb') as fh:
            f.retrbinary('RETR ' + fn, fh.write)
        print('  GOT  %-22s %d B' % (fn, os.path.getsize(p)))
    f.quit()

    def rd(fn):
        p = os.path.join(OUT, fn)
        return ' '.join(open(p, encoding='utf-8', errors='replace').read().split()) \
            if os.path.exists(p) else '(missing)'

    print('\n===== 自证链 =====')
    print('  setmode   : %s' % rd('m00_setmode.txt')[:100])
    print('  getusr 20 : %s' % rd('m01_getusr.txt')[:100])
    print('  DIALMODE  : %s' % rd('m02_dial.txt')[:100])
    print('  shot1 rc  : %s' % rd('q02_shot1.txt')[:80])
    print('  shot2 rc  : %s' % rd('q02_shot2.txt')[:80])
    print('  dcim pre  : %s' % rd('m03_dcim0.txt')[:130])
    print('  dcim after1: %s' % rd('m04_dcim1.txt')[:130])
    print('  dcim after2: %s' % rd('m04_dcim2.txt')[:130])

    ok = 'SAM_32' in rd('m04_dcim2.txt') and 'SAM_32' in rd('m03_dcim0.txt')
    print('\n  快门判据：需人工比对上面的 DCIM 时间戳是否变新。')

    print('\n===== md5=====')
    for fn in ('ep_q01_before.txt', 'ep_q03_after.txt', 'ep_q04_after2.txt'):
        p = os.path.join(OUT, fn)
        if os.path.exists(p):
            print('  %-22s %s' % (fn, hashlib.md5(open(p, 'rb').read()).hexdigest()))
    return 0


if __name__ == '__main__':
    sys.exit(main())