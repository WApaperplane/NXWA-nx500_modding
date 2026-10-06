#!/bin/sh
#=====================================================================
# flab-verify.sh — 「真一键」客观验证（★ 不依赖人工看一眼）
#---------------------------------------------------------------------
# 验证目标（2026-10-05 修复的那个 bug）：
#   FilmLab 固定写 slot 9 → enum 恒为 9 → 旧代码收尾的
#   `setusr 20 0x140009` 是【同值空操作】→ ISP 不重读 PW 段 → 按 S1 没反应。
#   修复后 pw_force_reload() 会借道0x140009 制造真实跳变。
#   ★ 本脚本要证明的正是【跳变真的发生了，且 PW 值真的在位】。
#
# ★★ 设计铁律（来自本项目血泪）：
#   1. 判据必须是可自证的客观读数，**绝不能用"用户看一眼取景器"**。
#   2. 单核相机：一次只跑一条命令，绝不批量、绝不并发。
#   3. 每条 telnet 命令单独跑，看清输出再跑下一条。
#   4. busybox 走绝对路径 /opt/usr/nx-ks/busybox。
#
# 用法（相机端）：
#   sh flab-verify.sh pre     # 前置检查：文件/进程/当前状态
#   sh flab-verify.sh reload  # ★核心：验证 enum 跳变真的发生
#   sh flab-verify.sh apply   <recipe>   # 写配方 + 读回 7 维
#   sh flab-verify.sh roundtrip <recipe>  # ★完整闭环：写→跳变→读回→复验
#   sh flab-verify.sh shot                # 自动快门 + 列出新照片名
#   sh flab-verify.sh report              # 汇总判据
#=====================================================================
B=/opt/usr/nx-ks/busybox
F=/opt/usr/nx-ks/filmlab.sh
LAB=/mnt/mmc/filmlab
VLOG=$LAB/verify.log
PB=41964# 0xa3ec PW 基址
A() { echo $(( PB + $1 * 52 + $2 * 4 )); }

#只读读回
rd() { prefman get 0 "$(printf 0x%05x $1)" l 2>/dev/null | tr -d '\r' \
        | sed -n 's/.*value = \([-0-9]*\).*/\1/p'; }
# enum 读回（★ 客观判据的核心）
rd_enum() { st cap capdtm getusr 20 2>/dev/null | tr -d '\r' \
        | sed -n 's/.*UserData is [A-Z_0-9]* (\(0x[0-9a-f]*\)).*/\1/p'; }
rd_enum_name() { st cap capdtm getusr 20 2>/dev/null | tr -d '\r' \
        | sed -n 's/.*UserData is \([A-Z_0-9]*\).*/\1/p'; }

log() { echo "[$($B date '+%H:%M:%S')] $*" >> $VLOG; echo "$*"; }

slot9_line() {
  echo "  slot9: R=$(rd $(A 0 9)) G=$(rd $(A 1 9)) B=$(rd $(A 2 9)) HUE=$(rd $(A 3 9)) SAT=$(rd $(A 4 9)) SHP=$(rd $(A 5 9)) CON=$(rd $(A 6 9))"
}

case "$1" in

#---------------------------------------------------------------
pre)
  echo "=== FilmLab 验证 · 前置检查 ==="
  echo "-- 文件"
  # ★ 注意：引擎 filmlab.sh 目前【不在 install.sh 的部署链里】
  #   （install.sh 只 cp /mnt/mmc/scripts/* → /opt/usr/nx-ks/，
  #     而母本 scripts/ 下没有 filmlab.sh，只有 scripts/nx-rc/ 下本脚本）。
  #   引擎走的是 FTP 单独投递路线，源文件 test_server/filmsim/filmlab-apply.sh
  #   → 相机 /opt/usr/nx-ks/filmlab.sh。
  #   ⇒ 报"缺引擎"时不要去跑 install.sh，要单独 FTP 推 filmlab.sh。
  [ -x "$F" ] && echo "  ✓ 引擎 $F" \
             || echo "  ✗ 缺引擎 $F —— 跑 install.sh 无用，需 FTP 推 filmlab-apply.sh → $F"
  [ -f "$LAB/recipes.json" ] && echo "  ✓ 配方库 $LAB/recipes.json" \
                           || echo "  ✗ 缺配方库（SD 卡未插或没部署）"
  [ -f "$LAB/recipes.json" ] && echo "    配方数: $($B grep -c '^    \"[a-z]' $LAB/recipes.json 2>/dev/null)"
  echo "-- 相机进程"
  for p in /proc/[0-9]*; do
    c=$($B cat $p/comm 2>/dev/null)
    case "$c" in *camera*) echo "  ✓ di-camera-app pid=${p#/proc/} $c";; esac
  done
  echo "-- 当前状态"
  echo "  PW_TYPE   = $(rd_enum_name) ($(rd_enum))"
  echo "  MemFree   = $($B grep ^MemFree: /proc/meminfo | $B tr -cd '0-9') kB"
  echo "  loadavg   = $($B cat /proc/loadavg)"
  echo "  SD 照片数 = $($B ls /mnt/mmc/DCIM/*/*.JPG 2>/dev/null | $B wc -l)"
  slot9_line
  echo
  echo "  ★ 判据基线：上面的 PW_TYPE 与 slot9 7 维先记下来，后面比对用"
  ;;

