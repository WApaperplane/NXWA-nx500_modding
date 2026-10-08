#!/bin/sh
#=====================================================================
# iqr_dump.sh — 导出 ISP 运行时参数快照（iqr 197 行表）
#---------------------------------------------------------------------
# ★★★ 这是判断"改了生效没有"的【唯一客观判据】（铁律 47）。
#   "参数值变了" ≠ "参数被消费了" —— 只有 iqr 能证明后者。
#
# ★ 关键字段速查：
#   WB_COLORTEMP≠0  ⇒ AWB 真在算（算出了色温）
#   WB_KELVIN       = 用户【请求】的 K 值（不等于实际使用值！）
#   CWB_R/B/G_GAIN  = 自定义 WB 三通道增益
#   PW_COLOR / PW_HUE / PW_SATURATION = Picture Wizard 运行时映射
#   SRA_WB_UPDATE   = 可能是强制 WB 更新开关
#
# 用法：iqr_dump.sh [输出文件]
#=====================================================================

BB=/opt/usr/nx-ks/busybox
OUT=${1:-/mnt/mmc/filmlab/iqr_last.txt}

[ -x "$BB" ] || { echo "ERR: 缺 busybox"; exit 1; }

# ★ 必须串行（铁律 1）；st 依赖 p7 capture 服务，崩了就没输出
T0=$("$BB" date +%s 2>/dev/null || echo 0)
st cap iqr > /tmp/iqr.raw 2>&1
RC=$?
T1=$("$BB" date +%s 2>/dev/null || echo 0)

if [ $RC -ne 0 ] || [ ! -s /tmp/iqr.raw ]; then
  echo "ERR: iqr 取值失败 rc=$RC"
  echo "★ 可能 p7 capture 服务已崩（铁律 53：写非法槽位会崩它）"
  echo "★ 读侧仍可用：/dev/mem EP 通路不依赖 p7"
  exit 1
fi

mkdir -p "$(dirname "$OUT")"
cp /tmp/iqr.raw "$OUT"

echo "==== iqr 快照已存: $OUT  ($((T1-T0)) 秒) ===="

# ---- 提取关键字段（可grep 的单行摘要）----
"$BB" grep -E 'WB_COLORTEMP|WB_KELVIN|WB_MODE|WB_TYPE|CWB_|PW_COLOR|PW_HUE|PW_SATURATION|SRA_WB_UPDATE|SMARTART' "$OUT" 2>/dev/null || \
  grep -E 'WB_COLORTEMP|WB_KELVIN|WB_MODE|WB_TYPE|CWB_|PW_COLOR|PW_HUE|PW_SATURATION|SRA_WB_UPDATE|SMARTART' "$OUT"

cat <<'EOF'

---- 判读要点 ----
★ WB_COLORTEMP≠0 ⇒ AWB 真在算
★ WB_KELVIN 只是请求值；实际用的是 WB_COLORTEMP（两者不是一回事）
★ 运行时与 pref 可临时"分叉" ⇒ 恢复出厂后 iqr 仍可能显示旧值
★ iqr / iq 全部只读（已实测 4 种写入语法均失败）
EOF
