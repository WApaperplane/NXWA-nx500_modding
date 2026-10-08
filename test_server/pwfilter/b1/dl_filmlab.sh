#!/bin/sh
#=====================================================================
# filmlab-apply.sh  —  FilmLab SD 卡配方引擎 v1
#---------------------------------------------------------------------
# 设计前提（2026-10-04 实机定案）：
#   · 配方库在 SD 卡（/mnt/mmc/filmlab/recipes.json），数量不限
#   · prefman只有 4 个 CUSTOM 槽（CUSTOM_1/2/3/4 = slot 9/10/11/12）
#     → 槽位不是配方，而是"当前选中项"
#   · prefman set 不需 save 即实时生效（已实机验证）
#   · prefman load -a 0 会【覆盖】刚 set 的值，绝对不要用
#   · setusr 20 <enum> 切风格，零延迟
#
# 用法：
#   sh filmlab-apply.sh list                    列出 SD 卡全部配方
#   sh filmlab-apply.sh show   <recipe>         打印配方内容
#   sh filmlab-apply.sh apply  <recipe> [slot]  写槽 + 切风格（实时生效）
#   sh filmlab-apply.sh quick  <recipe>         只切风格（槽已预写时用，零写入）
#   sh filmlab-apply.sh dump   [slot]           读回槽位当前值
#   sh filmlab-apply.sh preset                 把 preset 段写进 3 个可见槽
#   sh filmlab-apply.sh slots                  列出槽位占用
#=====================================================================

BB=/opt/usr/nx-ks/busybox
LAB=/mnt/mmc/filmlab
RECIPE=$LAB/recipes.json
LOG=$LAB/last.log

# ---- prefman 布局（★ 来自 prefman info 0 的官方命名表，4/4 对齐已验证）----
PW_BASE=41964          # 0xa3ec = APPPREF_EFFECT_STANDARD_R_COLOR
PSTEP=52               # 参数步进（R=0 G=1 B=2 HUE=3 SAT=4 SHARP=5 CON=6）
SSTEP=4                # 风格步进

# ---- WB (★全部来自 prefman info 0 官方命名表，勿凭记忆写) ----
WB_TYPE=41872         # 0x0a390  APPPREF_WB_TYPE
WB_K=41876            # 0x0a394  APPPREF_WB_K_VALUE (Kelvin)
WB_CUSTOM_BA=41916    # 0x0a3bc  APPPREF_WB_CUSTOM_DETAIL_BA_XY (tint 打包)
WB_MANUAL_BA=41920    # 0x0a3c0  APPPREF_WB_K_DETAIL_BA_XY  (K 模式的 tint)
CWB_R=41924           # 0x0a3c4  APPPREF_CWB_RED
CWB_G=41928           # 0x0a3c8  APPPREF_CWB_GREEN
CWB_B=41932           # 0x0a3cc  APPPREF_CWB_BLUE

# ---- WB_TYPE 枚举（setusr 6 实机扫出的真值表，14:58 定案）----
#  0=WB_AUTO          1=WB_AUTO_TUNGSTEN  2=WB_DAYLIGHT  3=WB_CLOUDY
#  4=WB_FLUORESCENTW  8=WB_FLASH          9=WB_CUSTOM
# 10=WB_MANUAL   ← ★ K 值只在这个模式下生效
# 11+ 被拒 (not set -1)
WB_MANUAL=10
TINT_NEUTRAL_A=7
TINT_NEUTRAL_B=7

# ---- slot <-> enum 映射（★ 实机特征色验证 + 命名表双重确认）----
# UI 显示:setusr enum : prefman slot : DATA ID
#   自定义1     9        9        0x140009
#   自定义2     10       10       0x14000a
#   自定义3     12       11       0x14000c   ← enum 与 slot 错位 1！
#   (隐藏)      —        12       —          ← CUSTOM_4 在 prefman 里存在但 UI 不显示
#   enum 11 (0x14000b) 被拒 "not set -1"，是空洞

