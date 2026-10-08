#!/bin/bash
# Telnet/FTP 开关(主菜单按钮调用)。
# 开: 启动 telnetd(23) + busybox ftpd(21, root, SD 卡根目录)
# 关: killall 两者。状态由 popup 反馈, 菜单标签在下次开菜单时刷新(gen_menu.sh)。
# 原 EV+WiFi 组合键(EV_MOBILE.sh)通道保留不变, 两者互不干扰。

DIR=/opt/usr/nx-ks

if ps -w 2>/dev/null | grep telnetd | grep -qv grep; then
    killall -q telnetd
    killall -q tcpsvd
    "$DIR/popup_timeout" "Telnet/FTP 已关闭" 3
else
    nice -n +10 "$DIR/telnetd" &
    nice -n +10 "$DIR/busybox" tcpsvd -u root -vE 0.0.0.0 21 \
        "$DIR/busybox" ftpd -w -v /opt/storage/sdcard &
    IP=$(ip addr ls 2>/dev/null | grep inet | grep mlan0 | cut -d/ -f 1 \
         | grep -o '[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}')
    if [ -n "$IP" ]; then
        "$DIR/popup_timeout" "Telnet/FTP: $IP" 8
    else
        "$DIR/popup_timeout" "WiFi未开 - Telnet/FTP已启动" 5
    fi
fi
exit 0
