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
#   sh filmlab-apply.sh mkgui                  ★ 从 SD 卡配方库生成 mod_gui 菜单页
#=====================================================================
# ★ mod_gui 集成（2026-10-04 定案）
#   mod_gui 菜单格式 = 纯文本 `button|标签|命令`，`@` 前缀开子菜单，
#   末两行固定「返回|@<上级>」和「取消|<gui_exit.sh>」，2 列网格上限约 24 个按钮。
#   ★★ 因此"配方数不限"必须靠动态生成菜单才成立 —— 手写菜单就是死的。
#   mkgui 读 SD 卡 recipes.json 的 label，按钮上限 22（给返回/取消留位）。
#   在 EV_EV.sh（mod_gui 入口）里先跑 mkgui 再起 mod_gui → 菜单与 SD 卡永远同步。
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

# ---- 强制ISP 重读 PW 段（2026-10-05 修正）--------------------------------
#★ 为什么需要这个函数（★ 一个真实的逻辑 bug）
#   旧apply 的收尾动作是 `setusr 20 $NEED`「写完再切一次，让 ISP 重读」。
#   但FilmLab 固定写 slot 9 → enum 恒为 9 → 连按两次同一个 enum。
#   ★ 第二次 setusr 写入的是【与当前完全相同的值】= 空操作，
#     ISP 收不到"风格变了"的通知 → 【不重读 PW 段】→ 画面不变。
#   ★ 这就是"按S1 没反应、必须回 GUI 把图片向导切走再切回来才生效"的根因。
#     它不是延迟，是那次setusr 根本没生效。
#
# ★ 正确的做法：制造一次【真实变化】。
#   enum 不同 → 直接切（本身就是变化，会触发重读）
#   enum 相同 → 先切到别处（STANDARD= 0x140000），再切回来 = 一次真实变化
_NEED_PW=0
pw_force_reload() {
  TGT=$1
  CUR=$(st cap capdtm getusr 20 2>/dev/null | tr -d '\r' \
        | sed -n 's/.*UserData is [A-Z_0-9]* (\(0x[0-9a-f]*\)).*/\1/p')
  _NEED_PW=$CUR
  # ★ 借道用的中间值：必须既不等于当前、也不等于目标，否则还是同值空操作。
  #   优先用 CUSTOM_1(0x140009)，它在任何 FilmLab 场景下都不可能是目标
  #   （FilmLab 只写 slot 9，槽位映射表里slot9=enum9，中间隔着原生槽）。
  MID=0x140009
  [ "$MID" = "$TGT" ] && MID=0x140000
  [ "$MID" = "$TGT" ] && MID=0x14000a
  if [ "$CUR" = "$TGT" ]; then
    st cap capdtm setusr 20 $MID >/dev/null 2>&1
    $B sleep 1
    st cap capdtm setusr 20 "$TGT" >/dev/null 2>&1
    $B sleep 1
    RELOAD=via-$MID
  else
    st cap capdtm setusr 20 "$TGT" >/dev/null 2>&1
    $B sleep 1
    RELOAD=direct
  fi
  # ★ 自证：切完回读，确认真的落在目标上（不信 setusr 的退出码）
  NOW=$(st cap capdtm getusr 20 2>/dev/null | tr -d '\r' \
        | sed -n 's/.*UserData is [A-Z_0-9]* (\(0x[0-9a-f]*\)).*/\1/p')
  [ "$NOW" = "$TGT" ] || RELOAD="$RELOAD-VERIFY-FAIL(now=$NOW want=$TGT)"
}