set_r() { prefman set 0 "$(printf 0x%05x $((PW_BASE + $1 * PSTEP + $2 * SSTEP)))" l "$3" >/dev/null 2>&1; }
get_r() { prefman get 0 "$(printf 0x%05x $((PW_BASE + $1 * PSTEP + $2 * SSTEP)))" l 2>/dev/null \
          | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p'; }
# ★ 原子写入白平衡：TYPE + K + tint 三项一起，中间不留半成品状态
# 用法: set_wb <K> <tint_a> <tint_b> [manual|auto|keep]
#   manual(默认) → 切WB_MANUAL，K 生效
#   auto         → 切 WB_AUTO，K 被忽略（相机自动）
#   keep         → 不动 WB_TYPE，只写 K 与 tint
# ★ 顺序关键：先切模式（决定 K 是否被采用），再写 K，最后写 tint。
#   顺序反了会出现"模式已是manual 但 K 还是旧值"的窗口。
set_wb() {
  K=$1; A=$2; B=$3; MODE=${4:-manual}
  case $MODE in
    manual) prefman set 0 "$(printf 0x%05x $WB_TYPE)" l "$WB_MANUAL" >/dev/null 2>&1
            st cap capdtm setusr 6 0x06000a >/dev/null 2>&1 ;;
    auto)   st cap capdtm setusr 6 0x060000 >/dev/null 2>&1 ;;
    keep)   ;;
  esac
  [ -n "$K" ] && [ "$K" != "0" ] && prefman set 0 "$(printf 0x%05x $WB_K)" l "$K" >/dev/null 2>&1
  BA=$(( (A << 16) | B ))
  prefman set 0 "$(printf 0x%05x $WB_MANUAL_BA)" l "$BA" >/dev/null 2>&1
  prefman set 0 "$(printf 0x%05x $WB_CUSTOM_BA)" l "$BA" >/dev/null 2>&1
}
get_wb()      { prefman get 0 "$(printf 0x%05x $WB_K)" l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p'; }
get_wb_type() { prefman get 0 "$(printf 0x%05x $WB_TYPE)" l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p'; }
get_tint()    { V=$(prefman get 0 "$(printf 0x%05x $WB_MANUAL_BA)" l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p');
                echo "A=$(( (V >> 16) & 0xffff )) B=$(( V & 0xffff ))"; }
get_wb() { prefman get 0 "$(printf 0x%05x $WB_K)" l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p'; }

# slot -> enum（切风格用）
enum_of_slot() {
  case $1 in
    9)  echo 9;;
    10) echo 10;;
    11) echo 12;;   # ★ slot 11 对应 enum 12
    12) echo 0;;    # slot 12 (CUSTOM_4) 无对应 enum → 退回 STANDARD 槽
    *)  echo $1;;   # 0-8 原生槽，enum = slot
  esac
}
# 自动挑一个可用槽（3 个可见槽轮转）
auto_slot() {
  C=$1
  [ $C -ge 3 ] && C=0
  echo $((9 + C))
}

