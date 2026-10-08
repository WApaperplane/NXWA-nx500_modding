#!/bin/sh
# ============================================================
# capdtm-httpd - 启动 busybox httpd(8080)提供拍摄参数 API
# 用法: capdtm-httpd.sh start|stop
# 建议加入 NX-KS 开机脚本 auto/a_init.sh 末尾:
#   /opt/usr/nx-ks/nx-rc/capdtm/capdtm-httpd.sh start &
# ============================================================

BASE=/opt/usr/nx-ks/nx-rc/capdtm
PORT=8080
# busybox 不在系统 PATH 里(实测 command not found),必须用绝对路径
BUSYBOX=/opt/usr/nx-ks/busybox

case "$1" in
    stop)
        [ -x "$BUSYBOX" ] && "$BUSYBOX" killall busybox 2>/dev/null
        # 只结束 httpd 实例(按端口过滤)
        for pid in $(ps -w | grep 'busybox httpd' | grep -v grep | awk '{print $1}'); do
            kill "$pid" 2>/dev/null
        done
        ;;
    *)
        # 已监听则跳过
        if [ -f /tmp/capdtm_httpd.pid ]; then
            pid=$(cat /tmp/capdtm_httpd.pid 2>/dev/null)
            if kill -0 "$pid" 2>/dev/null; then
                exit 0
            fi
        fi
        "$BUSYBOX" httpd -p "$PORT" -h "$BASE/www" &
        echo $! > /tmp/capdtm_httpd.pid
        ;;
esac

exit 0
