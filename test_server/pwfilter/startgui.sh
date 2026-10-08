#!/bin/sh
B=/opt/usr/nx-ks/busybox
O=/mnt/mmc/_pwtest/startgui.txt
: > $O
say() { echo "$*" >> $O; }
# 杀掉旧的
killall -q mod_gui 2>/dev/null
sleep 1
say "=== 启动 mod_gui ==="
setsid /opt/usr/nx-ks/mod_gui /opt/usr/nx-ks/gui_ini >/dev/null 2>&1 &
sleep 4
# 确认起来了
FOUND=""
for p in /proc/[0-9]*; do
  c=$($B cat $p/comm 2>/dev/null)
  [ "$c" = "mod_gui" ] && FOUND="${p#/proc/}"
done
if [ -n "$FOUND" ]; then
  say "mod_gui running pid=$FOUND"
else
  say "FAIL mod_gui not running"
  say "log: $($B tail -c 200 /mnt/mmc/_pwtest/mg.log 2>/dev/null)"
fi
say "STARTGUI_DONE"
