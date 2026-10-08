#!/bin/bash
# build_ui_pages.sh —— 编译 D2 五页离线渲染（ARM / 相机 ABI）
# 约束同 cjk_render：-O0；链接 EFL 用 .so 绝对路径当普通参数
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ZIG="D:/download/NX-KS2-88/.uploads/zig/zig-windows-x86_64-0.13.0/zig.exe"
EFL="D:/download/NX-KS2-88/test_server/filmlab/efl"
TARGET="arm-linux-gnueabi.2.15"
OUT="$HERE/out/ui_pages_render.arm"

[ -x "$ZIG" ] || { echo "zig 不在位: $ZIG"; exit 1; }
for f in libecore_evas.so.1 libevas.so.1 libecore.so.1; do
  [ -s "$EFL/$f" ] || { echo "缺链接库: $EFL/$f"; exit 1; }
done
mkdir -p "$HERE/out"

"$ZIG" cc -target $TARGET -O0 -mfloat-abi=soft -fno-stack-protector \
    "$HERE/ui_pages_render.c" \
    "$EFL/libecore_evas.so.1" \
    "$EFL/libevas.so.1" \
    "$EFL/libecore.so.1" \
    -s -Wl,--gc-sections \
    -o "$OUT"

echo "完成: $OUT"
ls -la "$OUT"
