#!/bin/sh
# @gate script=u6_probe.sh opens=rdonly one_shot=1
# =====================================================================
# u6_probe.sh -- U6 步骤 0：环境侦察 + 负载基线 + P8 结案补读（全只读）
# =====================================================================
# ★ 与 u1_probe.sh 的差别（U6 自包含版）：
#   1. 输出落 /mnt/mmc/u6/out/probe.log（不再依赖 u1 的机上残留）
#   2. ★ p8 sysfs 补读修正路径：u1 那次用 /sys/block/mmcblk0p8/ 全 N/A
#      （分区的 sysfs 不在 /sys/block 顶层），本版【三路径】齐上：
#        /sys/class/block/  <- class 视图（分区的正确路径）
#        /sys/block/mmcblk0/  <- 盘内子目录视图
#        /sys/block/  <- 原 u1 路径（留作对照，预期仍 N/A）
#   3. 保留 diskstats 全表（P8 定案复核 + 对照 p9/p10/p11/p14）
# =====================================================================
BB=/opt/usr/nx-ks/busybox
OUT=/mnt/mmc/u6/out
LOG="$OUT/probe.log"

$BB mkdir -p "$OUT"
{
  echo "== version.info"
  $BB cat /etc/version.info 2>/dev/null
  echo "== uname"; $BB uname -a
  echo "== uptime"; $BB uptime
  echo "== loadavg"; $BB cat /proc/loadavg
  echo "== ps lines"; $BB ps | $BB wc -l
  echo "== which (自证：确认工具真实存在)"
  $BB which st 2>/dev/null || echo "st NOT in PATH"
  $BB which dd 2>/dev/null || echo "dd NOT in PATH"
  echo "PATH=$PATH"
  echo "== EV_MOBILE.sh md5 (preflight 第 2 项：机上必须不是 55c47b89)"
  $BB md5sum /opt/usr/nx-ks/EV_MOBILE.sh 2>/dev/null
  echo "== /dev/input"
  $BB ls -l /dev/input/ 2>/dev/null
  echo "== diskstats"
  $BB cat /proc/diskstats 2>/dev/null
  echo "== p8 sysfs (三路径)"
  for f in ro start size stat force_ro; do
    printf "p8 class/%s=" "$f"
    $BB cat "/sys/class/block/mmcblk0p8/$f" 2>/dev/null || echo "N/A"
  done
  for f in ro start size stat force_ro; do
    printf "p8 disk/%s=" "$f"
    $BB cat "/sys/block/mmcblk0/mmcblk0p8/$f" 2>/dev/null || echo "N/A"
  done
  for f in ro start size stat force_ro; do
    printf "p8 u1path/%s=" "$f"
    $BB cat "/sys/block/mmcblk0p8/$f" 2>/dev/null || echo "N/A"
  done
  echo "== p8 partition node"
  $BB ls -l /dev/mmcblk0p8 2>/dev/null || echo "no /dev/mmcblk0p8"
  echo "== parttab"
  $BB cat /etc/parttab 2>/dev/null
  echo "== df"
  $BB df -k 2>/dev/null
  echo "== sync+done"
} > "$LOG" 2>&1

$BB sync
echo "probe lines=$($BB wc -l < "$LOG" 2>/dev/null)"
echo "probe md5=$($BB md5sum "$LOG" 2>/dev/null)"
exit 0
