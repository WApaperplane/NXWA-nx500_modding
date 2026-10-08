#!/bin/bash
# ============================================================
# pw-preview.sh - NX500 滤镜调参预览闭环 (Recipe Lab 式)
#
# 定位: 调参时需要的是"改一个参数 -> 立刻看到画面变化",
#       不是遥控取景(fps/延迟天花板那条 2026-09-07 已放弃)。
#       本脚本用纯已验证能力拼装调参闭环, 不需要新逆向。
#
# 闭环: 改 prefman PW 参数 -> st app nx capture single 拍一张
#       -> 最新 JPG 走已有 web 相册(8080/cgi-bin/dirlist) -> 网页对比
#
# 用法(相机端, 通过 telnet 或 SD 卡脚本执行):
#   sh pw-preview.sh check              # 阶段0: 探测所有依赖命令是否存在
#   sh pw-preview.sh snap                # 拍一张, 打印最新文件路径(给网页用)
#   sh pw-preview.sh set0x0a3ec12345     # 写 PW 偏移 + 自动拍一张
#   sh pw-preview.sh vector R G B H SAT SH CON   # 一次写 CUSTOM_1 全部7维 + 拍
#   sh pw-preview.sh lcdvideo            # 关掉叠加层, 只留 liveview(调参必做)
#   sh pw-preview.sh lcdon
#   sh pw-preview.sh loop <n>           # 连拍n 张(延时摄影式, 用于看稳定性)
#
# 已知相机端路径铁律(项目 MEMORY):
#   busybox 必须绝对路径 /opt/usr/nx-ks/busybox
#   st 在 /usr/bin/st, prefman 在 /usr/bin/prefman
# ============================================================

BB=/opt/usr/nx-ks/busybox
ST=/usr/bin/st
PREF=/usr/bin/prefman
DCIM=/mnt/mmc/DCIM

LOG=/mnt/mmc/pw-preview.log
say() { echo "$*" | tee -a "$LOG"; }

# PW CUSTOM_1 七维偏移(来自 pw_offsets.py 实测解析,13x7 网格严丝合缝)
# 每风格步进 4B, 每参数步进 52B, 基址 0x0a3ec
off_for() {
  # $1 = 参数序号 0..6  $2 = 风格序号 0..12
  # shell 算术里必须用十进制 0x0a3ec = 41964
  _p=$(( $1 * 52 + $2 * 4 + 41964 ))
  printf "0x%05x" $_p
}

latest_jpg() {
  ls -t "$DCIM"/*/*.jpg 2>/dev/null | head -1
}

case "$1" in

check)
    say "=== 依赖探测 ==="
    for c in "$ST" "$PREF" "$BB"; do
        [ -x "$c" ] && say "  OK      $c" || say "  MISSING $c"
    done
    say ""
    say "DCIM 可写: $( [ -d "$DCIM" ] && echo yes || echo no )"
    say ""
    say "-- st app 命令面 --"
    say "bb(lcd):   $($ST app bb 2>&1 | head -2 | tr '\n' ' ')"
    say "nx capture: $($ST app nx capture 2>&1 | head -2 | tr '\n' ' ')"
    say ""
    say "-- 偏移自检 (CUSTOM_1 = 风格9) --"
    for i in 0 1 2 3 4 5 6; do
        say "  param$i -> $(off_for $i 9)"
    done
    say ""
    say "预期: R=0x0a410 G=0x0a444 B=0x0a478 HUE=0x0a4ac SAT=0x0a4e0 SHARP=0x0a514 CON=0x0a548"
    ;;

lcdvideo)
    say "关闭叠加层, 只显示 liveview..."
    $ST app bb lcd video 2>&1 | tee -a "$LOG"
    ;;

lcdon)
    say "恢复完整显示..."
    $ST app bb lcd on 2>&1 | tee -a "$LOG"
    ;;

snap)
    say "触发单张拍摄..."
    $ST app nx capture single 2>&1 | tee -a "$LOG"
    # 等一拍: 单张 + 写卡
    sleep 3
    F=$(latest_jpg)
    if [ -n "$F" ]; then
        say "OK $F"
        # 输出 web 相册可直接用的相对路径
        echo "$F" | sed 's|/mnt/mmc/||' | tee -a "$LOG"
    else
        say "未找到 JPG。检查: 是不是 RAW+JPG 模式? SD 卡满? DCIM 路径变了?"
    fi
    ;;

set)
    OFF=$2
    VAL=$3
    if [ -z "$OFF" ] || [ -z "$VAL" ]; then say "用法: set <offset> <dec-value>"; exit 1; fi
    say "写 $OFF = $VAL"
    $PREF set 0 "$OFF" l "$VAL" 2>&1 | tee -a "$LOG"
    $PREF save 2>&1 | tee -a "$LOG"
    sync
    $0 snap
    ;;

vector)
    # vector R G B HUE SAT SHARP CONTRAST  -> 写 CUSTOM_1
    if [ $# -ne 8 ]; then
        say "用法: vector <R> <G> <B> <HUE> <SAT> <SHARP> <CONTRAST>   (均为十进制整数)"
        say "例:   vector 0 0 0 0 -3 -1 0= 低饱和哑光(接近 CLASSIC)"
        exit 1
    fi
    names="R_COLOR G_COLOR B_COLOR HUE SATURATION SHARPNESS CONTRAST"
    i=1
    for p in $names; do
        o=$(off_for $i 9)
        v=$(eval echo \$$i)
        say "  $p @ $o = $v"
        $PREF set 0 "$o" l "$v" >> "$LOG" 2>&1
        i=$(( i + 1 ))
    done
    say "写 CUSTOM_1 (风格 9) 完成, save..."
    $PREF save >> "$LOG" 2>&1
    sync
    say ""
    $0 snap
    ;;

loop)
    N=${2:-5}
    say "连拍 $N 张..."
    i=1
    while [ $i -le $N ]; do
        say "--- 第 $i/$N 张 ---"
        $ST app nx capture single >> "$LOG" 2>&1
        sleep 3
        F=$(latest_jpg)
        say "    $F"
        i=$(( i + 1 ))
    done
    say "完成。最新的: $(latest_jpg)"
    ;;

*)
    say "用法: sh pw-preview.sh {check|snap|set|vector|lcdvideo|lcdon|loop}"
    say ""
    say "典型调参流程:"
    say "  1. check                 探测命令是否存在"
    say "  2. lcdvideo              关叠加层(只留liveview, 避免数字压画面)"
    say "  3. vector 0 0 0 0 -3 -1 0   改 7 维 + 自动拍一张"
    say "  4. 浏览器打开 web 相册刷新对比"
    ;;

esac

exit 0