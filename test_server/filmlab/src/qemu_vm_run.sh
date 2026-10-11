#!/bin/bash
# qemu_vm_run.sh —— **QEMU 系统模式（真虚拟机）**：把相机 rootfs 直接当 VM 的根，原生跑 UI 渲染器
#
# 三条路的取舍（★ 历史实测，别重复踩）：
#   ① 相机自己的内核 + `-M virt`      → ❌ 零 console 输出（Samsung 3.5 BSP、非 DT）
#   ② 通用内核 + rootfs 作 virtio 磁盘 → ❌ Alpine lts 内核 VIRTIO_BLK/EXT4_FS 全是 =m
#   ③ 通用内核 + **rootfs 打进 initramfs** → ✅ 本脚本采用
#
# ★★ 可视化（用户要求"放前台看效果"；2026-10-11/12 实测结论）：
#   - **串口只有 1 个**（-M virt 只生成 pl011@9000000 一个节点；"窗口+文件"双通道在串口层不可能）
#   - `QVM_UI=gtk`   → QEMU GTK 窗口（`-display gtk -serial vc`）：**窗口内就是串口文本**；宿主不落日志
#   - `QVM_UI=live`  → 输出 tee 到 stdout + 日志：配合"在 Windows 终端窗口里启动"= 用户实时看 + 日志留档
#                      （推荐：cmd.exe /c start ... wsl.exe -d NXKS2 -- env QVM_UI=live bash 本脚本 150）
#   - 缺省(none)     → 原 headless 行为（只落日志）
#   ★ guest /init 已修去重（tee ... >/dev/null；此前每行两遍是 tee 同时写设备与 stdout 所致）
#
# 产物：raw8/repro/qemu_vm_run.log（各模式都有）；gtk 模式无宿主日志（内容在窗口里）
#
# 用法: bash qemu_vm_run.sh [秒数]
set -u
SECS=${1:-300}
UI=${QVM_UI:-none}
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

# ---------- 1. 组装「精简相机 rootfs」 ----------
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
mount -t devtmpfs dev /dev 2>/dev/null
mkdir -p /tmp/modui/out

run_all() {
  echo "=== GUEST 自证：这是虚拟机（armv7），且根 = 相机 rootfs ==="
  uname -a
  cat /proc/device-tree/model 2>/dev/null; echo
  echo "== 串口设备节点 =="
  ls -l /dev/ttyAMA* 2>&1
  ls -l /lib/ld-linux.so.3 /usr/share/fonts/SDIC_GP_US_20120720.ttf
  echo "=== 跑 UI 渲染器（★ 原生 ARM 执行，不是 qemu 逐指令解释）==="
  UI_LOG=/tmp/modui/ui_pages.log /tmp/modui/modui_render.arm /tmp/modui/out 720 480
  echo "renderer_rc=$?"
  echo "---- ui_pages.log ----"
  cat /tmp/modui/ui_pages.log 2>/dev/null
  echo "---- 产物 md5（应互不相同）----"
  md5sum /tmp/modui/out/ui_page_p*.png 2>/dev/null || ls -l /tmp/modui/out/
  echo "=== DONE-MARKER ==="
}

# ★ 输出走串口设备（tee 的 stdout 丢弃，否则每行会出现两遍）
if [ -c /dev/ttyAMA0 ] && command -v tee >/dev/null 2>&1; then
  if [ -c /dev/ttyAMA1 ]; then
    run_all 2>&1 | tee /dev/ttyAMA0 /dev/ttyAMA1 >/dev/null
  else
    run_all 2>&1 | tee /dev/ttyAMA0 >/dev/null
  fi
else
  run_all 2>&1
fi

# ★ 不能直接退出：init 一退出内核就 panic（"Attempted to kill init"）。
while :; do sleep 60; done
EOF
chmod +x "$LITE/init"

# ---------- 3. 打 initramfs ----------
if [ ! -s "$INITRD" ] || [ "$LITE/init" -nt "$INITRD" ]; then
  echo "== 打 initramfs（gzip -1）"
  ( cd "$LITE" && find . -print0 | cpio --null -o -H newc 2>/dev/null | gzip -1 ) > "$INITRD" || exit 1
fi
ls -lh "$INITRD"

# ---------- 4. 起虚拟机 ----------
case "$UI" in
  gtk)
    echo "== 启动 QEMU（★ GTK 窗口模式；窗口内即串口文本；${SECS}s 上限）"
    echo "### GUI/gtk $(date '+%F %T')" > "$LOG"
    timeout "$SECS" qemu-system-arm \
      -M virt -cpu cortex-a15 -m 1536 -smp 1 -no-reboot \
      -display gtk -serial vc \
      -kernel "$VM/vmlinuz-lts" -initrd "$INITRD" \
      -append "console=ttyAMA0 rdinit=/init" >> "$LOG" 2>&1
    echo "### exit=$?" >> "$LOG"
    echo "（窗口模式：内容在 GTK 窗口里；宿主日志仅 qemu 自身消息）"
    ;;
  live)
    echo "== 启动 QEMU（★ 实时流模式：stdout + 日志双写；${SECS}s 上限）"
    {
      echo "### live $(date '+%F %T')"
      echo "### kernel=alpine-armv7-lts  machine=virt cortex-a15  mem=1536M  ui=live"
    } > "$LOG"
    timeout "$SECS" qemu-system-arm \
      -M virt -cpu cortex-a15 -m 1536 -smp 1 -nographic -no-reboot \
      -kernel "$VM/vmlinuz-lts" -initrd "$INITRD" \
      -append "console=ttyAMA0 rdinit=/init" 2>&1 | tee -a "$LOG"
    echo "### exit=$?" >> "$LOG"
    echo "---- 日志尾部 ----"
    tail -20 "$LOG"
    ;;
  *)
    echo "== 启动 QEMU 系统模式（headless；${SECS}s 上限）"
    {
      echo "### qemu-system-arm 系统模式：相机 rootfs 作为 VM 的根（initramfs）$(date '+%F %T')"
      echo "### kernel=alpine-armv7-lts  machine=virt cortex-a15  mem=1536M"
    } > "$LOG"
    timeout "$SECS" qemu-system-arm \
      -M virt -cpu cortex-a15 -m 1536 -smp 1 -nographic -no-reboot \
      -kernel "$VM/vmlinuz-lts" -initrd "$INITRD" \
      -append "console=ttyAMA0 rdinit=/init" >> "$LOG" 2>&1
    echo "### exit=$?" >> "$LOG"
    echo "---- 日志尾部 ----"
    tail -55 "$LOG"
    ;;
esac
