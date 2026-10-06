#!/bin/bash
# ============================================================
# NX-KS2 卸载（相机菜单调用版）
#
# ★ 2026-10-06 修三个致命 bug —— 原版在"mod 没初始化"时永远跑不起来，
#   导致"要卸载 mod 才能重装，要mod 才能卸载 mod"的死锁：
#
#   bug1 开头 popup_ok 弹确认框是GUI 程序，需要 mod_gui 在跑。
#        mod 没起来 ⇒ 弹不出⇒ 返回非 255 ⇒ `[ $? -eq 255 ]` 为假 ⇒ 直接 exit
#        ★ 改成：能弹就弹确认；弹不出来（无 GUI）就【继续卸载】，不阻塞。
#          安全兜底：只有显式答"取消"才退出。
#
#   bug2 `mv ... /sdcard/popup_timeout` —— 相机上 SD 卡挂载点是
#        /opt/storage/sdcard，/sdcard 不存在。
#        ★ 改成 /opt/storage/sdcard，并加存在性判断。
#
#   bug3 版本校验 `[ $(grep ^NX500$ /etc/version.info) = "NX500" ]`
#        /etc/version.info 是 CRLF 行尾（od 实测 `31 2e 31 32 0d 0a`），
#        busybox grep 输出的行会带 \r ⇒ `[ "NX500\r" = "NX500" ]` 永远为假
#        ⇒ 整个 if 块永远不执行，直接 reboot。
#        ★ 改成不依赖行尾的比较：直接读文件并 tr -d '\r'，或用子串匹配。
#        ★ 顺带：卸载【不该被版本拦住】—— 只要 bluetoothd.orig 存在就该能卸。
#
#   另外补：stop 掉占用 /opt/usr/nx-ks 的进程（原来直接 rm -r 会留僵尸）
#   另外补：rm -rf 代替 rm -r（目录可能已被部分删除，rm -r 会报错中断）
#   另外补：把结果写/ 到 SD 卡 —— 万一弹不出窗也能事后查
#
# ★ 若 mod 完全没初始化、连本脚本都进不去，用 SD 卡直触版：
#   SD 卡根放 info.tg + nx_cs.adj(内容改指向 uninstall_direct.sh) + uninstall_direct.sh
#   见 scripts/uninstall_direct.sh（完全不依赖 GUI / 版本校验 / popup）
# ============================================================

SDCARD=/opt/storage/sdcard
DIR=/opt/usr/nx-ks
LOG="$SDCARD/uninstall_menu.log"

{
	echo "=== 菜单卸载 @ $(date 2>/dev/null) ==="
	echo "bluetoothd.orig : $([ -f /usr/sbin/bluetoothd.orig ] && echo EXISTS || echo ABSENT)"
	echo "$DIR : $([ -d "$DIR" ] && echo EXISTS || echo ABSENT)"
} > "$LOG" 2>&1

# ---- 1. 确认框：能弹就弹，弹不出来就继续（★ 这是死锁的关键修复点）----
ANSWER=0
if [ -x "$DIR/popup_ok" ]; then
	"$DIR/popup_ok" "确定要移除所有模块？" 卸载 取消
	rc=$?
	# 255 = 取消（原版逻辑）。其它值一律当作确认 => 不阻塞卸载
	[ "$rc" -eq 255 ] && ANSWER=1
fi
if [ "$ANSWER" = "1" ]; then
	echo "用户取消" >> "$LOG"
	# 取消时若 mod 还活着，可以给个反馈
	[ -x "$DIR/popup_timeout" ] && "$DIR/popup_timeout" " [ 已取消 ] " 2
	exit 0
fi
echo "继续卸载" >> "$LOG"

# ---- 2. 前置检查：只认 bluetoothd.orig（★ 不再做版本校验）----
if [ ! -f /usr/sbin/bluetoothd.orig ]; then
	echo "未检测到 BT 模块（bluetoothd.orig 不存在）" >> "$LOG"
	[ -x "$DIR/popup_timeout" ] && "$DIR/popup_timeout" " [ 未检测到BT模块 ] " 3
	sleep 2
	reboot
	exit 0
fi

# ---- 3. 停进程（原来直接 rm -r 会留占用僵尸）----
for p in keyscan mod_gui mod_lapse nx-rc.sh onscreen_rc onscreen_ov \
         onscreen_235 nx-remote-controller-daemon nx-input-injector \
         xev-nx telnetd tcpsvd ftpd focus_stack focus_buttons \
         popup_entry thumb-cgi push-cgi; do
	killall -q "$p" 2>/dev/null
done
sleep 2

# ---- 4. 把 popup_timeout 备份到 SD 卡（★ bug2：/sdcard -> /opt/storage/sdcard）----
POPUP_SD=""
if [ -f "$DIR/popup_timeout" ]; then
	if [ -d "$SDCARD" ]; then
		cp "$DIR/popup_timeout" "$SDCARD/popup_timeout" 2>/dev/null \
			&& POPUP_SD="$SDCARD/popup_timeout"
	fi
fi
echo "popup 备份 : ${POPUP_SD:-未备份}" >> "$LOG"

# ---- 5. 删 mod 主体 + 清 swapmod（★ rm -rf 防目录已部分缺失时报错中断）----
mount -o remount,rw / 2>/dev/null
swapoff /opt/usr/home/swapmod 2>/dev/null
rm -f  /opt/usr/home/swapmod
rm -rf "$DIR" 2>/dev/null
rm -f  /root/focus_stack.cfg
rm -f  /root/mod_lapse.cfg
rm -rf /opt/home/scripts 2>/dev/null
sync; sync; sync

# ---- 6. 恢复原始 bluetoothd（mod 的核心就是替换了它）----
cd /usr/sbin || exit 1
rm -f /usr/sbin/bluetoothd
mv /usr/sbin/bluetoothd.orig /usr/sbin/bluetoothd
chmod +x /usr/sbin/bluetoothd 2>/dev/null
sync; sync; sync
mount -o remount,ro / 2>/dev/null

# ---- 7. 结果反馈 + 自检落盘 ----
{
	echo "--- 卸载后验证 ---"
	echo "bluetoothd.orig : $([ -f /usr/sbin/bluetoothd.orig ] && echo '★ 仍存在(失败)' || echo 已清除)"
	echo "$DIR : $([ -d "$DIR" ] && echo '★ 仍存在(失败)' || echo 已清除)"
	echo "bluetoothd      : $([ -x /usr/sbin/bluetoothd ] && echo 已就位 || echo '★异常')"
	echo "=== 卸载完成 ==="
} >> "$LOG" 2>&1

[ -n "$POPUP_SD" ] && "$POPUP_SD" " [  卸载完成  ] " 4 &
sleep 4
[ -n "$POPUP_SD" ] && rm -f "$POPUP_SD"
sync; sync; sync

reboot
exit 0