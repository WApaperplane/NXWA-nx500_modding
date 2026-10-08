#!/bin/bash
# ============================================================
# update_nxrc.sh - NX-KS2 nx-rc 模块增量更新(安全,不卸载)
#
# 为什么需要它:
#   install.sh 是"二象性"脚本 —— bluetoothd.orig 不存在=安装;
#   已存在(装过一次后)= 走清理卸载分支(rm -r /opt/usr/nx-ks + reboot)!
#   因此日常更新绝不能重跑 install.sh,否则等于卸载。
#
# 本脚本只做增量覆盖 + 重启服务,不触碰 bluetoothd,不删除已装文件。
#
# 用法(在相机上执行,SD 卡 scripts 已更新为本仓库最新版):
#   /mnt/mmc/scripts/update_nxrc.sh
#
# 更新后浏览器端:首次需硬刷新一次(Ctrl+F5 / 清缓存)。
#   index.html 已带 ?v= 版本号,此后自动拉新,无需再手动清。
# ============================================================

SRC=/mnt/mmc/scripts/nx-rc          # SD 卡上的新版(本仓库母本)
DST=/opt/usr/nx-ks/nx-rc            # 相机运行目录
NX_KS=/opt/usr/nx-ks

[ -d "$SRC" ] || { echo "错误: 未找到 $SRC(SD 卡 scripts 未更新?)"; exit 1; }
[ -d "$DST" ] || { echo "错误: 未找到 $DST(未安装过? 首次安装请用 install.sh)"; exit 1; }

echo "==> 停止 web daemon(旧进程占用的旧 JS 不释放)"
killall -q nx-remote-controller-daemon 2>/dev/null
killall -q onscreen_rc 2>/dev/null
sleep 1

echo "==> 覆盖前端(web_root)与相册缩略图模块"
cp -f "$SRC/web_root/index.html"     "$DST/web_root/index.html"
cp -f "$SRC/web_root/css/"*.css      "$DST/web_root/css/"
cp -f "$SRC/web_root/js/"*.js        "$DST/web_root/js/"
mkdir -p "$DST/thumb"
cp -f "$SRC/thumb/thumb-cgi"         "$DST/thumb/"
cp -f "$SRC/thumb/"*.sh              "$DST/thumb/"
cp -f "$SRC/thumb/README.md"         "$DST/thumb/" 2>/dev/null
chmod +x "$DST/thumb/thumb-cgi" "$DST/thumb/"*.sh

echo "==> 覆盖 WiFi push 同步模块"
mkdir -p "$DST/push"
cp -f "$SRC/push/push-cgi" "$SRC/push/push-install.sh" "$SRC/push/push.sh" "$SRC/push/README.md" "$DST/push/" 2>/dev/null
chmod +x "$DST/push/push-cgi" "$DST/push/"*.sh 2>/dev/null

echo "==> 重装缩略图 CGI 与 push 接收端到 capdtm httpd(8080)"
[ -x "$DST/push/push-install.sh" ]   && "$DST/push/push-install.sh"
[ -x "$DST/thumb/thumb-install.sh" ] && "$DST/thumb/thumb-install.sh" start

sync; sync; sync

echo "==> 重启 web daemon(nx-rc.sh 自带 killall+启动+IP 显示)"
[ -x "$NX_KS/nx-rc.sh" ] && "$NX_KS/nx-rc.sh" &

echo ""
echo "完成。浏览器访问相机前请硬刷新一次(Ctrl+F5),之后更新无需再清缓存。"