#---------------------------------------------------------------
reload)
  # ★★★ 核心验证：证明 setusr 制造了真实跳变
  # 关键观察点：借道时 enum 会先变成 0x140009（CUSTOM_1），再回到目标值。
  # ★ 单次 setusr 无法看到中间态，所以这里手动分两步做，逐次回读。
  echo "=== 验证 enum 跳变（pw_force_reload 的底层原理）==="
  T0=$(rd_enum)
  echo "  [0] 当前 enum = $T0 ($(rd_enum_name))"
  echo
  echo "  [1] 手动借道 → 写 0x140009"
  st cap capdtm setusr 20 0x140009 >/dev/null 2>&1
  sleep 2
  T1=$(rd_enum)
  echo "      回读 enum = $T1  $([ "$T1" = "0x140009" ] && echo '✓ 跳变成功' || echo '✗ 没跳变')"
  echo
  echo "  [2] 切回目标 0x140009（与 [1] 相同 → 这里应为空操作，恰好复现原bug）"
  st cap capdtm setusr 20 0x140009 >/dev/null 2>&1
  sleep 2
  T2=$(rd_enum)
  echo "      回读 enum = $T2  $([ "$T2" = "$T1" ] && echo '（同值，符合预期）' || echo '异常')"
  echo
  echo "  [3] 再借道一次 → 0x140000(STANDARD)"
  st cap capdtm setusr 20 0x140000 >/dev/null 2>&1
  sleep 2
  T3=$(rd_enum)
  echo "      回读 enum = $T3  $([ "$T3" = "0x140000" ] && echo '✓ 二次跳变成功' || echo '✗ 没跳变')"
  echo
  echo "=== 判据 ==="
  echo "  A. [1] 与 [3] 都能成功跳变 → setusr 通道正常，借道机制可用"
  echo "  B. [2] 展示了原 bug：同值写入是空操作（回读不变、ISP 不会重读）"
  echo "  ★ 若 A 失败 → pw_force_reload 的借道思路在这台机器上不成立，"
  echo "    不要靠'重试几次'碰运气，要换触发重读的方式。"
  log "reload-test: T0=$T0 T1=$T1 T2=$T2 T3=$T3"
  ;;

#---------------------------------------------------------------
apply)
  [ -z "$2" ] && { echo "用法: apply <recipe>"; exit 1; }
  echo "=== apply '$2' ==="
  $F apply "$2"
  echo
  echo "--- 独立读回（不信任上面的输出，自己再读一遍）---"
  echo "  PW_TYPE = $(rd_enum_name) ($(rd_enum))"
  slot9_line
  echo
  echo "  ★ 判据：7 维读回值必须与 recipes.json 里'$2' 逐项一致。"
  echo "    不一致 = 写入失败（不是重读问题，是 set 本身失败）。"
  ;;

