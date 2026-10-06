# -*- coding: utf-8 -*-
"""第五批：ISP 固件定位 + 签名校验 + rootfs 可写性
   ★ 全部只读。核心目的：搞清 handle 墙那堵墙的"墙材质"到底有多硬。
   ★ 严格避开 `cat /proc/iomem`（会内核段错误）——改用分段 head/sed
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minitel import MiniTel
import ftplib

HOST = '192.168.0.105'
BB = '/opt/usr/nx-ks/busybox'
X = '/mnt/mmc/_xfer'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'raw4')

CMDS = [
    # ---------- A. iomem 完整分段（避开崩点） ----------
    ('e01_iomem_1',  'head -40 /proc/iomem'),
    ('e02_iomem_2',  'sed -n "41,80p" /proc/iomem'),
    ('e03_iomem_3',  'sed -n "81,120p" /proc/iomem'),
    ('e04_iomem_4',  'sed -n "121,160p" /proc/iomem'),
    ('e05_iomem_5',  'sed -n "161,200p" /proc/iomem'),
    ('e06_iomem_6',  'sed -n "201,240p" /proc/iomem'),
    ('e07_iomem_7',  'sed -n "241,280p" /proc/iomem'),
    ('e08_iomem_8',  'sed -n "281,320p" /proc/iomem'),
    ('e09_iomem_9',  'sed -n "321,400p" /proc/iomem'),
    ('e10_iomem_cnt','wc -l /proc/iomem'),

    # ---------- B. ISP 固件文件在哪 ----------
    ('e11_p9_top',    'ls /mnt/mmc/ 2>&1'),
    ('e12_p9_mount',  'cat /proc/mounts | grep -E "mmcblk0p[0-9]"'),
    ('e13_etc_fw',    'ls -la /etc/ 2>&1 | grep -iE "fw|firm|dsp|m4|isp|secur|sign"'),
    ('e14_lib_dsp',   'ls /usr/lib/ 2>&1 | grep -iE "dsp|m4|isp|fw"'),
    ('e15_appsdir',   'ls -la /usr/apps/ 2>&1'),
    ('e16_usrshare',  'ls /usr/share/ 2>&1 | head -40'),

    # ---------- C. rootfs 可写性（只读检查，不试写） ----------
    ('e17_filesystems','cat /proc/filesystems'),
    ('e18_mount_opts','cat /proc/mounts | head -6'),
    ('e19_blockdev_rw','cat /proc/partitions'),
    ('e20_dmesg_tail','dmesg | tail -40'),

    # ---------- D. 安全启动 / 签名痕迹 ----------
    ('e21_dmesg_sec', 'dmesg | grep -iE "secur|sign|verif|trust|authen|efuse|otp|secure|hash|encrypt|decrypt" | head -30'),
    ('e22_cmdline_sec','cat /proc/cmdline'),
    ('e23_cpu_rev',   'cat /proc/cpuinfo | head -8'),
    ('e24_sysctl',    'cat /proc/sys/kernel/secureboot 2>&1; cat /proc/sys/kernel/kptr_restrict 2>&1; ls /proc/sys/ 2>&1 | head -30'),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    t = MiniTel(HOST)
    t.read(3); t.send('root', 2); t.send('', 2)
    for fn, cmd in CMDS:
        t.send('{ echo "===== %s ====="; %s; } > %s/%s 2>&1' % (fn, cmd, X, fn), 2.2)
    t.send('echo E_DONE > %s/_e.done' % X, 1.5)
    t.close()
    print('sent %d' % len(CMDS))
    time.sleep(2)
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
        f.retrbinary('RETR _e.done', open(os.path.join(OUT, '_e.done'), 'wb').write)
    except Exception:
        print('!! no done')
    f.quit()
    print('pulled %d/%d' % (len(got), len(CMDS)))


if __name__ == '__main__':
    main()
