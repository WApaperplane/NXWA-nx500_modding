#!/bin/sh
#=====================================================================
# u1_input.sh -- U1 ③/④：抓一小段输入事件流（波轮 keysym / 触摸）
#=====================================================================
# ★ 生成物，勿手改：python test_server/tools/gate_pack_u1.py
# ★ 为什么不用 timeout：不确定 busybox 是否编了 timeout applet；
#   这里只用 dd + sleep + kill（核心 applet 必定存在）做一个有界读取。
# ★ 用法前先看 u1_probe.sh 的 /proc/bus/input/devices 输出，确定哪个 eventN 是波轮/触摸。
#   运行期间请人【转动波轮 / 触摸屏幕】，否则读不到事件。
# @gate script=u1_input.sh opens=rdonly one_shot=1
BB=/opt/usr/nx-ks/busybox
OUT=/mnt/mmc/u1/out
N="$1"
SEC="$2"

if [ -z "$N" ]; then echo "usage: sh u1_input.sh <eventN> [secs]"; exit 2; fi
[ -z "$SEC" ] && SEC=20
if [ ! -r "/dev/input/event$N" ]; then echo "not readable: /dev/input/event$N"; exit 3; fi

$BB mkdir -p "$OUT"
BIN="$OUT/input_event$N.bin"

# 有界读取：后台 dd + 到点 kill（bs=16 = 32 位 input_event 结构体大小）
$BB dd if="/dev/input/event$N" of="$BIN" bs=16 count=256 2>"$OUT/input_event$N.log" &
DDPID=$!
$BB sleep "$SEC"
$BB kill -TERM "$DDPID" 2>/dev/null
$BB sleep 1
$BB kill -9 "$DDPID" 2>/dev/null
wait 2>/dev/null
$BB sync

SZ=$($BB wc -c < "$BIN" 2>/dev/null)
echo "event$N bytes=$SZ  (events = bytes / 16，PC 侧再除)"
echo "md5=$($BB md5sum "$BIN" 2>/dev/null)"
exit 0
