#!/bin/sh
# 干净验证：set + save（不 load）
BB=/opt/usr/nx-ks/busybox
PW_BASE=41964
rd() { prefman get 0 "$(printf 0x%05x $1)" l 2>/dev/null | grep -o 'value = [-0-9]*' | sed 's/value = //'; }
wr() { prefman set 0 "$(printf 0x%05x $1)" l "$2" >/dev/null 2>&1; }
so() { echo $(( PW_BASE + $1 * 52 + $2 * 4 )); }

echo "=== A. set 之后立刻读（未经save/load） ==="
wr $(so 0 12) 120
wr $(so 1 12) 90
wr $(so 2 12) 200
echo "  slot12 R=$(rd $(so 0 12)) G=$(rd $(so 1 12)) B=$(rd $(so 2 12))"
echo "  PW_TYPE now = $(st cap capdtm getusr 20 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')"

echo "=== B. 切 PW_TYPE 到该槽（0x14000c = slot 12） ==="
st cap capdtm setusr 20 0x14000c
echo "  PW_TYPE = $(st cap capdtm getusr 20 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')"
echo "  >>>>> 现在看取景器：是否变成 偏蓝紫（R120/G90/B200）？ <<<<<"
echo "  slot12 读回 R=$(rd $(so 0 12)) G=$(rd $(so 1 12)) B=$(rd $(so 2 12))"
echo "NR2_DONE"
