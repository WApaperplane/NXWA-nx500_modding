#!/bin/sh
#=====================================================================
# lut_pick.sh — 应用一个已选定的 LUT（由 lut_scan.sh 的菜单页调用）
#=====================================================================

F=/opt/usr/nx-ks/lut_scan.sh
[ -x "$F" ] || { echo "ERR: 缺 $F"; exit 1; }

NAME="$1"
[ -z "$NAME" ] && { echo "ERR: 未指定 LUT 名"; exit 1; }

echo "==== 应用 LUT: $NAME ===="
"$F" apply "$NAME"