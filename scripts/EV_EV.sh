#!/bin/bash
if [ -x /opt/usr/nx-ks/nxui.sh ] && /opt/usr/nx-ks/nxui.sh available; then
    /opt/usr/nx-ks/nxui.sh menu
    exit $?
fi
[[ $(echo $(st cap capdtm getusr MONITOROUT) | grep LCD) > ""  ]] || { $(st app bb lcd on; st app disp lcd) &&  sleep 1 ; } & killall -q mod_gui 
nice -n -15 /opt/usr/nx-ks/loadgui.sh&
killall -q popup_entry & killall -q popup_ok &  killall -q focus_stack & killall -q focus_buttons & killall -q onscreen_ov &  killall -q onscreen_235 &
