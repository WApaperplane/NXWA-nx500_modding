#!/bin/bash
# b1/build.sh — 交叉编译 3D LUT dlopen 探针
# 目标三元组 arm-linux-gnueabi.2.15 (EABI5 softfp)，-O0 是铁律（-O1+ 真机段错误 139）
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
HERE_WIN="$(echo "$HERE" | sed 's#^/\([a-z]\)/#\U\1:/#')"
ROOT="$(echo "$HERE/../../.." | sed 's#^/\([a-z]\)/#\U\1:/#')"

ZIG="$ROOT/.uploads/zig/zig-windows-x86_64-0.13.0/zig.exe"
TARGET="arm-linux-gnueabi.2.15"
# dlopen/dlsym 在 libdl 里；NX500 的 glibc 2.13 可能需要 -ldl
CFLAGS="-target $TARGET -Os -mfloat-abi=soft -fno-stack-protector"
LDFLAGS="-ldl -s -Wl,--gc-sections"

mkdir -p "$HERE_WIN/out"
NAME="${1:-lut3dl_probe.arm}"
SRC="${2:-lut3dl_probe.c}"

echo "== 编译 $NAME （$SRC） =="
"$ZIG" cc $CFLAGS "$HERE_WIN/src/$SRC" $LDFLAGS -o "$HERE_WIN/out/$NAME"
ls -la "$HERE_WIN/out/$NAME"
echo
echo "== ELF 验证 =="
od -A d -t x1 -N 20 "$HERE_WIN/out/$NAME" | head -2
echo "(7f 45 4c 46 = ELF magic; 01 28 = 32-bit + little-endian)"
