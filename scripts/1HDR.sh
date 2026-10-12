#!/bin/bash
# =====================================================================
# [同构 批次1] 拍照入口统一为三级 fallback：
#   ① App 官方命令 st app nx capture single（同构目标）
#   ② 老 st cap capt single start
#   ③ 按键注入 st key push/click s1+s2（原做法，兜底）
#   任一级成功即返回 ⇒ 行为最坏等于改前，不可能更差。
#   依据：docs/current/SHELL_TO_APP_ISOMORPHISM_2026-10-12.md §4 批次 1
# =====================================================================
nx_shoot() {
    /usr/bin/st app nx capture single >/dev/null 2>&1 && return 0
    /usr/bin/st cap capt single start >/dev/null 2>&1 && return 0
    /usr/bin/st key push s1 && /usr/bin/st key click s2 && /usr/bin/st key release s1
}
/usr/bin/st app mode m
/usr/bin/st app nx capture af-mode manual
/usr/bin/st cap capdtm setusr AFMODE 0x70003
[ $(/bin/grep ^NX500$ /etc/version.info) = "NX500" -a $(/bin/grep ^1.12$ /etc/version.info) = "1.12" ]  && nx500="good"
[ $(/bin/grep   ^NX1$   /etc/version.info) = "NX1" -a $(/bin/grep ^1.41$ /etc/version.info) = "1.41"  ] && nx1="good"
#
[[ $nx1 = "good"  ]] && prefman set 0 0x0310 l 65
[[ $nx500 = "good" ]] &&  prefman set 0 0xa340 l 65
/usr/bin/st app mode m ; sleep 1
nx_shoot
/usr/bin/st app mode m ; sleep 1
#
#
[[ $nx1 = "good"  ]] && prefman set 0 0x0310 l 92
[[ $nx500 = "good" ]] &&  prefman set 0 0xa340 l 92
/usr/bin/st app mode m ; sleep 1
nx_shoot
/usr/bin/st app mode m ; sleep 1
#
#
[[ $nx1 = "good"  ]] && prefman set 0 0x0310 l 119
[[ $nx500 = "good" ]] &&  prefman set 0 0xa340 l 119
/usr/bin/st app mode m ; sleep 1
nx_shoot
/usr/bin/st app mode m ; sleep 1
#
#
[[ $nx1 = "good"  ]] && prefman set 0 0x0310 l 146
[[ $nx500 = "good" ]] &&  prefman set 0 0xa340 l 146
/usr/bin/st app mode m ; sleep 1
nx_shoot
/usr/bin/st app mode m ; sleep 1
#
#
[[ $nx1 = "good"  ]] && prefman set 0 0x0310 l 200
[[ $nx500 = "good" ]] &&  prefman set 0 0xa340 l 200
/usr/bin/st app mode m ; sleep 1
nx_shoot
/usr/bin/st app mode m ; sleep 1
#
st key click s1
