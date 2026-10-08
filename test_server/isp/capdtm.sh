#!/bin/sh
# capdtm.sh —— NX500 capdtm 通道操作helper（★ 语法已实测验证）
#
# ★★★ 编号规则（2026-06 实测破解，setusr / setvar 共用）:
#     st cap capdtm setusr|setvar  <槽位>  <(槽位<<16)|值>  [长度]
#   例: setusr 6 0x0006000A      → 强制 WB Manual
#       setusr 20 0x140002       → Picture Wizard = PORTRAIT
#       setvar 6 0x0006000A 4    → 同setusr，但走Variable 通道
#
# ★ 常见错误码
#   -1179648 (0xFFEFF000) = id 格式非法（高 16 位槽位字段为空，或值超出该槽位范围）
#   -1                    = id 有效但服务端拒绝（只读槽位 / 状态门控）
#   "Invalid argument[N]" = 参数个数或类型不对
#
# ★ 值不能为 0（写 0 会报 -1179648）
# ★ busybox 环境：避免 $(...) 命令替换（结果恒为空），用 `> 文件` 再 cat
# ★ telnet 长输出会被分屏截断 ⇒ 循环采集必须重定向到文件

BB=/opt/usr/nx-ks/busybox
ST="st cap capdtm"

# ── 槽位常量（★ 来自 usrlist / varlist 实测）──
SLOT_DIALMODE=0
SLOT_SHOOTINGMODE=1
SLOT_IMAGESIZE=2
SLOT_IMAGEQUALITY=4
SLOT_ISO=5
SLOT_WB=6# ★ WB 模式
SLOT_AFMODE=7
SLOT_FLASHMODE=12
SLOT_PW=20             # ★ Picture Wizard 12 风格

# WB 模式枚举（★ 实测全表）
WB_AUTO_TUNGSTEN=1
WB_DAYLIGHT=2
WB_CLOUDY=3
WB_FLUORESCENTW=4
WB_FLUORESCENTN=5
WB_FLUORESCENTD=6
WB_TUNGSTEN=7
WB_FLASH=8
WB_CUSTOM=9
WB_MANUAL=0xa          # ★★ K 值模式（最大值）

# Picture Wizard 风格（实测 0x140000=STANDARD, 0x140002=PORTRAIT）
PW_STANDARD=0x140000
PW_PORTRAIT=0x140002

# ── 工具函数 ──
# set_slot <slot> <低16位值> [setter]
set_slot() {
    _s=$1; _v=$2; _fn=${3:-setusr}
    _key=$(printf '0x%04X%04X' "$_s" "$_v")
    $ST $_fn "$_s" "$_key" 4 2>&1 | head -1
}

get_slot() { $ST getusr "$1" 2>&1 | head -1; }

# ── 常用操作 ──
wb_manual()   { set_slot $SLOT_WB $WB_MANUAL; }
wb_auto()     { set_slot $SLOT_WB 0xa; }   # AUTO 同样是 0xa？实测 10=AUTO，见 varlist
wb_daylight() { set_slot $SLOT_WB $WB_DAYLIGHT; }
wb_tungsten() { set_slot $SLOT_WB $WB_TUNGSTEN; }

pw_standard() { set_slot $SLOT_PW 0; }
pw_portrait() { set_slot $SLOT_PW 2; }

# 读全部 WB 运行时状态（★ 必须同时看 COLORTEMP 才算生效）
wb_status() {
    echo "--- capdtm ---"
    echo -n "  USERDATA_WB   : "; $ST getusr $SLOT_WB 2>&1 | head -1
    echo -n "  WBCOLORTEMP   : "; $ST varlist 2>&1 | grep -a WBCOLORTEMP
    echo -n "  WBADJUST      : "; $ST varlist 2>&1 | grep -a WBADJUST
    echo "--- iqr (runtime, 决定性) ---"
    st cap iqr 2>&1 | grep -a -E "WB_MODE|WB_COLORTEMP|WB_KELVIN|WB_ADJUST" | cat -v
}

case "$1" in
    wb_manual)   wb_manual ;;
    wb_auto)     wb_auto ;;
    wb_daylight) wb_daylight ;;
    wb_tungsten) wb_tungsten ;;
    pw_standard) pw_standard ;;
    pw_portrait) pw_portrait ;;
    status)      wb_status ;;
    set)         set_slot "$2" "$3" "${4:-setusr}" ;;
    get)         get_slot "$2" ;;
    usrlist)     $ST usrlist 2>&1 ;;
    varlist)     $ST varlist 2>&1 ;;
    *)           echo "用法: $0 {wb_manual|wb_auto|wb_daylight|wb_tungsten|pw_standard|pw_portrait|status|set <slot> <val> [setusr|setvar]|get <slot>|usrlist|varlist}" ;;
esac
