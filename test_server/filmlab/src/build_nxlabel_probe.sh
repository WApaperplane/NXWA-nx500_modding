#!/bin/bash
# build_nxlabel_probe.sh —— 编译 D7 的标签离机验证探针（ARM / 相机 ABI）
# 与 cjk_render 同源约束：① -O0（-O1+ 真机 SIGILL）② .so 绝对路径当普通参数传链接器
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ZIG="D:/download/NX-KS2-88/.uploads/zig/zig-windows-x86_64-0.13.0/zig.exe"
EFL="D:/download/NX-KS2-88/test_server/filmlab/efl"
TARGET="arm-linux-gnueabi.2.15"
OUT="$HERE/out/nxlabel_probe.arm"

[ -x "$ZIG" ] || { echo "zig 不在位: $ZIG"; exit 1; }
for f in libecore_evas.so.1 libevas.so.1 libecore.so.1; do
  [ -s "$EFL/$f" ] || { echo "缺链接库: $EFL/$f"; exit 1; }
done
mkdir -p "$HERE/out"

"$ZIG" cc -target $TARGET -O0 -mfloat-abi=soft -fno-stack-protector \
    "$HERE/nxlabel_probe.c" \
    "$EFL/libecore_evas.so.1" \
    "$EFL/libevas.so.1" \
    "$EFL/libecore.so.1" \
    -s -Wl,--gc-sections \
    -o "$OUT"

echo "完成: $OUT"
ls -la "$OUT"
