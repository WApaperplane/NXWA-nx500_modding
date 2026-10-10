#!/bin/sh
# @gate script=pwcalib.sh opens=rw one_shot=1 gate=mcb
# =====================================================================
# pwcalib.sh — PW 属性 id↔维度 校准（O3 通道；相机端）
# =====================================================================
# 目的（一次性）：把「PW 7 维 ↔ 属性 id / 值编码」敲实，为「一键滤镜」铺路。
#
# 原理链（见 docs/current/ATTR_BUS_MCB_2026-10-09.md）：
#   pwsend.arm → SetVariableDataMCB(id,&v,4) → MCB → p7 → ISP PW 引擎
#   读回判据 = `st cap capdtm varlist` 的 PW 7 变量（高 16 位）。
#
# 子命令（一次只跑一条；★ 全部发送【完整 32 位格式】，裸值会被存但不被消费）：
#   snap       读回当前 7 维 → 备份 /mnt/mmc/filmlab/pwcalib_backup.txt
#   probe1     发「编码桥」回归组：0x110/0x111/0x112 ← 完整 SCALAR 格式
#              （验证「发送值 = 读回值（完整 32 位）」+ 三维直推链路）
#   probe2     发「候选 id」探测组：0x10e/0x10f（COLOR 完整）、0x113（SCALAR 完整）
#              （10-09 夜结论：0x10e/0x113/0x114 无 varlist 响应；0x10f→PWCOLOR[14]。
#               本组留作新候选验证模板——R/G/B/HUE 直写正路 = subcategory 攻坚）
#   probe3     ★ 10-10 新解：R/G/B/HUE 内部 id = 0x130/0x131/0x132/0x133
#              （p7 d6bac 分发表 + 档位应用序列双证；发四个不同值 → readback 看跟随）
#   readback   读回 varlist → 与最近一次 probe 的发送值自动对照（客观判据）
#   restore    尽力恢复：把备份值【原样】发回（读回值即完整格式）；完整恢复建议
#              走「画面向导 → 自定义1」（官方路径，历史已验证）
#
# 安全：
#   * pwsend 内置白名单（id ∈ [0x100,0x12b]）+ 一次一条子命令
#   * probe 值均为温和值（不产生黑屏级/越界级扰动）；发送后必读回
#   * 任何异常（画面严重异常/返回非0）→ 停，走 restore 或画面向导
# =====================================================================

BB=/opt/usr/nx-ks/busybox
D=/mnt/mmc/filmlab
SEND=$D/pwsend.arm                    # 推荐落点：/mnt/mmc/filmlab/pwsend.arm
[ -x "$SEND" ] || SEND=/opt/usr/nx-ks/pwsend.arm
BAK=$D/pwcalib_backup.txt
SENT=$D/pwcalib_sent.txt
STS=$D/pwcalib_status.txt

[ -x "$BB" ] || { echo "ERR: 缺 busybox"; exit 1; }
"$BB" mkdir -p "$D"

# ---- varlist 抓 PW 行（与 filmlab.sh 同款解析；输出 NAME=0xHEX）----
get_pw() {
  st cap capdtm varlist 2>/dev/null | tr -d '\r' | "$BB" sed 's/\[[0-9;]*m//g' | \
  "$BB" awk -F'|' '
    /VARIABLE_PWCOLOR_[RGB]|VARIABLE_PWHUE|VARIABLE_PWSATURATION|VARIABLE_PWSHARPNESS|VARIABLE_PWCONTRAST/ {
      n = $2; gsub(/VARIABLE_/, "", n); gsub(/ /, "", n)
      h = $4; gsub(/ /, "", h)
      if (n != "" && h != "") print n"="h
    }'
}

usage() {
  echo "用法: pwcalib.sh snap|probe1|probe2|probe3|readback|restore"
  echo "  （每条 = 一次上机命令；probe 后必须 readback）"
}

case "$1" in

snap)
  OUT=$(get_pw)
  if [ -z "$OUT" ]; then
    echo "★ 读不到 PW 变量（varlist 无输出）——中止"
    exit 1
  fi
  echo "$OUT" > "$BAK"
  echo "=== 当前 ISP PW 7 维（已备份 → $BAK）==="
  echo "$OUT"
  ;;

probe1)
  # 已知 id + 完整 32 位格式：值 15 / 13 / 12 → raw16 = 16*(v-10)+15 = 95/63/47
  #   完整值 = (raw16 << 16) | 0xD80A
  echo "=== probe1：编码桥回归组（已知 id，完整 SCALAR 格式）==="
  echo "  0x110(SAT)   <- 0x005FD80A  (= 值15)"
  echo "  0x111(SHARP) <- 0x003FD80A  (= 值13)"
  echo "  0x112(CON)   <- 0x002FD80A  (= 值12)"
  : > "$SENT"
  echo "0x110 0x005FD80A" >> "$SENT"
  echo "0x111 0x003FD80A" >> "$SENT"
  echo "0x112 0x002FD80A" >> "$SENT"
  "$SEND" seq 0x110 0x005FD80A 0x111 0x003FD80A 0x112 0x002FD80A --yes
  RC=$?
  echo "pwsend rc=$RC"
  echo "★ 下一步：pwcalib.sh readback"
  exit $RC
  ;;

