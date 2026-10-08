#!/bin/sh
# scan64.sh <输出> <起> <止> — 扫 setusr 索引，列出非空项
ST="st cap capdtm"
OUT=$1
: > $OUT
i=$2
while [ $i" -le "$3 ]; do
  R=$($ST getusr $i 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')
  if [ -n "$R" ]; then
    H=$(printf "%02x" $i)
    echo "$i 0x${H}  $R" >> $OUT
  fi
  i=$((i+1))
done
echo "END" >> $OUT
