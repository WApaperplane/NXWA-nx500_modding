#!/bin/bash
# 编译 heapscan —— 读 /proc/pid/mem 批量扫内存
set -e
ROOT="D:/download/NX-KS2-88"
ZIG="$ROOT/.uploads/zig/zig-windows-x86_64-0.13.0/zig.exe"
TARGET="arm-linux-gnueabi.2.15"
CFLAGS="-target $TARGET -O0 -mfloat-abi=soft -fno-stack-protector"
mkdir -p out
echo "== 编译 heapscan =="
"$ZIG" cc $CFLAGS "$ROOT/test_server/pwfilter/b1/src/heapscan.c" -o "$ROOT/test_server/pwfilter/b1/out/heapscan.arm"
ls -la "$ROOT/test_server/pwfilter/b1/out/heapscan.arm"
od -A d -t x1 -N 8 "$ROOT/test_server/pwfilter/b1/out/heapscan.arm"