probe2)
  # 候选 id 探测组（完整格式）：0x10e/0x10f 用 COLOR 完整值（gain16=1000/1200）；
  #   0x113 用 SCALAR 完整值（raw16=79 = 值14）
  echo "=== probe2：候选 id 探测组（完整格式）==="
  echo "  0x10e <- 0x03E800FF  (COLOR；高16=gain16 1000)"
  echo "  0x10f <- 0x04B000FF  (COLOR；高16=gain16 1200)"
  echo "  0x113 <- 0x004FD80A  (SCALAR；高16=raw16 79 = 值14)"
  : > "$SENT"
  echo "0x10e 0x03E800FF" >> "$SENT"
  echo "0x10f 0x04B000FF" >> "$SENT"
  echo "0x113 0x004FD80A" >> "$SENT"
  "$SEND" seq 0x10e 0x03E800FF 0x10f 0x04B000FF 0x113 0x004FD80A --yes
  RC=$?
  echo "pwsend rc=$RC"
  echo "★ 下一步：pwcalib.sh readback"
  exit $RC
  ;;

probe3)
  # ★ 10-10 静态新解：R/G/B/HUE 的内部 id = 0x130-0x133（p7 FUN_000d6bac 分发表）
  #   四个不同值（值12-15 的 SCALAR 编码）→ readback 看哪个变量跟随哪个值
  echo "=== probe3：R/G/B/HUE 内部 id 实验（0x130-0x133）==="
  echo "  0x130(R)   <- 0x002FD80A  (值12)"
  echo "  0x131(G)   <- 0x003FD80A  (值13)"
  echo "  0x132(B)   <- 0x004FD80A  (值14)"
  echo "  0x133(HUE) <- 0x005FD80A  (值15)"
  : > "$SENT"
  echo "0x130 0x002FD80A" >> "$SENT"
  echo "0x131 0x003FD80A" >> "$SENT"
  echo "0x132 0x004FD80A" >> "$SENT"
  echo "0x133 0x005FD80A" >> "$SENT"
  "$SEND" seq 0x130 0x002FD80A 0x131 0x003FD80A 0x132 0x004FD80A 0x133 0x005FD80A --yes
  RC=$?
  echo "pwsend rc=$RC"
  echo "★ 下一步：pwcalib.sh readback"
  exit $RC
  ;;

readback)
  OUT=$(get_pw)
  if [ -z "$OUT" ]; then
    echo "★ 读不到 PW 变量——中止"
    exit 1
  fi
  echo "=== 读回（当前 ISP PW 7 维）==="
  echo "$OUT" | while read -r line; do echo "  $line"; done
  echo
  if [ ! -s "$SENT" ]; then
    echo "（无最近 probe 记录 $SENT；跳过自动对照）"
    exit 0
  fi
  echo "=== 自动对照（发送数据16位 vs 读回高16位）==="
  HIT=0
  while read -r ID V; do
    [ -z "$ID" ] && continue
    # 发送值（完整 32 位）的数据位 = 高 16 位；与读回高 16 位比对
    WANT=$(( (V >> 16) & 0xFFFF ))
    FOUND=""
    while IFS='=' read -r NAME HEX; do
      [ -z "$NAME" ] && continue
      H=$(( HEX >> 16 ))
      [ $(( H & 0xFFFF )) -eq "$WANT" ] && FOUND="$FOUND $NAME"
    done <<EOF2
$OUT
EOF2
    if [ -n "$FOUND" ]; then
      echo "  ✓ $ID 发送 $V（数据16=0x$(printf %04x $WANT)）→ 命中:$FOUND"
      HIT=$((HIT+1))
    else
      echo "  ✗ $ID 发送 $V → 无变量高16位匹配（该 id 无响应或编码不同）"
    fi
  done < "$SENT"
  echo
  echo "对照命中 $HIT 条。判据："
  echo "  · probe1 三条应全命中（发送数据16 = 读回高16）⇒ 三维直推链路回归通过"
  echo "  · probe2：0x10f 预期命中 PWCOLOR[14]；0x10e/0x113 按 10-09 结论无 varlist 命中"
  echo "  · probe3：0x130-0x133 预期命中 PWCOLOR_R/G/B / PWHUE（10-10 新解，首次实测）"
  echo "  · 全不中 ⇒ 负结论：该路径值编码不是直通，需换编码假说（带回离线轨）"
  echo "$OUT" > "$STS"
  ;;

restore)
  echo "=== restore（尽力恢复）==="
  [ -s "$BAK" ] || { echo "★ 无备份（$BAK）——请用「画面向导 → 自定义1」恢复"; exit 1; }
  # 备份里的读回值即为【完整 32 位格式】（发送 = 读回，逐位精确）⇒ 原样发回；
  # 已知映射（铁证）：SAT=0x110 / SHARP=0x111 / CON=0x112
  S95=$(grep PWSATURATION "$BAK" | cut -d= -f2)
  S63=$(grep PWSHARPNESS "$BAK" | cut -d= -f2)
  S47=$(grep PWCONTRAST  "$BAK" | cut -d= -f2)
  if [ -n "$S95" ] && [ -n "$S63" ] && [ -n "$S47" ]; then
    echo "  发回 SAT/SHARP/CON 备份完整值: $S95 $S63 $S47"
    "$SEND" seq 0x110 "$S95" 0x111 "$S63" 0x112 "$S47" --yes
  fi
  echo "★ COLOR/HUE 的完整恢复：请在机身「画面向导」重选「自定义1」"
  echo "  （官方路径，会把 slot9 的完整 7 维重新灌入 ISP——历史已验证）"
  ;;

*)
  usage
  exit 1
  ;;
esac
