#!/bin/bash
# run_semprobe.sh —— chroot sem 通路探针（环境三件套的最小验证）
# 用法（WSL 内）: bash run_semprobe.sh [rootfs]
RF=${1:-/opt/nxks2/rootfs-112}
SRC=/mnt/e/tmp/NXWA-nx500_modding/test_server/dicam/c2_qemu
CRT=/mnt/e/tmp/NXWA-nx500_modding/test_server/filmlab/src/crt0_arm.S
CC=arm-linux-gnueabi-gcc

set -e
mkdir -p "$SRC/out" "$RF/tmp/dicam_c2" "$RF/proc" "$RF/dev/shm"

$CC -O0 -mfloat-abi=soft -fno-stack-protector -fno-pic -no-pie \
    -nostdlib -nostartfiles -Wl,-e,_start -Wl,--dynamic-linker=/lib/ld-linux.so.3 \
    -Wl,--allow-shlib-undefined -Wl,-rpath-link,"$RF/usr/lib" -Wl,-rpath-link,"$RF/lib" \
    -o "$SRC/out/c2_semprobe.arm" "$SRC/c2_semprobe.c" "$CRT" \
    "$RF/lib/libc-2.13.so" "$RF/lib/libpthread.so.0" -lgcc
cp -f "$SRC/out/c2_semprobe.arm" "$RF/tmp/dicam_c2/semprobe.arm"

MP=0; MS=0
mountpoint -q "$RF/proc"    || { mount -t proc proc "$RF/proc"; MP=1; }
mountpoint -q "$RF/dev/shm" || { mount -t tmpfs -o mode=1777 tmpfs "$RF/dev/shm"; MS=1; }

echo "===== 探针（应看到 sem_open 返回有效指针 / sem_init=0） ====="
timeout 20 chroot "$RF" /tmp/dicam_c2/semprobe.arm || echo "rc=$?"

[ "$MS" = 1 ] && umount "$RF/dev/shm" && echo "(dev/shm 已卸载)"
[ "$MP" = 1 ] && umount "$RF/proc"    && echo "(proc 已卸载)"
