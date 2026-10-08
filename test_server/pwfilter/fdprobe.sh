#!/bin/sh
# fdprobe.sh — 列出 di-camera-app 打开的所有普通文件（排除 socket/anon/dev）
PID=${1:-252}

echo "=== 进程 $PID 打开的普通文件 ==="
for f in /proc/$PID/fd/*; do
    t=$(readlink "$f" 2>/dev/null)
    case "$t" in
        socket*|anon_inode*|/dev/*|"") ;;
        *) echo "$t" ;;
    esac
done | sort -u

echo
echo "=== 打开的 db/sqlite 类文件 ==="
for f in /proc/$PID/fd/*; do
    t=$(readlink "$f" 2>/dev/null)
    case "$t" in
        *.db|*.sqlite|*db*|*DB*) echo "$t" ;;
    esac
done | sort -u

echo
echo "=== 设备节点(非标准) ==="
for f in /proc/$PID/fd/*; do
    t=$(readlink "$f" 2>/dev/null)
    case "$t" in
        /dev/d5*|/dev/ump*|/dev/slp*|/dev/dri*) echo "$t" ;;
    esac
done | sort -u
