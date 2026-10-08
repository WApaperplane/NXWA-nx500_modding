#!/bin/bash
set -e
ROOT="D:/download/NX-KS2-88"
ZIG="$ROOT/.uploads/zig/zig-windows-x86_64-0.13.0/zig.exe"
CFLAGS="-target arm-linux-gnueabi.2.15 -O0 -mfloat-abi=soft -fno-stack-protector"
mkdir -p out
echo "== 编译 memread =="
"$ZIG" cc $CFLAGS "$ROOT/test_server/pwfilter/b1/src/memread.c" -o "$ROOT/test_server/pwfilter/b1/out/memread.arm"
ls -la "$ROOT/test_server/pwfilter/b1/out/memread.arm"
od -A d -t x1 -N 8 "$ROOT/test_server/pwfilter/b1/out/memread.arm"
