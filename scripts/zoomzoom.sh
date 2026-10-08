#!/bin/bash
z_d=$( /opt/usr/nx-ks/popup_entry "变焦延迟(毫秒):" "... 并开始" 取消 0 number)
[[ $z_d =~ ^[0-9]+$ ]] || exit
sleep 3
st key push s1 && st key click s2 && st key release s1
sleep $(($z_d/1000))
st app lens pzoom wide
