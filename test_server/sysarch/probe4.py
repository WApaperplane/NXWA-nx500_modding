# -*- coding: utf-8 -*-
"""第三批补采二：ISP DVFS 属性文件 / iomem 续段（分段读，避开 iomem 尾部崩）
   ★ 实测踩坑：cat /proc/iomem 读到 0x1003c0c0 附近时 kernel 段错误。
     iomem 里 drime5-adc 之后的下一段是保留空洞，逐段读更安全。
   ★ drime5-ispfreq 目录下是 bus_boost/dram_boost/dvfs_use/ep_lock/scen
     —— 不是常规 cpufreq 结构，是三星私有 DVFS 接口。
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minitel import MiniTel
import ftplib

HOST = '192.168.0.105'
X = '/mnt/mmc/_xfer'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'raw3')

CMDS = [
    ('d1_ispfreq_files',
     'ls -l /sys/devices/platform/drime5-ispfreq/ 2>&1'),
    ('d2_ispfreq_vals',
     'cat /sys/devices/platform/drime5-ispfreq/bus_boost /sys/devices/platform/drime5-ispfreq/dram_boost /sys/devices/platform/drime5-ispfreq/dvfs_use /sys/devices/platform/drime5-ispfreq/ep_lock /sys/devices/platform/drime5-ispfreq/scen 2>&1'),
    ('d3_ispfreq_scen',
     'ls -l /sys/devices/platform/drime5-ispfreq/scen/ 2>&1; cat /sys/devices/platform/drime5-ispfreq/scen/* 2>&1'),
    ('d4_ddrfreq_files',
     'ls -l /sys/devices/platform/drime5-ddrfreq/ 2>&1'),
    ('d5_ddrfreq_vals',
     'cat /sys/devices/platform/drime5-ddrfreq/* 2>&1 | head -20'),
    ('d6_iomem_head',
     'head -60 /proc/iomem'),
    ('d7_iomem_mid',
     'sed -n "61,130p" /proc/iomem'),
    ('d8_iomem_grep',
     'grep -iE "lcd|drm|mali|isp|ep|dsp|secure|modem" /proc/iomem 2>&1'),
    ('d9_gpiochip',
     'ls /sys/class/gpio/ 2>&1; cat /sys/class/gpio/gpiochip0/label 2>&1'),
    ('d10_gpiochip_dirs',
     'ls -d /sys/class/gpio/gpiochip*/ 2>&1; ls /sys/class/gpio/gpiochip0/ 2>&1'),
    ('d11_drm_clients',
     'cat /sys/kernel/debug/dri/0/clients 2>&1'),
    ('d12_drm_prealloc',
     'cat /sys/kernel/debug/dri/0/pre_alloc_info 2>&1'),
    ('d13_ep_platform',
     'ls -l /sys/devices/platform/drime5_ep.0/ 2>&1; cat /sys/devices/platform/drime5_ep.0/modalias 2>&1'),
    ('d14_asv_deep',
     'cat /sys/devices/platform/d5_promise/asv 2>&1; ls /sys/devices/platform/d5_promise/tmcb/ /sys/devices/platform/d5_promise/sec_ro/ /sys/devices/platform/d5_promise/dmu_ro/ /sys/devices/platform/d5_promise/dmu_tdc/ 2>&1'),
    ('d15_cpuinfo_cur',
     'grep -E "^cpu MHz|^processor|^model name|^Features" /proc/cpuinfo 2>&1'),
    ('d16_scaling',
     'ls /sys/devices/system/cpu/cpu0/cpufreq/ 2>&1; cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>&1'),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    t = MiniTel(HOST)
    t.read(3); t.send('root', 2); t.send('', 2)
    for fn, cmd in CMDS:
        t.send('{ echo "===== %s ====="; %s; } > %s/%s 2>&1' % (fn, cmd, X, fn), 2.5)
    t.send('echo P4DONE > %s/_p4.done' % X, 1.5)
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
        f.retrbinary('RETR _p4.done', open(os.path.join(OUT, '_p4.done'), 'wb').write)
    except Exception:
        print('!! no done')
    f.quit()
    print('pulled %d/%d' % (len(got), len(CMDS)))


if __name__ == '__main__':
    main()
