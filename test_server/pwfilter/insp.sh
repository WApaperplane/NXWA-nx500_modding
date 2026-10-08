#!/bin/sh
B=/opt/usr/nx-ks/busybox
O=/mnt/mmc/_pwtest/insp.txt
: > $O
echo "=== loadgui.sh 全文 ===" >> $O
cat /opt/usr/nx-ks/loadgui.sh >> $O 2>&1
echo "" >> $O
echo "=== gui_*.NX500 清单 ===" >> $O
ls -la /opt/usr/nx-ks/gui_*.NX500 2>&1 | $B sed 's/^/  /' >> $O
echo "" >> $O
echo "=== 我的 filmlab 菜单在不在 ===" >> $O
ls -la /opt/usr/nx-ks/gui_filmlab*.NX500 2>&1 >> $O
echo "" >> $O
echo "=== version.info ===" >> $O
cat /etc/version.info >> $O 2>&1
echo "" >> $O
echo "=== 有没有 info/install 类脚本 ===" >> $O
ls /opt/usr/nx-ks/*.sh 2>/dev/null | $B sed 's/^/  /' >> $O
echo "INSP_DONE" >> $O
