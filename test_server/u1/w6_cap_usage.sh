#!/bin/sh
# @gate script=w6_cap_usage.sh opens=rdonly one_shot=1
# =====================================================================
# w6_cap_usage.sh -- W-6 能力探针①：枚举 `st cap` 全部子命令的 usage（只读）
#
# 目的：`st cap help` 只给命令名（23 条），不给参数面。本脚本对每条【无参数】
#       调用，逼出它的 usage 文本 ⇒ 得到"零补丁可得能力"的完整清单。
#
# 安全性：`st cap <cmd>` 无参数一律走字典的 usage 分支（已用 path/lockinfo 验证），
#         不触发动作。全程无写入、无模式切换、无拍照。
# 纪律：一次跑完（单脚本内向 23 条各发一次，输出全部重定向到文件 ⇒ 屏幕零输出）
# =====================================================================
BB=/opt/usr/nx-ks/busybox
OUT=/mnt/mmc/u1/out
$BB mkdir -p "$OUT"

{
    echo "== st cap help（命令名表）=="
    st cap help 2>&1
    echo
    for c in al back capdtm capmm capt cis dp efs fd fenx iq iqr lens live lockinfo log obj path ref seq sh sh-ad str; do
        echo "##### $c"
        st cap "$c" 2>&1
        echo
    done
} > "$OUT/cap_usage.txt" 2>&1

$BB sync
echo "cap_usage lines=$($BB wc -l < "$OUT/cap_usage.txt")"
echo "cap_usage bytes=$($BB wc -c < "$OUT/cap_usage.txt")"
exit 0
