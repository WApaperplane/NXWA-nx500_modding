#!/bin/sh
B=/opt/usr/nx-ks/busybox
K=/opt/usr/nx-ks
L=/mnt/mmc/_fl2/guard2.log
: > $L

echo "=== 1. 备份 ===" >> $L
if [ ! -f $K/flab_guard.sh.orig ]; then
  cp $K/flab_guard.sh $K/flab_guard.sh.orig && echo "备份 → flab_guard.sh.orig" >> $L
else
  echo "备份已存在" >> $L
fi

echo "=== 2. 停掉旧 guard ===" >> $L
sh $K/flab_guard.sh stop >> $L 2>&1
$B pkill -f flab_guard 2>>$L
$B sleep 1

echo "=== 3. 部署新版本 ===" >> $L
cp /mnt/mmc/_fl2/flab_guard.sh $K/flab_guard.sh 2>>$L
chmod +x $K/flab_guard.sh
echo "行尾检查（须 23 21 2f）:" >> $L
$B od -A d -t x1 -N 3 $K/flab_guard.sh >> $L 2>&1

echo "=== 4. 语法检查 ===" >> $L
if sh -n $K/flab_guard.sh 2>>$L; then
  echo "语法 OK" >> $L
else
  echo "★ 语法错误！回滚" >> $L
  cp $K/flab_guard.sh.orig $K/flab_guard.sh
  echo "已回滚" >> $L
  exit 1
fi

echo "=== 5. 关键函数存在性 ===" >> $L
$B grep -n "^recover()\|^mark_dead()\|^iqr_alive()\|NEED=" $K/flab_guard.sh >> $L 2>&1

echo "=== 6. 归档旧日志 ===" >> $L
$B mv /mnt/mmc/filmlab/guard.log /mnt/mmc/filmlab/guard_2145.log 2>>$L
rm -f /mnt/mmc/filmlab/DEADLOCK.txt 2>>$L

echo "=== 7. 启动新 guard ===" >> $L
sh $K/flab_guard.sh start >> $L 2>&1
$B sleep 3

echo "=== 8. status ===" >> $L
sh $K/flab_guard.sh status >> $L 2>&1

echo "=== DONE ===" >> $L
