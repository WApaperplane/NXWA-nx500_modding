#!/bin/bash
# =====================================================================
# C-2 桩 v2 构建（WSL NXKS2，相机 ABI 无关 —— 纯位置相关汇编，无 libc 依赖）
#   产出：test_server/dicam/stub_v2.bin（机器码，供 mk_c2_patch.py --stub=v2 嵌入）
#   验证：反汇编里 bl 目标必须 = 0xadd08 (system@plt)，长度必须 < 656B
# 用法（Git Bash）:
#   MSYS_NO_PATHCONV=1 wsl -d NXKS2 -- bash /mnt/e/tmp/NXWA-nx500_modding/test_server/dicam/build_stub_v2.sh
# =====================================================================
set -e
cd "$(dirname "$0")"
AS=arm-linux-gnueabi-as
LD=arm-linux-gnueabi-ld
OC=arm-linux-gnueabi-objcopy
OD=arm-linux-gnueabi-objdump
BASE=0xca3a8              # 落点 vaddr（= FUN_000ca3a8 头部）

$AS -o stub_v2.o stub_v2.s
$LD -Ttext=$BASE -e c2_stub_v2 -o stub_v2.elf stub_v2.o
$OC -O binary -j .text stub_v2.elf stub_v2.bin

sz=$(wc -c < stub_v2.bin)
echo "== stub_v2.bin: ${sz} B（可用空间 656 B）=="
if [ "$sz" -ge 656 ]; then
    echo "!! 超长，会越入下一函数（0xca638 = uscap handler）—— 必须压缩"
    exit 1
fi

echo "-- 关键指令核对 --"
$OD -D stub_v2.elf | grep -E "bl\s+add08|bxcc|cmp\s+r0, #2" || true
$OD -D stub_v2.elf | grep -q "bl\s\+add08 <\*ABS\*0xadd08>" \
    && echo "   OK: 尾调用落在 system@plt(0xadd08)" \
    || { echo "   !! bl 目标不对"; exit 1; }

echo "-- 前缀串 --"
strings -t x stub_v2.bin | grep "nx-ks" && echo "   OK: 前缀串在内" || echo "   (提示) 未见前缀串"
echo "== 完成 =="
