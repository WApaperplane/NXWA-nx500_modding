#!/bin/sh
#=====================================================================
# f5.sh — FilmLab 控制通道验证（一次跑完，FTP 传/拉）
#=====================================================================
# 验证目标：
#   1. X11 能活过启动它的 shell（SIGHUP 不杀）
#   2. /tmp/flab_cmd 握手协议能被识别
#   3. down/right/apply 三个命令生效
#   4. quit 能关窗
#=====================================================================
B=/opt/usr/nx-ks/busybox
L=/mnt/mmc/filmlab/x11.log
O=/mnt/mmc/_pwtest/f5.txt
CMD=/tmp/flab_cmd
BIN=/opt/usr/nx-ks/filmlab/nxflab.arm
RCP=/mnt/mmc/filmlab/recipes.txt

: > $O
say() { echo "$*" >> $O; }

# ---------- 清理 ----------
for p in /proc/[0-9]*; do
  c=$($B cat $p/comm 2>/dev/null)
  [ "$c" = "nxflab.arm" ] && kill -9 ${p#/proc/} 2>/dev/null
done
rm -f $L $CMD
: > $CMD
say "=== 0. cleaned ==="

# ---------- 启动 ----------
setsid $BIN $RCP $L 120 </dev/null >/dev/null 2>&1 &
say "launched"

# 等它真正起来（最多 20 次 x 1 秒）
i=0
PID=""
while [ $i -lt 20 ]; do
  for p in /proc/[0-9]*; do
    c=$($B cat $p/comm 2>/dev/null)
    [ "$c" = "nxflab.arm" ] && { PID=${p#/proc/}; break; }
  done
  [ -n "$PID" ] && break
  i=$((i+1))
  $B sleep 1
done
if [ -z "$PID" ]; then
  say "FAIL not started"
  say "log: $($B cat $L 2>/dev/null | tr -d '\r')"
  echo "F5_DONE" >> $O
  exit 1
fi
say "pid=$PID started"

# ---------- 关键验证：shell 退出后是否存活 ----------
say "--- shell will exit now; X11 must survive ---"
echo "SHELL_EXIT_MARK" >> $O

# ============================================================
# ★ 下面这段由第二条 telnet/FTP 触发（X11 已在跑）
# ============================================================
if [ -n "$FLAB_PHASE2" ]; then
  i=0
  while [ $i -lt 15 ]; do
    $B cat /proc/$PID/comm >/dev/null 2>&1 && break
    i=$((i+1)); $B sleep 1
  done
  if $B cat /proc/$PID/comm >/dev/null 2>&1; then
    say "PHASE2: pid=$PID SURVIVED shell exit  (PASS)"
  else
    say "PHASE2: pid=$PID DIED with shell  (FAIL)"
    say "log: $($B cat $L 2>/dev/null | tr -d '\r')"
    echo "F5_DONE" >> $O
    exit 1
  fi

  # ---------- 命令测试 ----------
  say "--- cmd test: down ---"
  echo down > $CMD
  $B sleep 2
  say "cmd file size after down: $($B wc -c < $CMD) (0 = X11 已读走)"
  say "--- cmd test: right ---"
  echo right > $CMD
  $B sleep 2
  say "--- cmd test: apply ---"
  echo apply > $CMD
  $B sleep 4

  say "--- x11 log ---"
  $B cat $L 2>/dev/null | tr -d '\r' >> $O
  say ""
  say "--- slot9 after apply (velvia50: R=102 SAT=14 G=110 B=109) ---"
  say "R=$(prefman get 0 0x0a410 l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p')"
  say "G=$(prefman get 0 0x0a414 l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p')"
  say "B=$(prefman get 0 0x0a418 l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p')"
  say "SAT=$(prefman get 0 0x0a4e0 l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p')"
  say "--- PW_TYPE ---"
  st cap capdtm getusr 20 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p' >> $O

  # ---------- quit 测试 ----------
  say "--- cmd test: quit ---"
  echo quit > $CMD
  $B sleep 3
  if $B cat /proc/$PID/comm >/dev/null 2>&1; then
    say "QUIT: still alive (FAIL)"
    kill -9 $PID 2>/dev/null
  else
    say "QUIT: exited (PASS)"
  fi
  say "--- final log ---"
  $B cat $L 2>/dev/null | tr -d '\r' >> $O
fi

echo "F5_DONE" >> $O
