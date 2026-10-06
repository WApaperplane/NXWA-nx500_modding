#!/bin/sh
#=====================================================================
# flab_ui.sh —— FilmLab 机内 UI 启动器（波轮 + 触屏）
#=====================================================================
# ★ 两种用法（对应两种体验）：
#   ui     起UI（波轮选 + 触摸选，选中即应用）—— 交互式
#   cycle  零 UI 轮换下一个配方 + 弹配方名 —— 最轻，单核最友好
#
# ★ 为什么 UI 用 EFL 而不是 X11（NX-KS2 实测铁律）：
#   X11 满屏 720x480 在单核 NX500 上吃满 CPU，连 echo 都执行不完。
#   EFL/elementary 是 di-camera-app 和 mod_gui 已经在用的栈，
#   窗口走 evas 合成，不抢CPU —— 与相机原生 UI 同一套渲染路径。
#
# ★ 部署路径：
#   /opt/usr/nx-ks/filmlab/nxfilmui.arm   UI 程序（833KB）
#   /mnt/mmc/filmlab/recipes.txt          配方表（由 filmlab.sh export 生成）
#=====================================================================

BB=/opt/usr/nx-ks/busybox
D=/opt/usr/nx-ks
LAB=/mnt/mmc/filmlab
BIN=$D/filmlab/nxfilmui.arm
LOG=$LAB/filmui.log
# 进程名（.arm 后缀在 busybox pkill 里要匹配全）
PNAME=nxfilmui.arm

case "$1" in
cycle)
  # 零 UI 路径：不碰图形，直接问引擎要下一个配方
  [ -x "$D/filmlab.sh" ] || { $BB $D/popup_timeout " [ 引擎缺失 ] " 2; exit 1; }
  OUT=$("$D/filmlab.sh" cycle 2>&1)
  if [ $? -ne 0 ] || [ -z "$OUT" ]; then
    $BB $D/popup_timeout " [ 配方库为空 ] " 2
    exit 1
  fi
  LBL=$($BB echo "$OUT" | $BB sed 's/ (key=.*$//')
  $BB $D/popup_timeout " $LBL " 2
  case "$OUT" in *VERIFY-FAIL*) $BB $D/popup_timeout " [ 写入未生效 ] " 3 ;; esac
  exit 0
  ;;

ui|start)
  # ---- 引擎在不在（不在 install.sh 部署链里，走 FTP 单独投递）----
  if [ ! -x "$D/filmlab.sh" ]; then
    $BB $D/popup_timeout " [ FilmLab引擎缺失 ] " 3
    exit 1
  fi
  # ---- UI 程序在不在 ----
  if [ ! -x "$BIN" ]; then
    $BB $D/popup_timeout " [ UI程序缺失 ] " 3
    $BB $D/popup_timeout " 需FTP推nxfilmui.arm " 2
    exit 1
  fi

  # ---- 已有实例就杀掉（单核铁律：绝不并发跑两个图形进程）----
  killall -q $PNAME 2>/dev/null
  killall -q mod_gui 2>/dev/null
  $BB sleep 1

  # ---- 导出配方表：UI 读不了 JSON（相机上没有 jq）----
  # 导出失败不该挡住进 UI（可能上次生成的还在）→ 静默放行
  "$D/filmlab.sh" export >/dev/null 2>&1
  if [ ! -f "$LAB/recipes.txt" ]; then
    $BB $D/popup_timeout " [ 配方表缺失 ] " 3
    exit 1
  fi

  # ---- 切 LCD 视角（社区惯例，否则窗口起在 EVF 上看不见）----
  if ! $BB st cap capdtm getusr MONITOROUT 2>/dev/null | $BB grep -q LCD; then
    $BB st app disp lcd 2>/dev/null
    $BB sleep 1
  fi

  # ---- 干净启动环境（照抄 init.sh 的关键变量，EFL 必需）----
  export DISPLAY=:0
  export EINA_LOG_LEVEL=1
  export ELM_PROFILE=mobile
  export EVAS_FONT_DPI=72
  export XDG_CACHE_HOME=/tmp/.cache
  export HOME=/root
  export LD_LIBRARY_PATH=/usr/lib:/lib:/opt/usr/lib

  # nice -n +15：让相机主进程优先（社区约定，别跟拍照抢CPU）
  $BB nice -n +15 $BIN >/dev/null 2>&1 &
  exit 0
  ;;

stop)
  killall -q $PNAME 2>/dev/null
  $BB $D/popup_timeout " FilmLab UI 已关闭 " 1
  exit 0
  ;;

*)
  echo "flab_ui.sh — FilmLab 机内 UI"
  echo
  echo "  ui       起 UI（波轮选 + 触摸选，选中即应用）"
  echo "  cycle    零 UI 轮换下一个配方 + 弹配方名"
  echo "  stop     关闭 UI"
  echo
  echo "  部署: $BIN"
  echo "  日志: $LOG"
  echo "  依赖: $D/filmlab.sh（引擎）+ $LAB/recipes.txt（filmlab.sh export 生成）"
  ;;
esac
