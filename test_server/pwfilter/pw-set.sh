#!/bin/sh
# pw-set.sh - 读取/写入 Picture Wizard 7维参数 (NX500 实机验证版 2026-10-03)
#
# 用法:
#   sh pw-set.sh dump                打印全部风格当前值
#   sh pw-set.sh get<STYLE>          打印指定风格当前值
#   sh pw-set.sh <STYLE> R G B HUE SAT SHARP CONTRAST    写入并落盘
#   sh pw-set.sh rollback            从备份恢复 app 区
#
# 实机实测数据 (NX500 固件 1.12, drime5 3.5.0):
#   app 区 PW 基址 = 0x0a3ec, 参数步进 = 52, 风格步进 = 4
#   中性值: R/G/B = 100, HUE/SAT/SHARP/CONTRAST = 10
#   prefman 不裁剪值域 (-10..255 原样接受) -> 调用方自己约束
#   APPPREF_CHECKSUM (0x0fcbc) 恒为 108, 不随参数变化 -> 无需重算
#   备份路径: /opt/storage/sdcard/_pwtest/app.bak

STYLES="STANDARD VIVID PORTRAIT LANDSCAPE FOREST RETRO COOL CALM CLASSIC CUSTOM_1 CUSTOM_2 CUSTOM_3 CUSTOM_4"
PNAMES="R_COLOR G_COLOR B_COLOR HUE SATURATION SHARPNESS CONTRAST"
BASE=41964
BAK=/opt/storage/sdcard/_pwtest/app.bak

rd() {
    prefman get 0 "$(printf 0x%05x $1)" l 2>/dev/null | grep -o 'value = [-0-9]*' | sed 's/value = //'
}

sid_of() {
    _i=0
    for _s in $STYLES; do
        if [ "$_s" = "$1" ]; then return $_i; fi
        _i=$((_i + 1))
    done
    return 255
}

pname_of() {
    _i=0
    for _p in $PNAMES; do
        if [ "$_i" = "$1" ]; then echo "$_p"; return; fi
        _i=$((_i + 1))
    done
}

show_style() {
    _i=0
    while [ $_i -lt 7 ]; do
        printf "  %-11s %s\n" "$(pname_of $_i)" "$(rd $((BASE + _i * 52 + $1 * 4)))"
        _i=$((_i + 1))
    done
}

dump_all() {
    echo "=== Picture Wizard 全部风格 (13风格 x 7参数) ==="
    _i=0
    for _p in $PNAMES; do
        printf "%-11s" "$_p"
        _j=0
        for _s in $STYLES; do
            printf "%6s" "$(rd $((BASE + _i * 52 + _j * 4)))"
            _j=$((_j + 1))
        done
        echo ""
        _i=$((_i + 1))
    done
    echo ""
    echo "风格:STD VIVD PORT LAND FORES RETRO COOL CALM CLASSIC C1 C2 C3 C4"
    printf "PW_TYPE(0x0a3d4)      = %s\n" "$(rd 41812)"
    printf "SMART_FILTER(0x0a3d0) = %s\n" "$(rd 41808)"
}

if [ $# -lt 1 ]; then
    echo "用法: sh pw-set.sh dump | get<STYLE> | <STYLE> R G B HUE SAT SHARP CONTRAST | rollback"
    echo ""
    dump_all
    exit 0
fi

case "$1" in
    dump|reset)
        dump_all
        exit 0
        ;;
    rollback)
        if [ ! -f "$BAK" ]; then echo "备份不存在: $BAK"; exit 1; fi
        prefman load_file 0 "$BAK"
        prefman save 0
        sync
        echo "已从备份恢复: $BAK"
        exit 0
        ;;
    get*)
        _s=$(echo "$1" | sed 's/^get//' | tr 'a-z' 'A-Z')
        sid_of $_s
        _sid=$?
        if [ $_sid = 255 ]; then echo "未知风格: $_s"; exit 1; fi
        echo "=== $_s (序号 $_sid) ==="
        show_style $_sid
        exit 0
        ;;
esac

STYLE=$(echo "$1" | tr 'a-z' 'A-Z')
sid_of $STYLE
SID=$?
if [ $SID = 255 ]; then
    echo "错误: 未知风格 '$1'"
    echo "可选: $STYLES"
    exit 1
fi

if [ $# -lt 8 ]; then
    echo "错误: 需要 7 个参数 (R G B HUE SAT SHARP CONTRAST)"
    echo "当前 $STYLE 原值:"
    show_style $SID
    exit 1
fi

echo "目标风格 = $STYLE (序号 $SID)"
echo "写入前:"
show_style $SID
echo ""

_i=0
while [ $_i -lt 7 ]; do
    _v=$(eval echo \$$((_i + 2)))
    _off=$(printf 0x%05x $((BASE + _i * 52 + SID * 4)))
    printf "  set %-11s %s = %s\n" "$(pname_of $_i)" "$_off" "$_v"
    prefman set 0 "$_off" l "$_v"
    _i=$((_i + 1))
done

echo ""
prefman save
sync

echo "写入后复读:"
show_style $SID
echo ""
echo "★ 到机身 Picture Wizard 选 $STYLE 后拍一张对比。回滚: sh pw-set.sh rollback"