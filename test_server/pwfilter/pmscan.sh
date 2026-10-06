#!/bin/sh
# pmscan.sh <out> <pref_id> <起> <止>  — 扫 prefman 某段，列出非零/非默认值条目
PM=prefman
O=$1
ID=$2
: > $O
a=$3
while [ "$a" -le "$4" ]; do
  V=$($PM get $ID "$(printf 0x%05x $a)" l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p')
  if [ -n "$V" ] && [ "$V" != "0" ]; then
    echo "$a $(printf 0x%05x $a) $V" >> $O
  fi
  a=$((a+1))
done
echo "SCAN_DONE" >> $O
