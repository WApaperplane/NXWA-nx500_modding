#!/bin/sh
# pw-norestart.sh — 测试 prefman 免重启写入
#
# 关键问题：filmlab-apply.sh 用 `prefman set` + `prefman save` + `prefman load -a 0`。
# 其中 `save` 是写 eMMC（持久化）。如果**去掉 save**、只靠 load -a 0 能否生效？
#   生效 → 配方切换可以免重启、免写 eMMC（快速、无损flash 寿命）
#   不生效 → 必须 save（切换要等落盘，且有写磨损）
#
# 用法:
#   sh pw-norestart.sh test <slot> <R> <G> <B> <HUE> <SAT> <SHARP> <CONTRAST>
#   sh pw-norestart.sh verify <slot>
#   sh pw-norestart.sh restore        # 重新 save，恢复持久状态

BB=/opt/usr/nx-ks/busybox
# PW 参数块：基址 0x0a3ec，参数步进 52（0x34），风格步进 4
# ★ 布局（实机 prefman info 0，与 filmlab-apply.sh 完全一致）：
#   slot_off(参数索引 i, 风格 s) = PW_BASE + i*52 + s*4
#   PW_BASE = 41964 (0xa3ec)
#   参数索引: 0=R 1=G 2=B 3=HUE 4=SAT 5=SHARP 6=CONTRAST
#   风格: 0..8=厂商 9..12=CUSTOM_1..4 13=OFF
PW_BASE=41964
PSTEP=52
SSTEP=4

rd() { prefman get 0 "$(printf 0x%05x $1)" l 2>/dev/null | grep -o 'value = [-0-9]*' | sed 's/value = //'; }
wr() { prefman set 0 "$(printf 0x%05x $1)" l "$2" >/dev/null 2>&1; }

slot_rd() { rd $(( PW_BASE + $1 * PSTEP + $2 * SSTEP )); }
slot_wr() { wr $(( PW_BASE + $1 * PSTEP + $2 * SSTEP )) "$3"; }

case "$1" in

test)
  SLOT=$2; R=$3; G=$4; B=$5; HUE=$6; SAT=$7; SHARP=$8; CON=$9
  echo "=== 免 save 测试: slot=$SLOT R=$R G=$G B=$B HUE=$HUE SAT=$SAT SHARP=$SHARP CON=$CON ==="
  echo "--- 写入前 ---"
  echo "  R=$(slot_rd 0 $SLOT) G=$(slot_rd 1 $SLOT) B=$(slot_rd 2 $SLOT)"
  echo "  HUE=$(slot_rd 3 $SLOT) SAT=$(slot_rd 4 $SLOT)"

  slot_wr 0 $SLOT "$R"
  slot_wr 1 $SLOT "$G"
  slot_wr 2 $SLOT "$B"
  slot_wr 3 $SLOT "$HUE"
  slot_wr 4 $SLOT "$SAT"
  slot_wr 5 $SLOT "$SHARP"
  slot_wr 6 $SLOT "$CON"

  # ★ 关键：只 load，不 save
  prefman load -a 0 >/dev/null 2>&1
  sync

  echo "--- load后读回（未 save） ---"
  echo "  R=$(slot_rd 0 $SLOT) G=$(slot_rd 1 $SLOT) B=$(slot_rd 2 $SLOT)"
  echo "  HUE=$(slot_rd 3 $SLOT) SAT=$(slot_rd 4 $SLOT) SHARP=$(slot_rd 5 $SLOT) CON=$(slot_rd 6 $SLOT)"
  echo "--- ★ 现在看取景器 ---"
  ;;

verify)
  SLOT=$2
  echo "slot $SLOT 当前值:"
  echo "  R=$(slot_rd 0 $SLOT) G=$(slot_rd 1 $SLOT) B=$(slot_rd 2 $SLOT)"
  echo "  HUE=$(slot_rd 3 $SLOT) SAT=$(slot_rd 4 $SLOT) SHARP=$(slot_rd 5 $SLOT) CON=$(slot_rd 6 $SLOT)"
  ;;

restore)
  echo "=== 重新 save（恢复持久状态） ==="
  prefman save
  sync
  prefman load -a 0
  echo "done"
  ;;

esac
echo "NR_DONE"
