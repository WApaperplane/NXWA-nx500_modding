# -*- coding: utf-8 -*-
"""NX500 架构侦察 第二批：输入面 / 中断面 / display / 应用树 / cgroup
   ★ 铁律1：FTP 根 = SD 卡，/_xfer 必须先在相机上 mkdir，否则 storbinary 553
   ★ 铁律2：telnet 必串行 —— 全流程只开一个数据会话
   ★ 铁律3：Python 3.13 无 telnetlib → 用 minitel.MiniTel
   ★ 铁律4：脚本生成必须 LF 行尾（CRLF 会让 sh 语法错）
"""
import ftplib, time, os, io, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minitel import MiniTel

HOST='192.168.0.105'; BB='/opt/usr/nx-ks/busybox'; XFER='/mnt/mmc/_xfer'
OUT=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'raw2')

CMDS = [
 ('b1_inputdevices', 'cat /proc/bus/input/devices'),
 ('b2_interrupts',   'cat /proc/interrupts'),
 ('b3_misc',         'ls -l /sys/class/misc/ 2>&1'),
 ('b4_d5promise',    'ls /sys/devices/platform/d5_promise/ 2>&1'),
 ('b5_systemd_wants','echo "[multi-user]"; ls /etc/systemd/system/multi-user.target.wants/; echo; echo "[graphical]"; ls /etc/systemd/system/graphical.target.wants/; echo; echo "[basic]"; ls /etc/systemd/system/basic.target.wants/'),
 ('b6_camapp',       'ls -l /usr/apps/com.samsung.di-camera-app/; echo "[bin]"; ls -l /usr/apps/com.samsung.di-camera-app/bin/; echo "[lib]"; ls -l /usr/apps/com.samsung.di-camera-app/lib/ 2>&1'),
 ('b7_dri',          'ls /sys/kernel/debug/dri/0/ 2>&1; echo ---; cat /sys/kernel/debug/dri/0/name 2>&1'),
 ('b8_d5dev',        'ls -l /dev/d5* 2>&1; echo ---; ls /sys/class/isp 2>&1; echo ---; ls /sys/devices/platform/d5_ep.0/ 2>&1'),
 ('b9_cgroup_mgr',   'ls /sys/fs/cgroup/mgr/ 2>&1; echo "[tasks]"; cat /sys/fs/cgroup/mgr/tasks 2>&1 | head -20'),
 ('b10_slub',        'head -6 /proc/slabinfo; echo ---; cat /proc/vmstat | head -12'),
 ('b11_i2c',         'for b in /sys/bus/i2c/devices/*/; do n=$(cat $b/name 2>/dev/null); [ -n "$n" ] && echo "$(basename $b) -> $n"; done'),
 ('b12_nxks',        'ls /opt/usr/nx-ks/; echo "[count]"; ls /opt/usr/nx-ks/ | wc -l'),
 ('b13_opt_usr',     'ls /opt/usr/; echo ---; ls /opt/; echo ---; ls /opt/pref/ 2>&1'),
 ('b14_dlog',        'ls -l /var/log/ 2>&1 | head -30'),
]

def build():
    s = '#!/bin/sh\n'
    for fn, cmd in CMDS:
        s += '{ echo "===== %s ====="; %s; } > %s/%s 2>&1\n' % (fn, cmd, XFER, fn)
    return s + 'echo PROBE2_DONE > %s/_p2.done\n' % XFER

def login():
    t = MiniTel(HOST)
    t.read(3)
    t.send('root', 2)
    t.send('', 2)
    return t

def main():
    os.makedirs(OUT, exist_ok=True)
    # 1) 相机上建中转目录（FTP 根 = SD 卡）
    t = login(); t.send('%s mkdir -p %s' % (BB, XFER), 3); t.close()
    time.sleep(1)
    # 2) FTP 上传（强制 LF）
    sc = build().replace('\r\n', '\n')
    f = ftplib.FTP(HOST, timeout=25); f.login()
    f.storbinary('STOR /_xfer/_probe2.sh', io.BytesIO(sc.encode('utf-8')))
    f.quit(); print('uploaded %d bytes' % len(sc))
    # 3) telnet 单会话跑（不给相机留并发压力）
    time.sleep(1)
    t = login()
    t.send('%s sh %s/_probe2.sh' % (BB, XFER), 90)
    t.close(); time.sleep(2)
    # 4) 拉回
    f = ftplib.FTP(HOST, timeout=25); f.login(); f.cwd('/_xfer')
    got = []
    for fn, _ in CMDS:
        try:
            with open(os.path.join(OUT, fn), 'wb') as fh:
                f.retrbinary('RETR ' + fn, fh.write)
            got.append(fn)
        except Exception as e:
            print('MISS', fn, e)
    try:
        f.retrbinary('RETR _p2.done', open(os.path.join(OUT,'_p2.done'),'wb').write)
    except Exception:
        print('!! no done-flag —— 脚本可能仍在跑，稍后重拉')
    f.quit()
    print('pulled %d/%d' % (len(got), len(CMDS)))

if __name__ == '__main__':
    main()
