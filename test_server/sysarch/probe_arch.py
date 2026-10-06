#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_arch.py — NX500 系统/软件架构侦察（只读，单 telnet 会话）

铁律（项目血泪）：
1. telnet 必须串行，一次只开一个连接（单核相机并发会打挂）。
2. 只读命令，不写不删。除了在 /mnt/mmc/_xfer/ 建输出目录。
3. 单次会话内尽量少发命令 —— 每条命令都是往返，且相机可能 1-2s 才响应。
4. busybox 必须绝对路径 /opt/usr/nx-ks/busybox。
5. 输出统一走 /mnt/mmc/_xfer/，FTP 根 = SD 卡可直接拉。

用法:
  python probe_arch.py <ip>            # 默认输出到 raw/ 目录
  python probe_arch.py <ip> --list     # 只列命令，不执行
"""
import os
import socket
import sys
import time

HOST = '192.168.0.105'
BB = '/opt/usr/nx-ks/busybox'
XFER = '/mnt/mmc/_xfer'
LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'raw')

# (输出文件名, 命令)  —— 顺序即执行顺序
CMDS = [
    # ---- 身份与版本 ----
    ('00_version.txt',
     'cat /etc/version.info; echo; cat /etc/os-release 2>/dev/null'),

    # ---- CPU / 内核 ----
    ('01_cpu.txt',
     'cat /proc/cpuinfo; echo "=== uname ==="; uname -a'),

    ('02_cmdline.txt',
     'cat /proc/cmdline; echo; echo "=== mount ==="; cat /proc/mounts'),

    # ---- 内存：注意 CMA 静态预留（项目铁律：先看 dmesg 的 Memory/cma 行）----
    ('03_meminfo.txt',
     'head -5 /proc/meminfo; echo "=== mtd ==="; cat /proc/mtd 2>/dev/null'),

    # ---- 块设备与分区：判断哪些分区可写 ----
    ('04_blockdev.txt',
     'cat /proc/partitions; echo "=== df ==="; df -h 2>/dev/null'),

    # ---- 挂载点与文件系统类型：判断 rootfs 是否可写 ----
    ('05_mounts.txt',
     'mount 2>/dev/null | head -40'),

    # ---- 运行中进程全景：谁在跑、常驻内存多大 ----
    ('06_ps.txt',
     'ps aux 2>/dev/null || ps -ef 2>/dev/null || ps w'),

    # ---- 内核模块：哪些驱动在用 ----
    ('07_modules.txt',
     'cat /proc/modules 2>/dev/null | head -60'),

    # ---- Tizen 应用清单（/usr/apps 是签名只读分区）----
    ('08_apps.txt',
     'ls -la /usr/apps/ 2>/dev/null; echo "=== app 内部结构 ==="; '
     'ls -la /usr/apps/di-camera-app/ 2>/dev/null'),

    # ---- 设备节点：所有 /dev/d5* / drime5 相关 ----
    ('09_devnodes.txt',
     'ls -la /dev/ | grep -iE "d5|drime|cam|ipcc|sensor|v4l|fb|mem|i2c" ; '
     'echo "=== all/dev count ==="; ls /dev/ | wc -l'),

    # ---- 平台 sysfs：DRIMe5 设备树与总线 ----
    ('10_platform.txt',
     'ls /sys/devices/platform/ 2>/dev/null; echo "=== drime5 子树 ==="; '
     'find /sys/devices/platform/drime5* -maxdepth 2 2>/dev/null | head -40'),

    # ---- 相机 IOCTL 属性总线：st 工具的枚举（只读）----
    ('11_st_usrlist.txt',
     'st cap capdtm usrlist 2>&1 | head -100'),

    ('12_st_iqr.txt',
     'st cap iqr 2>&1 | head -120'),

    ('13_st_varlist.txt',
     'st cap capdtm varlist 2>&1 | head -60'),

    # ---- 网络服务端口（确认当前开着哪些通道）----
    ('14_netstat.txt',
     'netstat -tlnp 2>/dev/null || cat /proc/net/tcp'),

    # ---- 环境变量：Tizen 运行时上下文 ----
    ('15_env.txt',
     'env 2>/dev/null | sort'),

    # ---- 已安装的库与字体（决定能写什么类型的程序）----
    ('16_libs.txt',
     'ls /usr/lib/*.so* 2>/dev/null | head -60; echo "=== efl ==="; '
     'ls /usr/lib/libelementary* /usr/lib/libevas* /usr/lib/libecore* 2>/dev/null'),

    ('17_fonts.txt',
     'ls -la /usr/share/fonts/truetype/ 2>/dev/null; find /usr/share/fonts -name "*.ttf" 2>/dev/null | head -20'),

    # ---- 相机控制二进制清单：能调相机的工具全在这 ----
    ('18_cambin.txt',
     'ls -la /usr/bin/ | grep -iE "st|cap|cam|pref|poker|nx|keyscan|mod"; '
     'echo "=== /opt/usr/nx-ks ==="; ls -la /opt/usr/nx-ks/ 2>/dev/null'),

    # ---- 内核日志尾部：开机流程与驱动初始化顺序 ----
    ('19_dmesg.txt',
     'dmesg 2>/dev/null | tail -200'),

    ('20_dmesg_head.txt',
     'dmesg 2>/dev/null | head -120'),

    # ---- systemd 单元：开机自启清单 ----
    ('21_systemd.txt',
     'ls -la /usr/lib/systemd/system/ 2>/dev/null | head -50; '
     'echo "=== multi-user.target.wants ==="; '
     'ls -la /etc/systemd/system/multi-user.target.wants/ 2>/dev/null'),

    # ---- 启动脚本链：install.sh 怎么被拉起 ----
    ('22_boot_scripts.txt',
     'cat /etc/init.d/rcS 2>/dev/null | head -40; echo "=== dfmsd ==="; '
     'ls -la /usr/bin/dfmsd /usr/sbin/dfmsd 2>/dev/null; find / -maxdepth 4 -name "dfmsd*" 2>/dev/null'),

    # ---- 内核命令行里的启动参数（决定 rootfs 行为）----
    ('23_version_sys.txt',
     'cat /etc/version.info; echo "=== hostname ==="; cat /etc/hostname 2>/dev/null; '
     'echo "=== issue ==="; cat /etc/issue 2>/dev/null; '
     'echo "=== oem ==="; ls /etc/oem* 2>/dev/null; cat /etc/oem.conf 2>/dev/null'),
]

# 一次性打包成一个大脚本，避免几十次往返
SCRIPT_HEAD = """#!/bin/sh
OUT=%s
mkdir -p $OUT
B=%s
""" % (XFER, BB)

SCRIPT_TAIL = """
echo "PROBE_DONE"
"""


def build_script():
    s = SCRIPT_HEAD
    for fname, cmd in CMDS:
        # 双引号包裹命令，避免相机 shell 提前展开；
        # 命令里的 $ 保持原样让远端展开
        s += '\n{ echo "===== %s ====="; %s; } > %s/%s 2>&1\n' % (
            fname, cmd, XFER, fname)
    s += SCRIPT_TAIL
    return s


class Telnet:
    def __init__(self, host, port=23, timeout=15.0):
        self.s = socket.create_connection((host, port), timeout=timeout)
        self.s.settimeout(3)
        self._drain(2.0)
        self.s.sendall(b'root\n')
        self._drain(2.0)

    def _drain(self, t):
        end = time.time() + t
        out = b''
        while time.time() < end:
            try:
                c = self.s.recv(65536)
                if not c:
                    break
                out += c
            except socket.timeout:
                break
            except OSError:
                break
        return out

    def send(self, line):
        self.s.sendall(line.encode() + b'\n')

    def read_until(self, marker, timeout):
        end = time.time() + timeout
        out = b''
        while time.time() < end:
            try:
                c = self.s.recv(65536)
                if not c:
                    break
                out += c
                if marker in out:
                    break
            except socket.timeout:
                if out:
                    break
        return out

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else HOST
    if '--list' in sys.argv:
        for f, c in CMDS:
            print('%-24s %s' % (f, c[:100]))
        return 0

    os.makedirs(LOCAL, exist_ok=True)
    script = build_script()
    spath = '%s/_probe.sh' % XFER

    # ★ 铁律：FTP 根 = SD 卡，/_xfer 中转目录必须先在相机上建好，
    #   否则 storbinary 直接 553 Error（踩过一次）。
    t0 = Telnet(host)
    t0.send('%s mkdir -p %s' % (BB, XFER))
    t0._drain(2.0)
    t0.close()

    # 用 FTP 把脚本送上去（>=10KB 走 FTP 是铁律，脚本虽小但统一路径更省事）
    import ftplib
    f = ftplib.FTP(host, timeout=60)
    f.login('root', '')
    local_s = os.path.join(LOCAL, '_probe.sh')
    with open(local_s, 'w', newline='\n') as fh:
        fh.write(script)
    f.storbinary('STOR /_xfer/_probe.sh', open(local_s, 'rb'))
    f.quit()
    print('script uploaded: %d bytes' % len(script))

    # 单次 telnet 会话跑完
    t = Telnet(host)
    t.send('%s chmod +x %s' % (BB, spath))
    t._drain(1.0)
    t.send('%s sh %s' % (BB, spath))
    print('running probe on camera (this takes ~60-120s on single core)...')
    out = t.read_until(b'PROBE_DONE', 300)
    t.close()
    print('probe finished. tail:')
    print(out[-400:].decode('utf-8', 'replace'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
