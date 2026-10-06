#!/bin/sh
B=/opt/usr/nx-ks/busybox
O=/mnt/mmc/_pwtest/insp2.txt
: > $O
echo "=== gui_ini.NX500 当前内容 ===" >> $O
cat /opt/usr/nx-ks/gui_ini.NX500 >> $O 2>&1
echo "" >> $O
echo "=== gui_ini.NX500.orig（我的备份）===" >> $O
cat /opt/usr/nx-ks/gui_ini.NX500.orig >> $O 2>&1
echo "" >> $O
echo "=== gen_menu.sh 全文 ===" >> $O
cat /opt/usr/nx-ks/gen_menu.sh >> $O 2>&1
echo "" >> $O
echo "=== gen_menu 用到的模板文件 ===" >> $O
ls -la /opt/usr/nx-ks/*menu* /opt/usr/nx-ks/*tpl* /opt/usr/nx-ks/*.cfg 2>&1 | $B sed 's/^/  /' >> $O
echo "INSP2_DONE" >> $O
