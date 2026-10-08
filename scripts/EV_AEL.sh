#!/bin/bash
#=====================================================================
# EV_AEL.sh —— EV + AEL → 打开 FilmLab 配方菜单（mod_gui 路径）
#=====================================================================
# ★ 2026-10-08（上机轨 U2）换绑说明：
#   本槽位原为社区脚本「长录像 + 黑屏遮挡」（机上已备份为 /opt/usr/nx-ks/EV_AEL.sh.orig；
#   仓库 git 历史中可查原版）。
#   起因：用户实测「双击 FN 触发 mod 菜单」不成立 ⇒ 需要一个确定可用的机身入口。
#
# ★ 触发条件（keyscan 规则 A）：【按住 EV 键，再按 AEL 键】
#   keyscan.c: if (ev_pressed == 1 && code != NXKEY_EV && value == 1)
#                  sprintf(shell_name, "EV_%s", nxkeyname[code]);
#   ⇒ 文件名必须恰好是 EV_AEL.sh（AEL 有 nxkeyname 表项）。
#
# ★ 为什么走 mod_gui 而不是自绘 UI（2026-10-08 实测结论）：
#   自绘全屏 EFL 窗口在单核 NX500 上会把整机拖死 —— 窗口 720x480 时相机卡死，
#   连 21/23 端口都不通，只能物理重启。而 mod_gui 已证「可见 + 不卡」（loadavg ~1.1）。
#   代价：mod_gui 固有「点击即退」，拿不到「滚动不关窗」的对比体验。
#
# ★ 配方链路：EV+AEL → 配方菜单 → 点配方 = 立即生效（2 步，无需碰 Fn 菜单）
#   配方库 = /mnt/mmc/filmlab/recipes.json（SD 卡，可直接编辑）
#   改过配方后重开菜单会自动重建菜单（见下方 -ot 守卫；busybox test 实测支持 -ot）
#=====================================================================
BB=/opt/usr/nx-ks/busybox
D=/opt/usr/nx-ks

# ---- ★ 机型闸门：FilmLab 为 NX500 专属（prefman PW 偏移只在 NX500 1.12 实证）----
#   NX1 上退回社区原版「长录像+黑屏遮挡」脚本（EV_AEL.community.sh），零行为变化。
#   绝不把未经实机的 prefman 偏移写到 NX1 上。
if ! /bin/grep -q '^NX500$' /etc/version.info; then
    [ -x /opt/usr/nx-ks/EV_AEL.community.sh ] && exec /opt/usr/nx-ks/EV_AEL.community.sh "$@"
    exit 0
fi

# ---- 同槽重复触发 ⇒ 关掉（做成开关，免得开了关不掉）----
if $BB pidof mod_gui > /dev/null 2>&1; then
    $BB killall -q mod_gui
    exit 0
fi

# ---- 切 LCD（社区惯例：不切的话窗口起在 EVF 上，后屏看不见）----
#   注：实机 getusr MONITOROUT 返回 "Unkonwn Operation"，此判断恒为真 ⇒ 每次都切（无害）
{ st app bb lcd on; st app disp lcd; } > /dev/null 2>&1
sleep 1

# ---- 配方菜单一致性：菜单缺失、或比 recipes.json 旧 ⇒ 现场重建 ----
#   只在用户改过 SD 卡配方时才会真的重建（数秒）；平时零开销。
#   mkgui 由引擎提供（filmlab.sh），失败静默放行（保持旧菜单可用）。
REC=/mnt/mmc/filmlab/recipes.json
MENU=$D/gui_filmlab1b.NX500
if [ -x "$D/filmlab.sh" ] && [ -f "$REC" ]; then
    if [ ! -f "$MENU" ] || [ "$MENU" -ot "$REC" ]; then
        "$D/filmlab.sh" mkgui >/dev/null 2>&1
    fi
fi

# ---- 起配方菜单：gui_filmlab1b = 配方列表页（由 mkgui 从 SD 卡配方库生成）----
#   nice +15：让相机主进程优先（社区约定，别跟拍照抢 CPU）
nice -n +15 $D/mod_gui $D/gui_filmlab1b &
exit 0
