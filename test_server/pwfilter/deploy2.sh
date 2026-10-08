#!/bin/sh
#=====================================================================
# deploy2.sh — FilmLab 第二阶段部署（cycle + 按键绑定）
#=====================================================================
B=/opt/usr/nx-ks/busybox
S=/mnt/mmc/filmlab
D=/opt/usr/nx-ks
O=/mnt/mmc/_pwtest/deploy2.txt

: > $O
say() { echo "$*" >> $O; }

# 1. 清掉可能残留的 X11
for p in /proc/[0-9]*; do
  c=$($B cat $p/comm 2>/dev/null)
  [ "$c" = "nxflab.arm" ] && { kill -9 ${p#/proc/} 2>/dev/null; say "killed stale x11 $p"; }
done

# 2. 部署引擎（从 SD 卡读，FTP 已放好）
$B cp $S/filmlab.sh $D/filmlab.sh && $B chmod 755 $D/filmlab.sh && say "OK filmlab.sh ($($B wc -c < $D/filmlab.sh) bytes)"

# 3. 按键脚本
$B cp $S/EV_FLAB.sh $D/EV_FLAB.sh && $B chmod 755 $D/EV_FLAB.sh && say "OK EV_FLAB.sh"

# 4. 备份并挂到 EV_S1
if [ ! -f $D/EV_S1.sh.orig ]; then
  $B cp $D/EV_S1.sh $D/EV_S1.sh.orig && say "backed up EV_S1.sh"
fi
# 追加调用（只追加一次）
if ! $B grep -qa EV_FLAB $D/EV_S1.sh; then
  echo "# --- FilmLab 配方轮换（社区 mod 框架按键绑定）---" >> $D/EV_S1.sh
  echo "/opt/usr/nx-ks/EV_FLAB.sh" >> $D/EV_S1.sh
  say "hooked into EV_S1.sh"
else
  say "EV_S1.sh already hooked"
fi

# 5. 测 cycle 三次
say ""
say "=== cycle test x3 ==="
$D/filmlab.sh cycle >> $O 2>&1
$D/filmlab.sh cycle >> $O 2>&1
$D/filmlab.sh cycle >> $O 2>&1

# 6. 验证槽位
say ""
say "=== slot9 after 3x cycle (should be trix400: 100/100/100 SAT=0) ==="
say "R=$(prefman get 0 0x0a410 l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p')"
say "G=$(prefman get 0 0x0a414 l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p')"
say "B=$(prefman get 0 0x0a418 l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p')"
say "SAT=$(prefman get 0 0x0a4e0 l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p')"
say "PW_TYPE=$(st cap capdtm getusr 20 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')"
say "cur.idx=$(cat /mnt/mmc/filmlab/cur.idx 2>/dev/null)"

# 7. EV_S1.sh 尾部确认
say ""
say "=== EV_S1.sh tail ==="
$B tail -4 $D/EV_S1.sh >> $O

say ""
say "DEPLOY2_DONE"
