#!/bin/sh
# slot12.sh — 往三个自定义槽写可区分的特征值，供 UI 人工对照
# 只用prefman set（不 save），用 setusr 实时切枚举
PW_BASE=41964
rd() { prefman get 0 "$(printf 0x%05x $1)" l 2>/dev/null | grep -o 'value = [-0-9]*' | sed 's/value = //'; }
wr() { prefman set 0 "$(printf 0x%05x $1)" l "$2" >/dev/null 2>&1; }
so() { echo $(( PW_BASE + $1 * 52 + $2 * 4 )); }
set7() { # set7 <slot> <R> <G> <B> <HUE> <SAT> <SHARP> <CON>
  wr $(so 0 $1) $2; wr $(so 1 $1) $3; wr $(so 2 $1) $4
  wr $(so 3 $1) $5; wr $(so 4 $1) $6; wr $(so 5 $1) $7; wr $(so 6 $1) $8
}
prefman save >/dev/null 2>&1
# 三个自定义槽 = slot 9/ 10 / 12（跳过 11）
# 特征：slot9 强红 / slot10 强绿 / slot12 强蓝 —— 一眼可辨
set7 9  200 60  60  10 10 10 10
set7 10 60  200 60  10 10 10 10
set7 12 60  60  200 10 10 10 10
prefman save >/dev/null 2>&1
echo "slot 9  R=$(rd $(so 0 9)) G=$(rd $(so 1 9)) B=$(rd $(so 2 9))  <- 应为强红"
echo "slot 10 R=$(rd $(so 0 10)) G=$(rd $(so 1 10)) B=$(rd $(so 2 10))  <- 应为强绿"
echo "slot 12 R=$(rd $(so 0 12)) G=$(rd $(so 1 12)) B=$(rd $(so 2 12))  <- 应为强蓝"
echo "slot 11 R=$(rd $(so 0 11)) G=$(rd $(so 1 11)) B=$(rd $(so 2 11))  <- 无效槽（应为中性100）"
st cap capdtm setusr 20 0x140001 >/dev/null 2>&1
echo "已回到VIVID"
echo "S12_DONE"
