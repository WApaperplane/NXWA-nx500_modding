#!/bin/sh
U=/opt/usr/nx-ks/flab_ui.sh
L=/mnt/mmc/filmlab/x11.log
O=/mnt/mmc/_pwtest/d4.txt
: > $O
sh $U status >> $O 2>&1
echo "--- send down x2 ---" >> $O
sh $U down >> $O 2>&1
sleep 1
sh $U down >> $O 2>&1
sleep 1
echo "--- send right x3 ---" >> $O
sh $U right >> $O 2>&1
sleep 1
sh $U right >> $O 2>&1
sleep 1
sh $U right >> $O 2>&1
sleep 1
echo "--- send apply ---" >> $O
sh $U apply >> $O 2>&1
sleep 3
echo "--- X11 log tail ---" >> $O
tail -c 350 $L 2>/dev/null | tr -d '\r' >> $O
echo "" >> $O
echo "--- slot9 读回（apply 效果）---" >> $O
prefman get 0 0x0a410 l 2>/dev/null | tr -d '\r' | grep -ao 'value = [-0-9]*' >> $O
prefman get 0 0x0a414 l 2>/dev/null | tr -d '\r' | grep -ao 'value = [-0-9]*' >> $O
echo "--- PW_TYPE ---" >> $O
st cap capdtm getusr 20 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p' >> $O
echo "D4_DONE" >> $O
