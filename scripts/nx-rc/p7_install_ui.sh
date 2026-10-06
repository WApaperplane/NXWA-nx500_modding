#!/bin/sh
#=====================================================================
# p7_install_ui.sh — 把 P7 功能菜单挂进 mod_gui（一次性）
#---------------------------------------------------------------------
# 机制（社区框架）：
#   ★ 改 gui_ini.NX500 会被 loadgui.sh → gen_menu.sh → gui_tpl.NX500 覆盖
#   ⇒ 必须改【模板】 gui_tpl.NX500
#   ⇒ 本脚本备份原模板，再安装带 P7 项的新模板
#
# ★ 安全设计：P7 刷写菜单默认【不显示】
#   主模板里的 "P7 固件" 入口指向 gui_p7.NX500，
#   而 gui_p7flash.NX500 内的实际刷写由 p7flash.ok 门控。
#   卸载时由 uninstall.sh 清理。
#=====================================================================

BB=/opt/usr/nx-ks/busybox
SRC=/mnt/mmc/scripts/nx-rc
DST=/opt/usr/nx-ks

echo "==== 安装 P7 功能菜单 ===="

[ -d "$DST" ] || { echo "!! $DST 不存在 —— NX-KS mod 未安装？"; exit 1; }

# ---- 1. 复制新页面 ----
for f in gui_p7.NX500 gui_p7color.NX500 gui_p7ch.NX500 gui_p7flash.NX500 \
         gui_p7dev.NX500 gui_lutimport.NX500; do
  if [ -f "$SRC/$f" ]; then
    cp "$SRC/$f" "$DST/$f" && echo "  [页面] $f"
  else
    echo "  [跳过] $f 不存在"
  fi
done

# ---- 2. 复制脚本 ----
for f in 3dlut_set.sh 3dlut_stat.sh 3dlut_ch.sh iqr_dump.sh \
         p7_status.sh p7_checkimg.sh p7_backup.sh p7_verify.sh \
         p7_flash_slp.sh p7_recover_official.sh p7_restore_baseline.sh \
         lut_scan.sh lut_pick.sh lut_help.sh; do
  if [ -f "$SRC/$f" ]; then
    cp "$SRC/$f" "$DST/$f"
    chmod +x "$DST/$f"
    echo "  [脚本] $f"
  else
    echo "  [跳过] $f 不存在"
  fi
done

# ---- 2b. ★ 复制 ARM 工具（编译产物在 sysarch/）----
SYS=/mnt/mmc/scripts/sysarch
for f in lutload.arm; do
  if [ -f "$SYS/$f" ]; then
    cp "$SYS/$f" "$DST/$f"
    chmod +x "$DST/$f"
    echo "  [ARM ] $f"
  elif [ -f "$SRC/$f" ]; then
    cp "$SRC/$f" "$DST/$f"; chmod +x "$DST/$f"
    echo "  [ARM ] $f（来自 nx-rc）"
  else
    echo "  [缺失] ★ $f —— LUT 导入功能不可用"
    echo "          需先编译：cd test_server/sysarch && zig cc -O0 -o lutload.arm lutload.c"
  fi
done

# ---- 2c. 建 LUT 库目录 ----
mkdir -p /mnt/mmc/luts && echo "  [目录] /mnt/mmc/luts"
mkdir -p /mnt/mmc/filmlab

# ---- 3. 换主菜单模板（先备份）----
TPL=$DST/gui_tpl.NX500
if [ -f "$TPL" ] && [ ! -f "$TPL.pre_p7" ]; then
  cp "$TPL" "$TPL.pre_p7" && echo "  [备份] gui_tpl.NX500 → gui_tpl.NX500.pre_p7"
fi

if [ -f "$SRC/gui_tpl.NX500.p7" ]; then
  cp "$SRC/gui_tpl.NX500.p7" "$TPL" && echo "  [模板] 主菜单已含 P7 入口"
else
  echo "  [跳过] gui_tpl.NX500.p7 不存在，主菜单未改"
fi

echo
echo "★ 门控文件 p7flash.ok【未创建】⇒ 刷写功能保持隐藏"
echo "  确认 p7 备份与官方退路都就绪后，手动创建："
echo "    touch /mnt/mmc/filmlab/p7flash.ok"
echo
echo "完成。按 EV 键两次进入菜单，'P7 固件' 应出现在主菜单。"
