#!/bin/sh
U=/opt/usr/nx-ks/flab_ui.sh
L=/mnt/mmc/filmlab/x11.log
O=/mnt/mmc/_pwtest/final.txt
: > $O
echo "=== start ===" >> $O
FLAB_IDLE=40
export FLAB_IDLE
sh $U start >> $O 2>&1
echo "=== status ===" >> $O
sh $U status >> $O 2>&1
echo "=== send down (expect cur=1 velvia50) ===" >> $O
sh $U down >> $O 2>&1
sleep 2
echo "=== send apply ===" >> $O
sh $U apply >> $O 2>&1
sleep 4
echo "=== X11 log ===" >> $O
tail -c 400 $L 2>/dev/null | tr -d '\r' >> $O
echo "" >> $O
echo "=== slot9 R (velvia50=102) ===" >> $O
prefman get 0 0x0a410 l 2>/dev/null | tr -d '\r' | grep -ao 'value = [-0-9]*' >> $O
echo "=== slot9 SAT addr0xa4e0 (velvia=14) ===" >> $O
prefman get 0 0x0a4e0 l 2>/dev/null | tr -d '\r' | grep -ao 'value = [-0-9]*' >> $O
echo "=== PW_TYPE ===" >> $O
st cap capdtm getusr 20 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p' >> $O
echo "=== quit ===" >> $O
sh $U quit >> $O 2>&1
sleep 2
sh $U status >> $O 2>&1
echo "FINAL_DONE" >> $O
