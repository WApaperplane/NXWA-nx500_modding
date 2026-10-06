#!/bin/sh
# ab.sh <A_K> <A_A> <A_B> <B_K> <B_B> <A_MODE> <B_MODE>
# 在同一PW 风格下，只改WB，验证 K 与tint 哪个真正影响画面
BB=/opt/usr/nx-ks/busybox
rd() { prefman get 0 "$(printf 0x%05x $1)" l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p'; }
wr() { prefman set 0 "$(printf 0x%05x $1)" l "$2" >/dev/null 2>&1; }
setwb() { # setwb <K> <A> <B> <mode>
  if [ "$4" = "manual" ]; then
    wr 41872 10; st cap capdtm setusr 6 0x06000a >/dev/null 2>&1
  else
    st cap capdtm setusr 6 0x060000 >/dev/null 2>&1
  fi
  [ -n "$1" ] && [ "$1" != "0" ] && wr 41876 "$1"
  wr 41920 $(( ($2 << 16) | $3 ))
  wr 41916 $(( ($2 << 16) | $3 ))
}
echo "########## A组 ##########"
echo ">>> 请看画面并记住"
setwb $1 $2 $3 $6
echo "  mode=$6  WB_TYPE=$(rd 41872)  K=$(rd 41876)"
echo "  CUSTOM_BA=$(rd 41916)  K_BA=$(rd 41920)"
echo "  setusr6=$(st cap capdtm getusr 6 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')"
echo "AB_A_DONE"
