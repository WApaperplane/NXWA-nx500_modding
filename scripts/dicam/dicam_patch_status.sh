#!/bin/bash
# =====================================================================
# [T2] di-camera-app 补丁状态检查（只读）
#   输出：bind-mount 状态 / 目标与补丁的 md5 / App 进程 / 命令通道探活
#   用途：检查磁盘/挂载就位；不是运行代码或原生菜单生效证明。
#   10-16：P5 实测失败；快照恢复/fresh-exec 和 gettext 缓存必须另验。
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
mount | grep "di-camera-app/bin/di-camera-app" || echo "  (无 bind-mount；不能据此判定当前进程的代码版本)"
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
    echo "  ⇒ 目标路径 = C-2 v1 补丁文件（不证明当前进程已装载）"
elif [ "$cur" = "48d94bd63e4479fc931ae1a1fee4e94b" ]; then
    echo "  ⇒ 目标路径 = C-2 v2 补丁文件（不证明当前进程已装载）"
elif [ "$cur" = "$MD5_SRC_EXPECT" ]; then
    echo "  ⇒ 目标 = 官方件"
    # 若挂着 bind 但 md5 等于官方件，说明补丁体本身就是官方件（异常）
    mount | grep -q "di-camera-app/bin/di-camera-app" && echo "     （但存在 bind-mount ⇒ 补丁体内容可疑，请核对）"
else
    echo "  ⇒ 目标 md5 既非官方也非已知补丁 —— 可能是 v2 桩版本，请记录：$cur"
fi
echo
echo "-- App 进程 --"
# 只认 exe 的文件名，不用 cmdline 子串，避免把本诊断命令自身识别成 App。
_APP_PID=""
for _p in /proc/[0-9]*; do
    _c=$(readlink "$_p/exe" 2>/dev/null)
    case "$_c" in
        */di-camera-app|*/di-camera-app\ \(deleted\)) _APP_PID=${_p#/proc/}; break ;;
    esac
done
if [ -n "$_APP_PID" ]; then
    echo "  di-camera-app 在跑（pid $_APP_PID）"
else
    echo "  ★ 未找到 App 候选进程；需只读复核，禁止自动 start/restart"
fi
echo
echo "-- init.sh 重挂块 --"
grep -n "dicam-T2" "$D/init.sh" 2>/dev/null && echo "  ✓ 复挂块在位（不保证早于 App 或字典加载）" || echo "  ✗ 未找到复挂块"
echo
echo "-- P5 前置（unit ExecStartPre，10-15 裁决） --"
if grep -q "t2_premount.sh" /usr/lib/systemd/system/di-camera-app.service 2>/dev/null; then
    echo "  ✓ 磁盘 unit 含前置行；P5 已实测未执行，不能据此认定投递生效"
else
    echo "  ✗ 磁盘 unit 未含 P5 前置；不得自动重装或重启 App"
fi
echo
echo "-- M2 locale（配方名样机，10-16 新增；详见 M2_RECIPE_NAME_DESIGN） --"
MDEP=/opt/usr/nx-ks/locale/zh_CN/di-camera-app.mo
if [ -f "$MDEP" ]; then
    echo "  $(md5of "$MDEP")  $MDEP"
    mount | grep -q "LC_MESSAGES/di-camera-app.mo" \
        && echo "  ⇒ 路径已挂载（不证明已加载的 gettext 字典或可见菜单名已刷新）" \
        || echo "  ⇒ 路径未挂载；正常开关机后的生效方式仍待验证"
else
    echo "  <缺失>（未部署/已移除；运行中的旧字典是否保留仍需另验）"
fi
echo
echo "-- 命令通道探活 --"
st app help >/dev/null 2>&1 && echo "  st app 通道 OK" || echo "  st app 无响应（App 未起或队列不在）"
echo "===== end ====="
