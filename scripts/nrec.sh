#!/bin/bash
# [同构 批次1] 录像控制：优先 App 官方命令 record start/stop，失败退回 rec 键注入
#   依据：docs/current/SHELL_TO_APP_ISOMORPHISM_2026-10-12.md §4 批次 1
#   注：原 st key click rec 是 toggle（再按一次=停）；显式 start/stop 更不易错。
nx_rec_start() {
    /usr/bin/st app nx record start >/dev/null 2>&1 && return 0
    /usr/bin/st key click rec
}
nx_rec_stop() {
    /usr/bin/st app nx record stop >/dev/null 2>&1 && return 0
    /usr/bin/st key click rec
}
yell() { echo "$0: $*" >&2; }
die() { yell "$*"; exit 111; }
ticking() {
	end=$((SECONDS+$1))
	while [ $SECONDS -lt $end ]; do
		if [[ "$(cat /sdcard/presets/asleep)" > ""  ]]; then rm /sdcard/presets/asleep; 
			hevc=($(st pmu show | grep hevc)); if [[ "${hevc[1]}" == "ON" ]]; then nx_rec_stop; sleep 1; fi
 			st app bb lcd on
			die; fi
	    sleep 0.5
	done
}
[ -d "/sdcard/presets" ] || mkdir /sdcard/presets
killall -q mod_gui
sleep 1 
nx_rec_start
sleep 2
st app bb lcd off
cat /dev/event0 > /sdcard/presets/asleep &
cat /dev/event1 >> /sdcard/presets/asleep &
ticking 99999
exit
