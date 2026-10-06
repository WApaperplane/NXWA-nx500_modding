#!/bin/bash
# ============================================================
# pw-probe.sh - NX500 Picture Wizard 自定义参数探测 + 写入验证
#
# 目标: 搞清 prefman app 区 13 风格 x 7 参数的值域与语义,
#       验证 prefman set/save 能否真正改变 JPEG 出片。
#依据: Prefman_tool.md (ottokiksmaler/nx500_nx1_modding)
#       + ST_CAP_CAPDTM.md 的 varlist
#
# 部署: 放 SD 卡根, info.tg 内容 = "nx_cs.adj", nx_cs.adj 内容 =
#       "shell script /mnt/mmc/pw-probe.sh"
# 危险: 阶段 3 会写prefman 并 save。首次运行请务必在阶段 1/2 看完
#       备份文件确认后再开阶段 3。
# ============================================================

LOG=/mnt/mmc/pw-probe.log
BIN=/mnt/mmc/pw_probe_backup
mkdir -p $BIN 2>/dev/null

say() { echo "$*" >> "$LOG"; }
hr() { say "--------------------------------------------------"; }

say "=== pw-probe $(date) ==="

# ------------------------------------------------------------
# 阶段 0: 确认工具存在
# ------------------------------------------------------------
hr
say "[阶段0] 工具可用性"
say "prefman: $(which prefman 2>/dev/null || echo MISSING)"
say "prefman.sh: $(which prefman.sh 2>/dev/null || echo MISSING)"
say "dfmstool: $(which dfmstool 2>/dev/null || echo MISSING)"
say "st: $(which st 2>/dev/null || echo MISSING)"
if [ ! -x /usr/bin/prefman ]; then
    say "prefman 不存在，本脚本无法继续。后续请改用 capdtm varlist 路线。"
    sync; sync; sync
    echo "=== done (early exit) ===" >> "$LOG"
    exit 0
fi

# ------------------------------------------------------------
# 阶段 1: 全量备份（必做）
# ------------------------------------------------------------
hr
say "[阶段1] 备份全部 pref 区"
prefman load 2>&1 >> "$LOG"
if prefman save_file 0 $BIN/pref_app.bin 2>&1 >> "$LOG"; then
    say "OK pref_app.bin"
else
    say "FAIL pref_app.bin"
fi
for id in 1 2 3 4 5 6 7 8 9 10; do
    prefman save_file $id $BIN/pref_$id.bin >> "$LOG" 2>&1 && say "OK pref_$id.bin" || say "FAIL pref_$id.bin"
done
say "备份目录: $BIN"
ls -la $BIN >> "$LOG" 2>&1

# ------------------------------------------------------------
# 阶段 2: 只读探测 —— 拿到值域与语义
# ------------------------------------------------------------
hr
say "[阶段2] 读PW 全部字段当前值"

# 2.1 入口字段
for pair in "0x0a3d0 SMART_FILTER" "0x0a3d4 PW_TYPE" "0x0a3d8 OFF_COLOR" \
            "0x0a3dc OFF_SATURATION" "0x0a3e0 OFF_SHARPNESS" \
            "0x0a3e4 OFF_CONTRAST" "0x0a3e8 OFF_HUE"; do
    set -- $pair
    v=$(prefman get 0 $1 l 2>/dev/null | grep value)
    say "  $2 ($1) = $v"
done

# 2.2 13 风格 x 7 参数 矩阵
# 布局: 基址0x0a3ec, 按参数分组, 每组 13 模式 x 4 字节(步进 52)
say ""
say "  风格矩阵(行=参数, 列=STANDARD..CUSTOM_4):"
say "  %-12s %s" "" "STANDARD VIVID PORTRAIT LANDSCAPE FOREST RETRO COOL CALM CLASSIC C1 C2 C3 C4"
BASE=0x0a3ec
MODES="STANDARD VIVID PORTRAIT LANDSCAPE FOREST RETRO COOL CALM CLASSIC CUSTOM_1 CUSTOM_2 CUSTOM_3 CUSTOM_4"
for pi in 0 1 2 3 4 5 6; do
    case $pi in
        0) P=R_COLOR ;;
        1) P=G_COLOR ;;
        2) P=B_COLOR ;;
        3) P=HUE ;;
        4) P=SATURATION ;;
        5) P=SHARPNESS ;;
        6) P=CONTRAST ;;
    esac
    rowbase=$(( BASE + pi * 52 ))
    line=""
    for mi in 0 1 2 3 4 5 6 7 8 9 10 11 12; do
        off=$(printf "0x%05x" $(( rowbase + mi * 4 )))
        v=$(prefman get 0 $off l 2>/dev/null | grep value | sed 's/value = //')
        line="$line $v"
    done
    say "  %-12s%s" "$P" "$line"
