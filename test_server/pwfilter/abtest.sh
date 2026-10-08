#!/bin/sh
# abtest.sh <K> <tintA> <tintB> <manual|auto>
BB=/opt/usr/nx-ks/busybox
rd() { prefman get 0 "$(printf 0x%05x $1)" l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p'; }
wr() { prefman set 0 "$(printf 0x%05x $1)" l "$2" >/dev/null 2>&1; }

if [ "$4" = "manual" ]; then
  wr 41872 10
  st cap capdtm setusr 6 0x06000a >/dev/null 2>&1
else
  wr 41872 0
  st cap capdtm setusr 6 0x060000 >/dev/null 2>&1
fi
if [ -n "$1" ] && [ "$1" != "0" ]; then wr 41876 "$1"; fi
BA=$(( ($2 << 16) | $3 ))
wr 41920 $BA
wr 41916 $BA

echo "  WB_TYPE=$(rd 41872)  K=$(rd 41876)"
echo "  CUSTOM_BA=$(rd 41916)  K_BA=$(rd 41920)"
echo "  setusr6=$(st cap capdtm getusr 6 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')"
echo "  PW_TYPE=$(st cap capdtm getusr 20 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')"
echo "AB_DONE"

# ---- 追加：tint 归位 + 保留模式 ----
