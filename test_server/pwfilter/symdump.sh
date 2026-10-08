#!/bin/sh
# symdump.sh — 只提取库里的符号名字（不搬二进制，相机负载极低）
# 用法: sh symdump.sh <库路径> [关键词过滤]
LIB=$1
FILT=$2

echo "=== $LIB ==="
ls -la "$LIB" 2>&1

# tr 把非标识符字符换成换行, 再 sort -u 取唯一
if [ -n "$FILT" ]; then
    tr -c 'A-Za-z0-9_' '\n' < "$LIB" 2>/dev/null \
        | grep -E "^.{2,60}$" | sort -u | grep -iE "$FILT"
else
    tr -c 'A-Za-z0-9_' '\n' < "$LIB" 2>/dev/null \
        | grep -E "^.{2,60}$" | sort -u
fi
