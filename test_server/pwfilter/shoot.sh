#!/bin/sh
# shoot.sh <tag> — 拍一张照并记录拍摄前后的 PW/WB 状态
BB=/opt/usr/nx-ks/busybox
TAG=$1
D=/mnt/mmc/_pwtest/shots
mkdir -p $D
rd() { prefman get 0 "$(printf 0x%05x $1)" l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p'; }
PB=41964
A() { echo $(( PB + $1 * 52 + $2 * 4 )); }

echo "=== 拍摄前状态 [$TAG] ==="
echo "  PW_TYPE = $(st cap capdtm getusr 20 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')"
echo "  WB      = $(st cap capdtm getusr 6 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')"
echo "  WB_TYPE=$(rd 41872)  K=$(rd 41876)  CUSTOM_BA=$(rd 41916)  K_BA=$(rd 41920)"
echo "  slot9: R=$(rd $(A 0 9)) G=$(rd $(A 1 9)) B=$(rd $(A 2 9)) HUE=$(rd $(A 3 9)) SAT=$(rd $(A 4 9)) SHP=$(rd $(A 5 9)) CON=$(rd $(A 6 9))"
echo
echo "=== 触发快门 ==="
BEFORE=$($BB ls /mnt/mmc/DCIM/*/*.JPG 2>/dev/null | wc -l)
st cap sh 2>&1 | tr -d '\r' | head -3
i=0
while [ $i -lt 20 ]; do
  sleep 1
  AFTER=$($BB ls /mnt/mmc/DCIM/*/*.JPG 2>/dev/null | wc -l)
  if [ "$AFTER" -gt "$BEFORE" ]; then
    echo "  新照片已出现（等待 $i 秒）"
    $BB ls -lt /mnt/mmc/DCIM/*/*.JPG 2>/dev/null | head -1
    break
  fi
  i=$((i+1))
done
[ "$AFTER" = "$BEFORE" ] && echo "  ⚠ 20 秒内没检测到新照片"
echo "SHOOT_DONE"
