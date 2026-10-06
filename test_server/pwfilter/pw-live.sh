#!/bin/sh
# pw-live.sh - NX500 实时风格通道探针 (2026-10-04 实机)
#
# 背景：Recipe Lab(Sony) 的实时预览不是自己算像素，而是把参数写进相机
#       自己的 ISP 风格引擎，引擎在渲染 liveview 的同时顺带渲染风格 -> CPU 成本 0。
#       NX500 的对等物 = capdtm 的 userdata (USERDATA_PW / PWBRK / SMARTFILTER*)。
#       本脚本只做只读探测 + 可选写入，不碰 prefman/eMMC。
#
# 用法:
#   sh pw-live.sh list <start> <end>   扫描 userdata 索引区间并打印实况值
#   sh pw-live.sh get 20               读单个 userdata
#   sh pw-live.sh set 20 <val>         写 userdata (4 字节) 并读回验证
#   sh pw-live.sh enum 20 <max>        枚举 userdata 合法取值
#   sh pw-live.sh vars                 打印 PW 相关实时变量 + 尝试 setvar
#
# 实机环境：NX500 固件 1.12, drime5 3.5.0, root 空密码 telnet
# 注意：setusr 写入生效的前提是 capdtm 运行时已接管 —— 相机不在拍摄模式时
#       写入会被静默丢弃（值不跳变、无报错）。必须人工进拍摄模式后复测。

ST="st cap capdtm"

# ---- 实机确认的 userdata 索引 (2026-10-04) ----
# 注意：社区文档 ST_CAP_CAPDTM.md 里的索引是多个 profile 混编，全部错位，
#       必须以本表为准（本表为 getusr 实测）。
IDX_PW=20                  # USERDATA_PW
IDX_SMARTFILTER_T=62       # SMARTFILTERTYPE
IDX_SMARTFILTER_S=63       # SMARTFILTERSIZE
IDX_COLORSPACE=50          # COLORSPACE
IDX_SMARTRANGE=21          # SMARTRANGE
IDX_SMARTART=27            # SMARTART
IDX_SMARTARTLEVEL=28       # SMARTARTLEVEL
IDX_FACETONE=25            # FACETONE
IDX_HDRARTLEVEL=77         # HDRARTLEVEL
IDX_LLSLEVEL=78            # LLSLEVEL
IDX_PWBRK0=35              # PWBRKSTANDARD .. PWBRKCUSTOM4 (35..47, 13 槽)

# ---- PW 实时变量 (varlist, 只读镜像) ----
V_PWSAT=15
V_PWSHARP=16
V_PWCONT=17
V_PWHUE=51
V_PWCOLOR_R=48
V_PWCOLOR_G=49
V_PWCOLOR_B=50

clean() {
    tr -d '\r' | sed 's/^.*UserData is //'
}

cmd_list() {
    _i=$1
    _end=$2
    while [ $_i -le $_end ]; do
        printf "%3d  " $_i
        $ST getusr $_i 2>/dev/null | clean
        _i=$(( _i + 1 ))
    done
}

cmd_get() {
    $ST getusr $1 2>/dev/null | clean
}

cmd_set() {
    _idx=$1
    _val=$2
    printf "before: "
    cmd_get $_idx
    $ST setusr $_idx $_val 4 >/dev/null 2>&1
    printf "after : "
    cmd_get $_idx
    if [ "$_val" -gt 15 ]; then
        printf "hint  : 十六进制 ID 会被拒(getusr Invalid argument)，只吃十进制索引\n"
    fi
}

cmd_enum() {
    _idx=$1
    _max=$2
    _v=0
    while [ $_v -le $_max ]; do
        $ST setusr $_idx $_v 4 >/dev/null 2>&1
        printf "  %2d -> " $_v
        cmd_get $_idx
        _v=$(( _v + 1 ))
    done
}

cmd_vars() {
    echo "=== PW 实时变量 (varlist 声明值vs getvar 实况) ==="
    printf "%-22s %-10s %-10s %-10s %-10s\n" NAME DECL GETVAR SETVAR RESULT
    for _p in V_PWCOLOR_R:48 V_PWCOLOR_G:49 V_PWCOLOR_B:50 V_PWSAT:15 \
              V_PWSHARP:16 V_PWCONT:17 V_PWHUE:51; do
        _n=${_p%%:*}
        _i=${_p##*:}
        _d=$($ST getvar $_i 2>/dev/null | sed 's/^.*Variable Data is //')
        _r=$($ST setvar $_i 100 4 2>&1 | sed 's/^.*VariableData //')
        printf "%-22s %-10s %-10s %-10s\n" $_n "$_d" "$_d" "$_r"
    done
    echo
    echo "注：PW 系列变量 setvar 返回 'VariableData is not set' = 派生只读镜像，"
    echo "    引擎不接受直接写；真写入路径是 setusr USERDATA_PW(20) 或 prefman PW 参数块。"
}

case "$1" in
    list)  cmd_list "$2" "$3" ;;
    get)   cmd_get "$2" ;;
    set)   cmd_set "$2" "$3" ;;
    enum)  cmd_enum "$2" "$3" ;;
    vars)  cmd_vars ;;
    *)     echo "用法: sh pw-live.sh list|s|enum|vars ..."; exit 1 ;;
esac
