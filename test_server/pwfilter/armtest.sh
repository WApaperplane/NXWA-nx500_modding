#!/bin/sh
# armtest.sh — 重启验证脚本 (2026-10-04)
#
# 目的：验证「prefman 写入 + 重启」能否让 ISP 引擎真正应用配方。
#   背景：prefman set/save 只改存储( /opt/pref/pref_app.bin )，
#         引擎开机时读一次，之后不再读 → 必须重启才生效。
#         setvar 七种参数形式全被拒( VariableData is not set )。
#
# 本脚本只做一件事：把 slot10 (CUSTOM_2) 的 SAT 设为 0 = 纯黑白。
#   重启后若画面变黑白 → 整条链路成立。
#   重启后若仍是彩色 → 引擎连重启也不读 prefman，需另找路径。
#
# 用法: sh armtest.sh arm    布置（设 SAT=0 + save + 切 CUSTOM_2）
#       sh armtest.sh revert 还原（SAT 回14 + save + 切 STANDARD）
#       sh armtest.sh status  查看当前值

PW_BASE=41964          # 0x0a3ec
ST="st cap capdtm"

# slot10 SAT 偏移 =基址 + 参数4*步进52 + 风格10*步进4
SAT_OFF=$(( PW_BASE + 4 * 52 + 10 * 4 ))

rd() {
    prefman get 0 "$(printf 0x%05x $1)" l 2>/dev/null \
        | grep -o 'value = [-0-9]*' | sed 's/value = //'
}

wr() {
    prefman set 0 "$(printf 0x%05x $1)" l "$2" >/dev/null 2>&1
}

do_arm() {
    echo "=== ARM: slot10 SAT -> 0 (纯黑白) ==="
    echo "offset = $(printf 0x%05x $SAT_OFF)"
    echo "before SAT = $(rd $SAT_OFF)"
    wr $SAT_OFF 0
    prefman save >/dev/null 2>&1
    sync
    echo "after  SAT = $(rd $SAT_OFF)   (saved)"
    # 切到 CUSTOM_2 (prefman 风格索引 10)
    $ST setusr 20 0x14000a >/dev/null 2>&1
    echo "PW = $($ST getusr 20 2>/dev/null | tr -d '\r' | sed 's/.*UserData is //; s/ *(0x[0-9a-f]*)$//')"
    echo
    echo ">>> 现在重启相机，开机后切回A 档拍摄模式看画面 <<<<<"
    echo ">>> 期望: 纯黑白 <<<<<"
}

do_revert() {
    echo "=== REVERT: slot10 SAT -> 14 ==="
    wr $SAT_OFF 14
    prefman save >/dev/null 2>&1
    sync
    echo "SAT = $(rd $SAT_OFF)   (saved)"
    $ST setusr 20 0x140000 >/dev/null 2>&1
    echo "PW = $($ST getusr 20 2>/dev/null | tr -d '\r' | sed 's/.*UserData is //; s/ *(0x[0-9a-f]*)$//')"
}

do_status() {
    echo "slot10 各维 (偏移 $(printf 0x%05x $PW_BASE)起):"
    printf "  R=%s G=%s B=%s HUE=%s SAT=%s SHARP=%s CONTRAST=%s\n" \
        "$(rd $((PW_BASE + 0*52 + 10*4)))" "$(rd $((PW_BASE + 1*52 + 10*4)))" \
        "$(rd $((PW_BASE + 2*52 + 10*4)))" "$(rd $((PW_BASE + 3*52 + 10*4)))" \
        "$(rd $((PW_BASE + 4*52 + 10*4)))" "$(rd $((PW_BASE + 5*52 + 10*4)))" \
        "$(rd $((PW_BASE + 6*52 + 10*4)))"
    printf "  WB_K=%s  tint=%s\n" "$(prefman get 0 0x0a394 l 2>/dev/null | grep -o 'value = [-0-9]*' | sed 's/value = //')" \
        "$(prefman get 0 0x0a3bc l 2>/dev/null | grep -o 'value = [-0-9]*' | sed 's/value = //')"
}

case "$1" in
    arm)do_arm ;;
    revert)   do_revert ;;
    status)   do_status ;;
    *)echo "用法: sh armtest.sh arm|revert|status"; exit 1 ;;
esac
