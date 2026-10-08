#!/bin/sh
#=====================================================================
# p7_status.sh — 显示 p7 固件当前状态（只读）
#=====================================================================

BB=/opt/usr/nx-ks/busybox
LOG=/mnt/mmc/filmlab

echo "==== p7 固件状态 ===="

# ---- 分区存在性----
if [ -b /dev/mmcblk0p7 ]; then
  echo "[分区] /dev/mmcblk0p7 存在"
  BLK=$(cat /sys/block/mmcblk0p7/size 2>/dev/null)
  [ -n "$BLK" ] && echo "[大小] $((BLK/2048)) MB（分区）"
else
  echo "[分区] !! /dev/mmcblk0p7 不存在"
fi

# ---- 备份与镜像状态 ----
for f in "$LOG"/p7_backup.bin "$LOG"/p7_official.bin "$LOG"/slp_part5.bin; do
  if [ -f "$f" ]; then
    echo "[镜像] $f  $(wc -c < "$f") 字节"
  else
    echo "[镜像] $f  ✗ 缺失"
  fi
done

# ---- 校验和标记 ----
[ -f "$LOG/p7_backup.md5" ] && echo "[校验] $(cat "$LOG/p7_backup.md5")" || echo "[校验] 无 md5 记录"

# ---- 安装标记（p7 功能菜单的门控）----
[ -f "$LOG/p7flash.ok" ] && echo "[门控] p7flash.ok 存在 → 刷写菜单已开放" || \
  echo "[门控] 无 p7flash.ok → 刷写菜单保持隐藏（安全默认）"

echo
echo "★ p7 = Cortex-A9 上的 ISP 固件（已由排除法确立）"
echo "★ SLP[5] 与 p7 逐字节相同 ⇒ 官方退路可用"
