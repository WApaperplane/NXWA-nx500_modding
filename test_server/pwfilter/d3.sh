#!/bin/sh
U=/opt/usr/nx-ks/flab_ui.sh
sh $U start > /mnt/mmc/_pwtest/d3.txt 2>&1
echo "--- start 退出码 $? ---" >> /mnt/mmc/_pwtest/d3.txt
sh $U status >> /mnt/mmc/_pwtest/d3.txt 2>&1
echo "D3_DONE" >> /mnt/mmc/_pwtest/d3.txt
