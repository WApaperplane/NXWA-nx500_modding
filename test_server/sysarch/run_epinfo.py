# -*- coding: utf-8 -*-
"""第七批：★ 只读 ioctl 实测 ★
   把交叉编译好的 epinfo.arm 投到相机上跑，验证三件事：
     1. NX500 内核真实的 ioctl ABI（magic/nr/size）是否与 NX1 GPL 头文件一致
     2. EP 的 3DLUT / NOG 子块寄存器物理基址能否拿到（handle 墙绕道可能性）
     3. SMA 共享内存区域物理范围 + IPCC 跨核邮箱可用量

   ★ 安全边界：本程序只调_IO R 查询接口。
     不调 SMA_ALLOC(5)、IPCC_WRITE_PKT(7)、EP_IOCTL_UDD_LOCK(40)、st firmware up。
   ★ 铁律：telnet 串行；跑完等3s 让相机缓过来；不并发。
   用法： python run_epinfo.py [normal|nrscan]
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minitel import MiniTel
import ftplib

HOST = '192.168.0.105'
BB   = '/opt/usr/nx-ks/busybox'
X    = '/mnt/mmc/_xfer'
HERE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(HERE, 'probe_src', 'epinfo.arm')
OUT  = os.path.join(HERE, 'raw5')
MODE = sys.argv[1] if len(sys.argv) > 1 else 'normal'


def main():
    if not os.path.exists(SRC):
        print('MISSING binary:', SRC); return 1
    os.makedirs(OUT, exist_ok=True)

    # ---- 1. FTP 投递 ----
    f = ftplib.FTP(HOST, timeout=30); f.login(); f.cwd('/_xfer')
    with open(SRC, 'rb') as fh:
        f.storbinary('STOR epinfo.arm', fh)
    f.quit()
    print('uploaded epinfo.arm (%d bytes)' % os.path.getsize(SRC))

    # ---- 2. telnet 准备 + 运行 ----
    t = MiniTel(HOST)
    t.read(3); t.send('root', 2); t.send('', 2)
    out = t.send('{ echo "===== pre ====="; ls -l /dev/d5_ipcc /dev/d5_sma '
                 '/dev/drime5_ep; } > %s/n01_pre 2>&1' % X, 2.5)
    out = t.send('chmod 755 %s/epinfo.arm; %s/epinfo.arm %s > %s/n02_run 2>&1; '
                 'echo EXIT=$? >> %s/n02_run' % (X, X, MODE, X, X), 25)
    print('run tail:', (out or '')[-400:])
    t.send('echo N_DONE > %s/_n.done' % X, 2)
    t.close()

    # 铁律：让单核相机缓一下，别紧接着压
    time.sleep(4)

    # ---- 3. FTP 拉回 ----
    f = ftplib.FTP(HOST, timeout=30); f.login(); f.cwd('/_xfer')
    for fn in ('n01_pre', 'n02_run'):
        try:
            with open(os.path.join(OUT, fn), 'wb') as fh:
                f.retrbinary('RETR ' + fn, fh.write)
            print('pulled', fn)
        except Exception as e:
            print('MISS', fn, e)
    try:
        f.retrbinary('RETR _n.done', open(os.path.join(OUT, '_n.done'), 'wb').write)
        print('done-marker ok')
    except Exception:
        print('!! no done marker — 相机可能没跑完')
    f.quit()

    # ---- 4. 本地直接打印结果 ----
    p = os.path.join(OUT, 'n02_run')
    if os.path.exists(p):
        print('\n================= RUN OUTPUT =================')
        print(open(p, encoding='utf-8', errors='replace').read())
    return 0


if __name__ == '__main__':
    sys.exit(main())