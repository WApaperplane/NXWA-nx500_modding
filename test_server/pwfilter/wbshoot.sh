#!/bin/sh
# wbshoot.sh <tag> <K> <tintA> <tintB> <mode>
# 在同一 PW 风格（CUSTOM_1 全中性）下，只改 WB，拍一张，落盘到 shots/
BB=/opt/usr/nx-ks/busybox
TAG=$1; K=$2; TA=$3; TB=$4; MODE=$5
D=/mnt/mmc/_pwtest/shots
mkdir -p $D
rd() { prefman get 0 "$(printf 0x%05x $1)" l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p'; }
wr() { prefman set 0 "$(printf 0x%05x $1)" l "$2" >/dev/null 2>&1; }
PB=41964
AD() { echo $(( PB + $1 * 52 + $2 * 4 )); }

# 1)锁定 PW = CUSTOM_1 全中性（排除 PW 干扰）
for d in 0 1 2; do wr $(AD $d 9) 100; done
for d in 3 4 5 6; do wr $(AD $d 9) 10; done
st cap capdtm setusr 20 0x140009 >/dev/null 2>&1

# 2) 设 WB
case $MODE in
  manual) wr 41872 10; st cap capdtm setusr 6 0x06000a >/dev/null 2>&1 ;;
  custom) wr 41872 9;  st cap capdtm setusr 6 0x060009 >/dev/null 2>&1 ;;
  auto)   wr 41872 0;  st cap capdtm setusr 6 0x060000 >/dev/null 2>&1 ;;
esac
[ -n "$K" ] && [ "$K" != "0" ] && wr 41876 "$K"
BA=$(( (TA << 16) | TB ))
wr 41920 $BA
wr 41916 $BA

echo "=== [$TAG] 写入完成 ==="
echo "  PW=CUSTOM_1(全中性)  WB=$MODE  K=$K  tintA=$TA tintB=$TB"
echo "  实读: WB_TYPE=$(rd 41872) K=$(rd 41876) CUSTOM_BA=$(rd 41916) K_BA=$(rd 41920)"
echo "  setusr6=$(st cap capdtm getusr 6 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')"
echo "  setusr20=$(st cap capdtm getusr 20 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')"
echo "SHOOT_NOW"
