#!/bin/sh
#=====================================================================
# MOBILE_MOBILE.sh —— 双击 WiFi 键 = 零 UI 轮换配方（最轻的一键）
#=====================================================================
# keyscan.c 规则 B 的文件名：同键 1 秒内连按两次 → <键名>_<键名>
#   WiFi 键 code 215，nxkeyname[215] = "MOBILE"
#   判定代码：
#     if (NXKEY_EV1 != code && msec_elapsed < 1000
#         && code == previous_ev.code && value == previous_ev.value)
#         sprintf(shell_name, "%s_%s", ...)
#   门槛：strlen(shell_name) > 4 ⇒ "MOBILE_MOBILE"（13字符）通过
#
# ★ 为什么这个比 EV_MOBILE 更好：
#   EV_MOBILE 需要【按住 EV 再按 WiFi】，两只手。
#   双击 WiFi 是单手一次动作 —— 这才是真正的"一键"。
#
# ★ 零 UI 的理由（单核相机铁律）：
#   mod_gui / X11 全屏窗口在 NX500 上会吃满单核（已实测，连 echo 都执行不完）。
#   本脚本只做 prefman set（毫秒级、零 eMMC 写）+ 借道 enum 跳变，
#   全程不起任何图形进程，popup_timeout 是现成的轻量 ELF。
#
# 副作用：单击 WiFi 键仍然走相机原生行为（开/关 WiFi），互不干扰。
#=====================================================================

BB=/opt/usr/nx-ks/busybox
D=/opt/usr/nx-ks
LAB=/mnt/mmc/filmlab

# ---- 引擎在不在（不在 install.sh 部署链里，走 FTP 单独投递）----
if [ ! -x "$D/filmlab.sh" ]; then
  $BB $D/popup_timeout " [ FilmLab引擎缺失 ] " 3
  exit 1
fi

# ---- 轮换：cycle 自己会写 cur.idx、读SD 卡配方表、制造 enum 跳变 ----
# ★ 不吞 stderr：失败时引擎会打"配方库为空"/"取配方名失败"，
#   这些字串正好用来判别失败原因，吞了就只剩哑失败。
OUT=$("$D/filmlab.sh" cycle 2>&1)
RC=$?

if [ $RC -ne 0 ] || [ -z "$OUT" ]; then
  # 失败（配方库空/SD 卡没插/引擎异常）——弹窗告知，不留哑失败
  case "$OUT" in
    *"配方库为空"*|*"取配方名失败"*) $BB $D/popup_timeout " [ 配方库为空 ] " 2 ;;
    *"不存在"*|*"No such"*)            $BB $D/popup_timeout " [ 引擎无法执行 ] " 2 ;;
    *)                                $BB $D/popup_timeout " [ 轮换失败 ] " 2 ;;
  esac
  echo "$(date '+%H:%M:%S') cycle失败 rc=$RC: $OUT" >> $LAB/last.log 2>/dev/null
  exit 1
fi

# ---- 反馈：把 "[3/9] Portra 400 (key=..., reload=direct)" 砍成 "[3/9] Portra 400" ----
# ★ cycle 的输出格式是「标签(key=..., reload=...)」—— 标签与 ( 之间有空格，
#   但标签内部本身可能含空格（"Portra 400"），所以【不能按空格切】，
#   必须砍掉 " (key=" 及其后全部内容。用逗号切会把括号留在标签里。
LBL=$($BB echo "$OUT" | $BB sed 's/ (key=.*$//')
[ -z "$LBL" ] && LBL=$OUT

# 标签过长会挤掉（社区经验：≤6 全角字符），截断保护
# ★ 用 $BB wc -c（字节数）而不是 wc -m：busybox 的 wc -m 在部分构建下多字节
#   支持不可靠，且输出可能带前导空格，[$LEN -gt 22] 会语法错。
LEN=$($BB echo "$LBL" | $BB wc -c 2>/dev/null | $BB tr -cd '0-9')
case "$LEN" in ""|*[!0-9]*) LEN=0 ;; esac
# 22 字节 ≈ 7 个全角字，留足余量
if [ "$LEN" -gt 22 ]; then
  LBL=$($BB echo "$LBL" | $BB cut -c1-20)
fi

$BB $D/popup_timeout " $LBL " 2

# ---- 自证：写入是否真落在目标 enum 上（不信 setusr 退出码）----
# cycle 内部 pw_force_reload 已在切完回读并把结果写进 $RELOAD，
# 出现在输出末尾的 reload=direct / via-0x140009 / *-VERIFY-FAIL 里。
case "$OUT" in
  *VERIFY-FAIL*) $BB $D/popup_timeout " [ 写入未生效! ] " 3 ;;
esac

exit 0
