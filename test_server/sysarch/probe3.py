# -*- coding: utf-8 -*-
"""第三批：d5_promise / asv 电源频率表、m4、ep 细节、DRM 缓冲区
   ★ 全部只读，不碰任何写操作
"""
import ftplib, time, os, io, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minitel import MiniTel

HOST='192.168.0.105'; BB='/opt/usr/nx-ks/busybox'; XFER='/mnt/mmc/_xfer'
OUT=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'raw3')

CMDS = [
 ('c1_asv',      'echo "[asv]"; cat /sys/devices/platform/d5_promise/asv; echo; echo "[dmu_freq]"; cat /sys/devices/platform/d5_promise/dmu_freq; echo; echo "[dmu_ro]"; cat /sys/devices/platform/d5_promise/dmu_ro; echo; echo "[dmu_tdc]"; cat /sys/devices/platform/d5_promise/dmu_tdc; echo; echo "[sec_ro]"; cat /sys/devices/platform/d5_promise/sec_ro; echo; echo "[tmcb]"; cat /sys/devices/platform/d5_promise/tmcb; echo; echo "[avs_test]"; cat /sys/devices/platform/d5_promise/avs_test'),
 ('c2_isdvfs',   'find /sys/devices/platform -maxdepth 2 -iname "*isp*" -o -maxdepth 2 -iname "*dvfs*" 2>/dev/null; echo ---; cat /sys/devices/platform/drime5-ispfreq/ 2>&1; ls -l /sys/devices/platform/drime5-ispfreq/ 2>&1'),
 ('c3_dvfsvals', 'for d in /sys/devices/platform/drime5-ispfreq /sys/devices/platform/drime5-ddrfreq /sys/devices/platform/drime5-clock; do echo "[$d]"; ls $d 2>&1; for f in $d/*; do [ -f "$f" ] && echo "  $(basename $f) = $(cat $f 2>&1 | tr "\n" " ")"; done; done'),
 ('c4_m4',       'find /sys/devices/platform -maxdepth 3 -iname "*m4*" 2>/dev/null; echo ---; grep -iE "m4|isp_fw|dsp" /proc/iomem 2>&1 | head -20; echo "[all iomem]"; cat /proc/iomem'),
 ('c5_drmbufs',  'for f in /sys/kernel/debug/dri/0/pre_alloc_info /sys/kernel/debug/dri/0/clients /sys/kernel/debug/dri/0/bufs; do echo "[$f]"; head -30 $f 2>&1; done'),
 ('c6_ep',       'ls -l /sys/devices/platform/ | grep -E "d5|drime5_ep|ep\\."; echo ---; find /sys/devices/platform -maxdepth 1 -name "*ep*" 2>&1; echo ---; cat /sys/class/misc/drime5_ep/dev 2>&1'),
 ('c7_gpio',     'ls /sys/class/gpio/ 2>&1; echo "[exported]"; cat /sys/class/gpio/export 2>&1; echo "[gpiodev]"; ls /sys/class/gpio/gpiochip*/ 2>&1 | head -20'),
 ('c8_clk_summary','cat /proc/clocks 2>&1 | head -5; echo ---; ls /sys/devices/platform/drime5-clock/ 2>&1; ls /sys/devices/platform/drime5-ddrfreq/ 2>&1'),
 ('c9_thermal',  'ls /sys/class/thermal/ 2>&1; cat /sys/class/thermal/thermal_zone0/temp 2>&1; echo ---; cat /sys/class/misc/drime5-thermister/dev 2>&1'),
 ('c10_power',   'for d in /sys/devices/platform/*/power; do n=$(echo $d | sed "s|/sys/devices/platform/||;s|/power||"); echo "[$n] state=$(cat $d/state 2>/dev/null) control=$(cat $d/control 2>/dev/null)"; done 2>&1 | head -40'),
]

def build():
    s = '#!/bin/sh\n'
    for fn, cmd in CMDS:
        s += '{ echo "===== %s ====="; %s; } > %s/%s 2>&1\n' % (fn, cmd, XFER, fn)
    return s + 'echo P3DONE > %s/_p3.done\n' % XFER

def login():
    t = MiniTel(HOST); t.read(3); t.send('root', 2); t.send('', 2); return t

def main():
    os.makedirs(OUT, exist_ok=True)
    t = login(); t.send('%s mkdir -p %s' % (BB, XFER), 3); t.close(); time.sleep(1)
    sc = build().replace('\r\n', '\n')
    f = ftplib.FTP(HOST, timeout=25); f.login()
    f.storbinary('STOR /_xfer/_probe3.sh', io.BytesIO(sc.encode('utf-8'))); f.quit()
    print('uploaded %d' % len(sc))
    time.sleep(1)
    t = login(); t.send('%s sh %s/_probe3.sh' % (BB, XFER), 70); t.close(); time.sleep(2)
    f = ftplib.FTP(HOST, timeout=25); f.login(); f.cwd('/_xfer')
    got = []
    for fn, _ in CMDS:
        try:
            with open(os.path.join(OUT, fn), 'wb') as fh:
                f.retrbinary('RETR ' + fn, fh.write)
            got.append(fn)
        except Exception as e: print('MISS', fn, e)
    try: f.retrbinary('RETR _p3.done', open(os.path.join(OUT,'_p3.done'),'wb').write)
    except Exception: print('!! no done flag')
    f.quit(); print('pulled %d/%d' % (len(got), len(CMDS)))

if __name__ == '__main__': main()
