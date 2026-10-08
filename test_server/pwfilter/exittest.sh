#!/bin/sh
BB=/opt/usr/nx-ks/busybox
BIN=/opt/usr/nx-ks/filmlab/nxflab.arm
RCP=/mnt/mmc/filmlab/recipes.txt
LOG=/mnt/mmc/_pwtest/nxflab.log
findpid() {
  for p in /proc/[0-9]*; do
    c=$($BB cat $p/comm 2>/dev/null)
    [ "$c" = "nxflab.arm" ] && { basename $p; return; }
  done
  echo "none"
}

echo "===== 测试 1：SIGTERM 退出（kill 默认信号）====="
rm -f $LOG
$BIN $RCP $LOG 60 &
sleep 2
P=$(findpid)
echo "  pid=$P"
if [ "$P" = "none" ]; then echo "  FAIL 没启动"; else
  kill $P 2>/dev/null
  sleep 2
  P2=$(findpid)
  if [ "$P2" = "none" ]; then echo "  PASS SIGTERM 已退出"; else
    echo "  SIGTERM 无效，试 SIGINT"; kill -2 $P 2>/dev/null; sleep 2
    P3=$(findpid)
    [ "$P3" = "none" ] && echo "  PASS SIGINT 已退出" || echo "  FAIL 仍在(PID=$P3)"
  fi
fi
echo "  log: $($BB cat $LOG 2>/dev/null | tr -d '\r' | tail -c 60)"

echo
echo "===== 测试 2：空闲超时自动退出（用 6 秒限时）====="
rm -f $LOG
$BIN $RCP $LOG 6 &
sleep 9
P=$(findpid)
if [ "$P" = "none" ]; then echo "  PASS 6秒空闲后自动退出"; else
  echo "  FAIL 仍在(PID=$P)，杀掉"; kill -9 $P
fi
echo "  log: $($BB cat $LOG 2>/dev/null | tr -d '\r' | tail -c 60)"

echo
echo "===== 测试 3：启动后立刻可见（2 秒截图用）====="
rm -f $LOG
$BIN $RCP $LOG 20 &
sleep 3
echo "  pid=$(findpid)  窗口应该已显示"
echo "  log: $($BB cat $LOG 2>/dev/null | tr -d '\r')"
echo "  现在手动 kill（模拟用户关窗）"
P=$(findpid)
[ "$P" != "none" ] && kill $P 2>/dev/null
sleep 2
echo "  退出后 pid=$(findpid)"
echo "EXITTEST_DONE"