# ★★★ trigger_reload —— 真正能触发 ISP 重读的那一步（2026-10-08 实机发现）
#   为什么需要它（这一轮排查的结论）：
#     · `pw_force_reload` 用 `setusr 20` 改 PW 类型 ⇒ 实测【画面不刷新】
#     · 写 prefman 0xa3d4（APPPREF_EFFECT_PW_TYPE，UI 的 PW 类型字段）⇒ 也不刷新
#       （而相机 UI 里手动切 PW 时，正是这个字段从 9→1 / 1→9 变化 —— 已用 diff 实证）
#     · 真因：di-camera-app 用【自己进程内的 PW 参数副本】喂 ISP，
#             外部改 prefman / capdtm 它不知道，所以画面不动。
#   ★ 实测有效的触发方式 = 【切换一次拍摄模式】：
#         di-camera-app 重建 ISP 管线时会重读 prefman 的 PW 参数 ⇒ 画面立即变。
#   ★ 实机验证（2026-10-08）：`st app mode p; sleep 4; st app mode a`
#         之后画面立刻从彩色变成刚 apply 的黑白（TriX 400）。
#   ⇒ 有了它，链路 = 【打开菜单 → 点配方】两步，不再需要手动进 Fn 菜单选 PW。
trigger_reload() {
  M=$(st cap capdtm getusr DIALMODE 2>/dev/null | tr -d '\r' \
      | sed -n 's/.*UserData is DIALMODE_\([A-Z_]*\).*/\1/p')
  case "$M" in
    SMARTAUTO)    M2=auto ;;
    APERTURE)     M2=a ;;
    SHUTTERSPEED) M2=s ;;
    MANUAL)       M2=m ;;
    SMARTPRO)     M2=smart-pro ;;
    *)            M2=p ;;
  esac
  # 借道：先切到一个【不同】的模式，再切回原模式
  case "$M2" in
    p) TMP=a ;;
    *) TMP=p ;;
  esac
  st app mode $TMP >/dev/null 2>&1
  $B sleep 1
  st app mode $M2  >/dev/null 2>&1
  $B sleep 1
  RELOAD2="mode-switch($TMP->$M2)"
}

