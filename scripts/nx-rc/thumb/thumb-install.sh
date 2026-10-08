#!/bin/sh
# ============================================================
# thumb-install - 安装缩略图 CGI 到 capdtm 的 busybox httpd
# 用法: thumb-install.sh [start]
#   start 参数同时确保 8080 httpd 已启动(相机开机脚本里调用)
#
# 建议加入 NX-KS 开机脚本 auto/a_init.sh 末尾:
#   /opt/usr/nx-ks/nx-rc/thumb/thumb-install.sh start &
# ============================================================

SELF=$(cd "$(dirname "$0")" && pwd)
NX_KS=/opt/usr/nx-ks
# 相机端实际布局:install.sh 把 scripts/* 整体拷到 /opt/usr/nx-ks/,
# 本模块位于 /opt/usr/nx-ks/nx-rc/,capdtm 在 nx-rc 之下(2026-09-04 修正,
# 旧路径 /opt/usr/nx-ks/capdtm 从未存在,导致 8080 httpd 拉起失败被静默吞掉)
CGI_DIR=$NX_KS/nx-rc/capdtm/www/cgi-bin
CGI_TARGET=$CGI_DIR/thumb

# cgi-bin 目录缺失时主动创建,避免 cp 静默失败
mkdir -p "$CGI_DIR" 2>/dev/null
cp -f "$SELF/thumb-cgi" "$CGI_TARGET"
chmod +x "$CGI_TARGET"
# dirlist: DCIM 实时目录列表 CGI(80 端口 daemon 目录快照滞后,新照片不出现)
cp -f "$SELF/dirlist-cgi" "$CGI_DIR/dirlist"
chmod +x "$CGI_DIR/dirlist"
# prewarm: 缩略图预热进度查询/控制(前端显示"已缓存 N/M")
cp -f "$SELF/prewarm-cgi" "$CGI_DIR/prewarm"
chmod +x "$CGI_DIR/prewarm"

# 可选:确保 8080 httpd 运行(依赖 capdtm 模块)
if [ "$1" = "start" ] && [ -x "$NX_KS/nx-rc/capdtm/capdtm-httpd.sh" ]; then
    "$NX_KS/nx-rc/capdtm/capdtm-httpd.sh" start
fi

exit 0
