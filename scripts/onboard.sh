#!/bin/bash
# ============================================================
# NX-KS2 onboard —— 装机后无条件拉起 telnet + ftpd
#
# 存在的原因（2026-10-06）
# ----------------------
# 原来telnet 只能从 mod 菜单里的 "IP: x.x.x.x [Telnet关]" 那一行开启，
# 而那行来自 gui_ini.NX500，而 gui_ini.NX500 由 gen_menu.sh 在【菜单启动时】现场生成。
#
# ⇒ 死锁：菜单没生成 → 没有 telnet 开关 → 连不上 → 无法查问题 → 菜单更起不来
#
# 本脚本把 telnet 从"mod 功能"降级成"装机副产品"：
# 只要 install.sh 跑完，telnet 一定开着，不依赖 mod 任何其它部分是否正常。
# ★ 这是本项目唯一的远程排查通路，绝不能因为 mod 其它部件出错而失效。
#
# install.sh 在【全量安装】和【增量同步】两个分支结束后都会调用本脚本。
#
# ★ 实现严格对齐 scripts/telnet_toggle.sh（已验证可用的既有实现）：
#   - telnetd 用 mod 自带的 $DIR/telnetd（2MB ARM 二进制），不是 busybox 的
#   - ftpd 用 busybox tcpsvd -u root -vE 0.0.0.0 21转发
#   - WiFi 接口是 mlan0（不是 lan0！install.sh 头部注释有误）
#   - 全部 nice -n +10 降优先级，避免单核相机被拖死
#
# 行为：幂等，可重复执行（先 killall 再起，不堆进程）
# 日志：/opt/usr/nx-ks/onboard.log —— 装完连不上时可从 SD 卡读到
# ============================================================

DIR=/opt/usr/nx-ks
LOG="$DIR/onboard.log"
BB="$DIR/busybox"
SDCARD=/opt/storage/sdcard

{
	echo "=== onboard @ $(date 2>/dev/null) ==="
	echo "telnetd : $([ -x "$DIR/telnetd" ] && echo OK || echo 'MISSING(not exec?)')"
	echo "busybox : $([ -x "$BB" ] && echo OK || echo 'MISSING(not exec?)')"
	echo "sdcard  : $([ -d "$SDCARD" ] && echo OK || echo MISSING)"
} > "$LOG" 2>&1

# ---- 前置：缺二进制就放弃（写日志，不静默）----
if [ ! -x "$DIR/telnetd" ] || [ ! -x "$BB" ]; then
	echo "!! 缺可执行文件 -> onboard 放弃" >> "$LOG"
	echo "!! 提示: SD 卡 FAT 挂载会丢可执行位, install.sh 的 chmod 兜底应已补位" >> "$LOG"
	chmod +x "$DIR/telnetd" "$BB" 2>>"$LOG"
	if [ ! -x "$DIR/telnetd" ] || [ ! -x "$BB" ]; then
		echo "!! chmod 后仍不可执行 -> 确认 scripts/ 母本权限位" >> "$LOG"
		exit 1
	fi
fi

# ---- 杀旧的（幂等）----
killall -q telnetd 2>/dev/null
killall -q tcpsvd 2>/dev/null
killall -q ftpd   2>/dev/null
sleep 1

# ---- telnetd (23) ----
nice -n +10 "$DIR/telnetd" >>"$LOG" 2>&1 &

# ---- ftpd (21) —— busybox tcpsvd 转发到 ftpd，根目录 = SD 卡 ----
cd "$SDCARD" 2>/dev/null || cd /
nice -n +10 "$BB" tcpsvd -u root -vE 0.0.0.0 21 \
	"$BB" ftpd -w -v "$SDCARD" >>"$LOG" 2>&1 &

sleep 3

# ---- 结果自检并写日志（★ 用 ps 而非 killall -0，busybox 语义不同）----
{
	echo "--- 结果 ---"
	ps -w 2>/dev/null | grep -E 'telnetd|tcpsvd|ftpd' | grep -v grep
	if ps -w 2>/dev/null | grep -q '[t]elnetd'; then
		echo "telnetd : RUNNING"
	else
		echo "telnetd : DOWN"
	fi
	if ps -w 2>/dev/null | grep -qE '[t]cpsvd|[f]tpd'; then
		echo "ftp(21) : RUNNING"
	else
		echo "ftp(21) : DOWN"
	fi
	# ★ WiFi 接口实测：mlan0 与 lan0 都查（不同固件版本名不同）
	echo "ip(mlan0): $(ip addr ls 2>/dev/null | grep inet | grep mlan0 | cut -d/ -f1 | tr -d ' ')"
	echo "ip(lan0) : $(ip addr ls 2>/dev/null | grep inet | grep  lan0 | cut -d/ -f1 | tr -d ' ')"
} >>"$LOG" 2>&1

exit 0