#!/bin/sh
U=/opt/usr/nx-ks/flab_ui.sh
L=/mnt/mmc/filmlab/x11.log
O=/mnt/mmc/_pwtest/full.txt
: > $O
# 长超时 60 秒，留足时间
FLAB_IDLE=60 sh $U start >> $O 2>&1
echo "--- status after start ---" >> $O
sh $U status >> $O 2>&1
# 立刻发命令
echo down > /mnt/mmc/filmlab/cmd
sleep 2
echo right > /mnt/mmc/filmlab/cmd
sleep 2
echo apply > /mnt/mmc/filmlab/cmd
sleep 4
echo "--- X11 log ---" >> $O
tail -c 400 $L 2>/dev/null | tr -d '\r' >> $O
echo "" >> $O
echo "--- slot9 R (should be recipe[1] after down) ---" >> $O
prefman get 0 0x0a410 l 2>/dev/null | tr -d '\r' | grep -ao 'value = [-0-9]*' >> $O
echo "--- slot10 R ---" >> $O
prefman get 0 0x0a414 l 2>/dev/null | tr -d '\r' | grep -ao 'value = [-0-9]*' >> $O
echo "--- PW_TYPE ---" >> $O
st cap capdtm getusr 20 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p' >> $O
echo "--- quit ---" >> $O
echo quit > /mnt/mmc/filmlab/cmd
sleep 2
sh $U status >> $O 2>&1
echo "FULL_DONE" >> $O
