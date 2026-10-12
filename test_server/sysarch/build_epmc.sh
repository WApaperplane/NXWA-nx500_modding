#!/bin/bash
# =====================================================================
# build_epmc.sh —— 编译 epmc.arm（相机 ABI：glibc 2.13 / EABI5 softfp）
#
# 配方沿用 test_server/dicam/c2_qemu/build_c2_harness.sh 的实测结论：
#   -nostdlib -nostartfiles + 自备 crt0_arm.S + 直链相机 libc-2.13.so
#   （宿主 gcc-13 的 Scrt1.o 会带进 GLIBC_2.34 需求 ⇒ chroot/相机上都跑不起来）
#
# 依赖自证：epmc.c 只用 open/mmap/ioctl/printf/atoi/strtoul/strcmp/close ⇒ 仅 libc
#
# 用法（WSL 内）: bash test_server/sysarch/build_epmc.sh [rootfs]
# 产物:          test_server/sysarch/epmc.arm（u1_collect.py 的 push 清单会带上它）
# =====================================================================
set -e

ROOT=/mnt/e/tmp/NXWA-nx500_modding
SRC=$ROOT/test_server/sysarch
RF=${1:-/opt/nxks2/rootfs-112}
CC=$(command -v arm-linux-gnueabi-gcc || echo /usr/bin/arm-linux-gnueabi-gcc)

[ -s "$SRC/epmc.c" ]           || { echo "缺 $SRC/epmc.c"; exit 1; }
[ -s "$RF/lib/libc-2.13.so" ]  || { echo "缺 $RF/lib/libc-2.13.so（相机 libc）"; exit 1; }
[ -s "$ROOT/test_server/filmlab/src/crt0_arm.S" ] || { echo "缺 crt0_arm.S"; exit 1; }

# -I$SRC/inc：相机 EP 头（d5_ep_ioctl.h + d5_ep_type.h，取自 NX500 开源包，已随仓库自包含）
# -D_TIME_BITS=32：★ 宿主 glibc 2.39 对 32 位平台默认走 time64（ioctl→__ioctl_time64），
#   而相机 libc-2.13 只有旧接口 ⇒ 必须显式关掉，否则链接期 undefined reference。
CFLAGS="-O0 -mfloat-abi=soft -fno-stack-protector -fno-pic -no-pie -Wall \
  -I$SRC/inc -D_TIME_BITS=32 -D_FILE_OFFSET_BITS=32"
LDFLAGS="-nostdlib -nostartfiles -Wl,-e,_start -Wl,--dynamic-linker=/lib/ld-linux.so.3 \
  -Wl,--allow-shlib-undefined -Wl,-rpath-link,$RF/lib"

$CC $CFLAGS $LDFLAGS -o "$SRC/epmc.arm" \
    "$SRC/epmc.c" "$ROOT/test_server/filmlab/src/crt0_arm.S" \
    "$RF/lib/libc-2.13.so" -lgcc

echo "== 产物 =="
ls -l "$SRC/epmc.arm"
echo "== 版本需求（应只见 GLIBC_2.4/2.13 一类） =="
arm-linux-gnueabi-readelf --version-info "$SRC/epmc.arm" 2>/dev/null \
    | grep -E "Name: GLIBC" | sort -u || true
echo "== NEEDED =="
arm-linux-gnueabi-readelf -d "$SRC/epmc.arm" | grep NEEDED || true

echo "== 冒烟：chroot 内跑（无 /dev/drime5_ep，预期报错但能加载 ⇒ 证明 ABI 正确） =="
install -m 755 "$SRC/epmc.arm" "$RF/tmp/epmc.arm"
set +e
chroot "$RF" /tmp/epmc.arm 8 4 2>&1 | head -6
echo "   smoke rc=$?"
set -e
echo "== 完成 =="
