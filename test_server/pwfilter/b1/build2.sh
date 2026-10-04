#!/bin/bash
#编译 ispprobe —— ★铁律：-O0（-O1+ 实测段错误）；必须 -ldl
set -e
ROOT="D:/download/NX-KS2-88"
ZIG="$ROOT/.uploads/zig/zig-windows-x86_64-0.13.0/zig.exe"
TARGET="arm-linux-gnueabi.2.15"
CFLAGS="-target $TARGET -O0 -mfloat-abi=soft -fno-stack-protector"
LDFLAGS="-ldl"
mkdir -p out
echo "== 编译 ispprobe =="
"$ZIG" cc $CFLAGS "$ROOT/test_server/pwfilter/b1/src/ispprobe.c" $LDFLAGS -o "$ROOT/test_server/pwfilter/b1/out/ispprobe.arm"
ls -la "$ROOT/test_server/pwfilter/b1/out/ispprobe.arm"
echo "== ELF 验证（7f454c46 = ELF magic）=="
od -A d -t x1 -N 8 "$ROOT/test_server/pwfilter/b1/out/ispprobe.arm"
