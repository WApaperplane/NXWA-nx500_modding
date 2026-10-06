#!/bin/sh
# pw-scan.sh — 扫描 setusr/getusr 全部索引，输出非空项
# 用法: sh pw-scan.sh <起> <止>
BB=/opt/usr/nx-ks/busybox
ST="st cap capdtm"
A=${1:-0}
Z=${2:-95}
i=$A
while [ "$i" -le "$Z" ]; do
  # 十六进制索引的高位段（setusr 第二参数前缀 = index 的十六进制）
  H=$(printf "%02x" $i)
  R=$($ST getusr $i 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')
  if [ -n "$R" ]; then
    echo "$i 0x${H}0000  $R"
  fi
  i=$((i+1))
done
echo "SCAN_DONE"