done

# 2.3 capdtm varlist 的 PW 变量（对照用）
hr
say "[阶段2b] capdtm varlist PW 变量 (变量ID 是关键线索)"
echo "" >> "$LOG"
st cap capdtm varlist 2>&1 | sed -n '1,6p' >> "$LOG" 2>&1
st cap capdtm varlist 2>&1 | grep -iE "PW|COLOR" >> "$LOG" 2>&1
say "  期望看到: VARIABLE_PWCOLOR / PWSATURATION / PWSHARPNESS /"
say "            PWCONTRAST / PWHUE / PWCOLOR_R / _G / _B"
say "  若出现, 说明 capdtm 侧也有 PW 实时变量 -> 可能有 setvar 写接口"
say "  可试: st cap capdtm setvar <id> <val>  (本次未验证, 命令可能不存在)"

# 2.4 参考: 当前 PW 模式与capdtm 侧读数
hr
say "[阶段2c] capdtm PW 现状"
st cap capdtm getusr 20 >> "$LOG" 2>&1

# ------------------------------------------------------------
# 阶段 3: 写入验证（默认关闭,需手动改RUN_WRITE=1）
# ------------------------------------------------------------
hr
RUN_WRITE=0
if [ "$RUN_WRITE" = "1" ]; then
    say "[阶段3] 写入验证 —— 已开启"
    say "步骤: 读当前 PW_TYPE 与 CUSTOM_1 组基线"
    B_TYPE=$(prefman get 0 0x0a3d4 l | grep value | sed 's/value = //')
    B_C1R=$(prefman get 0 0x0a410 l | grep value | sed 's/value = //')   # CUSTOM_1_R_COLOR
    B_C1C=$(prefman get 0 0x0a548 l | grep value | sed 's/value = //')   # CUSTOM_1_CONTRAST
    say "  改前 PW_TYPE=$B_TYPE CUSTOM_1_R=$B_C1R CUSTOM_1_CONTRAST=$B_C1C"

    say "  写入: PW_TYPE=9(CUSTOM_1), CUSTOM_1_R_COLOR 加 1, CONTRAST 加 1"
    prefman set 0 0x0a3d4 l 9      >> "$LOG" 2>&1
    prefman set 0 0x0a410 l $(( B_C1R + 1 ))  >> "$LOG" 2>&1
    prefman set 0 0x0a548 l $(( B_C1C + 1 ))  >> "$LOG" 2>&1

    say "  内存回读:"
    say "    PW_TYPE = $(prefman get 0 0x0a3d4 l | grep value)"
    say "    C1_R    = $(prefman get 0 0x0a410 l | grep value)"
    say "    C1_C    = $(prefman get 0 0x0a548 l | grep value)"

    say "  落盘(prefman save 0)..."
    prefman save 0 >> "$LOG" 2>&1
    sync; sync; sync
    say "  已保存。请拍一张同参数照片，与之前对比。若无变化说明 ISP 另存了一套。"
    say "  回滚方法: prefman load_file 0 $BIN/pref_app.bin && prefman save 0"
else
    say "[阶段3] 写入验证已跳过 (RUN_WRITE=0)"
    say "  看完阶段 1/2 的日志后，把脚本顶部 RUN_WRITE 改成 1 重跑。"
fi

hr
say "=== probe done $(date) ==="
say "拔卡查看 $LOG"
say "备份在 SD 卡 $BIN 目录(换机/恢复用, 请勿删)"
sync; sync; sync
