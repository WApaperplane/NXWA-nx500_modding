#!/bin/sh
BB=/opt/usr/nx-ks/busybox
D=/opt/usr/nx-ks
LOG=/mnt/mmc/filmlab/x11.log
CMD=/mnt/mmc/filmlab/cmd
rm -f $LOG $CMD
# nohup 不可用，直接 setsid 式：手工 fork +脱离
$D/filmlab/nxflab.arm /mnt/mmc/filmlab/recipes.txt $LOG 30 </dev/null >/dev/null 2>&1 &
sleep 4
echo "log after start:"
$BB tail -c 200 $LOG 2>/dev/null | tr -d '\r'
echo ""
echo "cmd mtime before: $($BB stat -c %Y $CMD 2>/dev/null || echo NOFILE)"
echo down > $CMD
echo "cmd written: $($BB cat $CMD 2>/dev/null)  mtime=$($BB stat -c %Y $CMD 2>/dev/null)"
sleep 3
echo "log after cmd:"
$BB tail -c 300 $LOG 2>/dev/null | tr -d '\r'
echo ""
echo "cleanup"
$BB pkill -f nxflab.arm 2>/dev/null
echo CT3_DONE
