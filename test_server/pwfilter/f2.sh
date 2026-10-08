#!/bin/sh
O=/mnt/mmc/_pwtest/f2.txt
L=/mnt/mmc/filmlab/x11.log
B=/opt/usr/nx-ks/busybox
: > $O
# 手动清残留
for p in /proc/[0-9]*; do
  c=$($B cat $p/comm 2>/dev/null)
  [ "$c" = "nxflab.arm" ] && kill -9 ${p#/proc/} 2>/dev/null
done
rm -f $L /tmp/flab_cmd
: > /tmp/flab_cmd
echo "启动中..." >> $O
setsid /opt/usr/nx-ks/filmlab/nxflab.arm /mnt/mmc/filmlab/recipes.txt $L 40 </dev/null >/dev/null 2>&1 &
echo "PID=$!" >> $O
echo "F2_DONE" >> $O
