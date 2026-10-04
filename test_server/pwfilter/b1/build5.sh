#!/bin/bash
set -e
ROOT="D:/download/NX-KS2-88"
ZIG="$ROOT/.uploads/zig/zig-windows-x86_64-0.13.0/zig.exe"
CFLAGS="-target arm-linux-gnueabi.2.15 -O0 -mfloat-abi=soft -fno-stack-protector"
mkdir -p out
echo "== 编译 lut3d_probe =="
"$ZIG" cc $CFLAGS "$ROOT/test_server/pwfilter/b1/src/lut3d_probe.c" -ldl \
  -o "$ROOT/test_server/pwfilter/b1/out/lut3d_probe.arm" 2>&1 | head -20
ls -la "$ROOT/test_server/pwfilter/b1/out/lut3d_probe.arm"
od -A d -t x1 -N 8 "$ROOT/test_server/pwfilter/b1/out/lut3d_probe.arm"
