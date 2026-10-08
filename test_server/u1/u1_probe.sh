#!/bin/sh
#=====================================================================
# u1_probe.sh -- U1 步骤 0：环境侦察 + P8 定案判据（全只读）
#=====================================================================
# ★ 生成物，勿手改：python test_server/tools/gate_pack_u1.py
# ★ 本步同时承载两件事：
#   (a) 上机负载基线（铁律 104：'进程活着' != '系统没被拖垮'，参照物必须先取）
#   (b) p8(rtos_data) 全零悬案的**写死判据**（P8_ZERO_INVESTIGATION 的 P0 项）：
#       /proc/diskstats 里 p8 累计写入扇区 == 0  =>  定案"从未被写入"
#   (c) 自证：把 st / dd 的解析路径打出来，避免"用了不存在的工具"这类假结论
# @gate script=u1_probe.sh opens=rdonly one_shot=1
BB=/opt/usr/nx-ks/busybox
OUT=/mnt/mmc/u1/out
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
  echo "== input devices"
  $BB cat /proc/bus/input/devices 2>/dev/null
  echo "== diskstats"
  $BB cat /proc/diskstats 2>/dev/null
  echo "== p8 sysfs"
  for f in ro start size stat force_ro; do
    printf "p8 %s=" "$f"
    $BB cat "/sys/block/mmcblk0p8/$f" 2>/dev/null || echo "N/A"
  done
  echo "== parttab"
  $BB cat /etc/parttab 2>/dev/null
  echo "== df"
  $BB df -k 2>/dev/null
} > "$LOG" 2>&1

$BB sync
echo "probe lines=$($BB wc -l < "$LOG" 2>/dev/null)"
echo "probe md5=$($BB md5sum "$LOG" 2>/dev/null)"
exit 0
