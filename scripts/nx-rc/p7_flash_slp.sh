#!/bin/sh
#=====================================================================
# p7_flash_slp.sh — 通过 SLP 包刷写 p7（★★ 高危）
#---------------------------------------------------------------------
# ★★★ 本脚本是整个项目里【唯一】会写系统分区的脚本。
#   ⇒ 四道强制门控，缺一不可：
#     ① p7flash.ok 标记文件（安装成功才开放）
#     ② p7_backup.bin 已存在（强制先备份）
#     ③ popup_ok 二次人工确认
#     ④ 刷完立即回读校验
#
# ★ 官方退路：SLP[5] 与 p7 逐字节相同 ⇒ 改坏可用官方 .bin
#   走【机身菜单 Firmware Update】整机恢复，同版本 1.12 已验证刷成功。
#   ★ 必须把官方文件改名为 nx500.bin。
#
# ★★★ p7 改坏的实际后果（比"整机变砖"轻）：
#   p7 = ISP 固件 ⇒ 坏了表现为【画面异常/无图】，
#   而 Linux 侧（p6/p13）仍然活着 ⇒ telnet 仍可用 ⇒ 还有救。
#   真正会变砖的是 boot0/boot1，我们不碰。
#=====================================================================

BB=/opt/usr/nx-ks/busybox
LOG=/mnt/mmc/filmlab
OK=$LOG/p7flash.ok
IMG=$LOG/slp_part5.bin
BAK=$LOG/p7_backup.bin

# ---- 门①：安装标记 ----
[ -f "$OK" ] || { echo "!! 门控未开放：缺 $OK"; echo "   刷写菜单应保持隐藏。"; exit 1; }

# ---- 门②：必须已备份 ----
[ -s "$BAK" ] || { echo "!! 缺备份 $BAK"; echo "   请先执行 p7_backup.sh。"; exit 1; }
[ -s "$IMG" ] || { echo "!! 缺镜像 $IMG"; echo "   请先执行 p7_checkimg.sh 确认。"; exit 1; }

echo "==== 即将刷写 p7（高危）===="
echo "备份: $BAK"
echo "镜像: $IMG  $(wc -c < "$IMG") 字节"
echo
echo "★ 刷写期间【不要断电、不要拔卡】。"

# ---- 门③：二次人工确认 ----
if [ -x /opt/usr/nx-ks/popup_ok.sh ]; then
  /opt/usr/nx-ks/popup_ok.sh "FLASH P7? RISK BRICK" "YES" "NO" || {
    echo "已取消。"; exit 0; }
else
  printf "FLASH P7? type yes: "
  read A
  [ "$A" = "yes" ] || { echo "已取消。"; exit 0; }
fi

# ---- 门④A：刷新前再备份一次（防止用户上次备份后p7 又变了）----
echo "==> 刷写前二次备份..."
/opt/usr/nx-ks/p7_backup.sh || { echo "!! 二次备份失败，中止"; exit 1; }

# ---- 实际写入 ----
echo "==> 写入 p7 ..."
dd if="$IMG" of=/dev/mmcblk0p7 bs=1M conv=fsync 2>&1 | tail -3

echo
echo "==> 回读校验..."
/opt/usr/nx-ks/p7_verify.sh
echo
echo "★ 若画面异常：走【官方恢复】p7_recover_official.sh"
echo "★ 兜底：机身菜单 Firmware Update刷改名 nx500.bin 的官方固件"
