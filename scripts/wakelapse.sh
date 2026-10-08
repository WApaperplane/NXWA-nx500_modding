#!/bin/bash
hevc=($(st pmu show | grep hevc)); 
if [[ "${hevc[1]}" == "ON" ]]; then 
	/opt/usr/nx-ks/popup_timeout  "视频模式!?" 3
	/opt/usr/nx-ks/popup_timeout  "确定要冒险吗?" 2
	/opt/usr/nx-ks/popup_timeout  "倒计时: 3, 2,... 1" 2
	killall mod_gui
	exit
fi
#
tl_d=$(/opt/usr/nx-ks/popup_entry "延时摄影时长:" "设置分钟数" 取消 30 number )
[[ $tl_d =~ ^[0-9]+$ ]] || exit
tl_d=$(($tl_d*60))
#
tl_g=$(/opt/usr/nx-ks/popup_entry  "拍摄间隔时间:" "设置秒数" 取消 5 number)
[[ $tl_g =~ ^[0-9]+$ ]] || exit
#
sleepytime=$(/opt/usr/nx-ks/popup_entry "延时启动时间:" "设置分钟数并开始" 取消 0 number )
[[ $sleepytime =~ ^[0-9]+$ ]] || exit
#
sed -e "s/\${tl_d}/"$tl_d"/" -e "s/\${tl_g}/"$tl_g"/"   /opt/usr/nx-ks/timelapse.tp >  /opt/usr/nx-ks/auto/tl.sh
chmod +x /opt/usr/nx-ks/auto/tl.sh
#
sleepytime=$(($sleepytime*60))
#
/usr/bin/st app nx capture af-mode manual
/usr/bin/st cap capdtm setusr AFMODE 0x70003
af_info=($(st cap iq af pos))
pos_temp=${af_info[2]} 
echo $pos_temp > /sdcard/presets/hib
sync; sync; sync;
sleep 0.25
#
[[ $sleepytime > "0" ]] && $(  /opt/usr/nx-ks/popup_timeout  "$(($sleepytime/60))分钟后唤醒..." 3 && rtcwake -m mem -s $sleepytime && reboot ) || /opt/usr/nx-ks/auto/tl.sh
