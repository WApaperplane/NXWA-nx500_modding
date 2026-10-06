#!/bin/bash
#=====================================================================
# EV_MOBILE.sh —— FilmLab 直达页（挂在 WiFi/MOBILE 键上，EV+WiFi 触发）
#=====================================================================
# ★★ 2026-10-05 关键突破：mod_gui 可以指定【任意菜单文件】作顶层
#
#   从 mod_gui 二进制里挖出的路径解析逻辑：
#     Usage: %s [path_to_scripts_directory] [debug]
#     "%s/%s%s"  +  "mod_gui.cfg."  +  '/etc/version.info'
#   传入路径时：先试 <path>.<机型>，不可读再试 <path> 本身。
#   loadgui.sh 传的是 gui_ini → 实际读 gui_ini.NX500，机制就是这个。
#
#   ⇒ 所以不必走"主菜单 → FilmLab → 分类 → 配方"三层：
#     直接 mod_gui /opt/usr/nx-ks/gui_filmlab1b
#     打开【就是】配方列表，一层直达。
#
# 为什么这个槽位现在空着：
#   社区原版EV_MOBILE.sh = 开 telnetd + FTP。但项目里 telnet 已改成
#   主菜单按钮「IP: x.x.x.x [Telnet开/关]」点击即开关（见 gui_tpl.NX500），
#   telnet_toggle.sh 与 EV_MOBILE 互不干扰 ⇒ 组合键通道已弃用。
#   ★ 本文件是覆盖，不是新增；备份在 backup_original/EV_MOBILE.sh。
#
# 触发方式（keyscan.c 规则B：同键 1 秒内连按两次 → <键>_<键>）：
#   单击 WiFi 键 = 相机自己的原生行为（开/关 WiFi），keyscan 不介入
#   ⇒ FilmLab 挂在【双击 WiFi】上，对应槽位 MOBILE_MOBILE.sh
#
# 机型差异：WiFi 键 code 215 = nxkeyname "MOBILE"，NX500/NX1 通吃。
#=====================================================================

BB=/opt/usr/nx-ks/busybox
D=/opt/usr/nx-ks
LAB=/mnt/mmc/filmlab
MENU=$D/gui_filmlab1b

# ---- 机型判定（照抄社区脚本的双条件判据，别凭记忆简化）----
MODEL=$($BB grep -m1 . /etc/version.info 2>/dev/null)
case "$MODEL" in
  NX500) SUFFIX=NX500 ;;
  NX1)   SUFFIX=NX1   ;;
  *)     SUFFIX=NX500 ;;   # 兜底：NX500 是主力机型
esac

# ---- 前置：引擎在不在 ----
# ★ 引擎不在 install.sh 部署链里（母本 scripts/ 下没有 filmlab.sh），
#   它走 FTP 单独投递：test_server/filmsim/filmlab-apply.sh → $D/filmlab.sh
if [ ! -x "$D/filmlab.sh" ]; then
  $BB $D/popup_timeout " [ FilmLab引擎缺失 ] " 3
  exit 1
fi

# ---- 前置：SD 卡配方库在不在 ----
if [ ! -f "$LAB/recipes.json" ]; then
  $BB $D/popup_timeout " [ 未插卡或无配方库 ] " 3
  exit 1
fi

# ---- 菜单必须先刷新，否则新加的配方看不到 ----
# mkgui 失败（配方库格式异常）不该挡住进菜单 → 静默放行，沿用旧菜单
"$D/filmlab.sh" mkgui >/dev/null 2>&1

# ---- 菜单文件存在性（模型感知）----
if [ -r "$MENU.$SUFFIX" ]; then
  TARGET=$MENU.$SUFFIX
elif [ -r "$MENU" ]; then
  TARGET=$MENU
else
  $BB $D/popup_timeout " [ 菜单未生成 ] " 3
  exit 1
fi

# ---- 切到 LCD 视角（社区惯例：菜单要在 LCD 上才显示得出来）----
# ★ 不用 & 后台：这里必须等切完，否则 mod_gui 会在 EVF 屏上起，屏幕黑着。
# ★ 但 st app disp lcd 本身很快（<1s），单核上可接受。
if ! $BB st cap capdtm getusr MONITOROUT 2>/dev/null | $BB grep -q LCD; then
  $BB st app disp lcd 2>/dev/null
  $BB sleep 1
fi

# ---- 关掉可能残留的 UI（mod_gui 单实例）----
killall -q mod_gui 2>/dev/null
killall -q onscreen_ov 2>/dev/null
killall -q onscreen_235 2>/dev/null
killall -q popup_entry 2>/dev/null
killall -q popup_ok 2>/dev/null

# ---- 起菜单：★ 直接指定 FilmLab 配方页为顶层，跳过主菜单三层 ----
# nice -n +15：让出优先级，拍照时相机主进程优先（社区约定）
nice -n +15 $D/mod_gui "$TARGET" >/dev/null 2>&1 &

exit 0
