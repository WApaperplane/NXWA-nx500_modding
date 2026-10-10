#!/bin/bash
#=====================================================================
# flab_sim.sh —— filmlab.sh 离线仿真回归（PC 侧 · 无需相机）
#=====================================================================
# 背景（2026-10-10）：filmlab 引擎迭代频繁，而相机经常离线。本工具把
# filmlab.sh 放进"仿真相机环境"（路径替换 + prefman/st/pwsend shim），
# 在 PC 上回归验证核心链路与【进程调用数】（速度指标）。
#
# 原理：
#   1. sed 把 /opt/usr/nx-ks → <sim>/opt、/mnt/mmc/filmlab → <sim>/lab
#   2. shim：busybox（转发）/ prefman（记录调用+假读回）/ st（假 getusr）/
#      pwsend.arm（回显参数）——全部追加进 calls.log 供计数
#   3. 用例断言关键输出 + 进程数阈值
#
# 用法:
#   bash test_server/filmlab/flab_sim.sh            # 全部用例
#   bash test_server/filmlab/flab_sim.sh apply-fast # 单用例（见下方 case）
#
# ★ 只读 PC：不连接相机、不修改仓内源码（仿真产物全在 raw8/tmp/flsim/）
#=====================================================================
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
SIM="$ROOT/raw8/tmp/flsim"
RECIPES="$ROOT/scripts/filmlab/recipes.json"
SRC="$ROOT/scripts/filmlab.sh"

PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "  [PASS] $*"; }
bad()  { FAIL=$((FAIL+1)); echo "  [FAIL] $*"; }
n_calls() { grep -c "${1:-^}" "$SIM/calls.log" 2>/dev/null || echo 0; }

#--------------------------------------------------------------- setup
setup() {
  rm -rf "$SIM"
  mkdir -p "$SIM/opt" "$SIM/lab"

  cat > "$SIM/opt/busybox" <<EOF
#!/bin/sh
cmd=\$1; shift
exec "\$cmd" "\$@"
EOF
  cat > "$SIM/opt/prefman" <<EOF
#!/bin/sh
echo "prefman \$*" >> "$SIM/calls.log"
case "\$1" in get) echo "value = 100";; esac
exit 0
EOF
  cat > "$SIM/opt/st" <<EOF
#!/bin/sh
echo "st \$*" >> "$SIM/calls.log"
case "\$*" in
  "cap capdtm getusr 20"*) echo "UserData is CUSTOM (0x140009)";;
  *) : ;;
esac
exit 0
EOF
  cat > "$SIM/opt/pwsend.arm" <<EOF
#!/bin/sh
echo "PWSEND: \$*"
exit 0
EOF
  chmod +x "$SIM/opt/busybox" "$SIM/opt/prefman" "$SIM/opt/st" "$SIM/opt/pwsend.arm"

  cp "$RECIPES" "$SIM/lab/recipes.json"
  sed -e "s#/opt/usr/nx-ks#$SIM/opt#g" -e "s#/mnt/mmc/filmlab#$SIM/lab#g" \
      "$SRC" > "$SIM/opt/filmlab_sim.sh"
  chmod +x "$SIM/opt/filmlab_sim.sh"

  export PATH="$SIM/opt:$PATH"
}

reset_calls() { : > "$SIM/calls.log"; }
filmlab()     { sh "$SIM/opt/filmlab_sim.sh" "$@"; }

#--------------------------------------------------------------- 用例
case_apply_fast() {
  echo "== 用例 1：apply --fast（提速路径）=="
  reset_calls
  OUT=$(filmlab apply portra400 --fast)
  echo "$OUT" | grep -q "✓ portra400 -> slot9" && ok "单行结果输出" || bad "输出缺 ✓ 行：$OUT"
  N=$(grep -c "prefman set" "$SIM/calls.log" 2>/dev/null || echo 0)
  [ "$N" = "7" ] && ok "prefman set = 7 次" || bad "prefman set = $N（应 7）"
  T=$(grep -c "prefman\|^st " "$SIM/calls.log" 2>/dev/null || echo 0)
  [ "$T" -le 12 ] && ok "总进程调用 = $T（≤12，旧版 ~33）" || bad "总进程调用 = $T（应 ≤12）"
}

