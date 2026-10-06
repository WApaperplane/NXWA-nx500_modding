#!/bin/bash
# NX-KS2 方案B 构建脚本：交叉编译 ARM X11 原生窗口程序（nx-film-lab）
#
# 目标三元组 arm-linux-gnueabi.2.15（EABI5 softfp）
# -O0 是铁律：-O1/-O2 编译的 ARM 代码在 NX500 真机段错误(139)（2026-08-15 实测）
#
# X11 库来源：从相机 /usr/lib/libX11.so.6 拉下来放进 sysroot（NX1 GPL 包里没有 X11 头文件/库）
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
HERE_WIN="$(echo "$HERE" | sed 's#^/\([a-z]\)/#\U\1:/#')"
ROOT="$(echo "$HERE/../.." | sed 's#^/\([a-z]\)/#\U\1:/#')"

ZIG="$ROOT/.uploads/zig/zig-windows-x86_64-0.13.0/zig.exe"
SYSROOT="$ROOT/.uploads/nx1_open/rootfs_dev/standard-armv7l/usr"
TARGET="arm-linux-gnueabi.2.15"

CFLAGS="-target $TARGET -O0 -I$SYSROOT/include -mfloat-abi=soft -fno-stack-protector"
LDFLAGS="-L$SYSROOT/lib -lX11 -s -Wl,--gc-sections"

mkdir -p "$HERE_WIN/out"

build() {
    local name="$1" src="$2"
    echo "== 编译 $name =="
    "$ZIG" cc $CFLAGS "$HERE_WIN/src/$src" $LDFLAGS -o "$HERE_WIN/out/$name"
    echo "  -> out/$name"
    ls -la "$HERE_WIN/out/$name"
}

case "${1:-all}" in
    flab)  "$ZIG" cc $CFLAGS "$HERE_WIN/src/nxflab.c" "$HERE_WIN/src/font5x7.c" $LDFLAGS -o "$HERE_WIN/out/nxflab.arm"
           ls -la "$HERE_WIN/out/nxflab.arm";;
    grab)  build x11grab.arm x11grab.c ;;
    probe) build x11probe.arm x11probe.c ;;
    all)   build x11probe.arm x11probe.c
           build nxflab.arm nxflab.c ;;
    *) echo "用法: bash build.sh [flab|grab|probe|all]"; exit 2 ;;
esac

echo
echo "== 产物验证 =="
if [ -f "$HERE_WIN/out/x11probe.arm" ]; then
    od -A d -t x1 -N 20 "$HERE_WIN/out/x11probe.arm" | head -2
    echo "(7f 45 4c 46 = ELF magic；01 28 = 32-bit + ARM)"
fi
