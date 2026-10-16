#!/bin/bash
# =====================================================================
# [T2/P5 + M2] 前置挂载脚本 —— 被 di-camera-app.service 的 ExecStartPre 调用
#   裁决：T2_DELIVERY_REVISION_2026-10-15 §3-a（P5 前置，2026-10-15 拍板）
#   语义：在 di-camera-app 每次 exec 之前，把 p14 中的「替换件」bind-mount 到目标路径。
#   - 多条目：每条目独立判断（源不存在 ⇒ 该条目静默禁用；互不影响）
#       · 条目1 [T2]：dicam 命令桥补丁体  → /usr/apps/com.samsung.di-camera-app/bin/di-camera-app
#       · 条目2 [M2]：配方名 locale 样机  → /usr/share/locale/zh_CN/LC_MESSAGES/di-camera-app.mo
#         （M2_RECIPE_NAME_DESIGN_2026-10-16；文件由 dicam/m2_locale.sh 部署进 p14）
#   - 幂等：已挂载则跳过（与 init.sh 复挂块并存安全——先挂者生效，后来者跳过）
#   - 容错：任何失败皆 exit 0（退化为原厂行为 = 禁用语义）
#   - unit 中以 `ExecStartPre=-…` 前缀调用 ⇒ 不阻止 App 启动
#   ⛔ 本脚本绝不 restart 任何服务（该机型 restart di-camera-app = 卡死整机）
#   v2 · 2026-10-16 · 多条目化（加 M2 locale）；单条目行为与 v1 一致
#   v1 · 2026-10-15 · 离线编写（未上机验证；上机前建议先 dry-run：手工执行一次看 mount 表）
# =====================================================================

LOG=/tmp/dicam_p5_mount.log

do_mount() {
    SRC="$1"; DST="$2"; TAG="$3"
    [ -f "$SRC" ] || return 0            # 源不存在 ⇒ 该条目禁用（静默）
    [ -f "$DST" ] || return 0            # 目标不存在 ⇒ 跳过（防御）
    mount | grep -q "$DST" && return 0   # 已挂载 ⇒ 幂等跳过
    if mount --bind "$SRC" "$DST" 2>/dev/null; then
        # 最小审计日志（tmpfs；失败静默）
        echo "[$TAG] mount ok: $DST <- $SRC @ $(cut -d' ' -f1 /proc/uptime 2>/dev/null)s" >> "$LOG" 2>/dev/null
    fi
    return 0
}

do_mount /opt/usr/nx-ks/dicam/di-camera-app.c2 \
         /usr/apps/com.samsung.di-camera-app/bin/di-camera-app \
         T2

do_mount /opt/usr/nx-ks/locale/zh_CN/di-camera-app.mo \
         /usr/share/locale/zh_CN/LC_MESSAGES/di-camera-app.mo \
         M2

exit 0
