#!/bin/bash
if ! killall -q mod_gui 
  then
	# 动态生成主菜单(IP/Telnet 状态写入标签), 失败不影响菜单启动
	/opt/usr/nx-ks/gen_menu.sh 2>/dev/null
	 nice -n +15 /opt/usr/nx-ks/mod_gui /opt/usr/nx-ks/gui_ini & nice -n +19 /opt/usr/nx-ks/br_menu.sh &
fi 
killall -q popup_entry & killall -q popup_ok &  killall -q focus_stack & killall -q focus_buttons & killall -q onscreen_ov &  killall -q onscreen_235 &
