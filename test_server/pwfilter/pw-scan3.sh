#!/bin/sh
# pw-scan3.sh — 扫描一个索引区间的 getusr 回显
# 单核相机上 st 慢，一次只扫少量索引，PC 侧分批调用
# 用法: sh pw-scan3.sh <起> <止>
ST="st cap capdtm"
A=$1
Z=$2
i=$A
while [ "$i" -le "$Z" ]; do
  R=$($ST getusr $i 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')
  if [ -n "$R" ]; then
    H=$(printf "%02x" $i)
    echo "$i 0x${H}  $R"
  fi
  i=$((i+1))
done
echo "END_$Z"