case_apply_pw() {
  echo "== 用例 2：FILMLAB_PW=1 三维直推参数（10-10 上机定案：R/G/B/HUE 无外部通路）=="
  reset_calls
  OUT=$(FILMLAB_PW=1 filmlab apply portra400 --fast)
  echo "$OUT" | grep -q "seq 0x110 0xffffd80a 0x111 0xffffd80a 0x112 0xffefd80a --yes" \
    && ok "SAT/SHARP/CON 三维（0x110-0x112）" || bad "S/P/C 参数错：$(echo "$OUT" | grep seq)"
  echo "$OUT" | grep -q "0x130" \
    && bad "仍发 R/G/B/HUE（应默认跳过：无可达通路）" || ok "已跳过 0x130-0x133（无外部通路）"
  echo "$OUT" | grep -q "pw=direct" && ok "fast 行含 pw=direct" || bad "fast 行缺 pw 状态"
}

case_apply_detail() {
  echo "== 用例 3：apply（详细路径）=="
  reset_calls
  OUT=$(filmlab apply trix400)
  echo "$OUT" | grep -q "通道: ①存储=已写" && ok "通道状态行" || bad "缺通道状态行"
  echo "$OUT" | grep -q "已写入(saved)" && ok "回读写入确认" || bad "缺回读确认"
}

case_jline() {
  echo "== 用例 4：jline 单配方提取（对照实测值）=="
  # 以仿真脚本同款 awk 提取（配方 portra400 实测 = 106/100/93/11/9/9/8）
  LINE=$(awk -v want="portra400" '
    BEGIN { inr=0; key="" }
    /"recipes"/ { inr=1; next }
    /"presets"/ { inr=0; next }
    !inr { next }
    /^    "/ { key=$0; sub(/^    "/,"",key); sub(/": *\{.*$/,"",key); sub(/",? *$/,"",key); delete F; next }
    /^        "/ && key == want { name=$0; sub(/^ *"/,"",name); sub(/":.*$/,"",name); val=$0; gsub(/[^0-9-]/,"",val); F[name]=val; next }
    /^    \}/ { if (key == want) { printf "%s|%s|%s|%s|%s|%s|%s\n", F["R_COLOR"],F["G_COLOR"],F["B_COLOR"],F["HUE"],F["SATURATION"],F["SHARPNESS"],F["CONTRAST"]; exit } }
  ' "$RECIPES")
  [ "$LINE" = "106|100|93|11|9|9|8" ] && ok "portra400 = $LINE" || bad "portra400 提取 = $LINE"
}

case_mkgui() {
  echo "== 用例 5：mkgui 菜单（分页 + --fast 按钮）=="
  OUT=$(filmlab mkgui)
  echo "$OUT" | grep -q "18 个配方按钮" && ok "分页按钮数 = 18" || bad "按钮数异常：$OUT"
  MENU="$SIM/opt/gui_filmlab1b.NX500"
  grep -q "filmlab.sh apply portra400 --fast" "$MENU" && ok "按钮命令带 --fast" || bad "按钮缺 --fast"
  grep -q "▶ 下页" "$MENU" && ok "分页导航在" || bad "缺分页导航"
}

#--------------------------------------------------------------- main
ALL=(apply-fast apply-pw apply-detail jline mkgui)
WANT="${1:-all}"

setup
echo "仿真环境: $SIM"
echo ""

for c in "${ALL[@]}"; do
  [ "$WANT" != "all" ] && [ "$WANT" != "$c" ] && continue
  case "$c" in
    apply-fast)   case_apply_fast ;;
    apply-pw)     case_apply_pw ;;
    apply-detail) case_apply_detail ;;
    jline)        case_jline ;;
    mkgui)        case_mkgui ;;
  esac
  echo ""
done

echo "=========================================="
echo "RESULT: $([ $FAIL -eq 0 ] && echo PASS || echo FAIL)  ($FAIL fail / $PASS pass)"
exit $([ $FAIL -eq 0 ] && echo 0 || echo 1)
