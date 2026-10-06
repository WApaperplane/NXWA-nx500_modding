#!/bin/sh
BB=/opt/usr/nx-ks/busybox
ST="st cap capdtm"
O=$1
IDX=$2
: > $O
e=$3
while [ "$e" -le "$4" ]; do
  ID=$(printf "0x%06x" $(( (IDX << 16) + e )))
  S=$($ST setusr $IDX $ID 2>/dev/null | tr -d '\r' | sed -n 's/.*is \(.*\)/[\1]/p')
  G=$($ST getusr $IDX 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')
  echo "e=$e id=$ID set=$S get=[$G]" >> $O
  e=$((e+1))
done
echo "ENUM_DONE" >> $O
