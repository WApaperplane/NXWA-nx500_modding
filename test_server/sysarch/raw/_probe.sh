#!/bin/sh
OUT=/mnt/mmc/_xfer
mkdir -p $OUT
B=/opt/usr/nx-ks/busybox

{ echo "===== 00_version.txt ====="; cat /etc/version.info; echo; cat /etc/os-release 2>/dev/null; } > /mnt/mmc/_xfer/00_version.txt 2>&1

{ echo "===== 01_cpu.txt ====="; cat /proc/cpuinfo; echo "=== uname ==="; uname -a; } > /mnt/mmc/_xfer/01_cpu.txt 2>&1

{ echo "===== 02_cmdline.txt ====="; cat /proc/cmdline; echo; echo "=== mount ==="; cat /proc/mounts; } > /mnt/mmc/_xfer/02_cmdline.txt 2>&1

{ echo "===== 03_meminfo.txt ====="; head -5 /proc/meminfo; echo "=== mtd ==="; cat /proc/mtd 2>/dev/null; } > /mnt/mmc/_xfer/03_meminfo.txt 2>&1

{ echo "===== 04_blockdev.txt ====="; cat /proc/partitions; echo "=== df ==="; df -h 2>/dev/null; } > /mnt/mmc/_xfer/04_blockdev.txt 2>&1

{ echo "===== 05_mounts.txt ====="; mount 2>/dev/null | head -40; } > /mnt/mmc/_xfer/05_mounts.txt 2>&1

{ echo "===== 06_ps.txt ====="; ps aux 2>/dev/null || ps -ef 2>/dev/null || ps w; } > /mnt/mmc/_xfer/06_ps.txt 2>&1

{ echo "===== 07_modules.txt ====="; cat /proc/modules 2>/dev/null | head -60; } > /mnt/mmc/_xfer/07_modules.txt 2>&1

{ echo "===== 08_apps.txt ====="; ls -la /usr/apps/ 2>/dev/null; echo "=== app 内部结构 ==="; ls -la /usr/apps/di-camera-app/ 2>/dev/null; } > /mnt/mmc/_xfer/08_apps.txt 2>&1

{ echo "===== 09_devnodes.txt ====="; ls -la /dev/ | grep -iE "d5|drime|cam|ipcc|sensor|v4l|fb|mem|i2c" ; echo "=== all/dev count ==="; ls /dev/ | wc -l; } > /mnt/mmc/_xfer/09_devnodes.txt 2>&1

{ echo "===== 10_platform.txt ====="; ls /sys/devices/platform/ 2>/dev/null; echo "=== drime5 子树 ==="; find /sys/devices/platform/drime5* -maxdepth 2 2>/dev/null | head -40; } > /mnt/mmc/_xfer/10_platform.txt 2>&1

{ echo "===== 11_st_usrlist.txt ====="; st cap capdtm usrlist 2>&1 | head -100; } > /mnt/mmc/_xfer/11_st_usrlist.txt 2>&1

{ echo "===== 12_st_iqr.txt ====="; st cap iqr 2>&1 | head -120; } > /mnt/mmc/_xfer/12_st_iqr.txt 2>&1

{ echo "===== 13_st_varlist.txt ====="; st cap capdtm varlist 2>&1 | head -60; } > /mnt/mmc/_xfer/13_st_varlist.txt 2>&1

{ echo "===== 14_netstat.txt ====="; netstat -tlnp 2>/dev/null || cat /proc/net/tcp; } > /mnt/mmc/_xfer/14_netstat.txt 2>&1

{ echo "===== 15_env.txt ====="; env 2>/dev/null | sort; } > /mnt/mmc/_xfer/15_env.txt 2>&1

{ echo "===== 16_libs.txt ====="; ls /usr/lib/*.so* 2>/dev/null | head -60; echo "=== efl ==="; ls /usr/lib/libelementary* /usr/lib/libevas* /usr/lib/libecore* 2>/dev/null; } > /mnt/mmc/_xfer/16_libs.txt 2>&1

{ echo "===== 17_fonts.txt ====="; ls -la /usr/share/fonts/truetype/ 2>/dev/null; find /usr/share/fonts -name "*.ttf" 2>/dev/null | head -20; } > /mnt/mmc/_xfer/17_fonts.txt 2>&1

{ echo "===== 18_cambin.txt ====="; ls -la /usr/bin/ | grep -iE "st|cap|cam|pref|poker|nx|keyscan|mod"; echo "=== /opt/usr/nx-ks ==="; ls -la /opt/usr/nx-ks/ 2>/dev/null; } > /mnt/mmc/_xfer/18_cambin.txt 2>&1

{ echo "===== 19_dmesg.txt ====="; dmesg 2>/dev/null | tail -200; } > /mnt/mmc/_xfer/19_dmesg.txt 2>&1

{ echo "===== 20_dmesg_head.txt ====="; dmesg 2>/dev/null | head -120; } > /mnt/mmc/_xfer/20_dmesg_head.txt 2>&1

{ echo "===== 21_systemd.txt ====="; ls -la /usr/lib/systemd/system/ 2>/dev/null | head -50; echo "=== multi-user.target.wants ==="; ls -la /etc/systemd/system/multi-user.target.wants/ 2>/dev/null; } > /mnt/mmc/_xfer/21_systemd.txt 2>&1

{ echo "===== 22_boot_scripts.txt ====="; cat /etc/init.d/rcS 2>/dev/null | head -40; echo "=== dfmsd ==="; ls -la /usr/bin/dfmsd /usr/sbin/dfmsd 2>/dev/null; find / -maxdepth 4 -name "dfmsd*" 2>/dev/null; } > /mnt/mmc/_xfer/22_boot_scripts.txt 2>&1

{ echo "===== 23_version_sys.txt ====="; cat /etc/version.info; echo "=== hostname ==="; cat /etc/hostname 2>/dev/null; echo "=== issue ==="; cat /etc/issue 2>/dev/null; echo "=== oem ==="; ls /etc/oem* 2>/dev/null; cat /etc/oem.conf 2>/dev/null; } > /mnt/mmc/_xfer/23_version_sys.txt 2>&1

echo "PROBE_DONE"