# ---- JSON 极简解析（只取 recipes 段下的 key 和数值，够用即可）----
# 用法: jval <recipe_name> <field>   例: jval portra400 R_COLOR
jval() {
  /opt/usr/nx-ks/busybox awk -v r="\"$1\": " -v f="\"$2\":" '
    index($0, r) { inr=1; next }
    inr && index($0, f) {
      s = substr($0, index($0, f) + length(f))
      gsub(/[^0-9-]/, "", s)
      if (s != "") { print s; exit }
    }
    inr && $0 ~ /^    \}/ { exit }
  ' $RECIPE 2>/dev/null
}
# 列出所有配方名
jlist() {
  /opt/usr/nx-ks/busybox awk '
    /"recipes"/ { inr=1; next }
    /"presets"/ { inr=0; next }
    index($0, "\"") && inr && /^    "/ {
      k = $0
      gsub(/^ +"/,"", k); gsub(/".*/,"", k)
      if (k != "" && substr(k,1,1) != "_") print k
    }
  ' $RECIPE 2>/dev/null
}
# 取字符串值（用于 wb_mode 这类枚举字段）
jstr() {
  /opt/usr/nx-ks/busybox awk -v r="\"$1\": " -v f="\"$2\":" '
    index($0, r) { inr=1; next }
    inr && index($0, f) {
      s = substr($0, index($0, f) + length(f))
      gsub(/^[ \t]*"/, "", s)
      gsub(/".*$/, "", s)
      gsub(/[ \t]*$/, "", s)
      gsub(/,.*$/, "", s)
      if (s != "") { print s; exit }
    }
    inr && $0 ~ /^    \}/ { exit }
  ' $RECIPE 2>/dev/null
}
# 取 label
jlabel() {
  /opt/usr/nx-ks/busybox awk -v r="\"$1\":" '
    $0 ~ r { inr=1; next }
    inr && /"label":/ { gsub(/.*"label": *"/,""); gsub(/".*/,""); print; exit }
  ' $RECIPE 2>/dev/null
}

log() { echo "$*" >> $LOG; }

#===============================================================
CMD=$1
REC=$2
SLOT=$3
[ -z "$CMD" ] && CMD=help
mkdir -p $LAB 2>/dev/null

case $CMD in

#---------------------------------------------------------------
list)
  echo "=== FilmLab SD 卡配方库 ==="
  echo "文件: $RECIPE"
  echo
  printf "%-14s %-22s %s\n" "KEY" "LABEL" "7 维 (R/G/B/HUE/SAT/SHARP/CON)"
  echo "------------------------------------------------------------------------"
  jlist | while read k; do
    [ -z "$k" ] && continue
    R=$(jval $k R_COLOR); G=$(jval $k G_COLOR); B=$(jval $k B_COLOR)
    H=$(jval $k HUE);     S=$(jval $k SATURATION)
    P=$(jval $k SHARPNESS); C=$(jval $k CONTRAST)
    printf "%-14s %-22s %s/%s/%s %s/%s/%s/%s\n" "$k" "$(jlabel $k)" \
      "$R" "$G" "$B" "$H" "$S" "$P" "$C"
  done
  echo
  echo "预设槽（UI 零延迟）:"
  grep -o '"slot1[01]": *"[a-z0-9_]*"' $RECIPE 2>/dev/null | sed 's/^/  /'
  ;;

#---------------------------------------------------------------
show)
  [ -z "$REC" ] && { echo "用法: show <recipe>"; exit 1; }
  echo "=== $REC ==="
  L=$(jlabel $REC);[ -n "$L" ] && echo "显示名: $L"
  echo "  R=$(jval $REC R_COLOR)  G=$(jval $REC G_COLOR)  B=$(jval $REC B_COLOR)"
  echo "  HUE=$(jval $REC HUE)  SAT=$(jval $REC SATURATION)  SHARP=$(jval $REC SHARPNESS)  CONTRAST=$(jval $REC CONTRAST)"
  echo "  K=$(jval $REC K)  tintA=$(jval $REC tint_a)  tintB=$(jval $REC tint_b)"
  ;;

