#!/bin/sh
BB=/opt/usr/nx-ks/busybox
BIN=/opt/usr/nx-ks/filmlab/nxflab.arm
RCP=/mnt/mmc/filmlab/recipes.txt
LOG=/mnt/mmc/_pwtest/nxflab.log
alive() { [ -e /proc/$1/comm ] && $BB cat /proc/$1/comm 2>/dev/null | grep -qa nxflab; }

echo "T1 SIGTERM"
rm -f $LOG
$BIN $RCP $LOG 60 &
P=$!
sleep 3
alive $P && echo "  started pid=$P" || { echo "  FAIL not started"; }
kill $P 2>/dev/null
sleep 2
alive $P && { echo "  FAIL still alive, SIGKILL"; kill -9 $P; } || echo "  PASS exited by SIGTERM"
echo "  log_tail=$($BB tail -c 40 $LOG 2>/dev/null | tr -d '\r')"

echo "T2 idle-timeout 6s"
rm -f $LOG
$BIN $RCP $LOG 6 &
P=$!
sleep 10
alive $P && { echo "  FAIL still alive"; kill -9 $P; } || echo "  PASS auto-exited on idle"
echo "  log_tail=$($BB tail -c 40 $LOG 2>/dev/null | tr -d '\r')"

echo "T3 SIGHUP"
rm -f $LOG
$BIN $RCP $LOG 60 &
P=$!
sleep 3
kill -1 $P 2>/dev/null
sleep 2
alive $P && { echo "  FAIL"; kill -9 $P; } || echo "  PASS exited by SIGHUP"
echo "DONE2"
