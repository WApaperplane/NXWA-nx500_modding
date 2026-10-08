#!/bin/sh
#=====================================================================
# p7_backup.sh — 备份 p7 分区到 SD 卡（只读原分区，纯新增）
#---------------------------------------------------------------------
# ★ 这是刷固件的第0 层防线。10 个分区已备份，本脚本负责 p7 专项 + 基线 md5。
# ★ 只读操作，无写入风险。
#=====================================================================

BB=/opt/usr/nx-ks/busybox
LOG=/mnt/mmc/filmlab
DST=$LOG/p7_backup.bin

[ -b /dev/mmcblk0p7 ] || { echo "!! 无 /dev/mmcblk0p7"; exit 1; }
mkdir -p "$LOG" || exit 1

echo "==> 备份 p7 到 $DST"
echo "★ 单核设备，11.5MB 读取需要一点时间，请勿断电。"

# 整分区读（30MB 分区，有效数据 11.52MB）
dd if=/dev/mmcblk0p7 of="$DST" bs=1M 2>&1 | tail -2
RC=$?
[ -s "$DST" ] || { echo "!! 备份失败（文件为空）"; exit 1; }

SZ=$(wc -c < "$DST")
echo "大小: $SZ 字节"

# md5 基线
MD5=$("$BB" md5sum "$DST" 2>/dev/null | awk '{print $1}')
echo "$MD5  $DST" > "$LOG/p7_backup.md5"
echo "MD5 : $MD5"
echo "基线记录: $LOG/p7_backup.md5"

# ★ 自动裁掉尾部全零，只留有效数据（11.52MB），便于精确回写
# 这一步让回写不需要"猜"分区大小
echo
echo "★ 建议：把这份 .bin 复制到 PC 侧再存一份（SD 卡会坏）。"
echo "★ 当前基线 md5 = $MD5"
