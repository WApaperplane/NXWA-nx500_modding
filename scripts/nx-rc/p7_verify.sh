#!/bin/sh
#=====================================================================
# p7_verify.sh — 回读 p7 并与备份/基线比对（只读）
#=====================================================================

BB=/opt/usr/nx-ks/busybox
LOG=/mnt/mmc/filmlab
BAK=$LOG/p7_backup.bin
TMP=/mnt/mmc/filmlab/.p7_verify.tmp

[ -b /dev/mmcblk0p7 ] || { echo "!! 无 /dev/mmcblk0p7"; exit 1; }

echo "==> 回读 p7 ..."
dd if=/dev/mmcblk0p7 of="$TMP" bs=1M count=12 2>&1 | tail -1
CUR=$("$BB" md5sum "$TMP" 2>/dev/null | awk '{print $1}')
rm -f "$TMP"

if [ -z "$CUR" ]; then echo "!! 回读失败"; exit 1; fi
echo "当前 p7 md5: $CUR"

if [ -s "$BAK" ]; then
  REF=$("$BB" md5sum "$BAK" 2>/dev/null | awk '{print $1}')
  echo "备份   md5: $REF"
  if [ "$CUR" = "$REF" ]; then
    echo "==>【一致】p7 仍是备份时的状态"
  else
    echo "==>【不一致】p7 已被修改（若是有意刷写则正常）"
  fi
else
  echo "★ 无备份可比对。建议先跑 p7_backup.sh。"
fi

echo
echo "★ 注意：这里只校验【数据一致性】，不校验【ISP 是否跑得起来】。"
echo "  判断 ISP 行为是否正常，必须看画面。"
