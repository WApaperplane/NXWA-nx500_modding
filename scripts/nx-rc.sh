#!/bin/bash
#
killall -q nx-input-injector
killall -q xev-nx
killall -q nx-remote-controller-daemon
killall -q onscreen_rc
#
export APP_PATH=/opt/usr/nx-ks/nx-rc
# --- nx-rc 附属服务: 8080 httpd(缩略图 CGI / 参数 API / WiFi push 接收) ---
# push-install: 部署 push-cgi 到 capdtm cgi-bin(幂等); thumb-install: 部署
# thumb-cgi 并确保 8080 httpd 启动(带 pid 防重复)。Web 遥控一开即全套可用。
[ -x "$APP_PATH/push/push-install.sh" ]   && "$APP_PATH/push/push-install.sh"   >/dev/null 2>&1
[ -x "$APP_PATH/thumb/thumb-install.sh" ] && "$APP_PATH/thumb/thumb-install.sh" start >/dev/null 2>&1
# --- 缩略图预热:后台把最新照片的缓存铺好 ---
# 单核 ARM 上 convert 现场生成要 0.5-2s/张,几百张时首屏等几分钟且 CPU 打满
# (会饿死 80 端口心跳、前端误报断开)。预热用 nice -n 19 后台跑,
# 浏览时直接命中 .thumbcache -> 0.2s/张。脚本内部已后台化,这里再加 &
# 避免它自带的 sleep 1 拖慢 web 遥控启动。
# 参数: 320px/q75 供网格(最新 300 张), 1024px/q85 供灯箱(最新 60 张)
[ -x "$APP_PATH/thumb/thumb-prewarm.sh" ] && "$APP_PATH/thumb/thumb-prewarm.sh" start 320 75 300 1024 85 60 >/dev/null 2>&1 &
#
nice --adjustment=19 $APP_PATH/nx-remote-controller-daemon &> /dev/null &
#
showmetheway(){
	# IP 只显示一次(4 秒后消失)。常驻查看走主菜单: 每次按 EV 键开菜单时
	# gen_menu.sh 会把当前 IP / Telnet 状态写进菜单标签, 不再每 4 秒弹窗刷屏。
	IP=`ip addr ls|grep inet|grep mlan0|cut -d/ -f 1|grep -o '[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}'`
	[[ -z $IP ]] && IP="Enable WiFi"
	killall onscreen_rc
	 nice -n +10 /opt/usr/nx-ks/onscreen_rc "rc: $IP" &
	sleep 4
	killall onscreen_rc
}
showmetheway&
#tothenextwhiskeybar
