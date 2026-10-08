#!/bin/bash
# ============================================================
# fb-probe.sh - NX500 /dev/fb0 取流能力探测 + 屏幕快照
#
# 依据 (完整 GPL 内核源码 E:\新建文件夹\linux-3.5):
#   drivers/gpu/drm/drime5/drime5_drm_drv.c:259
#       ret = drime5_drm_fbdev_init(dev);      ← 无条件调用, 无 #ifdef
#   drivers/gpu/drm/drime5/drime5_drm_fbdev.c:52
#       static int drime5_drm_fb_mmap(...)      → dma_mmap_attrs 映射 GEM 到用户态
#   drivers/gpu/drm/drime5/drime5_drm_drv.c fops
#       .mmap = drime5_drm_gem_mmap / .poll = drm_poll
#   .config: CONFIG_FB=y
#
#   → 结论: /dev/fb0 存在, 可 mmap。shell 直接 dd 就能拿到当前屏幕像素。
#
# 重要: 拿到的是 LCD **实际显示内容**(含 OSD 叠加层数字/图标), 不是干净 liveview。
#       调参对比前必须先关叠加层:
#           st app bb lcd video
#
# 用法:
#   sh fb-probe.sh check# 探测 fb0 存在 + 尺寸 + 格式(只读)
#   sh fb-probe.sh snap# 抓一帧 raw 到 SD 卡
#   sh fb-probe.sh snapclean              # 先关叠加层再抓
#   sh fb-probe.sh loop <n>               # 连抓 n 帧(看是否连续刷新)
#   sh fb-probe.sh rmvideo|on           # 叠加层开关
# ============================================================

BB=/opt/usr/nx-ks/busybox
ST=/usr/bin/st
OUT=/mnt/mmc/fbsnap
LOG=/mnt/mmc/fb-probe.log

say() { echo "$*" | tee -a "$LOG"; }

case "$1" in

check)
    say "=== /dev/fb0 探测 ==="
    ls -la /dev/fb* 2>&1 | tee -a "$LOG"
    say ""
    # fbset 在 busybox 里通常没有; 用 ioctl 探测靠 dd 能否读出非空数据
    say "-- dmesg 里的 fb/DRIMe5 痕迹 --"
    dmesg 2>/dev/null | grep -iE "drime5|drm|fb0|framebuffer" | tail -20 | tee -a "$LOG"
    say ""
    say "-- 尝试读 fb0 头部 --"
    if [ -c /dev/fb0 ]; then
        dd if=/dev/fb0 of=/tmp/fbhead.bin bs=1024 count=4 2>&1 | tee -a "$LOG"
        ls -la /tmp/fbhead.bin 2>&1 | tee -a "$LOG"
        say ""
        say "若上面字节数 = 0 -> 该fb 未绑定或需要 mmap 而非 read(正常, 不代表不可用)"
        say "若字节数 > 0 -> 直接可读, 最省事"
        say ""
        say "查尺寸的可靠办法(不依赖 fbset):"
        say "  cat /sys/class/graphics/fb0/{virtual_size,virtual_pixels,bits_per_pixel,stride} 2>/dev/null"
        for f in virtual_size virtual_pixels bits_per_pixel stride; do
            v=$(cat /sys/class/graphics/fb0/$f 2>/dev/null)
            say "  $f = ${v:-N/A}"
        done
    else
        say "/dev/fb0 不存在。"
        say "排查: 1) 内核是否 CONFIG_FB=y (源码里是, 但实机固件可能不同)"
        say "      2) 可能节点是 /dev/fb1 /dev/fb2"
        say "      3) 可能被独占(机身 GUI 占着), 需停GUI 进程"
    fi
    ;;

snap)
    N=$(date +%H%M%S)
    mkdir -p $OUT
    F=$OUT/fb-$N.raw
    say "抓帧 -> $F"
    dd if=/dev/fb0 of="$F" bs=1048576 2>&1 | tee -a "$LOG"
    ls -la "$F" 2>&1 | tee -a "$LOG"
    say ""
    say "raw 无格式头, 需知道 宽x高xBPP 才能看。可用命令:"
    say "  xxd -l 64 $F | head -4      看头几个字节的pattern"
    say "  拉回 PC: nc / wget http://相机IP/cgi-bin/... "
    say ""
    say "PC 端转 JPEG (Python):"
    say "  from PIL import Image"
    say "  w,h = 从上面 virtual_size 读"
    say "  Image.frombytes('RGB',(w,h),open('$F','rb').read()).save('x.jpg')"
    ;;

snapclean)
    say "先关叠加层..."
    $ST app bb lcd video 2>&1 | tee -a "$LOG"
    sleep 1
    $0 snap
    say ""
    say "记得恢复: st app bb lcd on"
    ;;

rmvideo)
    $ST app bb lcd video 2>&1 | tee -a "$LOG"
    say "叠加层已关"
    ;;

on)
    $ST app bb lcd on 2>&1 | tee -a "$LOG"
    say "叠加层已恢复"
    ;;

loop)
    N=${2:-5}
    mkdir -p $OUT
    say "连抓 $N 帧(间隔 1 秒)..."
    i=1
    while [ $i -le $N ]; do
        F=$OUT/loop-$(date +%H%M%S)-$i.raw
        dd if=/dev/fb0 of="$F" bs=1048576 2>/dev/null
        sz=$(stat -c%s "$F" 2>/dev/null || echo 0)
        say "  $i) $F  $sz bytes"
        i=$(( i + 1 ))
        sleep 1
    done
    say ""
    say "若各帧字节数相同= 尺寸稳定(正常)。"
    say "把几帧拉到 PC 做差分, 相同 = 画面静止(说明 liveview 没在更新, 有问题)"
    ;;

*)
    say "用法: sh fb-probe.sh {check|snap|snapclean|rmvideo|on|loop <n>}"
    ;;

esac

exit 0