# slot -> enum（切风格用）
enum_of_slot() {
  case $1 in
    9)  echo 9;;
    10) echo 10;;
    11) echo 12;;   # ★ slot 11 对应 enum 12
    *)  echo $1;;   # 0-8 原生槽，enum = slot
  esac
}
# ★ 合法写入校验（2026-10-04 新增）
#  UI 可见的只有 slot 9/10/11（自定义1/2/3）。slot 12=CUSTOM_4 在 prefman 里
#  存在但 UI 不显示 → 写进去就是"看不见的脏数据"，会污染整机状态
#  （实测：slot 12 残留 240/240/40 时，相机拍完照片后台卡、照片删不掉）。
ok_slot() {
  case $1 in
    9|10|11) return 0;;    # 允许
    *) return 1;;          # 其余一律拒绝
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
  # ★★★ 默认永远写 slot 9（UI 的「自定义1」）★★★
  #   2026-10-04：原逻辑是"看当前 enum 轮换到下一个槽"，导致用户无法知道
  #   配方被写到了哪个槽，必须切到 UI 上逐个看 —— 这正是"不够一键"的根因。
  #   固定单槽后：按一下 = 当前槽被覆盖 = 取景器立刻变，无需任何 UI 确认。
  #   相机 UI 上会一直显示「Picture Wizard > 自定义1」，位置恒定、可预测。
  [ -z "$SLOT" ] && SLOT=9
  ENUM=$(enum_of_slot $SLOT)
  ok_slot $SLOT || { echo "拒绝：slot $SLOT 不是 UI 可见槽（只允许 9/10/11）。"; echo "  恢复出厂请用: filmlab.sh reset"; exit 1; }
  echo ">>> 应用 '$REC' -> slot $SLOT (enum $ENUM)"
  # ★★★ 2026-10-08 加固：先取全部 7 维，★ 任一为空就【拒绝写入】。
  #   起因（U2 上机实测，用户报告）：/mnt/mmc/filmlab/recipes.json 缺失时 jval 返回空串，
  #   set_r 把槽位写成 0 ⇒ slot9（UI 自定义1）全 0 ⇒ 相机【整屏黑】，只能靠 reset 救回。
  #   ★ 读不到就该报错退出，绝不该写入坏值 —— 这是"静默失败导致破坏性写入"的典型。
  V0=$(jval $REC R_COLOR);   V1=$(jval $REC G_COLOR);    V2=$(jval $REC B_COLOR)
  V3=$(jval $REC HUE);       V4=$(jval $REC SATURATION)
  V5=$(jval $REC SHARPNESS); V6=$(jval $REC CONTRAST)
  case "" in
    $V0|$V1|$V2|$V3|$V4|$V5|$V6)
      echo "★ 拒绝写入：配方 '$REC' 的字段读不到值。"
      echo "  原因通常是 /mnt/mmc/filmlab/recipes.json 缺失或格式不符（先用 filmlab.sh list 自查）。"
      echo "  ★ 强行写入会把槽位清成 0 ⇒ 画面全黑，故中止。"
      exit 1 ;;
  esac
  set_r 0 $SLOT "$V0"
  set_r 1 $SLOT "$V1"
  set_r 2 $SLOT "$V2"
  set_r 3 $SLOT "$V3"
  set_r 4 $SLOT "$V4"
  set_r 5 $SLOT "$V5"
  set_r 6 $SLOT "$V6"
  # v2: 白平衡不由配方控制，相机保持自动 WB（见 recipes.json 的 _note）
  # ★ 写完后强制 ISP 重读（2026-10-05：旧代码这里写的是同值空操作，永远不生效）
  pw_force_reload $(printf "0x%06x" $((0x140000 + ENUM)))
  # ★★★ 2026-10-08：关键一步 —— 切一次拍摄模式，逼 di-camera-app 重读 prefman 的 PW 参数。
  #   实测：仅 setusr 20 不足以刷新画面（详见 trigger_reload 的注释）。
  trigger_reload
  log "$(date '+%H:%M:%S') apply $REC -> slot$SLOT enum$ENUM reload=$RELOAD $RELOAD2"
  echo "  已写入:"
  echo "  R=$(get_r 0 $SLOT) G=$(get_r 1 $SLOT) B=$(get_r 2 $SLOT) HUE=$(get_r 3 $SLOT) SAT=$(get_r 4 $SLOT) SHARP=$(get_r 5 $SLOT) CON=$(get_r 6 $SLOT)"
  echo "  PW_TYPE  = $(st cap capdtm getusr 20 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')"
  echo "  重读方式 = $RELOAD + $RELOAD2"
  case "$RELOAD" in *VERIFY-FAIL*) echo "  ★★ 自证失败：切完回读不等于目标，ISP 大概率没重读";; esac
  echo "  ★ 相机 UI 上固定显示「自定义1」，不用切菜单确认"
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
  pw_force_reload $(printf "0x%06x" $((0x140000 + ENUM)))
  echo "quick: $REC -> slot $SLOT enum $ENUM (reload=$RELOAD)  PW_TYPE=$(st cap capdtm getusr 20 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')"
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
  ok_slot $T || { echo "拒绝：slot $T 不是 UI 可见槽（只允许 9/10/11）。"; exit 1; }
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
  # 把全部 14 个槽恢复出厂中性
  # ★★★ 必须包含 slot 12（CUSTOM_4）★★★
  #   2026-10-04：slot 12 残留 R=240 G=240 B=40（黄绿）导致相机"拍完照片后台卡、
  #   照片删不掉"，只有 reset 能救 —— 而当时的循环只到 11，漏了它。
  #   写 slot 12 很容易发生（preset <recipe> 12），UI 又看不见，查不出来。
  for s in 0 1 2 3 4 5 6 7 8 9 10 11 12; do
    set_r 0 $s 100; set_r 1 $s 100; set_r 2 $s 100
    set_r 3 $s 10;  set_r 4 $s 10;  set_r 5 $s 10;  set_r 6 $s 10
  done
  # ★ 先离开再回来，制造一次真实跳变。
  #   ★ 不能连续两次都写 0x140000 —— 第二次是同值空操作，借道也借不动。
  #   先切到 CUSTOM_1(0x140009)，再让 pw_force_reload 切回 STANDARD。
  st cap capdtm setusr 20 0x140009 >/dev/null 2>&1
  $B sleep 1
  pw_force_reload 0x140000
  # 读回验证：任何一槽不中性就报出来（不要静默成功）
  BAD=0
  i=0
  while [ $i -le 6 ]; do
    s=0
    while [ $s -le 12 ]; do
      case $i in 0|1|2) OK=100;; *) OK=10;; esac
      V=$(get_r $i $s)
      case "$V" in
        $OK|"$OK (*)"|"") ;;
        *) echo "  ★ 未恢复 dim$i slot$s =$V (期望 $OK)"; BAD=$((BAD+1));;
      esac
      s=$((s+1))
    done
    i=$((i+1))
  done
  [ $BAD -eq 0 ] && echo "  ✓14 槽全部已核对为中性" || echo "  ★仍有 $BAD 处异常"
  echo "当前 PW_TYPE = $(st cap capdtm getusr 20 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')"
  ;;

