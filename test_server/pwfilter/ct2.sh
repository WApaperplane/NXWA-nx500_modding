#!/bin/sh
BB=/opt/usr/nx-ks/busybox
D=/opt/usr/nx-ks
CMD=/mnt/mmc/filmlab/cmd
rm -f $CMD $D/flmlab_cmd.txt
$D/flab_ui.sh start
sleep 3
echo "--- 写第1条 down ---"
echo down > $CMD
sleep 2
echo "  log: $($BB cat /mnt/mmc/filmlab/x11.log 2>/dev/null | tr -d '\r' | $BB tail -c 120)"
echo "--- 写第2条 apply ---"
echo apply > $CMD
sleep 4
echo "  log: $($BB cat /mnt/mmc/filmlab/x11.log 2>/dev/null | tr -d '\r' | $BB tail -c 200)"
echo "--- quit ---"
echo quit > $CMD
sleep 2
$BB cat /proc/1575/comm 2>/dev/null || true
for p in $($BB ls -d /proc/[0-9]* 2>/dev/null); do
  c=$($BB cat $p/comm 2>/dev/null)
  [ "$c" = "nxflab.arm" ] && echo "  still: $p"
done
echo "CT2_DONE"
