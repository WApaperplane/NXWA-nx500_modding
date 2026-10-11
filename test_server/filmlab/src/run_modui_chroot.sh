#!/bin/bash
# run_modui_chroot.sh —— 在相机 rootfs 的 chroot 里跑 ARM 渲染器（qemu-arm-static 用户态模拟）
#
# 原理：guest 侧是**相机自己的 glibc 2.13 + EFL 1.7.99 + SDIC_GP_US 字体**，
#       二进制由 qemu-arm-static 逐指令解释 ⇒ 不依赖相机、不依赖 X、纯离线出图。
#       （渲染走 evas 的 **buffer 引擎**：渲染到内存，无需显示服务。）
#
# 用法（在 WSL 内执行）:
#   bash .../run_modui_chroot.sh [rootfs] [renderer]
# 默认 rootfs=/opt/nxks2/rootfs-112  renderer=modui_render.arm
# 产出：raw8/repro/ui_page_p*.png + raw8/repro/ui_pages.log（并同步一份到 raw8/repro/modui/）
set -e

ROOT=/mnt/e/tmp/NXWA-nx500_modding
SRC=$ROOT/test_server/filmlab/src
RF=${1:-/opt/nxks2/rootfs-112}
BIN=${2:-modui_render.arm}
OUT=$ROOT/raw8/repro

[ -s "$SRC/out/$BIN" ] || { echo "缺产物 $SRC/out/$BIN —— 先跑 build_modui.sh"; exit 1; }
[ -d "$RF/usr" ] || { echo "rootfs 不存在: $RF"; exit 1; }

# 1) 装进 chroot；输出目录放 rootfs 内（chroot 看不到 /mnt/e，除非绑定）
mkdir -p "$RF/tmp/modui/out"
rm -f  "$RF/tmp/modui/out/"*.png "$RF/tmp/modui/ui_pages.log"
cp -f  "$SRC/out/$BIN" "$RF/tmp/modui/$BIN"
chmod +x "$RF/tmp/modui/$BIN"

# 2) /dev/null 等最小设备节点（部分库初始化会碰）
[ -e "$RF/dev/null" ] || { mkdir -p "$RF/dev"; mknod -m 666 "$RF/dev/null" c 1 3 || true; }

# 3) 自证：chroot 里确认打的是**相机**的库与字体（避免 S5 §2.5 那类"其实跑在宿主"的错误）
echo "---- chroot 自证 ----"
chroot "$RF" /bin/sh -c 'ls -l /lib/ld-linux.so.3 /usr/lib/libevas.so.1 /usr/share/fonts/SDIC_GP_US_20120720.ttf 2>&1'
chroot "$RF" /bin/sh -c 'head -c 16 /lib/libc-2.13.so >/dev/null 2>&1 && echo "glibc 2.13 在位"'

# 4) 跑渲染
echo "---- 渲染 ----"
chroot "$RF" /usr/bin/env UI_LOG=/tmp/modui/ui_pages.log \
    "/tmp/modui/$BIN" /tmp/modui/out 720 480
echo "rc=$?"

# 5) 收产物
mkdir -p "$OUT"
cp -f "$RF/tmp/modui/out/ui_page_p"*.png "$OUT/" 2>/dev/null || true
cp -f "$RF/tmp/modui/ui_pages.log" "$OUT/ui_pages.log"

echo "---- 产物 ----"
ls -l "$OUT"/ui_page_p*.png "$OUT/ui_pages.log"
echo "---- 日志尾 ----"
tail -n 20 "$OUT/ui_pages.log"