#---------------------------------------------------------------
# ★ gui / quit 已于 2026-10-05 移除（X11 全屏 720x480 在单核机上吃满 CPU，
#   点一下整机卡死；flab_ui.sh 已删除）。
#   交互入口只剩 mod_gui（菜单页由 mkgui 生成）+ 机身键 cycle。
#   配方选择一律走 mod_gui，不要试图恢复 X11 方案。
#  ;;

#---------------------------------------------------------------
cycle)
  # ★ 轮换到下一个配方（为机身按键设计，零界面、零 X11）
  # ★★ 与 apply 一样：永远写 slot 9（UI「自定义1」），位置恒定 → 真正的一键
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
  # ★ 同样必须强制重读：cycle 恒定写 slot 9，enum 永远是 9，
  #   旧代码的 setusr 20 <9> 在第二次按 S1 时是同值空操作 → 按了没反应。
  pw_force_reload $(printf "0x%06x" $((0x140000 + ENUM)))
  echo $NEXT > $ST
  NTH=$((NEXT+1))
  echo "[$NTH/$N] $(jlabel $KEY)  (key=$KEY, reload=$RELOAD)"
  log "$(date '+%H:%M:%S') cycle -> [$NTH/$N] $KEY reload=$RELOAD"
  ;;

slots)
  echo "=== 槽位映射 ==="
  echo "slot 9 = 0x140009  UI 自定义1  可见  ← FilmLab 主用"
  echo "slot 10= 0x14000a  UI 自定义2  可见"
  echo "slot 11= 0x14000c  UI 自定义3  可见   ★ enum 与 slot 错位 1"
  echo "slot 12= —               隐藏  ★ CUSTOM_4 在 prefman 存在但 UI 不显示"
  echo "                          ★ 已禁止写入：脏数据会污染整机状态"
  echo "                          ★ 修复请跑 filmlab.sh reset（它会清到 slot 12）"
  echo
  echo "当前 PW_TYPE = $(st cap capdtm getusr 20 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')"
  ;;

