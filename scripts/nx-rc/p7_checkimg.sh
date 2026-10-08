#!/bin/sh
#=====================================================================
# p7_checkimg.sh — 校验待刷镜像的完整性（只读，不写任何东西）
#---------------------------------------------------------------------
# ★ 刷固件的第一道门：镜像不对就不许刷。
#=====================================================================

BB=/opt/usr/nx-ks/busybox
LOG=/mnt/mmc/filmlab

echo "==== 镜像校验 ===="

IMG=""
for f in "$LOG"/p7_official.bin "$LOG"/slp_part5.bin "$LOG"/p7_new.bin; do
  if [ -f "$f" ]; then IMG="$f"; break; fi
done

if [ -z "$IMG" ]; then
  echo "!! 未找到待刷镜像。"
  echo "   查找路径: $LOG/{p7_official.bin, slp_part5.bin, p7_new.bin}"
  echo "★ 放好镜像后再跑本步。"
  exit 1
fi

SZ=$(wc -c < "$IMG")
echo "文件: $IMG"
echo "大小: $SZ 字节"

# ---- 大小合理性（p7 有效数据 11.52MB = 12075648；分区 30MB）----
if [ "$SZ" -lt 1000000 ]; then
  echo "!! 太小：$SZ 字节。p7 有效数据应约 12MB。"
  echo "★ 拒绝继续。"
  exit 1
fi

# ---- md5 ----
if [ -x "$BB" ]; then
  MD5=$("$BB" md5sum "$IMG" 2>/dev/null | awk '{print $1}')
  if [ -n "$MD5" ]; then
    echo "MD5 : $MD5"
    # 与官方基线比对
    if [ -f "$LOG/p7_official.md5" ]; then
      REF=$(cat "$LOG/p7_official.md5" | awk '{print $1}')
      if [ "$MD5" = "$REF" ]; then
        echo "==> 与官方基线【一致】★ 官方退路镜像"
      else
        echo "==> 与官方基线【不同】"
        echo "    官方: $REF"
        echo "    当前: $MD5"
        echo "★ 若这是你新改的镜像，属正常。继续前请确认它已被验证过。"
      fi
    else
      echo "★ 无官方 md5 基线可比对。建议先跑 p7_backup.sh 建立基线。"
    fi
  fi
fi

echo
echo "★ 提醒：p7 改坏的后果是ISP 无响应（画面异常），"
echo "  但 Linux 侧仍活着 ⇒ telnet 可用 ⇒ 仍有机会用官方 bin 恢复。"
