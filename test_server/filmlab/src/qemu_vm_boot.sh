#!/bin/bash
# qemu_vm_boot.sh —— QEMU **系统模式（虚拟机）** 启动尝试：把相机内核/rootfs 拉起来
#
# 与 run_modui_chroot.sh 的分工（★ 重要，别混）：
#   * run_modui_chroot.sh —— **用户态模拟**（qemu-arm-static + chroot）：把「相机用户态」跑起来，
#     用于出图 / 跑 ARM 程序。**本项目 UI 出图证据就是它产出的。**
#   * qemu_vm_boot.sh（本脚本）—— **系统模式**：`qemu-system-arm -M virt` 起一台真虚拟机，
#     用来回答"相机内核在通用机器模型上能不能起来"这个**独立问题**。
#
# 用法: bash qemu_vm_boot.sh [kernel.bin] [秒数]
set -u
K=${1:-/mnt/e/NXWA/fw/v1.12/vmlinux_02.bin}
SECS=${2:-45}
LOG=/mnt/e/tmp/NXWA-nx500_modding/raw8/repro/qemu_vm_boot.log

mkdir -p "$(dirname "$LOG")"
echo "### qemu-system-arm 系统模式启动尝试 $(date '+%F %T')" > "$LOG"
echo "### kernel=$K  timeout=${SECS}s" >> "$LOG"
qemu-system-arm --version >> "$LOG" 2>&1

timeout "$SECS" qemu-system-arm \
    -M virt -cpu cortex-a15 -m 512M -nographic -no-reboot \
    -kernel "$K" \
    -append "console=ttyAMA0 earlyprintk=serial" \
    >> "$LOG" 2>&1
rc=$?
echo "### exit=$rc （124 = 被 timeout 终止，说明虚拟机**没有退出**，即"没有 panic 后自杀"）" >> "$LOG"

echo "---- 日志（前 60 行）----"
head -60 "$LOG"
echo "---- 日志（后 20 行）----"
tail -20 "$LOG"
echo "---- 落盘: $LOG ----"