#---------------------------------------------------------------
roundtrip)
  # ★ 完整闭环：这是唯一能证明「一键」真的成立的测试
  [ -z "$2" ] && { echo "用法: roundtrip <recipe>"; exit 1; }
  R=$2
  mkdir -p $LAB 2>/dev/null
  echo "=== roundtrip: '$R' ==="
  echo
  echo "--- 步骤 0: 换成一个【已知不同】的配方作为对照 ---"
  echo "    目的：排除'画面本来就没变'的假阳性。"
  OTHER=$($B awk '/"recipes"/{i=1;next} /"presets"/{i=0} i && /^    "/{
           k=$0; gsub(/^ +"/,"",k); gsub(/".*/,"",k);
           if (k != "" && substr(k,1,1) != "_" && k != "'"$R"'") { print k; exit }}' \
        $LAB/recipes.json 2>/dev/null)
  [ -z "$OTHER" ] && { echo "  找不到第二个配方，跳过对照"; OTHER=$R; }
  echo "    对照配方 = $OTHER"
  $F apply "$OTHER" >/dev/null 2>&1
  sleep 2
  echo "    对照态: $(rd_enum_name) $(rd_enum)"
  slot9_line
  BEFORE="$(rd $(A 4 9)).$(rd $(A 0 9)).$(rd $(A 1 9)).$(rd $(A 2 9))"
  echo "    SAT.R.G.B = $BEFORE"
  echo
  echo "--- 步骤 1: 应用目标配方 '$R' ---"
  OUT=$($F apply "$R" 2>&1)
  echo "$OUT" | $B grep -E "重读方式|VERIFY-FAIL" | sed 's/^/  /'
  sleep 2
  echo
  echo "--- 步骤 2: 独立读回 ---"
  ENUM_AFTER=$(rd_enum)
  NAME_AFTER=$(rd_enum_name)
  slot9_line
  AFTER="$(rd $(A 4 9)).$(rd $(A 0 9)).$(rd $(A 1 9)).$(rd $(A 2 9))"
  echo "    SAT.R.G.B = $AFTER"
  echo
  echo "=== 判据表（全部通过才算「一键」成立）==="
  printf "  %-4s %s\n" "1" "enum 落在目标: $ENUM_AFTER $([ "$ENUM_AFTER" = "0x140009" ] && echo '✓' || echo "✗ 期望 0x140009")"
  printf "  %-4s %s\n" "2" "PW_TYPE 名称: $NAME_AFTER"
  printf "  %-4s %s\n" "3" "重读方式非空操作: $(echo "$OUT" | $B grep -o '重读方式 = .*' | head -1)"
  printf "  %-4s %s\n" "4" "★ 7 维与对照不同: $([ "$BEFORE" != "$AFTER" ] && echo "✓ $BEFORE → $AFTER" || echo "✗ 两者相同 = 写入没生效或配方数值相同")"
  printf "  %-4s %s\n" "5" "★ 无 VERIFY-FAIL: $(echo "$OUT" | $B grep -q VERIFY-FAIL && echo '✗ 有失败标记' || echo '✓')"
  echo
  echo "  ★★ 第 4 条是【唯一能证明画面真变了】的客观判据。"
  echo "     若 1/2/3/5 都过而 4 不过 → 说明两个配方数值相同，换一对再测。"
  echo "     ★ 全部通过后，还需跑一次 shot 拍图 + 拉 JPG 算R/G/B 均值，才算端到端成立。"
  log "roundtrip $R: before=$BEFORE after=$AFTER enum=$ENUM_AFTER mode=$(echo "$OUT"|$B grep -o '重读方式 = .*')"
  ;;

#---------------------------------------------------------------
shot)
  # 自动快门 + 列出新照片，供 80 端口拉取做像素统计
  echo "=== 自动快门 ==="
  PHD=/mnt/mmc/DCIM/575PHOTO
  BEFORE=$($B ls $PHD/*.JPG 2>/dev/null | $B wc -l)
  echo "  拍前 $BEFORE 张"
  st cap sh 2>&1 | tr -d '\r' | head -3
  i=0
  GOT=0
  while [ $i -lt 25 ]; do
    sleep 1
    AFTER=$($B ls $PHD/*.JPG 2>/dev/null | $B wc -l)
    if [ "$AFTER" -gt "$BEFORE" ]; then
      echo "  ✓ 新照片已出现（+$(($AFTER - $BEFORE))，等 ${i}s）"
      $B ls -lt $PHD/*.JPG 2>/dev/null | head -1 | sed 's/^/  /'
      $B ls -lt $PHD/*.JPG 2>/dev/null | head -1 | awk '{print $NF}' > $LAB/last_shot.txt
      GOT=1
      break
    fi
    i=$((i + 1))
  done
  [ "$GOT" = "0" ] && echo "  ✗ 25 秒内没检测到新照片"
  echo
  echo "  下一步（PC 端拉图做像素统计，80 端口）："
  echo "    curl -s --noproxy '*' 'http://<相机IP>/DCIM/575PHOTO/$(cat $LAB/last_shot.txt)' -o shot.jpg"
  echo "  ★ 判据：不同配方的同一场景，R/G/B 均值应有可测量差异。"
  echo "    纯黑白配方(trix400/hp5/monowarm SAT=0) 的 R≈G≈B，是最干净的判据。"
  ;;

#---------------------------------------------------------------
report)
  echo "===== FilmLab 验证汇总====="
  [ -f $VLOG ] && { echo "--- verify.log 末 30 行 ---"; $B tail -30 $VLOG; } \
                || echo "(无 $VLOG —— 还没跑过 reload/roundtrip)"
  echo
  echo "--- 当前状态 ---"
  echo "  PW_TYPE = $(rd_enum_name) ($(rd_enum))"
  slot9_line
  echo "  MemFree = $($B grep ^MemFree: /proc/meminfo | $B tr -cd '0-9') kB  loadavg=$($B cat /proc/loadavg)"
  echo
  echo "--- 判据对照---"
  echo "  ① enum 借道能跳变      → reload 第 [1][3] 步都✓"
  echo "  ② apply 后 7 维读回正确 → roundtrip 判据 1/2"
  echo "  ③ 7 维与对照不同       → roundtrip 判据 4（★ 唯一能证明画面变了）"
  echo "  ④ 拍图 R/G/B 有差异     → shot + PC 端像素统计（端到端）"
  echo "  ⑤ 无 VERIFY-FAIL       → roundtrip 判据 5"
  ;;

*)
  echo "用法: flab-verify.sh {pre|reload|apply <recipe>|roundtrip <recipe>|shot|report}"
  ;;
esac
