#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pull_arch.py — 从相机 FTP 拉回 probe_arch.py 的输出（/_xfer/*.txt）

用法: python pull_arch.py [ip]
"""
import ftplib
import os
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else '192.168.0.105'
LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'raw')

FILES = [
    '00_version.txt', '01_cpu.txt', '02_cmdline.txt', '03_meminfo.txt',
    '04_blockdev.txt', '05_mounts.txt', '06_ps.txt', '07_modules.txt',
    '08_apps.txt', '09_devnodes.txt', '10_platform.txt',
    '11_st_usrlist.txt', '12_st_iqr.txt', '13_st_varlist.txt',
    '14_netstat.txt', '15_env.txt', '16_libs.txt', '17_fonts.txt',
    '18_cambin.txt', '19_dmesg.txt', '20_dmesg_head.txt',
    '21_systemd.txt', '22_boot_scripts.txt', '23_version_sys.txt',
]


def main():
    os.makedirs(LOCAL, exist_ok=True)
    f = ftplib.FTP(HOST, timeout=120)
    f.login('root', '')
    f.cwd('/_xfer')
    names = set()
    for n in f.nlst():
        names.add(n.rsplit('/', 1)[-1])
    ok, miss = 0, []
    for name in FILES:
        if name not in names:
            miss.append(name)
            continue
        dst = os.path.join(LOCAL, name)
        with open(dst, 'wb') as fh:
            f.retrbinary('RETR ' + name, fh.write)
        sz = os.path.getsize(dst)
        print('  %-22s %8d B' % (name, sz))
        ok += 1
    f.quit()
    print('\n拉回 %d / %d' % (ok, len(FILES)))
    if miss:
        print('缺失:', ', '.join(miss))
    return 0


if __name__ == '__main__':
    sys.exit(main())
