# -*- coding: utf-8 -*-
"""EP dump 序列 v2 —— 用已实证的 setusr 直接切PW 风格做对照
★★ 修正：v1 用 /opt/usr/nx-ks/filmlab.sh 做前置，实机 RC=127（文件不存在，
   那是FilmLab 引擎，需 FTP 单独投递，不在 install.sh 链里）⇒ 四次 dump 完全相同，
   那是「什么都没做」，不是「配方不影响 EP」。本版改用 setusr，无外部依赖。

对照维度（全部走 setusr/getusr，已实证免save 即时生效）：
  ① PW 风格：0x140001(PW_VIVID) vs 0x140009(PW_CUSTOM1) vs 0x14000d
     —— 同槽不同值 ⇒ 变量只有「风格枚举」，最干净的对照
  ② 槽内参数：固定 PW_VIVID，用 prefman set 改R/G/B 中性↔偏色
     —— 变量是「槽内 PW 数值」
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minitel import MiniTel
import ftplib

HOST = '192.168.0.105'
X = '/mnt/mmc/_xfer'
BB = '/opt/usr/nx-ks/busybox'
PXM = '/opt/usr/nx-ks/nx-rc/x'          # prefman 母本
HERE = os.path.dirname(os.path.abspath(__file__))
ARM = os.path.join(HERE, 'epdump2.arm')
OUT = os.path.join(HERE, 'raw7')
MAXW = '256'

DO_ISO = '--iso' in sys.argv
DO_SHOT = '--shot' in sys.argv

# PW 中性值：R/G/B=100, HUE/SAT/SHARP/CONTRAST=10（记忆铁律，不是 Sony 的 ±3）
NEUTRAL = [100, 100, 100, 10, 10, 10, 10]
# addr(参数i, 风格s) = 41964 + i*52 + s*4
def paddr(i, s):
    return 41964 + i * 52 + s * 4

S_VIVID = 1     # 0x140001
S_CUST1 = 9     # 0x140009


def stages():
    st = []
    # ---- 实验① PW 风格对照（槽 9 = UI 自定义1，位置恒定）----
    st.append(('s01_cust1', 'st cap capdtm setusr 20 0x140009', 'st cap capdtm getusr 20'))
    st.append(('s02_vivid', 'st cap capdtm setusr 20 0x140001', 'st cap capdtm getusr 20'))
    st.append(('s03_cust1', 'st cap capdtm setusr 20 0x140009', 'st cap capdtm getusr 20'))
    return st


def stages_shot():
    """实验②：拍照前后。★ st cap sh 是已验证的客观快门通道。"""
    return [
        ('p01_before', None, None),
        ('p02_after', 'SHOT', None),
        ('p03_after2', None, None),      # 二次采样：区分「快门瞬间」与「持续状态」
    ]


def sh(t, cmd, wait=8, tag='_last.txt'):
    full = '{ %s; } > %s/%s 2>&1; echo "RC=$?" >> %s/%s' % (cmd, X, tag, X, tag)
    t.send(full, wait)
    time.sleep(1)


def dump(t, label):
    sh(t, 'nice -n 19 %s/epdump2.arm %s %s' % (X, label, MAXW), 25,
       '%s_dump.txt' % label)
    time.sleep(1.5)


def main():
    if not os.path.exists(ARM):
        print('MISSING', ARM); return 1
    os.makedirs(OUT, exist_ok=True)
    plan = stages_shot() if DO_SHOT else stages()
    print('plan: %s' % ', '.join(p[0] for p in plan))

    f = ftplib.FTP(HOST, timeout=30); f.login(); f.cwd('/_xfer')
    with open(ARM, 'rb') as fh:
        f.storbinary('STOR epdump2.arm', fh)
    f.quit()
    print('uploaded %d bytes' % os.path.getsize(ARM))

    t = MiniTel(HOST); t.read(3); t.send('root', 2); t.send('', 2)
    t.send('%s chmod 755 %s/epdump2.arm' % (BB, X), 5)
    # 开拍前先记 DCIM 快照，作为「快门是否真的发生」的客观判据
    t.send('{ ls -lt /mnt/mmc/DCIM/*/ 2>/dev/null | head -6; '
           'echo ---ALL---; ls /mnt/mmc/DCIM/ 2>/dev/null; } > %s/dcim_ls.txt 2>&1'
           % X, 12)
    time.sleep(1)

    for label, pre, verify in plan:
        print('>>> %s  <- %s' % (label, pre or '(none)'))
        if pre == 'SHOT':
            # ★ 自动快门：st cap sh 是已验证的客观通道
            sh(t, 'st cap sh', 30, '%s_shot.txt' % label)
            time.sleep(6)          # 等ISP 走完 pipeline 再 dump
        elif pre:
            sh(t, pre, 10, '%s_pre.txt' % label)
            time.sleep(2)
            if verify:
                sh(t, verify, 10, '%s_verify.txt' % label)
                time.sleep(1)
        dump(t, label)

    t.send('echo DONE > %s/_v2.done' % X, 4)
    # 拍完再记一次 DCIM，用于对比是否新增文件
    t.send('{ ls -lt /mnt/mmc/DCIM/*/ 2>/dev/null | head -6; } > %s/dcim_ls2.txt 2>&1' % X, 12)
    t.close()
    print('\npulling ...')
    time.sleep(1)

    f = ftplib.FTP(HOST, timeout=90); f.login(); f.cwd('/_xfer')
    names = f.nlst()
    got = []
    for label, _, _ in plan:
        cands = ['ep_%s.txt' % label, '%s_pre.txt' % label,
                 '%s_verify.txt' % label, '%s_shot.txt' % label,
                 '%s_dump.txt' % label]
        for fn in cands:
            if fn not in names: continue
            p = os.path.join(OUT, fn)
            with open(p, 'wb') as fh:
                f.retrbinary('RETR ' + fn, fh.write)
            got.append(fn)
            print('  GOT  %-24s %d B' % (fn, os.path.getsize(p)))
    # ★ 追加：DCIM 最新文件清单 —— 自证「快门真的响了」的唯一客观通道
    for fn, dst in (('dcim_ls.txt', 'dcim_ls.txt'), ('dcim_ls2.txt', 'dcim_ls2.txt')):
        if fn in names:
            with open(os.path.join(OUT, dst), 'wb') as fh:
                f.retrbinary('RETR ' + fn, fh.write)
            print('  GOT  %-24s' % fn)
    f.quit()

    print('\n== 自证 ==')
    for label, _, _ in plan:
        for suf in ('verify', 'shot'):
            p = os.path.join(OUT, '%s_%s.txt' % (label, suf))
            if os.path.exists(p):
                txt = ' '.join(open(p, encoding='utf-8',
                                    errors='replace').read().split())
                print('  %-12s %-8s %s' % (label, suf, txt[:110]))
    d = os.path.join(OUT, 'dcim_ls.txt')
    if os.path.exists(d):
        print('\n== DCIM 末尾（自证快门） ==')
        for ln in open(d, encoding='utf-8', errors='replace').read().splitlines()[-6:]:
            print('  ' + ln)
    print('\n== md5 ==')
    for label, _, _ in plan:
        p = os.path.join(OUT, 'ep_%s.txt' % label)
        if os.path.exists(p):
            import hashlib
            print('  %-12s %s' % (label,
                  hashlib.md5(open(p, 'rb').read()).hexdigest()))
    return 0


if __name__ == '__main__':
    sys.exit(main())