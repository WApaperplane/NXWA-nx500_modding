# -*- coding: utf-8 -*-
"""第三批补采：不用 find、不用长 for 循环 —— 全部是单条 ls/cat
   ★ 教训：probe3 用 `find /sys` 在单核上跑了 3 分钟没结束，
     telnet 会话一断 SIGHUP 把整个脚本带走 ⇒ 只落地 c1 一个文件。
     ⇒ 铁律：sysarch 探测禁用 find -sys；命令逐条下发、每条 ≤1 秒。
   ★ 教训：bash heredoc 里写 \$(...) 会被 bash 预展开 ⇒ 脚本落盘再跑。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minitel import MiniTel

HOST = '192.168.0.105'
X = '/mnt/mmc/_xfer'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'raw3')

# (输出文件, 命令)  —— 命令里不用 find、不用嵌套 for
CMDS = [
    ('c2_isdvfs',
     'ls /sys/devices/platform/drime5-ispfreq/ 2>&1'),
    ('c2b_platfreq',
     'ls /sys/devices/platform/ 2>&1 | grep -iE "isp|dvfs|freq|clock|ddr|m4"'),
    ('c3_ispfreq',
     'cat /sys/devices/platform/drime5-ispfreq/cur_freq /sys/devices/platform/drime5-ispfreq/target_freq /sys/devices/platform/drime5-ispfreq/min_freq /sys/devices/platform/drime5-ispfreq/max_freq 2>&1'),
    ('c3b_ddrfreq',
     'cat /sys/devices/platform/drime5-ddrfreq/cur_freq /sys/devices/platform/drime5-ddrfreq/target_freq 2>&1'),
    ('c4_iomem',
     'cat /proc/iomem'),
    ('c5_drmbufs',
     'cat /sys/kernel/debug/dri/0/pre_alloc_info 2>&1'),
    ('c5b_drmclients',
     'cat /sys/kernel/debug/dri/0/clients 2>&1'),
    ('c6_epdev',
     'cat /sys/class/misc/drime5_ep/dev 2>&1'),
    ('c6b_miscdev',
     'grep -H . /sys/class/misc/d5*/dev 2>&1'),
    ('c7_gpio',
     'ls /sys/class/gpio/ 2>&1'),
    ('c7b_gpiodirs',
     'ls -d /sys/class/gpio/*/ 2>&1'),
    ('c9_thermal',
     'cat /sys/class/thermal/thermal_zone0/temp /sys/class/thermal/thermal_zone1/temp 2>&1'),
    ('c10_platcount',
     'ls /sys/devices/platform/ 2>&1 | wc -l'),
    ('c11_platfull',
     'ls /sys/devices/platform/ 2>&1'),
    ('c12_epdir',
     'ls /sys/devices/platform/d5_ep.0/ /sys/devices/platform/drime5_ep.0/ 2>&1'),
    ('c13_asvsub',
     'ls -R /sys/devices/platform/d5_promise/ 2>&1 | head -40'),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    t = MiniTel(HOST)
    t.read(3); t.send('root', 2); t.send('', 2)
    for fn, cmd in CMDS:
        line = '{ echo "===== %s ====="; %s; } > %s/%s 2>&1' % (fn, cmd, X, fn)
        t.send(line, 2.5)
    t.send('echo P3DONE > %s/_p3.done' % X, 1.5)
    t.close()
    print('sent %d commands' % len(CMDS))

    import ftplib, time
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
        f.retrbinary('RETR _p3.done', open(os.path.join(OUT, '_p3.done'), 'wb').write)
    except Exception:
        print('!! no done flag')
    f.quit()
    print('pulled %d/%d' % (len(got), len(CMDS)))


if __name__ == '__main__':
    main()
