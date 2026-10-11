#!/bin/bash
# build_c2_harness.sh —— 交叉编译 C-2 验证载体（相机 ABI：glibc 2.13 / EABI5 softfp）
#
# 配方沿用 test_server/filmlab/src/build_modui.sh 的实测结论：
#   -nostdlib -nostartfiles + 自备 crt0_arm.S + 直链相机 libc-2.13.so
#   （否则宿主 gcc-13 的 Scrt1.o 会把 GLIBC_2.34 需求带进来，chroot 里直接跑不起来）
#
# 用法（在 WSL 内）: bash build_c2_harness.sh [rootfs]
set -e

ROOT=/mnt/e/tmp/NXWA-nx500_modding
SRC=$ROOT/test_server/dicam/c2_qemu
RF=${1:-/opt/nxks2/rootfs-112}
CC=$(command -v arm-linux-gnueabi-gcc || echo /usr/bin/arm-linux-gnueabi-gcc)

[ -s "$RF/usr/lib/libshell-command.so" ] || { echo "缺 $RF/usr/lib/libshell-command.so"; exit 1; }
[ -s "$RF/lib/libc-2.13.so" ]           || { echo "缺 $RF/lib/libc-2.13.so"; exit 1; }

mkdir -p "$SRC/out"

echo "== 依赖自证：libshell 导出 + SONAME =="
arm-linux-gnueabi-readelf -sW "$RF/usr/lib/libshell-command.so" \
    | grep -E "shell_exec|start_shellthread|shell_app_set_start_function" || true
arm-linux-gnueabi-readelf -d "$RF/usr/lib/libshell-command.so" | grep -i soname || echo "(no SONAME)"

CFLAGS="-O0 -mfloat-abi=soft -fno-stack-protector -fno-pic -no-pie -Wall"
LDFLAGS="-nostdlib -nostartfiles -Wl,-e,_start -Wl,--dynamic-linker=/lib/ld-linux.so.3 \
  -Wl,--allow-shlib-undefined -Wl,-rpath-link,$RF/usr/lib -Wl,-rpath-link,$RF/lib"

$CC $CFLAGS $LDFLAGS -o "$SRC/out/c2_harness.arm" \
    "$SRC/c2_harness.c" "$ROOT/test_server/filmlab/src/crt0_arm.S" \
    "$RF/lib/libc-2.13.so" -L"$RF/usr/lib" -l:libshell-command.so \
    -lgcc

echo "== 产物 =="
ls -l "$SRC/out/c2_harness.arm"
echo "== 版本需求（应只见 GLIBC_2.4/2.13 一类） =="
arm-linux-gnueabi-readelf --version-info "$SRC/out/c2_harness.arm" 2>/dev/null \
    | grep -E "Name: GLIBC" | sort -u
echo "== NEEDED =="
arm-linux-gnueabi-readelf -d "$SRC/out/c2_harness.arm" | grep NEEDED
