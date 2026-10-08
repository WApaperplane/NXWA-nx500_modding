#!/bin/bash
renice -n -10 -p $$
tii=($(systemctl show-environment))
for i in "${tii[@]}"; do if [[ $i == "fps="* ]]; then cfps=${i:4}; fi; done
fps=$(/opt/usr/nx-ks/popup_entry "对焦拉动速度 [ 1 ~ 255 ]:" "设置速度" 取消 $cfps number )
[[ $fps =~ ^[0-9]+$ ]] || fps=4
systemctl set-environment fps=$fps
sync;sync;sync
/opt/usr/nx-ks/br_up.sh