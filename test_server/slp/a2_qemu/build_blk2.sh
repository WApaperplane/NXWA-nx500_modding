#!/bin/bash
# 汇编 A2 特判块（-Ttext=0x80011530）→ blk2.bin + 反汇编复核
set -e
cd /tmp/a2
arm-linux-gnueabihf-as -o blk2.o /mnt/e/NXWA/rea-tmp/a2/blk2.s
arm-linux-gnueabihf-ld -Ttext=0x80011530 -e _start -o blk2.elf blk2.o
echo "=== objdump ==="
arm-linux-gnueabihf-objdump -d blk2.elf | sed -n '/<_start>:/,/^$/p'
arm-linux-gnueabihf-objcopy -O binary --only-section=.text blk2.elf /tmp/a2/blk2.bin
echo "=== size ==="
stat -c%s /tmp/a2/blk2.bin
cp /tmp/a2/blk2.bin /mnt/e/NXWA/rea-tmp/a2/
echo done
