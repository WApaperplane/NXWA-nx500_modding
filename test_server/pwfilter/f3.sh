#!/bin/sh
# 验证：X11 能不能活过启动它的 shell 退出
B=/opt/usr/nx-ks/busybox
L=/mnt/mmc/filmlab/x11.log
O=/mnt/mmc/_pwtest/f3.txt
: > $O
rm -f $L
# 不用 setsid，直接 &，看能活多久
/opt/usr/nx-ks/filmlab/nxflab.arm /mnt/mmc/filmlab/recipes.txt $L 30 </dev/null >/dev/null 2>&1 &
P=$!
echo "started pid=$P" >> $O
sleep 3
$B cat /proc/$P/comm >/dev/null 2>&1 && echo "  after 3s: ALIVE" >> $O || echo "  after 3s: GONE" >> $O
echo "SHELL_WILL_EXIT_NOW" >> $O
echo "F3_DONE" >> $O
