#!/bin/sh
# pw-setusr.sh - NX500 实时风格通道 (2026-10-04 实机打通)
#
# ★ 正确语法（踩了 4轮才找到，社区文档没写）：
#     st cap capdtm setusr <索引> <DATA_ID_十六进制完整值>
#   第二参数必须是**完整 DATA ID**（如 0x140001），不是裸值 1/2/3。
#   传错形式会返回 "UserData is not set -1179648"，被误判为 dfmsd 未启动。
#   正确返回是 "UserData is set"。
#
# 格式化: getusr 回显 NAME (0xHHHHHH)
#   DATA ID = 0x<index><enum>    例: PW 索引20 -> 0x140000 = 索引0x14 + 枚举 0
#                                索引0x14/0x3e/0x1b/0x15 是固定的分组前缀
#
# 用法:
#   sh pw-setusr.sh pw <0-12>        切Picture Wizard 风格 (实时)
#   sh pw-setusr.sh sft <0-13>       切 Smart Filter 类型 (实时)
#   sh pw-setusr.sh sfs <0-4>        切 Smart Filter 强度
#   sh pw-setusr.sh get              读回当前全部关键维度
#   sh pw-setusr.sh list-pw          列出 PW 全部枚举
#   sh pw-setusr.sh list-sft         列出 Smart Filter 全部类型
#   sh pw-setusr.sh restore          恢复出厂 (STANDARD + SmartFilter OFF)
#
# 前提: 需在拍摄模式。dfmsd 不需要（它只是脚本/OSD 通道，与 PW 无关）。

ST="st cap capdtm"

# ---- 索引与 DATA ID 前缀（实机getusr 逐个确认）----
I_PW=20          # 0x14xxxx  Picture Wizard 风格
I_SFT=62         # 0x3exxxx  Smart Filter 类型
I_SFS=63         # 0x3fxxxx  Smart Filter 强度
I_SART=27        # 0x1bxxxx  SmartArt
I_SARTLV=28      # 0x1cxxxx  SmartArt 强度
I_SRANGE=21      # 0x15xxxx  SmartRange
I_PWBRK0=35      # 35..47    PWBRK x13 (风格已编辑标志)
I_FACETONE=25    # 0x19xxxx
I_CS=50          # 0x32xxxx  ColorSpace
I_HDRART=77      # 0x4dxxxx
I_LLS=78         # 0x4exxxx

PW_NAMES="STANDARD VIVID PORTRAIT LANDSCAPE FOREST RETRO COOL CALM CLASSIC CUSTOM_1 CUSTOM_2 CUSTOM_3 CUSTOM_4"
SFT_NAMES="OFF VIGNETTING MINIATURE_H MINIATURE_V RANDOMMOSAIC COLOREDPENCIL WATERCOLOR WASH_DRAWING OILPAINTING INKPAINTING RADIALBLUR FISHEYE ACRYL NEGATIVE"

hex() {
    printf "0x%06x" $(( $1 << 16 | $2 ))
}

getval() {
    # getusr 回显格式: "UserData is NAME (0xHHHHHH)"  -> 只取 NAME (hex)
    _r=$($ST getusr $1 2>/dev/null | tr -d '\r' | sed 's/.*UserData is //')
    echo "$_r" | sed 's/ *(0x[0-9a-fA-F]*)$//'
}

gethex() {
    $ST getusr $1 2>/dev/null | tr -d '\r' | sed -n 's/.*(\(0x[0-9a-fA-F]*\)).*/\1/p'
}

setval() {
    # $1=索引 $2=DATA ID
    $ST setusr $1 $2 2>/dev/null | tr -d '\r' | sed 's/^ *//'
}

name_at() {
    _i=0
    for _n in $2; do
        if [ "$_i" = "$1" ]; then echo "$_n"; return; fi
        _i=$(( _i + 1 ))
    done
}

cmd_pw() {
    _d=$(hex 20 $1)
    printf "set PW = %-11s (%s) -> " "$(name_at $1 "$PW_NAMES")" "$_d"
    setval $I_PW $_d
}

cmd_sft() {
    _d=$(hex 62 $1)
    printf "set SmartFilter = %-15s (%s) -> " "$(name_at $1 "$SFT_NAMES")" "$_d"
    setval $I_SFT $_d
}

cmd_sfs() {
    _d=$(hex 63 $1)
    printf "set SmartFilterSize = %s -> " "$_d"
    setval $I_SFS $_d
}

cmd_get() {
    echo "=== 当前实时风格状态 ==="
    printf "  %-14s %-14s %s\n" "USERDATA_PW" "SMARTFILTER" "SMARTSIZE"
    printf "  %-14s %-14s %s\n" "$(getval $I_PW)" "$(getval $I_SFT)" "$(getval $I_SFS)"
    echo
    echo "--- 其它维度 ---"
    printf "  %-16s %s\n" "SMARTRANGE" "$(getval $I_SRANGE)"
    printf "  %-16s %s\n" "SMARTART" "$(getval $I_SART)"
    printf "  %-16s %s\n" "SMARTARTLEVEL" "$(getval $I_SARTLV)"
    printf "  %-16s %s\n" "FACETONE" "$(getval $I_FACETONE)"
    printf "  %-16s %s\n" "COLORSPACE" "$(getval $I_CS)"
    printf "  %-16s %s\n" "HDRARTLEVEL" "$(getval $I_HDRART)"
    printf "  %-16s %s\n" "LLSLEVEL" "$(getval $I_LLS)"
    echo
    echo "--- PW 参数块 (prefman 侧, 需 prefman 才有值) ---"
    for _o in 0x0a3ec 0x0a420 0x0a454 0x0a488 0x0a4bc 0x0a4f0 0x0a524; do
        printf "  %-9s %s\n" "$_o" "$(prefman get 0 $_o l 2>/dev/null | grep -o 'value = [-0-9]*' | sed 's/value = //')"
    done
}

cmd_list_pw() {
    echo "=== Picture Wizard 13 风格 -> DATA ID ==="
    _i=0
    for _n in $PW_NAMES; do
        printf "  %2d%-11s %s\n" $_i "$_n" "$(hex 20 $_i)"
        _i=$(( _i + 1 ))
    done
}

cmd_list_sft() {
    echo "=== Smart Filter 类型 -> DATA ID ==="
    _i=0
    for _n in $SFT_NAMES; do
        printf "  %2d%-15s %s\n" $_i "$_n" "$(hex 62 $_i)"
        _i=$(( _i + 1 ))
    done
}

cmd_restore() {
    echo "恢复出厂状态..."
    setval $I_SFT $(hex 62 0)
    setval $I_SFS $(hex 63 0)
    setval $I_PW $(hex 20 0)
    echo "  PW        = $(getval $I_PW)"
    echo "  SmartFilt = $(getval $I_SFT)"
}

case "$1" in
    pw)         cmd_pw "$2" ;;
    sft)        cmd_sft "$2" ;;
    sfs)        cmd_sfs "$2" ;;
    get)        cmd_get ;;
    list-pw)    cmd_list_pw ;;
    list-sft)   cmd_list_sft ;;
    restore)    cmd_restore ;;
    *)          echo "用法: sh pw-setusr.sh pw|sft|sfs|get|list-pw|list-sft|restore"; exit 1 ;;
esac
