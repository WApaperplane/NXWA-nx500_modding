#!/bin/sh
# slotmap.sh — 一次写5 个 slot 为 5 种截然不同的颜色，用来反查 UI 枚举 ↔ prefman slot 映射
#
# 背景：木一实测 强红(slot9) 强绿(slot10) 可见，强蓝(slot12) 看不到
#       → slot 12 不是 UI 的"自定义3"，需要重新定位
#
# 配色（互不相同，一眼可辨）：
#   slot 9  = 200/ 60/ 60  强红
#   slot 10 =  60/200/ 60  强绿
#   slot 11 =  60/ 60/200  强蓝
#   slot 12 = 240/240/ 40  强黄
#   slot 13 = 200/ 60/200  强紫
#
# 然后木一在 UI 上逐个选 12 个风格，记录每个的颜色 → 建立完整映射表
PW_BASE=41964
rd() { prefman get 0 "$(printf 0x%05x $1)" l 2>/dev/null | grep -o 'value = [-0-9]*' | sed 's/value = //'; }
wr() { prefman set 0 "$(printf 0x%05x $1)" l "$2" >/dev/null 2>&1; }
so() { echo $(( PW_BASE + $1 * 52 + $2 * 4 )); }

# 只改 R/G/B 三通道，其余参数保持中性
setrgb() { wr $(so 0 $1) $2; wr $(so 1 $1) $3; wr $(so 2 $1) $4; }

setrgb 9  200  60  60
setrgb 10  60 200  60
setrgb 11  60  60 200
setrgb 12 240 240  40
setrgb 13 200  60 200

echo "写入后读回："
echo "  9  $(rd $(so 0 9))/$(rd $(so 1 9))/$(rd $(so 2 9))  强红"
echo " 10  $(rd $(so 0 10))/$(rd $(so 1 10))/$(rd $(so 2 10))  强绿"
echo " 11  $(rd $(so 0 11))/$(rd $(so 1 11))/$(rd $(so 2 11))  强蓝"
echo " 12  $(rd $(so 0 12))/$(rd $(so 1 12))/$(rd $(so 2 12))  强黄"
echo " 13  $(rd $(so 0 13))/$(rd $(so 1 13))/$(rd $(so 2 13))  强紫"
st cap capdtm setusr 20 0x140001 >/dev/null 2>&1
echo "SM_DONE"
