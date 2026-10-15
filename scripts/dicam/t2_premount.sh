#!/bin/bash
# =====================================================================
# [T2/P5] 前置挂载脚本 —— 被 di-camera-app.service 的 ExecStartPre 调用
#   裁决：T2_DELIVERY_REVISION_2026-10-15 §3-a（P5 前置，2026-10-15 拍板）
#   语义：在 di-camera-app 每次 exec 之前，把补丁体 bind-mount 到目标路径。
#   - 幂等：已挂载则跳过（与 init.sh 复挂块并存安全——先挂者生效，后来者跳过）
#   - 容错：补丁体不存在 ⇒ 静默退出 0（退化为原厂行为 = 禁用语义）
#   - unit 中以 `ExecStartPre=-…` 前缀调用 ⇒ 本脚本任何失败都不阻止 App 启动
#   ⛔ 本脚本绝不 restart 任何服务（该机型 restart di-camera-app = 卡死整机）
#   v1 · 2026-10-15 · 离线编写（未上机验证；上机前建议先 dry-run：手工执行一次看 mount 表）
# =====================================================================

PATCH=/opt/usr/nx-ks/dicam/di-camera-app.c2
TARGET=/usr/apps/com.samsung.di-camera-app/bin/di-camera-app

# 补丁体不存在 ⇒ 禁用（静默）
[ -f "$PATCH" ] || exit 0

# 已挂载 ⇒ 幂等跳过（可能由 init.sh 复挂块/上次会话挂过）
if mount | grep -q "$TARGET"; then
    exit 0
fi

# 挂载（失败静默——不阻止 App 启动）
if mount --bind "$PATCH" "$TARGET" 2>/dev/null; then
    # 最小审计日志（tmpfs；失败静默）
    echo "P5-mount ok: $(cat /proc/uptime 2>/dev/null | awk '{print $1}')s" >> /tmp/dicam_p5_mount.log 2>/dev/null
fi
exit 0
