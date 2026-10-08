#!/bin/sh
# 把 CUSTOM_1 预设成极端可辨状态，用于验证 WB 通路
BB=/opt/usr/nx-ks/busybox
rd() { prefman get 0 "$(printf 0x%05x $1)" l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p'; }
wr() { prefman set 0 "$(printf 0x%05x $1)" l "$2" >/dev/null 2>&1; }
PB=41964
A() { wr $(( PB + $1 * 52 + $2 * 4 )) "$3"; }
# CUSTOM_1 = slot 9，全部设成中性（先清干净）
for d in 0 1 2; do A $d 9 100; done
for d in 3 4 5 6; do A $d 9 10; done
# 切到 CUSTOM_1
st cap capdtm setusr 20 0x140009 >/dev/null 2>&1
echo "CUSTOM_1 已清成中性，切到 PW_CUSTOM1"
echo "  R=$(rd $((PB+0*52+9*4))) G=$(rd $((PB+1*52+9*4))) B=$(rd $((PB+2*52+9*4)))"
echo "  HUE=$(rd $((PB+3*52+9*4))) SAT=$(rd $((PB+4*52+9*4))) SHARP=$(rd $((PB+5*52+9*4))) CON=$(rd $((PB+6*52+9*4)))"
echo "  PW_TYPE=$(st cap capdtm getusr 20 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')"
echo ">>> 现在 CUSTOM_1 是纯中性，画面应为标准无风格效果。这是 WB 实验的干净基准。"
echo "CS_DONE"
