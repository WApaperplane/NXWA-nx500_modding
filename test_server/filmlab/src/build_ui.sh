#!/bin/bash
# build_ui.sh —— 编译离线 UI 渲染程序（elm 真控件 + evas buffer 引擎，ARM 相机 ABI）
#
# 用法： build_ui.sh <src.c> <输出名>
#   例： build_ui.sh ui_probe.c ui_probe.arm
#
# 沿袭 build_cjk_render.sh 的两条真机铁律：
#   ① -O0（-O1+ ARM 代码在 NX500 真机 SIGILL）
#   ② 链接 EFL 必须把 .so 绝对路径当【普通参数】传给链接器
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$1"
NAME="$2"
[ -n "$SRC" ] && [ -n "$NAME" ] || { echo "用法: build_ui.sh <src.c> <outname>"; exit 1; }
ZIG="D:/download/NX-KS2-88/.uploads/zig/zig-windows-x86_64-0.13.0/zig.exe"
EFL="D:/download/NX-KS2-88/test_server/filmlab/efl"
TARGET="arm-linux-gnueabi.2.15"
OUT="$HERE/out/$NAME"

[ -x "$ZIG" ] || { echo "zig 不在位: $ZIG"; exit 1; }
for f in libelementary.so.1 libecore_evas.so.1 libevas.so.1 libecore.so.1; do
  [ -s "$EFL/$f" ] || { echo "缺链接库: $EFL/$f"; exit 1; }
done
mkdir -p "$HERE/out"

"$ZIG" cc -target $TARGET -O0 -mfloat-abi=soft -fno-stack-protector \
    "$HERE/$SRC" \
    "$EFL/libelementary.so.1" \
    "$EFL/libecore_evas.so.1" \
    "$EFL/libevas.so.1" \
    "$EFL/libecore.so.1" \
    -s -Wl,--gc-sections \
    -o "$OUT"

echo "完成: $OUT"
ls -la "$OUT"
echo "--- DT_NEEDED 自证 ---"
python "$HERE/readelf_needed.py" "$OUT" 2>/dev/null | sed 's/^/  /' || true
