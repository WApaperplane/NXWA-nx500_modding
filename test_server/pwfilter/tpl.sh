#!/bin/sh
B=/opt/usr/nx-ks/busybox
O=/mnt/mmc/_pwtest/tpl.txt
: > $O
echo "=== gui_tpl.NX500 模板内容 ===" >> $O
cat -A /opt/usr/nx-ks/gui_tpl.NX500 2>&1 | $B sed 's/\$$//' >> $O
echo "" >> $O
echo "=== gen_menu.sh 尾部 ===" >> $O
tail -12 /opt/usr/nx-ks/gen_menu.sh >> $O 2>&1
echo "" >> $O
echo "=== gui_tpl.NX1 是否存在 ===" >> $O
ls -la /opt/usr/nx-ks/gui_tpl.NX* 2>&1 >> $O
echo "TPL_DONE" >> $O
