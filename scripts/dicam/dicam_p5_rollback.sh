#!/bin/bash
# =====================================================================
# [P5] unit 注入恢复器：移除 di-camera-app.service 的 ExecStartPre 前置挂载行
#   与 dicam_p5_install.sh 互逆；幂等。
#   动作：remount rw → 精准删除 t2_premount 行 → 自检（必须 0 命中）→ sync → 恢复 ro
#         → daemon-reload
#   ⛔ 不 restart（卡死）；恢复官方加载 = 正常关机→开机。
#   v1 · 2026-10-15 · 离线编写（未上机验证）
# =====================================================================

UNIT=/usr/lib/systemd/system/di-camera-app.service

echo "== dicam P5 rollback =="

[ -f "$UNIT" ] || { echo "!! unit 不存在：$UNIT"; exit 1; }

if ! grep -q "t2_premount.sh" "$UNIT" 2>/dev/null; then
    echo "   unit 未含 t2_premount 行，无需恢复"
else
    if ! mount -o remount,rw / 2>/dev/null; then
        echo "!! remount rw / 失败，无法恢复"; exit 1
    fi

    # 纯 POSIX sh 精准删除（跳过含 t2_premount.sh 的行）
    : > "$UNIT.p5.new" 2>/dev/null || { mount -o remount,ro /; echo "!! 写临时文件失败"; exit 1; }
    while IFS= read -r l || [ -n "$l" ]; do
        case "$l" in
            *t2_premount.sh*) : ;;          # 丢弃
            *) printf '%s\n' "$l" >> "$UNIT.p5.new" ;;
        esac
    done < "$UNIT"
    mv -f "$UNIT.p5.new" "$UNIT"

    # 自检：必须 0 命中
    n=$(grep -c "t2_premount.sh" "$UNIT" 2>/dev/null)
    if [ "$n" != "0" ]; then
        echo "!! 恢复自检失败（仍命中 $n 次）——请人工检查 $UNIT（备份：/opt/usr/nx-ks/dicam/di-camera-app.service.p5.bak）"
        sync; sync; sync
        mount -o remount,ro / 2>/dev/null
        exit 1
    fi
    sync; sync; sync
    mount -o remount,ro / 2>/dev/null
    echo "   已移除 ExecStartPre 前置行"
fi

systemctl daemon-reload 2>/dev/null && echo "   daemon-reload OK" || echo "   （daemon-reload 跳过）"

echo "== 完成。当前运行进程不变；恢复官方加载 = 正常关机→开机（禁 restart）。=="
echo "== 注：init.sh 复挂块（若在）不受本脚本影响——如需一并解除，跑 dicam_patch_rollback.sh。 =="
