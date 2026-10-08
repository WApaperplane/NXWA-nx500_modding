#!/bin/bash
# ============================================================
# push.sh - NX-KS2 web 前端 WiFi 一键推送 (PC 端, 免拔 SD 卡)
#
# 用法:
#   push.sh <相机IP>                      # 推送整个 web_root
#   push.sh <相机IP>:<端口>               # 指定端口(默认 8080, 联调用)
#   push.sh <相机IP> js/gallery.js        # 只推指定文件(相对 web_root)
#   push.sh <相机IP> js/a.js css/a.css    # 推多个文件
#
# 前提:
#   1. 相机 web 遥控(nx-rc)已开启, 记下屏幕显示的 IP
#   2. 相机 8080 push 接收端在线(与缩略图共用 busybox httpd)
#      首次使用前需先插一次 SD 卡完成引导同步, 把 push 模块装进相机
#   3. 本机可访问相机 WiFi 网段
#
# 推完后浏览器硬刷新一次(Ctrl+F5)。之后因 index.html 带 ?v= 版本号,
# 业务 js/css 会自动失效缓存, 无需再手动清。
# 在 Windows 上请用 Git Bash 运行本脚本。
# ============================================================
set -u

HOSTARG=${1:-}
if [ -z "$HOSTARG" ]; then
    echo "用法: $0 <相机IP[:端口]> [相对路径...]"
    echo "示例: $0 192.168.0.10            # 推送整个 web_root"
    echo "      $0 192.168.0.10:8080       # 指定端口(联调用)"
    echo "      $0 192.168.0.10 js/gallery.js css/style.css"
    exit 1
fi
shift

# ---- 解析 host[:port] ----
case "$HOSTARG" in
    *:*) HOST=${HOSTARG%:*}; PORT=${HOSTARG##*:} ;;
    *)   HOST=$HOSTARG; PORT=8080 ;;
esac

# ---- 定位 web_root(脚本位于 scripts/nx-rc/push/) ----
PUSH_DIR=$(cd "$(dirname "$0")" && pwd)
WEB_ROOT=$(cd "$PUSH_DIR/.." && pwd)/web_root
if [ ! -d "$WEB_ROOT" ]; then
    echo "错误: 找不到 web_root: $WEB_ROOT"
    exit 1
fi
BASE="http://$HOST:$PORT/cgi-bin/push"

# ---- 探测 push 接收端在线(ping 无副作用) ----
# --noproxy: 本机系统代理会把对相机内网地址的请求转发出去,
# 返回 502 假象, 导致"明明 httpd 活着却探测失败"(2026-09-04)
probe=$(curl -s --noproxy '*' --max-time 5 "$BASE?action=ping" 2>/dev/null)
case "$probe" in
    *'"ok":true'*) ;;
    *) echo "错误: $HOST:$PORT 无响应或未安装 push 接收端。"
       echo "      请确认相机 web 遥控已开、且已通过 SD 卡同步过一次(装入 push 模块)。"
       exit 1 ;;
esac

# ---- 收集待推文件: 无参数 = 整个 web_root ----
if [ $# -gt 0 ]; then
    RELS=("$@")
else
    mapfile -t RELS < <(cd "$WEB_ROOT" && find . -type f | sed 's#^\./##' | sort)
fi

echo "==> 目标: $HOST:$PORT  (共 ${#RELS[@]} 个文件)"
FAIL=0
# Windows 原生 curl 读不了 /d/... POSIX 绝对路径, 故 cd 进 web_root 用相对路径推
for rel in "${RELS[@]}"; do
    if [ ! -f "$WEB_ROOT/$rel" ]; then
        echo "跳过(本地不存在): $rel"
        continue
    fi
    out=$(cd "$WEB_ROOT" && curl -s --noproxy '*' --max-time 30 --data-binary "@$rel" \
          -H "Content-Type: application/octet-stream" \
          "$BASE?path=nx-rc/web_root/$rel" 2>/dev/null)
    case "$out" in
        *'"ok":true'*) echo "OK   $rel" ;;
        *) echo "ERR  $rel -> ${out:-curl 失败}"; FAIL=1 ;;
    esac
done

echo "==> 重启相机 web daemon..."
out=$(curl -s --noproxy '*' --max-time 15 "$BASE?action=apply" 2>/dev/null)
case "$out" in
    *'"ok":true'*) echo "==> 完成。浏览器请硬刷新一次(Ctrl+F5)。" ;;
    *) echo "!!  apply 未确认: $out (可稍后手动刷新页面观察)"; FAIL=1 ;;
esac

exit $FAIL
