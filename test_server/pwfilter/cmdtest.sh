#!/bin/sh
BB=/opt/usr/nx-ks/busybox
D=/opt/usr/nx-ks
LOG=/mnt/mmc/filmlab/x11.log
rm -f $LOG
$D/flab_ui.sh start
sleep 3
echo "=== X11 已启动（会盖住 LCD）==="
echo "--- 进程 ---"
for p in $($BB ls -d /proc/[0-9]* 2>/dev/null); do
  c=$($BB cat $p/comm 2>/dev/null)
  [ "$c" = "nxflab.arm" ] && echo "  running: $p"
done
echo "--- 发 down x2 ---"
$D/flab_ui.sh down; sleep 1
$D/flab_ui.sh down; sleep 1
echo "--- 发 right x3 ---"
$D/flab_ui.sh right; sleep 1
$D/flab_ui.sh right; sleep 1
$D/flab_ui.sh right; sleep 1
echo "--- 发 apply ---"
$D/flab_ui.sh apply; sleep 3
echo "--- 日志（应看到 cmd file: [...] 记录）---"
$BB cat $LOG 2>/dev/null | tr -d '\r' | $BB tail -c 400
echo ""
echo "--- 槽位读回验证 apply 是否生效 ---"
$BB prefman get 0 0x0a3ec l 2>/dev/null | tr -d '\r' | $BB grep -ao 'value = [-0-9]*'
$BB prefman get 0 0x0a3f0 l 2>/dev/null | tr -d '\r' | $BB grep -ao 'value = [-0-9]*'
echo "--- quit 测试 ---"
$D/flab_ui.sh quit; sleep 2
LEFT=0
for p in $($BB ls -d /proc/[0-9]* 2>/dev/null); do
  c=$($BB cat $p/comm 2>/dev/null)
  [ "$c" = "nxflab.arm" ] && LEFT=1
done
[ $LEFT -eq 0 ] && echo "  PASS quit 生效，进程已退出" || echo "  FAIL 进程仍在"
echo "CMDTEST_DONE"
