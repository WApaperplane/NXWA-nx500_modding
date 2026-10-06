#!/bin/sh
# cwb-test.sh — CWB (Custom White Balance) 三通道独立增益测试
#
# CWB = NX500 上独立于 PW 的第四个色彩域（对应 Recipe Lab 说的
#      "one hidden colour setting Sony never exposed"）。
# 位置: APPPREF_CWB_RED/GREEN/BLUE = 0x00a3c4 / c8 / cc
# 实测: prefman 完全不裁剪，24 位可写，三通道互相独立。
# 原始值: R=0x021300  G=0x010000  B=0x012330 (high16|low16 双段打包)
#
# 用法:
#   sh cwb-test.sh base      还原出厂 (R=0x021300 G=0x010000 B=0x012330)
#   sh cwb-test.sh warm      暖调 (红提升 / 蓝压低)
#   sh cwb-test.sh cool      冷调 (蓝提升 / 红压低)
#   sh cwb-test.sh green     绿调 (绿大幅提升)
#   sh cwb-test.sh magenta   洋红 (红+蓝提升)
#   sh cwb-test.sh extreme   极端 (看引擎认不认这个范围)
#   sh cwb-test.sh show      读回当前值

R=41860     # 0x00a3c4
G=41864     # 0x00a3c8
B=41868     # 0x00a3cc
BASE_R=135936   # 0x021300
BASE_G=65536    # 0x010000
BASE_B=74496    # 0x012330

rd() {
    prefman get 0 "$(printf 0x%05x $1)" l 2>/dev/null \
        | grep -o 'value = [-0-9]*' | sed 's/value = //'
}

# ★ dual16 <hi> <lo>  打包成一个 24 位值
dual16() {
    echo $(( ($1 << 16) | $2 ))
}

wr() {
    prefman set 0 "$(printf 0x%05x $1)" l "$2" >/dev/null 2>&1
}

apply3() {
    echo "  CWB: R=$(printf 0x%06x $1)  G=$(printf 0x%06x $2)  B=$(printf 0x%06x $3)"
    wr $R "$1"; wr $G "$2"; wr $B "$3"
    prefman save >/dev/null 2>&1
    sync
    echo "  读回: R=$(rd $R) G=$(rd $G) B=$(rd $B)"
}

case "$1" in
    base)
        echo "== 还原 CWB 出厂值 =="
        apply3 $BASE_R $BASE_G $BASE_B
        ;;
    warm)
        echo "== 暖调 (高16位: R+2 G+1 B不变; 低16位: R+2000 B-2000) =="
        apply3 $(dual16 4 6864) $(dual16 1 0) $(dual16 1 6960)
        ;;
    cool)
        echo "== 冷调 (R 压低 / B 提升) =="
        apply3 $(dual16 1 2864) $(dual16 1 0) $(dual16 3 10960)
        ;;
    green)
        echo "== 绿调 (G 高16位大幅提升) =="
        apply3 $(dual16 2 1300) $(dual16 5 0) $(dual16 1 2330)
        ;;
    magenta)
        echo "== 洋红 (R 与 B 同时提升, G 压低) =="
        apply3 $(dual16 4 6864) $(dual16 0 0) $(dual16 3 10960)
        ;;
    extreme)
        echo "== 极端 (全通道拉满, 测试引擎是否接受) =="
        apply3 16777215 8388608 12582912
        ;;
    show)
        echo "R=$(rd $R) (0x$(printf %06x $(rd $R)))"
        echo "G=$(rd $G) (0x$(printf %06x $(rd $G)))"
        echo "B=$(rd $B) (0x$(printf %06x $(rd $B)))"
        ;;
    *)
        echo "用法: sh cwb-test.sh base|warm|cool|green|magenta|extreme|show"
        exit 1
        ;;
esac
