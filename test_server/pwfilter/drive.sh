#!/bin/sh
BB=/opt/usr/nx-ks/busybox
U=/opt/usr/nx-ks/flab_ui.sh
L=/mnt/mmc/filmlab/x11.log

echo "### 1. 启动（setsid 脱离会话）"
sh $U start
echo ""
echo "### 2. 立刻检查是否存活（这一步 telnet 会关闭，模拟 mod_gui 退出）"
sh $U status
