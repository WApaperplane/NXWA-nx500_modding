#!/bin/sh
B=/opt/usr/nx-ks/busybox
O=/mnt/mmc/_pwtest/wt.txt
: > $O
T0=$($B date +%s%N 2>/dev/null || echo 0)
echo hello > /tmp/t3.txt
T1=$($B date +%s%N 2>/dev/null || echo 0)
echo "write_tmpfs_ms=$(( (T1-T0)/1000000 ))" >> $O
echo "content=$(cat /tmp/t3.txt)" >> $O
# 再测 X11 是否还活着
for p in /proc/[0-9]*; do
  c=$($B cat $p/comm 2>/dev/null)
  [ "$c" = "nxflab.arm" ] && echo "x11_alive=$p" >> $O
done
echo "WT_DONE" >> $O
