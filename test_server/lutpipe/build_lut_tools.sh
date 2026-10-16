#!/bin/bash
# build_lut_tools.sh — 补齐 LUT 链路缺失部署件（cmasafe.arm / lutsentinel.arm）
#
# 背景（2026-10-16）：「LUT 路线重启」资产盘点发现——deploy_luts.py 期望的两个工具
#   在仓库中缺失（源码在：test_server/u6/cmasafe.c、test_server/lutpipe/lutsentinel.c）。
#   原编法为 zig cc（D 盘已丢）⇒ 改用已验证的相机 ABI 配方：
#     -nostdlib -nostartfiles + 自备 crt0_arm.S + 直链相机 libc-2.13.so
#   （与 build_c2_harness.sh / build_modui.sh / build_m2_probe.sh 同源；-O0 硬性）
#
# 用法（WSL 内）: bash build_lut_tools.sh [rootfs]
# 产出（deploy_luts.py 期望路径）：
#   test_server/u6/cmasafe.arm
#   test_server/lutpipe/lutsentinel.arm
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"              # test_server/lutpipe
ROOT="$(cd "$HERE/../.." && pwd)"
RF=${1:-/opt/nxks2/rootfs-112}
CC=$(command -v arm-linux-gnueabi-gcc || echo /usr/bin/arm-linux-gnueabi-gcc)
CRT0="$ROOT/test_server/filmlab/src/crt0_arm.S"

[ -x "$(command -v $CC)" ] || { echo "缺 $CC"; exit 1; }
[ -s "$RF/lib/libc-2.13.so" ] || { echo "缺相机 libc"; exit 1; }
[ -s "$RF/lib/libdl-2.13.so" ] || { echo "缺相机 libdl"; exit 1; }
[ -s "$CRT0" ] || { echo "缺 crt0: $CRT0"; exit 1; }

# ★ -D_TIME_BITS=32 -D_FILE_OFFSET_BITS=32：相机 glibc 2.13 无 time64 符号
#   （否则 clock_gettime/ioctl 会引用 __clock_gettime64/__ioctl_time64 导致链接失败）
CFLAGS="-O0 -mfloat-abi=soft -fno-stack-protector -fno-pic -no-pie -Wall \
  -D_TIME_BITS=32 -D_FILE_OFFSET_BITS=32"
LDFLAGS="-nostdlib -nostartfiles -Wl,-e,_start -Wl,--dynamic-linker=/lib/ld-linux.so.3 \
  -Wl,--allow-shlib-undefined -Wl,-rpath-link,$RF/usr/lib -Wl,-rpath-link,$RF/lib"

build_one(){
    local src="$1" out="$2"; shift 2
    echo "== 编译 $(basename "$src") -> $out"
    $CC $CFLAGS $LDFLAGS -o "$out" "$src" "$CRT0" "$RF/lib/libc-2.13.so" "$@" -lgcc
    ls -l "$out" | sed 's/^/   /'
    echo "   -- GLIBC 版本需求 --"
    arm-linux-gnueabi-readelf --version-info "$out" 2>/dev/null | grep -E "Name: GLIBC" | sort -u | sed 's/^/   /'
    echo "   -- NEEDED --"
    arm-linux-gnueabi-readelf -d "$out" | grep NEEDED | sed 's/^/   /'
}

build_one "$ROOT/test_server/u6/cmasafe.c"  "$ROOT/test_server/u6/cmasafe.arm"
# ★ glibc 2.13 的 clock_gettime 在 librt（2.17 才并入 libc）；相机自身程序（st）亦 NEEDED librt.so.1
build_one "$HERE/lutsentinel.c"             "$HERE/lutsentinel.arm" \
          "$RF/lib/librt-2.13.so" "$RF/lib/libdl-2.13.so"

echo "== 完成 =="
md5sum "$ROOT/test_server/u6/cmasafe.arm" "$HERE/lutsentinel.arm"
