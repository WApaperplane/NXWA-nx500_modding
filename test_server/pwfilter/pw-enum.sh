#!/bin/sh
# pw-enum.sh <输出文件> <起> <止> — 逐个枚举切PW_TYPE 并读回
# 回显名有 bug（10/11 都显 CUSTOM2，12/13 都显 CUSTOM4），需人工对照 UI
ST="st cap capdtm"
OUT=$1
A=$2
Z=$3
: > $OUT
E=$A
while [ $E -le $Z ]; do
  ID=$(printf "0x%06x" $(( 0x140000 + E )))
  S=$($ST setusr 20 $ID 2>/dev/null | tr -d '\r' | sed -n 's/.*is \(.*\)/\1/p')
  G=$($ST getusr 20 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')
  echo "e=$E id=$ID set=[$S] get=[$G]" >> $OUT
  E=$((E+1))
done
$ST setusr 20 0x140001 >/dev/null 2>&1
echo "ENUM_DONE" >> $OUT
