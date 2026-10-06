#!/bin/sh
#=====================================================================
# 3dlut_set.sh — 切换 3D LUT 到 4 个预置色彩方案之一
#---------------------------------------------------------------------
# 依据（2026-10-06 p7 静态解出+ 实机 6 步序列复现）：
#   3D LUT 块基址 0x2082b000
#   +0x000 bit0   OnOff/Acc_OnOff
#   +0x004 bits[1:0]  SelCbCr_ch（通道选择，★ 取值表未解，默认 0）
#   +0x008        握手 = write-1-clear 脉冲（写=bit8）
#   +0x00c        LUT0 数据物理地址   ★ 本脚本改的就是这里
#   +0x010        LUT1 数据地址
#
# 4 个预置缓冲（p7 .data 常量，只读）：
#   0x810fd100  非单调       → 风格化曲线
#   0x81101e00  完美线性     → 纯 identity / 灰阶
#   0x81106b00  =0x810fd100
#   0x81115200  R↑G↓暖调     → 肤色优化（= 出厂 +0x00c 的值）
#
# ★ 重要边界：这4 个地址在 0x81xxxxxx，超出 Linux mem=512M
#   ⇒ 本脚本【只能切换】，不能改写内容。改内容必须改 p7。
#
# 用法：3dlut_set.sh <0|1|2|3>
#   0 = 标准  1 = 黑白  2 = 电影  3 = 肤色
#=====================================================================

BB=/opt/usr/nx-ks/busybox
EPDEV=/dev/drime5_ep
EPBASE=0x2082b000

# ---- 4 个预置 LUT 缓冲物理地址（顺序 =菜单编号）----
LUT0=0x810fd100    # 0 标准
LUT1=0x81101e00    # 1 黑白（线性/灰阶）
LUT2=0x81106b00    # 2 电影
LUT3=0x81115200    # 3 肤色（★ 出厂值）

# ★ 写寄存器用的 ARM 工具（自建，/dev/mem 逐页 mmap，SIGBUS 安全）
WRITER=/opt/usr/nx-ks/ep3dlut.arm
[ -x "$WRITER" ] || WRITER=/opt/usr/nx-ks/rd.arm

SEL=${1:-3}

case "$SEL" in
  0) ADDR=$LUT0; NAME="标准" ;;
  1) ADDR=$LUT1; NAME="黑白" ;;
  2) ADDR=$LUT2; NAME="电影" ;;
  3) ADDR=$LUT3; NAME="肤色" ;;
  *) echo "用法: $0 <0|1|2|3>"; exit 1 ;;
esac

# ---- 前置条件检查（铁律 42：必须在拍摄态，否则 SIGBUS）----
[ -c "$EPDEV" ] || { echo "ERR: 无 $EPDEV"; exit 1; }

# ★ 恢复/退出时清掉，避免留下软状态
case "$SEL" in
  restore|0x00) ADDR=$LUT3; NAME="肤色(恢复)" ;;
esac

echo "==> 3D LUT 切换到 [$SEL] $NAME"
echo "    地址 = $ADDR"

# ---- 执行 6 步写入序列（p7 FUN_004a5e30 权威序列）----
# 注意：通道字段(SelCbCr_ch) 固定 0 —— ★ 未验证的正确取值，见 docs/P7_FEATURE_MATRIX
"$WRITER" "$EPBASE" 0 "$ADDR" 0
RC=$?

if [ $RC -ne 0 ]; then
  echo "ERR: 写入失败 rc=$RC"
  echo "★ 若出现 SIGBUS：相机不在拍摄态（铁律 42）"
  exit $RC
fi

echo "==> 写入完成，回读验证："
/opt/usr/nx-ks/3dlut_stat.sh
