#!/bin/sh
# pw-scan2.sh — 对每个索引只扫 4 个枚举值（0..3），大幅减少 st 调用次数
# 单核相机上 st 每次调用约 1-2 秒，96 次会超时。分批由PC 侧循环控制。
# 用法: sh pw-scan2.sh <idx>
BB=/opt/usr/nx-ks/busybox
ST="st cap capdtm"
I=$1
if [ -z "$I" ]; then echo "用法: sh pw-scan2.sh <idx>"; exit 1; fi
H=$(printf "%02x" $I)
E=0
while [ $E -lt 6 ]; do
  ID=$(printf "0x%s%04x" "$H" $E)
  R=$($ST getusr $I $ID 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')
  if [ -n "$R" ]; then
    echo "  $I $ID  $R"
  fi
  E=$((E+1))
done
echo "IDX_$I"
echo "DONE_$I"
