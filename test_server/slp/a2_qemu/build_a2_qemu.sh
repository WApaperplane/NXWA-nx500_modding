#!/bin/bash
# build_a2_qemu.sh —— A2 补丁「真字节」QEMU 验证：提取 → 构建 → 运行 → 判定
# 用法（Windows 侧）:
#   MSYS_NO_PATHCONV=1 wsl -d NXKS2 -- bash /mnt/e/tmp/NXWA-nx500_modding/test_server/slp/a2_qemu/build_a2_qemu.sh
set -e

REPO=/mnt/e/tmp/NXWA-nx500_modding
SRC=$REPO/test_server/slp/a2_qemu
P7A2=/mnt/e/NXWA/fw/v1.12/a2/p7_a2.bin
WK=/tmp/a2_qemu_wk
PY=python3

rm -rf "$WK"; mkdir -p "$WK"
cd "$WK"

echo "########## 1/4 提取（p7_a2.bin → 3 段） ##########"
$PY "$SRC/extract_a2.py" "$P7A2" "$WK"

echo
echo "########## 2/4 构建载具 ##########"
cp "$SRC/a2_harness.s" "$WK/"
arm-linux-gnueabihf-as -o a2h.o a2_harness.s
arm-linux-gnueabihf-ld -Ttext=0x10000 -e _start -o a2h.elf a2h.o
echo "载具构建 OK"

echo
echo "########## 3/4 运行（qemu-arm-static） ##########"
set +e
qemu-arm-static ./a2h.elf > out.bin 2> err.txt
rc=$?
set -e
printf 'qemu exit=%s  out=%s B  stderr=%s B\n' "$rc" "$(stat -c%s out.bin)" "$(stat -c%s err.txt)"
if [ -s err.txt ]; then head -5 err.txt; fi

echo
echo "########## 4/4 判定 ##########"
mkdir -p "$SRC/logs"
set +e
$PY "$SRC/check_a2.py" "$WK" | tee "$SRC/logs/a2_check_report.txt"
crc=${PIPESTATUS[0]}
set -e
cp -f out.bin "$SRC/logs/a2_out.bin"
cp -f a2h.elf "$SRC/logs/a2h.elf" 2>/dev/null || true
echo
echo "check rc=$crc"
exit $crc
