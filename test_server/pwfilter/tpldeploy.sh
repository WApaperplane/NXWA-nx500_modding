#!/bin/sh
#=====================================================================
# tpldeploy.sh — 把 FilmLab 挂进 mod_gui 主菜单（改模板，不是改生成结果）
#=====================================================================
# ★★★ 关键教训：gui_ini.NX500 是【生成结果】，
#     loadgui.sh 每次都会跑 gen_menu.sh 用 gui_tpl.NX500 模板覆盖它。
#     所以必须改【模板 gui_tpl.NX500】，改生成结果会被覆盖。
#=====================================================================
B=/opt/usr/nx-ks/busybox
S=/mnt/mmc/filmlab
D=/opt/usr/nx-ks
O=/mnt/mmc/_pwtest/tpldeploy.txt
: > $O
say() { echo "$*" >> $O; }

# 1. 备份模板
if [ ! -f $D/gui_tpl.NX500.orig ]; then
  $B cp $D/gui_tpl.NX500 $D/gui_tpl.NX500.orig
  say "backed up gui_tpl.NX500 -> .orig"
else
  say "gui_tpl.NX500.orig already exists"
fi

# 2. 装模板
$B cp $S/tpl.new $D/gui_tpl.NX500 && $B chmod 755 $D/gui_tpl.NX500
say "installed new template ($($B wc -c < $D/gui_tpl.NX500) bytes)"

# 3. 跑 gen_menu 重新生成
/opt/usr/nx-ks/gen_menu.sh 2>/dev/null
say "gen_menu.sh done"

# 4. 验证生成结果里有 FilmLab
say ""
say "=== gui_ini.NX500 after gen_menu ==="
$B cat $D/gui_ini.NX500 >> $O 2>&1
say ""
if $B grep -qa FilmLab $D/gui_ini.NX500; then
  say "PASS: FilmLab 已出现在生成的主菜单里"
else
  say "FAIL: 生成结果里没有 FilmLab"
fi

# 5. 检查 mod_gui 用的按钮数上限
say ""
say "=== gui_ini.NX500 按钮数 ==="
say "button 条数: $($B grep -ac '^button|' $D/gui_ini.NX500)"

# 6. 检查子菜单文件都在
say ""
say "=== FilmLab 子菜单 ==="
for f in gui_filmlab.NX500 gui_filmlab1b.NX500 gui_filmlab2.NX500 gui_filmlab3.NX500 gui_filmlab4.NX500; do
  if [ -f $D/$f ]; then say "  OK $f"; else say "  MISSING $f"; fi
done

# 7. 检查被引用的命令是否存在
say ""
say "=== 命令依赖检查 ==="
for c in /opt/usr/nx-ks/filmlab.sh /opt/usr/nx-ks/gui_exit.sh; do
  if [ -x $c ]; then say "  OK $c"; else say "  MISSING/NOT-EXEC $c"; fi
done

say ""
say "TPLDEPLOY_DONE"
