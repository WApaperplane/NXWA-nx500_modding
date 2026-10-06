#!/bin/sh
echo "--- 直接跑 status ---"
sh /opt/usr/nx-ks/flab_ui.sh status 2>&1
echo "RC=$?"
echo ""
echo "--- 手工解析 args 测试 ---"
sh -c 'echo "arg1=[$1]" ' _ hello
echo ""
echo "--- setsid 存在? ---"
ls -la /usr/bin/setsid
echo ""
echo "--- nxflab 在? ---"
ls -la /opt/usr/nx-ks/filmlab/
echo "D2_DONE"