#---------------------------------------------------------------
mkgui)
  # ★ 从 SD 卡配方库生成 mod_gui 菜单页 —— 让"配方数不限"真正成立
  # 手写菜单是死的：往 SD 卡加配方但不改菜单文件，界面上就看不到。
  # 每次打开 mod_gui（EV_EV.sh）先跑一次本命令 → 菜单与 SD 卡永远同步。
  OUT=/opt/usr/nx-ks/gui_filmlab1b.NX500
  MAXBTN=22                    # mod_gui 上限约 24，去掉「返回/取消」两行
  ST=/mnt/mmc/filmlab/cur.idx  # 当前配方索引，用来打 ★ 标记

  CUR=0
  [ -f "$ST" ] && CUR=$(cat $ST 2>/dev/null)
  case "$CUR" in ""|*[!0-9]*) CUR=0 ;; esac

  N=0
  TOTAL=0
  jlist > /tmp/fl.keys
  [ -s /tmp/fl.keys ] || { echo "mkgui: 配方库为空，保持原菜单不动"; rm -f /tmp/fl.keys; exit 1; }
  TOTAL=$(grep -c . /tmp/fl.keys 2>/dev/null)
  case "$TOTAL" in ""|*[!0-9]*) TOTAL=0 ;; esac

  #先写头部（务必 LF 行尾 —— CRLF 会让 mod_gui 解析失败）
  {
    echo "#====================================================================="
    echo "# gui_filmlab1b.NX500 —— FilmLab 一键配方（由filmlab.sh mkgui 自动生成）"
    echo "#====================================================================="
    echo "# ★ 本文件是生成物，不要手改。改配方请编辑 SD卡 filmlab/recipes.json"
    echo "#   然后重新打开 mod_gui（或 telnet 执行 filmlab.sh mkgui）"
    echo "#格式：button|标签|命令"
    echo ""
  } > $OUT

  while read KEY; do
    [ -z "$KEY" ] && continue
    N=$((N + 1))
    [ $N -gt $MAXBTN ] && break
    LBL=$(jlabel $KEY)
    [ -z "$LBL" ] && LBL=$KEY
    # ★ 剥掉标签里可能混入的引号/逗号/CR —— 竖线会破坏菜单解析
    LBL=$(echo "$LBL" | tr -d '"\r,' | sed 's/[|]//g')
    # 当前生效的配方打★（静态标记，生成那一刻的状态）
    [ $((N - 1)) -eq $CUR ] && LBL="★ $LBL"
    echo "button|$LBL|/opt/usr/nx-ks/filmlab.sh apply $KEY" >> $OUT
  done < /tmp/fl.keys
  rm -f /tmp/fl.keys

  {
    echo ""
    echo "button|返回|@/opt/usr/nx-ks/gui_filmlab.NX500"
    echo "button|取消|/opt/usr/nx-ks/gui_exit.sh"
  } >> $OUT

  echo "mkgui: 已生成 $OUT — $N 个配方按钮（配方库共 $TOTAL 个）"
  [ "$TOTAL" -gt "$MAXBTN" ] && echo "  ★ 超出 $MAXBTN 按钮上限，剩余 $((TOTAL - MAXBTN)) 个请用 filmlab.sh cycle 或 telnet apply"
  log "$(date '+%H:%M:%S') mkgui -> $N buttons (of $TOTAL)"
  ;;

#---------------------------------------------------------------
export)
  # ★ 从 SD 卡 JSON 导出扁平配方表，给机内 UI 程序（nxfilmui.arm）读。
  #   nxfilmui 不解析 JSON（相机上也没有 jq），只读纯文本：
  #     key|label|R|G|B|HUE|SAT|SHARP|CON
  #   每次启动 UI 前跑一次，保证配方库改了 UI 就跟着变。
  OUT=$LAB/recipes.txt
  TMP=$OUT.tmp
  N=0
  jlist > /tmp/fl.keys
  [ -s /tmp/fl.keys ] || { echo "export: 配方库为空，未改动 $OUT"; rm -f /tmp/fl.keys; exit 1; }
  {
    while read KEY; do
      [ -z "$KEY" ] && continue
      LBL=$(jlabel "$KEY")
      [ -z "$LBL" ] && LBL=$KEY
      # ★ 竖线会破坏 UI 的 strtok('|') 解析；换行/回车会串行
      LBL=$(echo "$LBL" | tr -d '|\r\n' | cut -c1-40)
      echo "$KEY|$LBL|$(jval $KEY R_COLOR)|$(jval $KEY G_COLOR)|$(jval $KEY B_COLOR)|$(jval $KEY HUE)|$(jval $KEY SATURATION)|$(jval $KEY SHARPNESS)|$(jval $KEY CONTRAST)"
      N=$((N + 1))
    done < /tmp/fl.keys
  } > $TMP
  rm -f /tmp/fl.keys
  if [ -s "$TMP" ]; then
    mv -f $TMP $OUT
    echo "export: 已生成 $OUT — $N 个配方"
  else
    rm -f $TMP
    echo "export: 生成失败，保持原$OUT 不变"
    exit 1
  fi
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
  echo "  mkgui             ★ 从 SD 卡配方库生成 mod_gui 菜单页（打开 mod_gui 时自动跑）"
  echo "  export            ★ 导出 recipes.txt（给机内 UI 程序读）"
  echo "  cycle              轮换到下一个配方（绑机身键用，零界面）"
  echo "  quit               关闭 X11 选择器（已弃用，X11 在单核机上会吃满 CPU）"
  ;;
esac
