#!/bin/bash
# =====================================================================
# [T2] di-camera-app 补丁状态检查（只读）
#   输出：bind-mount 状态 / 目标与补丁的 md5 / App 进程 / 命令通道探活
#   用途：刷机后复查"T2 是否仍生效"（抗刷机判据，见 TASKFLOW_2026-10-12 W-2 序 3）
# =====================================================================

D=/opt/usr/nx-ks
PD=$D/dicam
TARGET=/usr/apps/com.samsung.di-camera-app/bin/di-camera-app
PATCH=$PD/di-camera-app.c2
ORIG=$PD/di-camera-app.v1.12.orig
MD5_SRC_EXPECT="ae44293e969101d1cf0a93cbe9b99f75"
MD5_PATCH_EXPECT="0e1da8b326f49728e9394f98a53ffd35"

md5of() { /opt/usr/nx-ks/busybox md5sum "$1" 2>/dev/null | awk '{print $1}'; }

echo "===== dicam T2 status ====="
echo "-- mount --"
mount | grep "di-camera-app/bin/di-camera-app" || echo "  (无 bind-mount ⇒ 当前跑的是 rootfs 里的官方件)"
echo
echo "-- files --"
for f in "$TARGET" "$PATCH" "$ORIG"; do
    if [ -f "$f" ]; then
        echo "  $(md5of "$f")  $f"
    else
        echo "  <缺失>            $f"
    fi
done
echo
echo "-- 判定 --"
cur=$(md5of "$TARGET")
if [ "$cur" = "$MD5_PATCH_EXPECT" ]; then
    echo "  ⇒ 目标 = 补丁件（T2 生效中的强证据）"
elif [ "$cur" = "$MD5_SRC_EXPECT" ]; then
    echo "  ⇒ 目标 = 官方件"
    # 若挂着 bind 但 md5 等于官方件，说明补丁体本身就是官方件（异常）
    mount | grep -q "di-camera-app/bin/di-camera-app" && echo "     （但存在 bind-mount ⇒ 补丁体内容可疑，请核对）"
else
    echo "  ⇒ 目标 md5 既非官方也非已知补丁 —— 可能是 v2 桩版本，请记录：$cur"
fi
echo
echo "-- App 进程 --"
if pidof di-camera-app >/dev/null 2>&1; then
    echo "  di-camera-app 在跑（pid $(pidof di-camera-app)）"
else
    echo "  ★ di-camera-app 未在跑 —— 注意 unit 里 Restart=always 被注释，崩了不自愈，需手动 start"
fi
echo
echo "-- init.sh 重挂块 --"
grep -n "dicam-T2" "$D/init.sh" 2>/dev/null && echo "  ✓ 块在位（开机自动重挂）" || echo "  ✗ 块不在 ⇒ 刷机后不会自动重挂"
echo
echo "-- 命令通道探活 --"
st app help >/dev/null 2>&1 && echo "  st app 通道 OK" || echo "  st app 无响应（App 未起或队列不在）"
echo "===== end ====="
