#!/bin/bash
# build_modui.sh —— 在 WSL(NXKS2) 里交叉编译 NX-WA 原生 UI 离线渲染器（ARM / 相机 ABI）
#
# ★ 2026-10-11 重写：原 build_ui_pages.sh 依赖
#     `D:/download/NX-KS2-88/.uploads/zig/.../zig.exe` 与 `D:/download/NX-KS2-88/test_server/filmlab/efl`
#   —— D 盘已并入 C 盘，该链路整体失效（G3 证据也因此丢失过）。
#   现改用 apt 的 **arm-linux-gnueabi-gcc（softfp，与相机 EABI5 / ld-linux.so.3 一致）**，
#   EFL 直接取**相机 rootfs 里的真库**（不另存副本，天然同版本）。
#
# 用法（在 WSL 内执行）:
#   bash /mnt/e/tmp/NXWA-nx500_modding/test_server/filmlab/src/build_modui.sh [rootfs]
# 默认 rootfs = /opt/nxks2/rootfs-112
set -e

ROOT=/mnt/e/tmp/NXWA-nx500_modding
SRC=$ROOT/test_server/filmlab/src
RF=${1:-/opt/nxks2/rootfs-112}
CC=arm-linux-gnueabi-gcc

[ -x "$(command -v $CC)" ] || { echo "缺 $CC —— 先 apt-get install -y gcc-arm-linux-gnueabi"; exit 1; }
for f in libecore_evas.so.1 libevas.so.1 libecore.so.1; do
  [ -s "$RF/usr/lib/$f" ] || { echo "缺链接库: $RF/usr/lib/$f"; exit 1; }
done
[ -s "$RF/lib/ld-linux.so.3" ] || { echo "缺 camera ld-linux.so.3 —— rootfs 路径不对？"; exit 1; }

mkdir -p "$SRC/out"

# 约束：-O0（硬性，历史教训）/ -no-pie（对齐相机 2.13 loader）/ -fno-stack-protector（避免引入新 glibc 符号）
#
# ★ 2026-10-11 实测修正（两处必须，否则 chroot 里报 GLIBC_2.34 not found）：
#   1) **-nostdlib -nostartfiles** —— 丢掉宿主 gcc-13 的 Scrt1.o（它引用
#      `__libc_start_main@GLIBC_2.34`），改用自己的 crt0_arm.S（引用 `@GLIBC_2.4`，
#      与相机 /usr/bin/st 一致）。
#   2) **直接链相机的 libc-2.13.so**（而不是宿主 sysroot 的 glibc 2.39）——
#      让所有 libc 符号的版本需求落到 GLIBC_2.4/2.13。
#   + --allow-shlib-undefined：libevas/libecore_evas 的传递依赖（eina/ecore_x/freetype/
#     fontconfig/harfbuzz/fribidi/eet…）静态期解析不全；它们的 DT_NEEDED 已写在 .so 里，
#     运行期由相机 loader 自动装载。
CFLAGS="-O0 -mfloat-abi=soft -fno-stack-protector -fno-pic -no-pie -Wall -Wextra -Wno-unused-parameter"
# -DUSE_ZLIB：PNG 走相机自带 libz（/lib/libz.so.1）压缩 ⇒ 出图从 ~1.0MB/张降到几十 KB，
#             便于把「UI 出图证据」入库（窄例外只收小件）。不加则回落到零依赖 stored 块。
LDFLAGS="-nostdlib -nostartfiles -Wl,-e,_start -Wl,--dynamic-linker=/lib/ld-linux.so.3 \
  -Wl,--allow-shlib-undefined -Wl,-rpath-link,$RF/usr/lib -Wl,-rpath-link,$RF/lib"

build_one() {
  local c="$1" o="$2"
  echo "== 编译 $c"
  $CC $CFLAGS -DUSE_ZLIB $LDFLAGS -o "$SRC/out/$o" "$SRC/$c" "$SRC/crt0_arm.S" \
      "$RF/lib/libc-2.13.so" "$RF/lib/libz.so.1" \
      "$RF/usr/lib/libecore_evas.so.1" "$RF/usr/lib/libevas.so.1" "$RF/usr/lib/libecore.so.1" \
      -lgcc
  ls -l "$SRC/out/$o"
  /usr/bin/arm-linux-gnueabi-readelf --version-info "$SRC/out/$o" 2>/dev/null \
    | grep -E "Name: GLIBC|File:" | sed 's/^/     /'
}

build_one modui_render.c   modui_render.arm
build_one ui_pages_render.c ui_pages_render.arm

echo "== 完成。产物在 $SRC/out/"
echo "== 下一步：bash $SRC/run_modui_chroot.sh"
