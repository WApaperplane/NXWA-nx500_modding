#!/bin/sh
#=====================================================================
# lut_scan.sh — 列出并选择可用的 LUT 文件
#---------------------------------------------------------------------
# ★ .cube 是 PC 端文本格式，相机不认识。必须先转成 nxks 二进制：
#     PC:  python cube2nxks.py in.cube out.nxks.bin
#     相机本脚本只负责【列出 + 应用】
#
# 用法:
#   lut_scan.sh            扫/mnt/mmc/luts/*.nxks.bin
#   lut_scan.sh filmlab    扫 FilmLab 配方目录里的 _3dlut 引用
#   lut_scan.sh apply <名字> 应用指定 LUT
#=====================================================================

BB=/opt/usr/nx-ks/busybox
DIR=/mnt/mmc/luts
LOADER=/opt/usr/nx-ks/lutload.arm
MAX=22# ★ 2 列网格上限约 24，给返回/取消留位

case "$1" in
apply)
  [ -z "$2" ] && { echo "用法: $0 apply <名字>"; exit 1; }
  if [ ! -f "$DIR/$2.nxks.bin" ]; then
    echo "找不到 $DIR/$2.nxks.bin"
    exit 1
  fi
  echo "==> 导入 $2"
  #★ 关键：先用 CMA 落地+ 11 步序列（含 rw_Start DMA 脉冲）
  "$LOADER" import "$DIR/$2.nxks.bin"
  RC=$?
  if [ $RC -ne 0 ]; then
    echo "ERR: 导入失败 rc=$RC"
    echo "★ 立即恢复出厂: $LOADER restore"
    "$LOADER" restore
    exit $RC
  fi
  echo "$2" > /mnt/mmc/filmlab/lut_active.txt 2>/dev/null
  echo "★ 请看取景器。异常则执行: $LOADER restore"
  exit 0
  ;;
filmlab)
  DIR2=/mnt/mmc/filmlab
  echo "==== FilmLab 配方里的 LUT 引用 ===="
  if [ -d "$DIR2" ]; then
    ls "$DIR2"/*.nxks.bin 2>/dev/null || echo "(无)"
  else
    echo "(目录不存在)"
  fi
  exit 0
  ;;
esac

echo "==== 可用 LUT（$DIR）===="
if [ ! -d "$DIR" ]; then
  echo "(目录不存在)"
  echo
  echo "★ 怎么放进来的："
  echo "  1. PC 端：python cube2nxks.py in.cube out.nxks.bin"
  echo "  2. 把 out.nxks.bin 复制到 SD 卡 $DIR/"
  echo "  3. 相机端菜单 → P7 固件 → 色彩方案 → 导入 LUT"
  exit 0
fi

# 列出并生成菜单页
COUNT=0
GEN=/opt/usr/nx-ks/gui_lutlist.NX500
"$BB" rm -f "$GEN"
echo "button|返回|@/opt/usr/nx-ks/gui_lutimport.NX500" > "$GEN"

for f in "$DIR"/*.nxks.bin; do
  [ -f "$f" ] || continue
  [ $COUNT -ge $MAX ] && break
  NAME=$("$BB" basename "$f" .nxks.bin)
  SZ=$("$BB" wc -c < "$f" | tr -d ' ')
  echo "button|$NAME|@/opt/usr/nx-ks/lut_pick.sh $NAME" >> "$GEN"
  printf "  [%2d] %-28s %6s 字节\n" $((COUNT+1)) "$NAME" "$SZ"
  COUNT=$((COUNT+1))
done

echo "button|取消|/opt/usr/nx-ks/gui_exit.sh" >> "$GEN"

if [ $COUNT -eq 0 ]; then
  echo "(空 —— 先用 cube2nxks.py 转换)"
  exit 0
fi

echo
echo "共 $COUNT 个。菜单页: $GEN"
echo "★ 选中后请看取景器确认；异常立刻：$LOADER restore"