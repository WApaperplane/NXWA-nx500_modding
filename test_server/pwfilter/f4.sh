#!/bin/sh
B=/opt/usr/nx-ks/busybox
L=/mnt/mmc/filmlab/x11.log
O=/mnt/mmc/_pwtest/f4.txt
: > $O
rm -f $L /tmp/flab_cmd
: > /tmp/flab_cmd
# 180 秒超时，留足时间
/opt/usr/nx-ks/filmlab/nxflab.arm /mnt/mmc/filmlab/recipes.txt $L 180 </dev/null >/dev/null 2>&1 &
P=$!
echo "pid=$P" >> $O
sleep 4
echo "--- 存活? ---" >> $O
$B cat /proc/$P/comm >/dev/null 2>&1 && echo "ALIVE" >> $O || echo "GONE" >> $O
echo "--- 发 down ---" >> $O
echo down > /tmp/flab_cmd
sleep 2
echo "cmd文件大小: $($B wc -c < /tmp/flab_cmd)" >> $O
echo "--- 发 apply ---" >> $O
echo apply > /tmp/flab_cmd
sleep 5
echo "--- log ---" >> $O
$B cat $L 2>/dev/null | tr -d '\r' >> $O
echo "" >> $O
echo "--- slot9 R/SAT (velvia=102/14) ---" >> $O
prefman get 0 0x0a410 l 2>/dev/null | tr -d '\r' | grep -ao 'value = [-0-9]*' >> $O
prefman get 0 0x0a4e0 l 2>/dev/null | tr -d '\r' | grep -ao 'value = [-0-9]*' >> $O
echo "--- PW_TYPE ---" >> $O
st cap capdtm getusr 20 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p' >> $O
echo "F4_DONE" >> $O
