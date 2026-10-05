# -*- coding: utf-8 -*-
"""EP 寄存器实验序列驱动器（★★纯只读 EP，绝不写任何 EP 寄存器）

三个实验：
  ① 切配方   → base / recipe_a / recipe_b / restore
  ② 拍照前后 → before_shot / after_shot
  ③ ISO 档位 → iso_base / iso_hi_nr

★★ 单核铁律（违反会压死相机，只能拔电池）：
  - telnet 必串行，一次只跑一条命令
  - 每阶段之间 sleep，让 ISP 有喘息
  - epdump2 是 PROT_READ mmap，负担极小，但仍 nice -n 19
  - 一次上机只做这一组，不夹带其他任务

★★ 上一版的两处缺陷（本版已修）：
  1. STAGES 里的 pre 写成 'FILMLAB portra400' / 'ISONR_OFF' 这种裸词，
     但分发处判的是 startswith('FLAB=') ⇒ 永远走不到分支，
     结果把裸词当 shell 命令下发，必然 Unknown command。
     ⇒ 本版 pre 一律是**完整可执行命令串**，分发处不再做前缀猜测。
  2. 控制面写入（setusr / filmlab apply）写完必须 getusr 回读自证，
     只信 "UserData is set" 这句不算数（记忆铁律 11）。
     ⇒ 每条 pre 命令后追加一条回读命令，落到 <label>_verify.txt。

用法:
  python run_epxfer.py                  # 实验①（配方）+ base，最小集
  python run_epxfer.py --shot# 实验②（拍照前后）
  python run_epxfer.py --iso            # 实验③（ISO，枚举值从 isoprobe 结果填）
  python run_epxfer.py --all
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

DO_SHOT = '--shot' in sys.argv
DO_ISO = '--iso' in sys.argv or '--all' in sys.argv
DO_RECIPE = '--all' in sys.argv or not (DO_SHOT or DO_ISO)

# ★ ISO 枚举占位：必须由 isoprobe.py 实测回读确认后填入。
#   记忆铁律：任何列表索引都不能假定可用于写；枚举值没实证就是假证据。
ISO_LO = os.environ.get('ISO_LO', '')   # 例 '0x00050006'
ISO_HI = os.environ.get('ISO_HI', '')   # 例 '0x0005000a'
ISONR_OFF = os.environ.get('ISONR_OFF', '')

FLAB = '/opt/usr/nx-ks/filmlab.sh'

# (label, 前置命令 or None, 回读命令 or None)
STAGES = []


def build_stages():
    del STAGES[:]
    STAGES.append(('base', None, None))
    if DO_RECIPE:
        STAGES.append(('recipe_a', '%s apply portra400' % FLAB,
                       'st cap capdtm getusr 20'))
        STAGES.append(('recipe_b', '%s apply cineteal' % FLAB,
                       'st cap capdtm getusr 20'))
        STAGES.append(('restore', '%s apply portra400' % FLAB,
                       'st cap capdtm getusr 20'))
    if DO_SHOT:
        STAGES.append(('before_shot', None, None))
        STAGES.append(('after_shot', 'SHOT', None))
    if DO_ISO:
        if not (ISO_LO and ISO_HI):
            print('[ABORT] 实验③ 需要 ISO_LO/ISO_HI 环境变量'
                  '（先跑 isoprobe.py 拿到实测枚举）')
            sys.exit(2)
        STAGES.append(('iso_base', None, 'st cap capdtm getusr 5'))
        STAGES.append(('iso_lo', 'st cap capdtm setusr 5 %s' % ISO_LO,
                       'st cap capdtm getusr 5'))
        STAGES.append(('iso_hi', 'st cap capdtm setusr 5 %s' % ISO_HI,
                       'st cap capdtm getusr 5'))
        if ISONR_OFF:
            STAGES.append(('iso_hi_nr', 'st cap capdtm setusr 30 %s' % ISONR_OFF,
                           'st cap capdtm getusr 30'))
        STAGES.append(('iso_restore', 'st cap capdtm setusr 5 0x00050000',
                       'st cap capdtm getusr 5'))


def sh(t, cmd, wait=6, tag='_last.txt'):
    """单条命令下发，写远端文件。★ telnet 吃引号 ⇒ 命令在 Python 侧拼好。"""
    full = '{ %s; } > %s/%s 2>&1; echo "RC=$?" >> %s/%s' % (cmd, X, tag, X, tag)
    t.send(full, wait)
    time.sleep(1)


def main():
    build_stages()
    if not os.path.exists(ARM):
        print('MISSING', ARM)
        return 1
    os.makedirs(OUT, exist_ok=True)
    print('stages: %s' % ', '.join(s[0] for s in STAGES))

    # ---- FTP 投工具 ----
    f = ftplib.FTP(HOST, timeout=30)
    f.login()
    f.cwd('/_xfer')
    with open(ARM, 'rb') as fh:
        f.storbinary('STOR epdump2.arm', fh)
    f.quit()
    print('uploaded epdump2.arm (%d bytes)' % os.path.getsize(ARM))

    t = MiniTel(HOST)
    t.read(3)
    t.send('root', 2)
    t.send('', 2)

    # 环境体检（结果落到 _env.txt，回读用）
    t.send('ls -l %s/epdump2.arm; %s chmod 755 %s/epdump2.arm; '
           'ls -l %s/filmlab.sh; head -3 /proc/meminfo > %s/_env.txt 2>&1'
           % (X, BB, X, X, X), 8)
    time.sleep(1)

    for label, pre, verify in STAGES:
        if label == 'after_shot':
            # ★ 自动快门：st cap sh 是已验证的客观通道
            print('>>> taking shot via st cap sh ...')
            t.send('st cap sh 2>&1 | tail -3 > %s/shot.txt' % X, 30)
            time.sleep(5)

        if pre and pre != 'SHOT':
            print('>>> pre: %s' % pre)
            sh(t, pre, 30, '%s_pre.txt' % label)
            time.sleep(3)
            if verify:
                print('    verify: %s' % verify)
                sh(t, verify, 12, '%s_verify.txt' % label)
                time.sleep(1)

        print('>>> dump: %s' % label)
        sh(t, 'nice -n 19 %s/epdump2.arm %s 256' % (X, label), 30)
        time.sleep(2)

    t.send('echo DONE > %s/_seq.done' % X, 5)
    t.close()
    print('\nsequence done, pulling back ...')
    time.sleep(1)

    # ---- FTP 拉回 ----
    got = []
    f = ftplib.FTP(HOST, timeout=90)
    f.login()
    f.cwd('/_xfer')
    names = f.nlst()
    for label, _, _ in STAGES:
        for fn in ('ep_%s.txt' % label,
                   '%s_pre.txt' % label,
                   '%s_verify.txt' % label):
            if fn not in names:
                continue
            p = os.path.join(OUT, fn)
            with open(p, 'wb') as fh:
                f.retrbinary('RETR ' + fn, fh.write)
            got.append(fn)
            print('  GOT  %-26s %d bytes' % (fn, os.path.getsize(p)))
    for extra in ('_seq.done', '_env.txt', 'shot.txt'):
        if extra in names:
            p = os.path.join(OUT, extra.strip('_'))
            with open(p, 'wb') as fh:
                f.retrbinary('RETR ' + extra, fh.write)
    f.quit()

    print('\npulled %d files into %s' % (len(got), OUT))
    return 0


if __name__ == '__main__':
    sys.exit(main())