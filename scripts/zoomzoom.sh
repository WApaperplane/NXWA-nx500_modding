#!/bin/bash
# [同构 批次1] 拍照三级 fallback（App 命令 → 老 st cap → 按键注入）
#   依据：docs/current/SHELL_TO_APP_ISOMORPHISM_2026-10-12.md §4 批次 1
nx_shoot() {
    /usr/bin/st app nx capture single >/dev/null 2>&1 && return 0
    /usr/bin/st cap capt single start >/dev/null 2>&1 && return 0
    /usr/bin/st key push s1 && /usr/bin/st key click s2 && /usr/bin/st key release s1
}
z_d=$( /opt/usr/nx-ks/popup_entry "变焦延迟(毫秒):" "... 并开始" 取消 0 number)
[[ $z_d =~ ^[0-9]+$ ]] || exit
sleep 3
nx_shoot
sleep $(($z_d/1000))
st app lens pzoom wide
