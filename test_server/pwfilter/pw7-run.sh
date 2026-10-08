#!/bin/sh
# pw7-run.sh — 在相机上执行 PW7 探针。参数化调用必须走脚本，
# 因为 telnet_run.py 在循环/管道里会吞掉参数（实测 mode 总是变0）。
# 用法: sh pw7-run.sh <mode> <pat_hex> [sigma_hex]
BB=/opt/usr/nx-ks/busybox
BIN=/opt/usr/nx-ks/lut3dl/pw7_v2.arm
LOG=/mnt/mmc/_pwtest/pw7b.log
M=${1:-0}
P=${2:-00010101}
S=${3:-00000000}

rm -f $LOG
"$BIN" /usr/lib/libudd5.so "$M" "$P" "$S"
RC=$?
echo "RC=$RC"
echo "--- log ---"
$BB cat $LOG
