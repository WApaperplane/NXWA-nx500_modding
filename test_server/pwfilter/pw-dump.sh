#!/bin/sh
# pw-dump.sh — 读回指定索引区间的全部值，输出到文件
# 用法: sh pw-dump.sh <起> <止> <输出文件>
ST="st cap capdtm"
A=$1
Z=$2
OUT=$3
: > $OUT
i=$A
while [ "$i" -le "$Z" ]; do
  R=$($ST getusr $i 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')
  if [ -n "$R" ]; then
    echo "$i $R" >> $OUT
  else
    echo "$i (empty)" >> $OUT
  fi
  i=$((i+1))
done
echo "DUMP_DONE" >> $OUT
