#!/bin/bash
# =====================================================================
# [T2] di-camera-app 补丁安装器（bind-mount 方式 / 相机端执行 / 幂等）
#
# 为什么是 T2 而不是 T1（rootfs 原地补丁）：
#   SLP 容器 idx6 = rootfs（见 SLP_CONTAINER_FORMAT_2026-10-08.md）
#   ⇒ 走官方升级刷任何 SLP 包（含 A1）都可能把 /usr/apps/.../di-camera-app
#     重写回官方版 ⇒ T1 会被冲掉。
#   T2 把补丁体放在 /opt/usr/nx-ks/（p14，刷机不覆盖），每次开机由 init.sh 重挂。
#   决策：docs/current/MOD_DECISION_P7_APP_2026-10-12.md D-5
#
# 用法：sh /opt/usr/nx-ks/dicam/dicam_patch_install.sh
# 前置：补丁体已放到 /opt/usr/nx-ks/dicam/di-camera-app.c2
# =====================================================================

D=/opt/usr/nx-ks
PD=$D/dicam
TARGET=/usr/apps/com.samsung.di-camera-app/bin/di-camera-app
PATCH=$PD/di-camera-app.c2
ORIG=$PD/di-camera-app.v1.12.orig
INITS=$D/init.sh
MARK="[dicam-T2]"
MD5_SRC_EXPECT="ae44293e969101d1cf0a93cbe9b99f75"
MD5_PATCH_EXPECT="0e1da8b326f49728e9394f98a53ffd35"

md5of() { /opt/usr/nx-ks/busybox md5sum "$1" 2>/dev/null | awk '{print $1}'; }

echo "== dicam T2 installer =="

# ---- 0. 前置检查 ----
[ -f "$PATCH" ] || { echo "!! 缺补丁体：$PATCH（先用 push/sync 把它拷进相机）"; exit 1; }
[ -f "$TARGET" ] || { echo "!! 找不到目标：$TARGET"; exit 1; }

# ---- 1. 首次安装：备份官方件（只做一次） ----
if [ ! -f "$ORIG" ]; then
    cp -f "$TARGET" "$ORIG" || { echo "!! 备份失败"; exit 1; }
    echo "   已备份官方件 → $ORIG"
fi

# ---- 2. 校验（源 / 补丁） ----
echo "   备份 md5: $(md5of "$ORIG")  （期望 $MD5_SRC_EXPECT）"
m=$(md5of "$PATCH")
echo "   补丁 md5: $m  （期望 $MD5_PATCH_EXPECT）"
if [ "$m" != "$MD5_PATCH_EXPECT" ]; then
    echo "   ⚠ 补丁 md5 与记录不符（可能是 v2 桩版本）——继续，但请记录实际值"
fi
chmod +x "$PATCH" 2>/dev/null

# ---- 3. init.sh 追加重挂块（幂等：已存在则跳过） ----
if grep -q "$MARK" "$INITS" 2>/dev/null; then
    echo "   init.sh 已含 $MARK 块，跳过"
else
    cp -f "$INITS" "$INITS.dicam.bak" 2>/dev/null
    cat >> "$INITS" << 'EOF'

# [dicam-T2] di-camera-app 补丁以 bind-mount 形式生效（补丁体在 p14，固件刷写不丢）
#   决策：MOD_DECISION_P7_APP_2026-10-12.md D-5；本块必须早于 di-camera-app.service
if [ -f /opt/usr/nx-ks/dicam/di-camera-app.c2 ]; then
    mount --bind /opt/usr/nx-ks/dicam/di-camera-app.c2 \
        /usr/apps/com.samsung.di-camera-app/bin/di-camera-app 2>/dev/null
fi
EOF
    echo "   已向 init.sh 追加重挂块（原文件备份为 init.sh.dicam.bak）"
fi

# ---- 4. 立即生效（本次不重启相机，只重启 App） ----
if ! mount | grep -q "di-camera-app/bin/di-camera-app"; then
    mount --bind "$PATCH" "$TARGET" && echo "   已 bind-mount 生效" || { echo "!! bind 失败"; exit 1; }
else
    echo "   已有 bind-mount"
fi

echo "   restart di-camera-app ...（画面会闪一下，属正常）"
systemctl restart di-camera-app 2>/dev/null
sleep 3

# ---- 5. 收尾状态 ----
echo "---- 状态 ----"
mount | grep di-camera-app || echo "   (mount 表里没有 → 见 status 脚本排查)"
echo "   目标现 md5: $(md5of "$TARGET")"
echo "== 完成。判据：st app help 有回显 + st app film \"…\" 能执行 =="