#---------------------------------------------------------------
apply)
  [ -z "$REC" ] && { echo "用法: apply <recipe> [slot]"; exit 1; }
  if [ -z "$SLOT" ]; then
    # 自动挑槽：看当前 enum 决定下一个
    CUR=$(/opt/usr/nx-ks/busybox sh -c 'st cap capdtm getusr 20 2>/dev/null' | tr -d '\r' \
          | sed -n 's/.*UserData is [A-Z_0-9]* (\(0x[0-9a-f]*\)).*/\1/p')
    case $CUR in
      0x140009) SLOT=10;;
      0x14000a) SLOT=11;;
      *)SLOT=9;;
    esac
  fi
  ENUM=$(enum_of_slot $SLOT)
  echo ">>> 应用 '$REC' -> slot $SLOT (enum $ENUM)"
  set_r 0 $SLOT "$(jval $REC R_COLOR)"
  set_r 1 $SLOT "$(jval $REC G_COLOR)"
  set_r 2 $SLOT "$(jval $REC B_COLOR)"
  set_r 3 $SLOT "$(jval $REC HUE)"
  set_r 4 $SLOT "$(jval $REC SATURATION)"
  set_r 5 $SLOT "$(jval $REC SHARPNESS)"
  set_r 6 $SLOT "$(jval $REC CONTRAST)"
  # v2: 白平衡不由配方控制，相机保持自动 WB（见 recipes.json 的 _note）
  st cap capdtm setusr 20 $(printf "0x%06x" $((0x140000 + ENUM))) >/dev/null 2>&1
  log "$(date '+%H:%M:%S') apply $REC -> slot$SLOT enum$ENUM"
  echo "  已写入:"
  echo "  R=$(get_r 0 $SLOT) G=$(get_r 1 $SLOT) B=$(get_r 2 $SLOT) HUE=$(get_r 3 $SLOT) SAT=$(get_r 4 $SLOT) SHARP=$(get_r 5 $SLOT) CON=$(get_r 6 $SLOT)"
  echo "  PW_TYPE  = $(st cap capdtm getusr 20 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')"
  ;;

#---------------------------------------------------------------
quick)
  # 只切风格，零prefman 写入（槽已预写好时用）
  [ -z "$REC" ] && { echo "用法: quick <recipe>  （槽已在preset 里）"; exit 1; }
  P=$(/opt/usr/nx-ks/busybox awk -v r="\"$REC\":" '/"presets"/{p=1} p && $0 ~ r {print; exit}' $RECIPE 2>/dev/null)
  SLOT=$(echo "$P" | sed -n 's/.*"slot1\?\([0-9]\+\)".*/\1/p')
  [ -z "$SLOT" ] && SLOT=$(echo "$P" | sed -n 's/.*"slot\([0-9]\+\)".*/\1/p')
  if [ -z "$SLOT" ]; then echo "配方 '$REC' 不在 preset 段，请用 apply"; exit 1; fi
  ENUM=$(enum_of_slot $SLOT)
  st cap capdtm setusr 20 $(printf "0x%06x" $((0x140000 + ENUM))) >/dev/null 2>&1
  echo "quick: $REC -> slot $SLOT enum $ENUM  PW_TYPE=$(st cap capdtm getusr 20 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')"
  ;;

#---------------------------------------------------------------

#---------------------------------------------------------------
dump)
  if [ -n "$SLOT" ]; then
    echo "slot $SLOT: R=$(get_r 0 $SLOT) G=$(get_r 1 $SLOT) B=$(get_r 2 $SLOT) HUE=$(get_r 3 $SLOT) SAT=$(get_r 4 $SLOT) SHARP=$(get_r 5 $SLOT) CON=$(get_r 6 $SLOT)"
  else
    for S in 0 1 2 3 4 5 6 7 8 9 10 11 12; do
      printf "slot %-3s R=%-5s G=%-5s B=%-5s HUE=%-4s SAT=%-4s SHARP=%-4s CON=%-4s\n" $S \
        "$(get_r 0 $S)" "$(get_r 1 $S)" "$(get_r 2 $S)" "$(get_r 3 $S)" \
        "$(get_r 4 $S)" "$(get_r 5 $S)" "$(get_r 6 $S)"
    done
  fi
  ;;

