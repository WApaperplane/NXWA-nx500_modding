#!/bin/bash
# qemu_vm_run.sh —— **QEMU 系统模式（真虚拟机）**：把相机 rootfs 直接当 VM 的根，原生跑 UI 渲染器
#
# 三条路的取舍（★ 本轮实测，别重复踩）：
#   ① 相机自己的内核 + `-M virt`      → ❌ 零 console 输出（Samsung 3.5 BSP、非 DT）。见 qemu_vm_boot.log
#   ② 通用内核 + rootfs 作 virtio 磁盘 → ❌ Alpine lts 内核 VIRTIO_BLK / EXT4_FS **全是 =m**（模块），
#                                          initramfs 里没有模块 ⇒ `mount /dev/vda` → "No such device"
#   ③ 通用内核 + **rootfs 打进 initramfs** → ✅ 本脚本采用：由内核自带 initramfs 装载，
#                                          不依赖任何块设备驱动
#
# 产物：raw8/repro/qemu_vm_run.log（含 guest 自证、渲染器日志、产物 md5）
#
# 用法: bash qemu_vm_run.sh [秒数]
set -u
SECS=${1:-300}
VM=/mnt/e/tools/qemu-vm
ROOT=/mnt/e/tmp/NXWA-nx500_modding
SRC=$ROOT/test_server/filmlab/src
RF=/opt/nxks2/rootfs-112
LITE=$VM/lite
INITRD=$VM/camera-initramfs.cpio.gz
LOG=$ROOT/raw8/repro/qemu_vm_run.log
ALP=https://dl-cdn.alpinelinux.org/alpine/v3.20/releases/armv7/netboot

mkdir -p "$VM" "$(dirname "$LOG")"

# ---------- 0. 通用 armhf 内核 ----------
if [ ! -s "$VM/vmlinuz-lts" ]; then
  echo "== 下载 Alpine armv7 virt 内核"
  curl -fsSL --retry 3 -o "$VM/vmlinuz-lts" "$ALP/vmlinuz-lts" || exit 1
fi
ls -l "$VM/vmlinuz-lts"

# ---------- 1. 组装「精简相机 rootfs」（只留跑渲染器需要的） ----------
if [ ! -d "$LITE/usr/lib" ]; then
  echo "== 组装精简相机 rootfs（/lib /bin /sbin /etc /usr/{lib,bin,share}）"
  mkdir -p "$LITE/usr/share" "$LITE/tmp/modui/out"
  for d in lib bin sbin etc; do cp -a "$RF/$d" "$LITE/" 2>/dev/null || true; done
  for d in lib bin share/fonts share/evas; do
    mkdir -p "$LITE/usr/$(dirname "$d")"
    cp -a "$RF/usr/$d" "$LITE/usr/$(dirname "$d")/" 2>/dev/null || true
  done
fi
cp -f "$SRC/out/modui_render.arm" "$LITE/tmp/modui/" 2>/dev/null || \
  echo "  [warn] 还没有 modui_render.arm —— 先跑 build_modui.sh"

# ---------- 2. /init（guest 里跑的东西） ----------
cat > "$LITE/init" <<'EOF'
#!/bin/sh
export PATH=/bin:/sbin:/usr/bin:/usr/sbin
mount -t proc  proc /proc 2>/dev/null
mount -t sysfs sys  /sys  2>/dev/null
mkdir -p /tmp/modui/out
echo "=== GUEST 自证：这是虚拟机（armv7），且根 = 相机 rootfs ==="
uname -a
cat /proc/device-tree/model 2>/dev/null; echo
ls -l /lib/ld-linux.so.3 /usr/share/fonts/SDIC_GP_US_20120720.ttf
echo "=== 跑 UI 渲染器（★ 原生 ARM 执行，不是 qemu 逐指令解释）==="
UI_LOG=/tmp/modui/ui_pages.log /tmp/modui/modui_render.arm /tmp/modui/out 720 480
echo "renderer_rc=$?"
echo "---- ui_pages.log ----"
cat /tmp/modui/ui_pages.log 2>/dev/null
echo "---- 产物 md5（应互不相同）----"
md5sum /tmp/modui/out/ui_page_p*.png 2>/dev/null || ls -l /tmp/modui/out/
echo "=== DONE-MARKER ==="
# ★ 不能直接退出：init 一退出内核就 panic（"Attempted to kill init"）。
#   这里挂住等外部 timeout 结束虚拟机，日志才干净。
while :; do sleep 60; done
EOF
chmod +x "$LITE/init"

# ---------- 3. 打 initramfs（cpio/newc + gzip） ----------
if [ ! -s "$INITRD" ] || [ "$LITE/init" -nt "$INITRD" ]; then
  echo "== 打 initramfs（gzip -1）"
  ( cd "$LITE" && find . -print0 | cpio --null -o -H newc 2>/dev/null | gzip -1 ) > "$INITRD" || exit 1
fi
ls -lh "$INITRD"

# ---------- 4. 起虚拟机 ----------
echo "== 启动 QEMU 系统模式（${SECS}s 上限）"
{
  echo "### qemu-system-arm 系统模式：相机 rootfs 作为 VM 的根（initramfs）$(date '+%F %T')"
  echo "### kernel=alpine-armv7-lts  machine=virt cortex-a15  mem=1536M"
} > "$LOG"

timeout "$SECS" qemu-system-arm \
  -M virt -cpu cortex-a15 -m 1536 -smp 1 -nographic -no-reboot \
  -kernel "$VM/vmlinuz-lts" -initrd "$INITRD" \
  -append "console=ttyAMA0 rdinit=/init" \
  >> "$LOG" 2>&1
echo "### exit=$?" >> "$LOG"

echo "---- 日志尾部 ----"
tail -55 "$LOG"
