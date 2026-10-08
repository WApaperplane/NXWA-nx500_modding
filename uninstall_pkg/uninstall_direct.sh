#!/bin/bash
# ============================================================
# NX-KS2 直触卸载 —— 不依赖 mod 任何组件
#
# 为什么需要它（2026-10-06）
# ----------------------
# 现场状态：bluetoothd.orig 还在（增量分支已跑过），但 mod 没初始化。
# 而旧 uninstall.sh 有三个致命 bug，在这种状态下【永远跑不起来】：
#   bug1 开头 popup_ok 弹确认框 —— 那是 GUI 程序，需要 mod_gui 在跑；
#        mod 没起来 ⇒ 弹不出 ⇒ 返回非 255 ⇒ `[ $? -eq 255 ]` 为假 ⇒ 直接 exit
#   bug2 mv 到 /sdcard/popup_timeout —— 相机上 SD 卡挂载点是 /opt/storage/sdcard，
#        /sdcard 不存在（仓库里 102 处引用都用 /sdcard，这是个历史遗留错路径）
#   bug3 版本校验 grep 输出含 CRLF 的 \r ⇒ `[ "NX500\r" = "NX500" ]` 永远为假
#
# 但卸载真正要做的只有 4 件事，【完全不需要弹窗、不需要版本校验】：
#   1. 恢复 bluetoothd（把 .orig 移回去）
#   2. 删 /opt/usr/nx-ks
#   3. 清 swapmod / focus_stack.cfg
#   4. 重启
#
# 所以绕过 uninstall.sh，直接从 SD 卡触发。插卡 = 卸载，无需任何按键。
#
# 幂等：可重复执行。若 bluetoothd.orig 不存在（本来就没装），只做清理并退出 0。
#
# ★ 顺序很重要：必须先"停进程 -> 恢复 bluetoothd -> 删目录 -> 重启"
# ============================================================

LOG=/mnt/mmc/uninstall.log
SD=/mnt/mmc

{
	echo "=== 直触卸载 @ $(date 2>/dev/null) ==="
	echo "--- 卸载前状态 ---"
	ls -la /usr/sbin/bluetoothd.orig 2>&1 | head -1
	ls -d /opt/usr/nx-ks 2>&1 | head -1
	ls /opt/usr/home/swapmod 2>&1 | head -1
} > "$LOG" 2>&1

# ---- 0. 可执行位兜底（SD 卡 FAT 挂载会丢）----
chmod +x "$SD/scripts/busybox" 2>/dev/null
BB="$SD/scripts/busybox"

# ---- 1. 停掉所有 mod 进程（先杀，否则删目录时进程还占着）----
for p in keyscan mod_gui mod_lapse nx-rc.sh onscreen_rc onscreen_ov \
         onscreen_235 nx-remote-controller-daemon nx-input-injector \
         xev-nx telnetd tcpsvd ftpd focus_stack focus_buttons \
         popup_entry popup_ok popup_timeout thumb-cgi push-cgi; do
	killall -q "$p" 2>/dev/null
done
# keyscan 可能带参数，killall -q 已够；再兜底一次 pkill
[ -n "$BB" ] && "$BB" pkill -f '/opt/usr/nx-ks' 2>/dev/null
sleep 2

# ---- 2. 恢复原始 bluetoothd（★ mod 的核心是替换了它）----
{
	if [ -f /usr/sbin/bluetoothd.orig ]; then
		mount -o remount,rw / 2>/dev/null
		cd /usr/sbin || exit 1
		rm -f /usr/sbin/bluetoothd
		mv /usr/sbin/bluetoothd.orig /usr/sbin/bluetoothd
		chmod +x /usr/sbin/bluetoothd 2>/dev/null
		sync; sync; sync
		mount -o remount,ro / 2>/dev/null
		echo "bluetoothd : 已从 .orig 恢复"
	else
		echo "bluetoothd : .orig 不存在，跳过（本来就没装或已卸载）"
	fi
} >> "$LOG" 2>&1

# ---- 3. 删除 mod 主体 ----
{
	mount -o remount,rw / 2>/dev/null
	swapoff /opt/usr/home/swapmod 2>/dev/null
	rm -f  /opt/usr/home/swapmod
	rm -rf /opt/usr/nx-ks
	rm -f  /root/focus_stack.cfg
	rm -f  /root/mod_lapse.cfg
	rm -rf /opt/home/scripts
	sync; sync; sync
	mount -o remount,ro / 2>/dev/null
	echo "mod 主体   : 已删除"
} >> "$LOG" 2>&1

# ---- 4. 自检 ----
{
	echo "--- 卸载后验证 ---"
	if [ -f /usr/sbin/bluetoothd.orig ]; then
		echo "bluetoothd.orig : ★ 仍存在（卸载失败）"
	else
		echo "bluetoothd.orig : 已清除"
	fi
	if [ -d /opt/usr/nx-ks ]; then
		echo "/opt/usr/nx-ks : ★ 仍存在（卸载失败）"
	else
		echo "/opt/usr/nx-ks : 已清除"
	fi
	[ -x /usr/sbin/bluetoothd ] && echo "bluetoothd      : 原始版本已就位" \
		|| echo "bluetoothd      : ★ 缺失或不可执行"
	echo "=== 卸载完成，即将重启 ==="
} >> "$LOG" 2>&1

# ---- 5. 清SD 卡触发文件（防下次开机重复执行）----
rm -f "$SD/info.tg" "$SD/nx_cs.adj" "$SD/install.sh" "$SD/uninstall.sh" 2>/dev/null
sync; sync; sync

sleep 3
reboot
exit 0