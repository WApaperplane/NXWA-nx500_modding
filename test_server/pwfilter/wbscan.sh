#!/bin/sh
BB=/opt/usr/nx-ks/busybox
ST="st cap capdtm"
O=$1
: > $O
# WB 的 setusr 索引在 6-18 段（我们没扫过的那段）
i=$2
while [ "$i" -le "$3" ]; do
  R=$($ST getusr $i 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')
  if [ -n "$R" ]; then
    echo "$i 0x$(printf '%02x' $i)  $R" >> $O
  fi
  i=$((i+1))
done
echo "DONE" >> $O
