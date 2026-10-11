#!/bin/bash
# build_ui_pages.sh —— ⛔【已弃用，2026-10-11】改用 build_modui.sh
#
# ★ 弃用原因：本脚本依赖 `D:/download/NX-KS2-88/...` 下的 zig 交叉编译器与 EFL 库副本，
#   而 **D 盘已并入 C 盘**，整条链路失效（G3 的 ui_page_p*.png 证据也因此丢失过一次）。
#   ⇒ 现在统一用：
#        bash test_server/filmlab/src/build_modui.sh        # 交叉编译（arm-linux-gnueabi-gcc + 相机 rootfs 真库）
#        bash test_server/filmlab/src/run_modui_chroot.sh   # chroot + qemu-arm-static 出图
#        bash test_server/filmlab/src/qemu_vm_run.sh        # 系统模式真虚拟机出图
#   本文件保留仅为追溯当时的做法，**不要直接跑**。
exit 1
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
