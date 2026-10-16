#!/bin/bash
# =====================================================================
# [M2] 配方名 locale 部署器（相机端；只动 p14，不碰 rootfs）
#   设计：docs/current/M2_RECIPE_NAME_DESIGN_2026-10-16.md
#   用途：菜单「画面向导 → 自定义 1/2/3」显示名 → 三个配方名（样机）
#
#   用法：sh m2_locale.sh deploy|remove|status
#     deploy : SD:/mnt/mmc/m2-locale/di-camera-app.zh_CN.m2sample.mo
#              → /opt/usr/nx-ks/locale/zh_CN/di-camera-app.mo（md5 双校验）
#     remove : 删除部署件（正常开关机后恢复官方文案）
#     status : 部署件 / 挂载 / P5 行 / 判定
#
#   生效：正常关机→开机（t2_premount.sh 经 unit ExecStartPre 条件挂载）
#   前置：P5 已安装（相机端 sh /opt/usr/nx-ks/dicam/dicam_p5_install.sh）
#   ⛔ 禁 restart di-camera-app（卡死整机）
#   v1 · 2026-10-16 · 离线编写（未上机验证）
# =====================================================================

D=/opt/usr/nx-ks
SRCDIR=/mnt/mmc/m2-locale
LK=$D/locale/zh_CN
DEP=$LK/di-camera-app.mo
TGT=/usr/share/locale/zh_CN/LC_MESSAGES/di-camera-app.mo
BB=$D/busybox
UNIT=/usr/lib/systemd/system/di-camera-app.service

md5of() { $BB md5sum "$1" 2>/dev/null | cut -d' ' -f1; }

case "$1" in
deploy)
    SRC=$SRCDIR/di-camera-app.zh_CN.m2sample.mo
    [ -f "$SRC" ] || { echo "!! 缺 $SRC（请先经 FTP 把样机目录 fw/v1.12/dicam/locale/ 的内容上传到 SD 的 m2-locale/）"; exit 1; }
    mkdir -p "$LK" || { echo "!! 无法创建 $LK"; exit 1; }
    cp -f "$SRC" "$DEP" || { echo "!! 拷贝失败"; exit 1; }
    SRCV=$(md5of "$SRC"); GOT=$(md5of "$DEP")
    echo "  src md5: $SRCV"
    echo "  dep md5: $GOT"
    if [ "$GOT" != "$SRCV" ]; then
        echo "!! 拷贝校验失败（双端不一致）——请重传"; exit 1
    fi
    EXP=$(head -1 "$SRCDIR/MANIFEST.md5" 2>/dev/null | cut -d' ' -f1)
    if [ -n "$EXP" ]; then
        if [ "$GOT" = "$EXP" ]; then
            echo "  manifest 校验: 一致 ✓"
        else
            echo "!! manifest 校验不符（期望 $EXP）——请核对样本来源"; exit 1
        fi
    else
        echo "  （无 MANIFEST.md5，跳过期望值比对；请人工核对部署 md5）"
    fi
    echo "== 已部署到 p14。生效 = 正常关机→开机（禁 restart）。=="
    echo "== 开机后：status 复查 + 看菜单「画面向导」内三个自定义项显示名 =="
    ;;
remove)
    if [ -f "$DEP" ]; then
        rm -f "$DEP" && echo "  已移除 $DEP（正常关机开机后恢复官方文案）"
    else
        echo "  无部署件，无需移除"
    fi
    ;;
status)
    echo "===== M2 locale status ====="
    echo "-- 部署件（p14） --"
    if [ -f "$DEP" ]; then echo "  $(md5of "$DEP")  $DEP"; else echo "  <缺失> $DEP（= 未部署/已回退；语义 = 不改名）"; fi
    echo "-- 挂载状态 --"
    mount | grep "LC_MESSAGES/di-camera-app.mo" || echo "  (未挂载：未开机生效 / P5 未装 / 部署件缺失)"
    echo "-- P5 前置（unit ExecStartPre） --"
    grep -q "t2_premount.sh" "$UNIT" 2>/dev/null && echo "  ✓ unit 含前置行" || echo "  ✗ unit 未含（先跑 dicam_p5_install.sh）"
    echo "-- 判定（目标路径当前内容 vs 部署件） --"
    cur=$(md5of "$TGT"); dep=$(md5of "$DEP")
    if [ -n "$dep" ] && [ "$cur" = "$dep" ]; then
        echo "  ⇒ 目标 = 部署件（M2 生效中）"
    else
        echo "  ⇒ 目标 ≠ 部署件（官方件或未挂载；当前 md5: $cur）"
    fi
    echo "===== end ====="
    ;;
*)
    echo "用法: sh m2_locale.sh deploy|remove|status"
    exit 2
    ;;
esac
exit 0
