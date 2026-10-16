#!/bin/bash
# =====================================================================
# [P5] unit 注入器：为 di-camera-app.service 增加 ExecStartPre 前置挂载
#   裁决：T2_DELIVERY_REVISION_2026-10-15 §3-a（P5 前置；2026-10-15 拍板）
#
#   动作：
#     1) 确保 t2_premount.sh 在 /opt/usr/nx-ks/dicam/ 且可执行（幂等）
#     2) remount rw 根 → 备份 unit → 在 ExecStart= 行前注入 ExecStartPre 行（幂等）
#        → 自检（命中数必须 == 1）→ sync → 恢复 ro
#     3) systemctl daemon-reload（安全实测过；不触发任何 App 重启）
#
#   效果：从**下一次正常开机**起，mount 在 App exec 之前就位（时序硬保证——
#         解决「init.sh 晚 25s」缺口）。
#   ⛔ 全程禁 restart（restart di-camera-app = 卡死整机，10-13 实测）。
#   恢复：dicam_p5_rollback.sh
#   刷机后：rootfs 被官方镜像重写 ⇒ 本注入被冲掉 ⇒ 需重跑本脚本（见文档 §6）。
#
#   用法：sh /opt/usr/nx-ks/dicam/dicam_p5_install.sh
#   v1 · 2026-10-15 · 离线编写（未上机验证）
# =====================================================================

D=/opt/usr/nx-ks
PD=$D/dicam
UNIT=/usr/lib/systemd/system/di-camera-app.service
PRE=$PD/t2_premount.sh
BAK=$PD/di-camera-app.service.p5.bak
LINE='ExecStartPre=-/opt/usr/nx-ks/dicam/t2_premount.sh'

echo "== dicam P5 installer（unit 前置挂载注入） =="

# ---- 0. 前置检查 ----
[ -f "$UNIT" ] || { echo "!! unit 不存在：$UNIT"; exit 1; }
[ -f "$PRE"  ] || { echo "!! 缺 $PRE（请先把 scripts/dicam/ 同步到相机）"; exit 1; }
chmod +x "$PRE" 2>/dev/null

# ---- 1. 幂等检查 ----
if grep -q "t2_premount.sh" "$UNIT"; then
    echo "   unit 已含 t2_premount 行，跳过注入"
else
    # ---- 2. remount rw ----
    if ! mount -o remount,rw / 2>/dev/null; then
        echo "!! remount rw / 失败（rootfs 只读，无法注入）"; exit 1
    fi

    # ---- 3. 备份（仅首次；放 p14，不占 rootfs） ----
    [ -f "$BAK" ] || cp -f "$UNIT" "$BAK" 2>/dev/null

    # ---- 4. 注入（纯 POSIX sh 逐行改写；busybox 全兼容） ----
    done_flag=0
    : > "$UNIT.p5.new" 2>/dev/null || { mount -o remount,ro /; echo "!! 写临时文件失败"; exit 1; }
    while IFS= read -r l || [ -n "$l" ]; do
        if [ "$done_flag" = "0" ]; then
            case "$l" in
                ExecStart=*)
                    printf '%s\n' "$LINE" >> "$UNIT.p5.new"
                    done_flag=1
                    ;;
            esac
        fi
        printf '%s\n' "$l" >> "$UNIT.p5.new"
    done < "$UNIT"

    if [ "$done_flag" != "1" ]; then
        rm -f "$UNIT.p5.new"
        mount -o remount,ro / 2>/dev/null
        echo "!! 未找到 ExecStart= 行——unit 形态异常，未做修改"
        exit 1
    fi
    mv -f "$UNIT.p5.new" "$UNIT"

    # ---- 5. 自检（命中数必须恰为 1） ----
    n=$(grep -c "t2_premount.sh" "$UNIT" 2>/dev/null)
    if [ "$n" != "1" ]; then
        echo "!! 注入自检失败（命中 $n 次）——从备份恢复"
        [ -f "$BAK" ] && cp -f "$BAK" "$UNIT"
        sync; sync; sync
        mount -o remount,ro / 2>/dev/null
        exit 1
    fi
    sync; sync; sync
    mount -o remount,ro / 2>/dev/null
    echo "   已注入：$LINE"
fi

# ---- 6. daemon-reload（安全；使 systemd 立即重读 unit 缓存） ----
systemctl daemon-reload 2>/dev/null && echo "   daemon-reload OK" || echo "   （daemon-reload 跳过）"

# ---- 7. 展示结果 ----
echo "---- unit [Service] 段现貌 ----"
sed -n '/\[Service\]/,/^$/p' "$UNIT" 2>/dev/null | head -12

echo "== 完成。生效 = 下一次【正常关机→开机】（systemd 在 App exec 前调用 t2_premount.sh）。=="
echo "== ⛔ 禁 restart。开机后验证：sh /opt/usr/nx-ks/dicam/dicam_patch_status.sh（应显示 mount 在位 + P5 行在位） =="
