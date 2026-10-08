#!/bin/bash
# ============================================================
# lv-probe.sh - NX500 liveview 控制面探测 (st cap live)
#
# 重要性(2026-10-04 查证ottokiksmaler/nx500_nx1_modding 的 ST Commands.md):
#   我之前判定"相机端没有 liveview 通路 / 要买 HDMI 采集卡"——错的。
#   `st cap live` 是完整的 liveview 控制面, 社区文档化的命令:
#     st cap live start / startPP / stop / freeze / release
#     st cap live setpath 0-9   0:OTF 1:IPCout 2:RawOut 3:Ldc Out
#                              4-7:同上120FPS 8:panorama 9:MFZoom
#     st cap live dump 2-5 (cnt)      ← 直接 dump 帧数
#     st cap live resize op1 op2 ...
#     st cap live sd sensorframerate 12..240 / outputframerate / dataframerate
#     st cap live sd hdmioutsize 0-3  (0:480 1:576 2:720 3:1080)
#     st cap live sd smartfiltermode 0-16 (15:SmartFilterOFF)  ← 直接控Smart Filter!
#     st cap live sd moviemode / panoramatype / mfassist / zoommagnification ...
#     st cap live resize / loglevel / log all|3d|cb|msg|framerate|normal|warnning|error
#   另有 st cap fenx lv [otf|mem|120|stop]  ← "mem" = liveview memory out
#
# 本脚本只做只读探测 + help 抓取, 不改任何状态(dump 除外, 见 dump 子命令)。
#
# 用法:
#   sh lv-probe.sh help      # 抓 liveview 命令面帮助(只读, 最安全)
#   sh lv-probe.sh status# 探测当前 liveview 状态
#   sh lv-probe.sh paths     # 列出 setpath 0-9 各路径(逐个设了再还原)
#   sh lv-probe.sh dump <n>  # 试 dump n 帧(2-5), 看能否拿到 liveview 数据
#   sh lv-probe.sh rate# 列出可用帧率
#   sh lv-probe.sh sfilter   # 探测 smartfiltermode 0-16
# ============================================================

ST=/usr/bin/st
BB=/opt/usr/nx-ks/busybox
LOG=/mnt/mmc/lv-probe.log

say() { echo "$*" | tee -a "$LOG"; }

case "$1" in

help)
    say "=== st cap live 帮助 ==="
    $ST cap live 2>&1 | tee -a "$LOG"
    say ""
    say "=== st cap fenx lv 帮助 ==="
    $ST cap fenx lv 2>&1 | tee -a "$LOG"
    say ""
    say "=== st cap live log 帮助 ==="
    $ST cap live log 2>&1 | tee -a "$LOG"
    ;;

status)
    say "=== liveview 状态探测 ==="
    say "-- 显示器输出模式 (MONITOROUT) --"
    $ST cap capdtm getusr MONITOROUT 2>&1 | tee -a "$LOG"
    say ""
    say "-- 当前分辨率 --"
    for k in RESOLUTION RESMODE S2_COUNT; do
        say "  $k = $($ST cap capdtm getusr $k 2>&1 | tr '\n' ' ')"
    done
    say ""
    say "-- 进程里的 capture 线程 --"
    ps -w 2>/dev/null | grep -iE "capdtm|capture|a7" | grep -v grep | tee -a "$LOG"
    say ""
    say "-- dmesg 里的 liveview/fenx --"
    dmesg 2>/dev/null | grep -iE "liveview|lview|fenx|otf|stream" | tail -20 | tee -a "$LOG"
    ;;

paths)
    say "=== 探测 setpath 各路径 ==="
    say "注意: 这会改liveview 输出路径。测完务必 restore (path 0 = OTF)"
    say ""
    for p in 0 1 2 3 4 5 6 7 8 9; do
        say "--- setpath $p ---"
        $ST cap live setpath $p 2>&1 | tee -a "$LOG"
        sleep 1
    done
    say ""
    say "还原: st cap live setpath 0"
    $ST cap live setpath 0 2>&1 | tee -a "$LOG"
    ;;

dump)
    N=${2:-2}
    say "=== 试dump $N 帧 liveview ==="
    say "先设路径 2 (RawOut) —— 原始数据最可能落盘"
    $ST cap live setpath 2 2>&1 | tee -a "$LOG"
    sleep 1
    say "执行 dump..."
    $ST cap live dump $N 2>&1 | tee -a "$LOG"
    sleep 2
    say ""
    say "-- 找新生成的文件 --"
    ls -lat /mnt/mmc/ 2>/dev/null | head -10 | tee -a "$LOG"
    ls -lat /tmp/ 2>/dev/null | head -10 | tee -a "$LOG"
    find /mnt/mmc /tmp -newermt '-3 minutes' -type f 2>/dev/null | head -20 | tee -a "$LOG"
    say ""
    say "还原: st cap live setpath 0"
    $ST cap live setpath 0 2>&1 | tee -a "$LOG"
    ;;

rate)
    say "=== 可用帧率 ==="
    for r in 12 15 20 24 25 30 40 50 60 100 120 240; do
        say "  sensorframerate=$r -> $($ST cap live sd sensorframerate $r 2>&1 | tr '\n' ' ')"
    done
    say "还原: st cap live sd sensorframerate 30"
    $ST cap live sd sensorframerate 30 2>&1 | tee -a "$LOG"
    ;;

sfilter)
    say "=== smartfiltermode 探测 (0-16, 15=OFF) ==="
    for m in 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16; do
        say "  smartfiltermode=$m -> $($ST cap live sd smartfiltermode $m 2>&1 | tr '\n' ' ')"
    done
    say "还原: st cap live sd smartfiltermode 15"
    $ST cap live sd smartfiltermode 15 2>&1 | tee -a "$LOG"
    say ""
    say "★ 若这些值能改且出片/画面变化 -> Smart Filter 是比 prefman PW 更直接的通路"
    ;;

*)
    say "用法: sh lv-probe.sh {help|status|paths|dump <n>|rate|sfilter}"
    ;;

esac

exit 0
