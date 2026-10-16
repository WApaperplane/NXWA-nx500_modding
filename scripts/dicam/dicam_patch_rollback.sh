#!/bin/bash
# =====================================================================
# [T2] di-camera-app 补丁卸载器（相机端执行 / 幂等 / 与 install 互逆）
#   1) umount 绑定
#   2) 从 init.sh 删除 [dicam-T2] 块（连同其注释两行）
#   3) 恢复官方件：umount 后即失效；恢复【官方件运行】需正常关机→开机（禁用 restart）
#   补丁体与备份【保留】在 /opt/usr/nx-ks/dicam/（可再次 install）
#   决策：docs/current/MOD_DECISION_P7_APP_2026-10-12.md D-5
#   ★ 10-15 修订：删除 `systemctl restart di-camera-app`（10-13 实测会整机卡死，
#     机型有 hibernation 快照联锁；见 CAMERA_ONLINE_PROBE_2026-10-13 §2 / 附 C）
#     —— 改走「正常关机→开机」恢复路径（与 NATIVE_UI_ROADMAP_2026-10-15 §5 对齐）。
# =====================================================================

D=/opt/usr/nx-ks
PD=$D/dicam
TARGET=/usr/apps/com.samsung.di-camera-app/bin/di-camera-app
INITS=$D/init.sh
MARK="[dicam-T2]"

echo "== dicam T2 rollback =="

# ---- 1. umount（可能挂多次，循环卸干净） ----
n=0
while mount | grep -q "di-camera-app/bin/di-camera-app"; do
    umount "$TARGET" 2>/dev/null || break
    n=$((n + 1))
    [ $n -gt 5 ] && break
done
echo "   已 umount $n 次"

# ---- 2. 清 init.sh 块（删 注释2行 + if/fi 共6行） ----
if grep -q "$MARK" "$INITS" 2>/dev/null; then
    /opt/usr/nx-ks/busybox sed -i "/$MARK/,/^fi$/d" "$INITS" 2>/dev/null \
        || sed -i "/$MARK/,/^fi$/d" "$INITS"
    # 上面 sed 会连注释行一起删；再兜底删掉可能残留的孤立注释行
    # （含旧版「本块必须早于…」注释与新版「10-15 修订…T2_DELIVERY_REVISION」注释）
    /opt/usr/nx-ks/busybox sed -i '/di-camera-app 补丁以 bind-mount 形式生效/d;/本块必须早于 di-camera-app.service/d;/T2_DELIVERY_REVISION_2026-10-15.md/d' "$INITS" 2>/dev/null
    if grep -q "$MARK" "$INITS"; then
        echo "   !! 自动清理失败，请手工编辑 $INITS（删除 $MARK 块）"
    else
        echo "   已从 init.sh 移除重挂块"
    fi
else
    echo "   init.sh 无 $MARK 块，跳过"
fi

# ---- 3. 恢复官方件运行（★ 10-15 修订：禁用 restart） ----
# umount 已完成 + init.sh 块已清 ⇒ 下次开机不会再挂补丁体。
# ⛔ 不执行 `systemctl restart di-camera-app`：10-13 实测会整机卡死（须物理重启）。
# ⇒ 当前运行进程仍是补丁件，**恢复官方件运行需正常关机→开机一次**。
echo "   已解除挂载与钩子。恢复官方件运行：请正常关机→开机（禁止 restart，会卡死整机）。"
echo "   只读复查：sh /opt/usr/nx-ks/dicam/dicam_patch_status.sh"

echo "---- 状态 ----"
mount | grep di-camera-app || echo "   无 bind-mount ✓"
echo "== 完成：挂载与钩子已解除；当前进程仍是补丁件，自然重启后回到官方件 =="
echo "== 恢复判据（st app uscom 又能输出 UserSpec dump 表）需在正常关机→开机后核对 =="