#---------------------------------------------------------------
#---------------------------------------------------------------
wb)
  # 单独设置白平衡（不动 PW）
  K=$2; A=$3; B=$4; MODE=${5:-manual}
  [ -z "$K" ] && { echo "用法: wb <K> <tint_a> <tint_b> [manual|auto|keep]"; exit 1; }
  [ -z "$A" ] && A=$TINT_NEUTRAL_A
  [ -z "$B" ] && B=$TINT_NEUTRAL_B
  set_wb "$K" "$A" "$B" "$MODE"
  echo "WB 已设置:"
  echo "  PW_TYPE  = $(st cap capdtm getusr 20 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')"
  ;;

#---------------------------------------------------------------
wbdump)
  echo "=== WB 段完整状态 ==="
  printf "  %-34s %s\n" "WB_TYPE (0xa390)" "$(get_wb_type)"
  printf "  %-34s %s\n" "WB_K_VALUE (0xa394)" "$(get_wb)"
  printf "  %-34s %s\n" "WB_K_BA (0xa3c0)" "$(get_tint)"
  printf "  %-34s %s\n" "WB_CUSTOM_BA (0xa3bc)" "$(get_tint)"
  printf "  %-34s %s\n" "CWB_RED (0xa3c4)" "$(prefman get 0 0x0a3c4 l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p')"
  printf "  %-34s %s\n" "CWB_GREEN (0xa3c8)" "$(prefman get 0 0x0a3c8 l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p')"
  printf "  %-34s %s\n" "CWB_BLUE (0xa3cc)" "$(prefman get 0 0x0a3cc l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p')"
  printf "  %-34s %s\n" "setusr 6 (WB 模式)" "$(st cap capdtm getusr 6 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')"
  ;;

#---------------------------------------------------------------
preset)
  # 把配方写进指定槽（默认 9），用于预置 3 个可见槽
  R=$2; T=$3
  [ -z "$R" ] && { echo "用法: preset <recipe> [slot]"; exit 1; }
  [ -z "$T" ] && T=9
  set_r 0 $T "$(jval $R R_COLOR)"; set_r 1 $T "$(jval $R G_COLOR)"
  set_r 2 $T "$(jval $R B_COLOR)"; set_r 3 $T "$(jval $R HUE)"
  set_r 4 $T "$(jval $R SATURATION)"; set_r 5 $T "$(jval $R SHARPNESS)"
  set_r 6 $T "$(jval $R CONTRAST)"
  echo "预设 $R -> slot $T:
    R=$(get_r 0 $T) G=$(get_r 1 $T) B=$(get_r 2 $T) HUE=$(get_r 3 $T) SAT=$(get_r 4 $T) SHARP=$(get_r 5 $T) CON=$(get_r 6 $T)"
  echo "  提示：现在可在机身 UI 上选对应的『自定义』槽查看"
  ;;

#---------------------------------------------------------------
reset)
  # 把三个可见槽恢复出厂中性（0-12 槽全部置中性）
  for s in 0 1 2 3 4 5 6 7 8 9 10 11; do
    set_r 0 $s 100; set_r 1 $s 100; set_r 2 $s 100
    set_r 3 $s 10;  set_r 4 $s 10;  set_r 5 $s 10;  set_r 6 $s 10
  done
  st cap capdtm setusr 20 0x140000 >/dev/null 2>&1
  echo "全部槽位已恢复中性，当前 PW_TYPE = $(st cap capdtm getusr 20 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')"
  ;;

#---------------------------------------------------------------
gui)
  # 启动 X11 图形配方选择器（委托给 flab_ui.sh，它用 setsid 脱离会话）
  # 用法: filmlab.sh gui [空闲秒数]
  # 退出方式（不依赖 telnet）：
  #   ① 触屏 / EV_OK 键 → gui_exit.sh → 杀 nxflab.arm
  #   ② flab_ui.sh quit
  #   ③ 空闲超时自动退出（默认 25秒）
  [ -n "$2" ] && FLAB_IDLE=$2
  export FLAB_IDLE
  sh /opt/usr/nx-ks/flab_ui.sh start
  ;;

