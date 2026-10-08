#!/bin/sh
# ============================================================
# capdtm-cgi - NX 相机拍摄参数读写 API(busybox httpd CGI)
# 通过 st cap capdtm getusr/setusr 读取/写入拍摄参数。
#
# 部署(相机端,需 NX-KS root):
#   1. 拷贝本目录到  /opt/usr/nx-ks/nx-rc/capdtm/
#   2. 运行  capdtm-httpd.sh 启动 8080 端口 httpd(CGI 指向本脚本)
#   3. 校准参数:编辑 capdtm.conf,按实际固件版本核对取值
#
# 访问:
#   GET /cgi-bin/capdtm-api?action=list
#   GET /cgi-bin/capdtm-api?action=set&name=USERDATA_ISO&value=ISO_400
# ============================================================

ST=/usr/bin/st
BASE=/opt/usr/nx-ks/nx-rc/capdtm
CONF=$BASE/capdtm.conf

echo "Content-Type: application/json; charset=utf-8"
echo "Access-Control-Allow-Origin: *"
echo "Cache-Control: no-store"
echo ""

json_str() {
    # 极简 JSON 字符串转义
    printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

# ---- 解析 QUERY_STRING:name=value&... ----
QS=$QUERY_STRING
[ -z "$QS" ] && QS="action=list"
ACTION=""
PNAME=""
PVAL=""
IFS='&'
for pair in $QS; do
    key=${pair%%=*}
    val=${pair#*=}
    case "$key" in
        action) ACTION=$val ;;
        name)   PNAME=$val ;;
        value)  PVAL=$val ;;
    esac
done
unset IFS

# ---- 查找参数配置行:name|label|name=hex,name=hex ----
find_conf() {
    while IFS='|' read -r cname clabel cvals; do
        case "$cname" in
            ""|\#*) continue ;;
        esac
        if [ "$cname" = "$1" ]; then
            echo "$clabel|$cvals"
            return 0
        fi
    done < "$CONF"
    return 1
}

# ---- 从取值列表 "name=hex,name=hex" 中查 value 对应的 hex ----
find_hex() {
    # $1 = 取值列表, $2 = 目标名称
    IFS=','
    for kv in $1; do
        n=${kv%%=*}
        h=${kv#*=}
        if [ "$n" = "$2" ]; then
            unset IFS
            echo "$h"
            return 0
        fi
    done
    unset IFS
    return 1
}

case "$ACTION" in
    list)
        printf '{"ok":true,"params":{'
        first=1
        while IFS='|' read -r cname clabel cvals; do
            case "$cname" in
                ""|\#*) continue ;;
            esac
            cur=$($ST cap capdtm getusr "$cname" 2>/dev/null | head -1)
            val=$(printf '%s' "$cur" | awk -F'|' '{gsub(/^ +| +$/,"",$3); print $3}')
            [ -z "$val" ] && val=""
            if [ $first -eq 0 ]; then printf ','; fi
            first=0
            printf '"%s":"%s"' "$cname" "$val"
        done < "$CONF"
        printf '}}'
        echo
        ;;
    set)
        if [ -z "$PNAME" ] || [ -z "$PVAL" ]; then
            echo '{"ok":false,"error":"name and value required"}'
            exit 0
        fi
        conf=$(find_conf "$PNAME")
        if [ -z "$conf" ]; then
            echo "{\"ok\":false,\"error\":\"unknown param: $PNAME\"}"
            exit 0
        fi
        clabel=${conf%%|*}
        cvals=${conf#*|}
        hex=$(find_hex "$cvals" "$PVAL")
        if [ -n "$hex" ]; then
            $ST cap capdtm setusr "$PNAME" "$hex" >/dev/null 2>&1
        else
            # 未配置 hex 时直接透传名称(部分固件版本支持)
            $ST cap capdtm setusr "$PNAME" "$PVAL" >/dev/null 2>&1
        fi
        echo "{\"ok\":true,\"name\":\"$PNAME\",\"value\":\"$PVAL\"}"
        ;;
    *)
        echo '{"ok":false,"error":"unknown action"}'
        ;;
esac

exit 0
