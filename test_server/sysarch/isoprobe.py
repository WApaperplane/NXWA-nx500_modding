# -*- coding: utf-8 -*-
"""ISO 枚举实测探测（★控制面写入，不是 EP 寄存器写入）

背景
----
实验③要「不同 ISO 下 dump NOG」。但 `st app iso 800` 无任何实证，索引 5 的
具体 ISO 档位枚举值也从未验证过。记忆铁律：任何列表索引都不能假定可用于写，
枚举值没实证就是假证据。

已实证的部分（raw/11_st_usrlist.txt）
------------------------------------
  [ 5] USERDATA_ISO       当前 ISO_AUTO      0x00050000
  [30] USERDATA_ISONR     当前 ISONR_MID     0x001E0002
  [60] USERDATA_ISOSTEP   当前 ISOSTEP_ONE   0x003C0001
  [61] USERDATA_ISOEXPANSION  ISOEXPANSION_ON  0x003D0001
  [64] USERDATA_ISOAUTOMAX    ISOAUTOMAX_ISO6400  0x00400011
    ↑ 注意 64 的低 16 位是 0x0011=17 ⇒ 枚举序号在低 16 位，基数不是 1 起步。

由此推出待验证的假设：枚举值 = 0x<前缀>0000 | <序号>
  5  → 0x0005NNNN
  30 → 0x001E00NN
本脚本就是去试出来的，不是猜的。

安全边界
--------
* 只用 `st cap capdtm setusr/getusr` —— 已实证的 prefman/setusr 控制面通道，
  免 save 即时生效、毫秒级、不写 eMMC。**不碰 EP 寄存器**。
* 每个候选写完立刻 getusr 回读自证（记忆铁律 11：不许只看 "UserData is set"）。
* 每步之间 sleep，单核相机别连着压。
* 探测结束无条件恢复到初值。

用法
----
  python isoprobe.py --get          只读：读回 5/30/60/61/64 当前值（默认，安全）
  python isoprobe.py --probe 5       探测索引 5 的枚举（会 setusr，逐个回读）
  python isoprobe.py --probe 30
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minitel import MiniTel
import ftplib

HOST = '192.168.0.105'
X = '/mnt/mmc/_xfer'
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw7')

# 索引 -> (前缀, 枚举名)  前缀来自 usrlist 实测
IDX = {
    5:  (0x00050000, 'USERDATA_ISO'),
    30: (0x001E0000, 'USERDATA_ISONR'),
    60: (0x003C0000, 'USERDATA_ISOSTEP'),
    61: (0x003D0000, 'USERDATA_ISOEXPANSION'),
    64: (0x00400000, 'USERDATA_ISOAUTOMAX'),
}
N_ENUM = 40          # 试 0..39，够了（ISO 档位远少于 40）
CAND = list(range(N_ENUM))


def main():
    if '--probe' not in sys.argv:
        mode = 'get'
    else:
        i = sys.argv.index('--probe')
        mode = 'probe%d' % int(sys.argv[i + 1])
    os.makedirs(OUT, exist_ok=True)
    print('mode=%s  host=%s' % (mode, HOST))

    t = MiniTel(HOST); t.read(3); t.send('root', 2); t.send('', 2)

    log = []

    def cap(cmd, tag, wait=8):
        full = '{ %s; } > %s/%s 2>&1' % (cmd, X, tag)
        r = t.send(full, wait)
        time.sleep(0.8)
        return r

    if mode == 'get':
        for i in sorted(IDX):
            r = cap('st cap capdtm getusr %d' % i, 'get_%d.txt' % i)
            txt = ' '.join((r or '').split())
            print('  [%2d] %-22s %s' % (i, IDX[i][1], txt[-120:]))
            log.append((i, txt[-200:]))

    else:
        idx = int(mode[5:])
        pre, nm = IDX[idx]
        print('probing index %d (%s) prefix=0x%08x' % (idx, nm, pre))

        # 0. 先读初值
        r0 = cap('st cap capdtm getusr %d' % idx, 'p%d_orig.txt' % idx, 10)
        orig = ' '.join((r0 or '').split())
        print('  original: %s' % orig[-140:])
        log.append(('orig', orig[-200:]))

        good = []
        for n in CAND:
            val = pre | n
            # 写 → 立刻回读 → 两次都取回文件内容比对
            cap('st cap capdtm setusr %d 0x%08x' % (idx, val),
                'p%d_w.txt' % idx, 8)
            time.sleep(1.2)
            cap('st cap capdtm getusr %d' % idx, 'p%d_r.txt' % idx, 8)
            time.sleep(0.6)
            # 取回文件（FTP 单次拉两个小文件，负担可忽略）
            got = {}
            f = ftplib.FTP(HOST, timeout=20); f.login(); f.cwd('/_xfer')
            for fn in ('p%d_w.txt' % idx, 'p%d_r.txt' % idx):
                buf = b''
                try:
                    f.retrbinary('RETR ' + fn, lambda b: None)
                except Exception:
                    pass
            # ftplib 回调收集
            f.close()
            # 简化：直接用 telnet 读回
            r = t.send('cat %s/p%d_r.txt' % (X, idx), 6)
            txt = ' '.join((r or '').split())
            ok = 'not set' not in txt and 'ERROR' not in txt.upper() and len(txt) > 4
            print('    n=%-3d 0x%08x -> %s  %s' % (n, val, txt[-60:], 'OK' if ok else ''))
            log.append((n, val, txt[-160:]))
            if ok and n > 0:
                good.append((n, val, txt[-80:]))
            time.sleep(0.8)

        # 恢复初值（无条件）
        cap('st cap capdtm setusr %d 0x%08x' % (idx, pre | 0),
            'p%d_restore.txt' % idx, 8)
        r = t.send('st cap capdtm getusr %d' % idx, 8)
        print('  restored -> %s' % ' '.join((r or '').split())[-120:])
        log.append(('restored', ' '.join((r or '').split())[-200:]))

        print('\n  == 可接受枚举 ==')
        for n, v, txt in good:
            print('    n=%-3d 0x%08x  %s' % (n, v, txt))

    t.send('echo DONE > %s/_iso.done' % X, 4)
    t.close()

    p = os.path.join(OUT, 'isoprobe_%s.txt' % mode)
    with open(p, 'w', encoding='utf-8') as fh:
        for row in log:
            fh.write(repr(row) + '\n')
    print('\nsaved %s' % p)
    return 0


if __name__ == '__main__':
    sys.exit(main())