#---------------------------------------------------------------
quit)
  # 关闭 X11 选择器（供触屏/按键脚本调用）
  killall -q nxflab.arm 2>/dev/null
  echo "X11 选择器已关闭"
  ;;

#---------------------------------------------------------------
cycle)
  # ★ 轮换到下一个配方（为机身按键设计，零界面）
  # 状态文件记录当前索引，SD 卡上，相机重启后保持
  ST=/mnt/mmc/filmlab/cur.idx
  N=$(jlist | grep -c .)
  [ -z "$N" ] || [ "$N" -lt 1 ] && { echo "配方库为空"; exit 1; }
  CUR=0
  [ -f "$ST" ] && CUR=$(cat $ST 2>/dev/null)
  case "$CUR" in ""|*[!0-9]*) CUR=0 ;; esac
  NEXT=$(( (CUR + 1) % N ))
  # 取第 NEXT 个配方名
  KEY=$(jlist | sed -n "$((NEXT+1))p")
  [ -z "$KEY" ] && { echo "取配方名失败"; exit 1; }
  # 固定写 slot 9（UI 上的自定义1），保证"当前选中项"固定
  SLOT=9
  ENUM=$(enum_of_slot $SLOT)
  set_r 0 $SLOT "$(jval $KEY R_COLOR)"; set_r 1 $SLOT "$(jval $KEY G_COLOR)"
  set_r 2 $SLOT "$(jval $KEY B_COLOR)"; set_r 3 $SLOT "$(jval $KEY HUE)"
  set_r 4 $SLOT "$(jval $KEY SATURATION)"; set_r 5 $SLOT "$(jval $KEY SHARPNESS)"
  set_r 6 $SLOT "$(jval $KEY CONTRAST)"
  st cap capdtm setusr 20 $(printf "0x%06x" $((0x140000 + ENUM))) >/dev/null 2>&1
  echo $NEXT > $ST
  NTH=$((NEXT+1))
  echo "[$NTH/$N] $(jlabel $KEY)  (key=$KEY)"
  log "$(date '+%H:%M:%S') cycle -> [$NTH/$N] $KEY"
  ;;

slots)
  echo "=== 槽位占用 ==="
  echo "slot 9= 0x140009  UI自定义1   可见"
  echo "slot 10= 0x14000a  UI 自定义2   可见"
  echo "slot 11 = 0x14000c  UI 自定义3   可见   ★ enum 与 slot 错位 1"
  echo "slot 12 = —              隐藏   ★ CUSTOM_4 在 prefman 存在但 UI 不显示"
  echo
  echo "当前 PW_TYPE = $(st cap capdtm getusr 20 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')"
  ;;

#---------------------------------------------------------------
*)
  echo "filmlab-apply.sh — FilmLab SD 卡配方引擎"
  echo
  echo "  list              列出 SD 卡全部配方"
  echo "  show <recipe>     查看配方内容"
  echo "  apply <recipe> [slot]   写槽 + 切风格（实时生效，约 1 秒）"
  echo "  quick <recipe>    只切风格（零写入，槽需已预写）"
  echo "  preset            预写 3 个可见槽并 save"
  echo "  dump [slot]       读回槽位值"
  echo "  slots             槽位映射表"
  echo "  wb <K> <a> <b> [manual|auto|keep]   单独设白平衡"
  echo "  wbdump            WB 段完整状态"
  echo "  preset <recipe> [slot]     预写一个槽（供 UI 零延迟选）"
  echo "  reset             全部槽位恢复出厂中性"
  echo "  gui [秒]           启动 X11 图形选择器（默认 45 秒自动退出）"
  echo "  cycle              轮换到下一个配方（绑机身键用，零界面）"
  echo "  quit                关闭 X11 选择器（等同 killall nxflab）"
  ;;
esac
