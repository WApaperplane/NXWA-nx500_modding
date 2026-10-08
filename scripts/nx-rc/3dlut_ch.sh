#!/bin/sh
#=====================================================================
# 3dlut_ch.sh — 设置 3D LUT 的 SelCbCr_ch 通道字段
#---------------------------------------------------------------------
# ★★待验证：SelCbCr_ch（+0x004 bits[1:0]）的正确取值表尚未解出。
#   p7 侧：FUN_004a5ff0 从 param_1+0xd 取、FUN_004a5e30 从 param_1+0xc 取
#   ⇒ 11 次实验里这两个字段一律写 0，★ 可能全错。
#   ⇒ 本脚本用于【逐值试探】，不是"已知正确的设置"。
#
# ★ 安全约束：每次只改一个字段，改完立即回读 + 要求用户肉眼确认画面。
#
# 用法：3dlut_ch.sh <0|1|2|3>
#=====================================================================

BB=/opt/usr/nx-ks/busybox
EPBASE=0x2082b000
WRITER=/opt/usr/nx-ks/ep3dlut.arm

SEL=${1:-0}
case "$SEL" in
  0|1|2|3) ;;
  *) echo "用法: $0 <0|1|2|3>"; exit 1 ;;
esac

[ -x "$WRITER" ] || { echo "ERR: 缺 ep3dlut.arm"; exit 1; }
[ -c /dev/drime5_ep ] || { echo "ERR: 无 /dev/drime5_ep"; exit 1; }

echo "==> SelCbCr_ch = $SEL"
echo "★这是试探值，不是已验证的设置。改完请肉眼确认画面是否变化/花屏。"
echo "★ 若花屏：立刻执行 3dlut_set.sh 3 回到出厂态。"

/opt/usr/nx-ks/popup_ok.sh "Set SelCbCr_ch=$SEL?" "OK" "NO" || exit 0

"$WRITER" "$EPBASE" 1 0 0
echo "==> 回读："
/opt/usr/nx-ks/3dlut_stat.sh
