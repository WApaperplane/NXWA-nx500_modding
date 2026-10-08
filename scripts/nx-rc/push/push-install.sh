#!/bin/sh
# ============================================================
# push-install.sh - 安装 push-cgi 到 8080 httpd 的 cgi-bin (幂等)
# 用法: push-install.sh
#
# 拷贝本模块的 push-cgi 到 capdtm httpd 的 CGI 目录, 使其可被
# PC 端 push.sh 调用。可重复执行; 建议加入开机链(nx-rc.sh 启动时
# 会自动调用本脚本, 无需手工执行)。
# ============================================================

SELF=$(cd "$(dirname "$0")" && pwd)
NX_KS=/opt/usr/nx-ks
# 相机端实际布局:capdtm 在 nx-rc 之下(2026-09-04 修正)
CGI_DIR=$NX_KS/nx-rc/capdtm/www/cgi-bin
CGI_TARGET=$CGI_DIR/push

# 目标 httpd 目录不存在(capdtm 模块缺失)时主动创建,不中断
if [ ! -d "$CGI_DIR" ]; then
    echo "提示: $CGI_DIR 不存在,自动创建" >&2
    mkdir -p "$CGI_DIR" 2>/dev/null || { echo "错误: 目录创建失败" >&2; exit 1; }
fi

cp -f "$SELF/push-cgi" "$CGI_TARGET"
chmod +x "$CGI_TARGET"
echo "push-cgi 已安装 -> $CGI_TARGET"

# 确保 8080 httpd 在跑(thumb-install.sh start 也会做同样的事)
if [ -x "$NX_KS/nx-rc/capdtm/capdtm-httpd.sh" ]; then
    "$NX_KS/nx-rc/capdtm/capdtm-httpd.sh" start
fi

exit 0
