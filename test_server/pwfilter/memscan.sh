#!/bin/sh
# memscan.sh — 在 di-camera-app 内存里搜 iqr 特征串（只读，不写）
#
# 目标: 验证 iqr[] 的运行时值是否为独立内存存储。
#   特征: PW_HUE/SATURATION/SHARPNESS/CONTRAST 四值相同 = 0x000FD80A
#         在小端内存里是连续 16 字节: 0AD8F700 x4
#   若搜到-> 是独立存储, /dev/mem 方案可行
#   若搜不到 -> 可能是 iqr 命令自己算的, 方案不成立
#
# 用法: sh memscan.sh [PID]

PID=${1:-252}

echo "=== 1) 进程可读段统计 ==="
grep -E "rw" /proc/$PID/maps 2>/dev/null | wc -l

echo
echo "=== 2) 各可读段大小 (前 20) ==="
grep -E "rw" /proc/$PID/maps 2>/dev/null | awk '{print $1, $6}' | head -20

echo
echo "=== 3) 尝试直接搜特征字节 0AD8F700 (iqr PW中性值) ==="
# 用 dd + busybox 逐段扫, 太慢; 改用 strings 快筛
# 先看能不能在整段里找到 4 连相同模式
for R in $(grep -oE "^[0-9a-f]+-[0-9a-f]+" /proc/$PID/maps 2>/dev/null | head -40); do
    A=${R%-*}
    B=${R#*-}
    SZ=$(( 0x$B - 0x$A ))
    [ "$SZ" -gt 20000000 ] && continue
    N=$(dd if=/proc/$PID/mem bs=1 skip=$(( 0x$A )) count=$SZ 2>/dev/null | /opt/usr/nx-ks/busybox od -An -tx1 | grep -o "0a d8 f7 00 0a d8 f7 00" | wc -l)
    [ "$N" -gt 0 ] && echo "  段 $R ($SZ 字节): 命中 $N 处"
done

echo
echo "=== 4) 检查 /proc/PID/mem 是否可读 ==="
dd if=/proc/$PID/mem bs=1 skip=0 count=16 2>&1 | /opt/usr/nx-ks/busybox od -An -tx1 | head -2
