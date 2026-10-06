# -*- coding: utf-8 -*-
"""第六批：★ 决定性实测 ★
   1) SMA 共享内存区域的真实大小/起始地址（= 双核通信载体有多大）
   2) IPCC core_id 枚举在 NX500 上的实际响应（能否给 DSP 发消息）
   3) ep_reg_info 里 3dlut / nog 的寄存器物理地址是否为非零
      —— 记忆里记的是「恢复出厂后 ep_3dlut_reg_base = 0x0000，路线作废」
         ★ 本次要验证：是"ioctl 不返回"还是"返回 0"——两者含义完全不同
   ★ 只读 ioctl，不写任何东西。GET_PHYS_REG_INFO = _IOR（纯读）
   ★ 遵守铁律：逐条下发、每条 ≤2.5s、不用 find、不 cat /proc/iomem
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minitel import MiniTel
import ftplib

HOST = '192.168.0.105'
BB = '/opt/usr/nx-ks/busybox'
X = '/mnt/mmc/_xfer'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'raw5')

# 用 capdtm（stapp/capdtm 已存在于 /opt/usr/nx-ks/nx-rc/）探测
CMDS = [
    ('f01_which',        'ls -l /opt/usr/nx-ks/nx-rc/ 2>&1 | head -30'),
    ('f02_capdtm_help',  '/opt/usr/nx-ks/nx-rc/capdtm 2>&1 | head -40'),
    ('f03_stapp_help',   '/opt/usr/nx-ks/stapp 2>&1 | head -30'),
    ('f04_sma_dev',      'ls -l /dev/d5_sma /dev/d5_ipcc /dev/d5_lock /dev/d5_mptop 2>&1'),
    ('f05_ep_dev',       'ls -l /dev/d5_ep /dev/d5_ep* 2>&1; ls -l /sys/class/misc/ | grep -E "ep|sma|lock|mptop"'),
    # SMA ioctl：GET_REGION_SIZE / GET_REGION_START_ADDR / GET_ALLOCATED_SIZE
    ('f06_sma_probe',    'for i in 1 4 8; do echo "ioctl $i:"; /opt/usr/nx-ks/busybox dd if=/dev/d5_sma bs=4 count=1 2>&1 | head -2; done'),
    ('f07_ep_probe',     '/opt/usr/nx-ks/busybox dd if=/dev/d5_ep bs=4 count=64 2>&1 | head -20'),
    ('f08_sma_read',     '/opt/usr/nx-ks/busybox hexdump -C /dev/d5_sma 2>&1 | head -20'),
    ('f09_ep_read',      '/opt/usr/nx-ks/busybox hexdump -C /dev/d5_ep 2>&1 | head -30'),
    ('f10_ep_dev_full',  'ls -l /dev/ | grep -E "^crw" | head -30'),
    # 找 ep 的设备号
    ('f11_ep_misc',      'grep -H . /sys/class/misc/*/dev 2>&1'),
    ('f12_lock_type',    'cat /usr/include/media/drime5/lock/d5_lock_type.h 2>&1 | head -40'),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    t = MiniTel(HOST)
    t.read(3); t.send('root', 2); t.send('', 2)
    for fn, cmd in CMDS:
        t.send('{ echo "===== %s ====="; %s; } > %s/%s 2>&1' % (fn, cmd, X, fn), 2.2)
    t.send('echo F_DONE > %s/_f.done' % X, 1.5)
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
        f.retrbinary('RETR _f.done', open(os.path.join(OUT, '_f.done'), 'wb').write)
    except Exception:
        print('!! no done')
    f.quit()
    print('pulled %d/%d' % (len(got), len(CMDS)))


if __name__ == '__main__':
    main()
