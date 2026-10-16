#!/bin/bash
# build_m2_probe.sh — 编译 M2 gettext 探针（相机 ABI：glibc 2.13 / EABI5 softfp）
#
# 配方沿用 build_modui.sh / build_c2_harness.sh 的实测结论：
#   -nostdlib -nostartfiles + 自备 crt0_arm.S + 直链相机 libc-2.13.so
#   （宿主 gcc 的 Scrt1.o 会带 GLIBC_2.34 需求；直接链相机 libc 使符号需求落到 GLIBC_2.4）
#
# 用法（WSL 内）: bash build_m2_probe.sh [rootfs]
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
RF=${1:-/opt/nxks2/rootfs-112}
CC=$(command -v arm-linux-gnueabi-gcc || echo /usr/bin/arm-linux-gnueabi-gcc)
CRT0="$ROOT/test_server/filmlab/src/crt0_arm.S"

[ -x "$(command -v $CC)" ] || { echo "缺 $CC（apt-get install -y gcc-arm-linux-gnueabi）"; exit 1; }
[ -s "$RF/lib/libc-2.13.so" ] || { echo "缺 $RF/lib/libc-2.13.so"; exit 1; }
[ -s "$CRT0" ] || { echo "缺 crt0: $CRT0"; exit 1; }

mkdir -p "$HERE/out"

CFLAGS="-O0 -mfloat-abi=soft -fno-stack-protector -fno-pic -no-pie -Wall"
LDFLAGS="-nostdlib -nostartfiles -Wl,-e,_start -Wl,--dynamic-linker=/lib/ld-linux.so.3 \
  -Wl,--allow-shlib-undefined -Wl,-rpath-link,$RF/usr/lib -Wl,-rpath-link,$RF/lib"

$CC $CFLAGS $LDFLAGS -o "$HERE/out/m2_probe.arm" \
    "$HERE/m2_probe.c" "$CRT0" \
    "$RF/lib/libc-2.13.so" -lgcc

echo "== 产物 =="
ls -l "$HERE/out/m2_probe.arm"
echo "== GLIBC 版本需求（应只见 2.4/2.13 一类） =="
arm-linux-gnueabi-readelf --version-info "$HERE/out/m2_probe.arm" 2>/dev/null \
    | grep -E "Name: GLIBC" | sort -u
echo "== NEEDED =="
arm-linux-gnueabi-readelf -d "$HERE/out/m2_probe.arm" | grep NEEDED
echo "== gettext 符号直连自证 =="
arm-linux-gnueabi-readelf -sW "$HERE/out/m2_probe.arm" | grep -E "gettext|textdomain" | head -8
