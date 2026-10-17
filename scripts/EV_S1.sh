#!/bin/bash
# ★ 2026-10-17：mod 菜单（nxui）打开时，半按快门 = 关闭菜单；原 AF 微调不执行。
echo "S1 $(date +%H:%M:%S) nxui=$(/opt/usr/nx-ks/busybox ps 2>/dev/null | /bin/grep -c '[n]xui.arm')" >> /mnt/mmc/s1.log 2>/dev/null
if /opt/usr/nx-ks/busybox ps 2>/dev/null | /bin/grep -q '[n]xui.arm'; then
    touch /tmp/nxui-close
    exit 0
fi
sync;sync;sync
echo 3 > /proc/sys/vm/drop_caches
renice -n -10 -p $$
renice -n +10 -p $(pgrep di-camera-app)
af_info=($(st cap iq af pos))
pos_temp=${af_info[2]} 
tii=($(systemctl show-environment))
for i in "${tii[@]}"; do if [[ $i == "pos="* ]]; then pos_mv=$((${i:4} - $pos_temp)); fi; done
for i in "${tii[@]}"; do if [[ $i == "fps="* ]]; then fp_speed=${i:4}; fi; done
[[ $fp_speed =~ ^[0-9]+$ ]] || fp_speed=4
systemctl set-environment pos=$pos_temp
st cap iq af mv 10 $pos_mv $fp_speed
exit
