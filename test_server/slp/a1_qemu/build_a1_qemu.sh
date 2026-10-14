#!/bin/bash
# =============================================================================
# build_a1_qemu.sh —— A1 p7「包级真字节」QEMU 行为测试：提取 → 构建 → 运行 → 判定
# =============================================================================
# 在 WSL NXKS2 内运行（依赖: arm-linux-gnueabihf-as/ld、qemu-arm-static、python3）。
# Windows 侧调用（前台，输出直接可见）:
#   MSYS_NO_PATHCONV=1 wsl -d NXKS2 -- bash /mnt/e/tmp/NXWA-nx500_modding/test_server/slp/a1_qemu/build_a1_qemu.sh
#
# 测试对象 = 三个 SLP 成品包解出的 idx5（真实待刷字节），非中间产物:
#   orig  = NX500_v1.12.bin（官方基线）
#   step1 = slp_a1_p7_g_step1_v116.bin（绕行，应逐位等价）
#   full  = slp_a1_p7_g_v116.bin（特判块，应仅 0x130..0x133 行为变化）
# =============================================================================
set -e

REPO=/mnt/e/tmp/NXWA-nx500_modding
SRC=$REPO/test_server/slp/a1_qemu
FW=/mnt/e/NXWA/fw/v1.12
WK=/tmp/a1_qemu_wk
PY=${PY:-python3}

say(){ echo; echo "########## $* ##########"; }

rm -rf "$WK"; mkdir -p "$WK"
cd "$WK"

say "1/4 从三个成品包提取（idx5 + 测试区段）"
$PY "$SRC/extract_variants.py" \
    "$FW/NX500_v1.12.bin" \
    "$FW/a1/slp_a1_p7_g_step1_v116.bin" \
    "$FW/a1/slp_a1_p7_g_v116.bin" \
    "$WK"

say "2/4 组装 harness 源"
cp "$SRC/harness.s" "$WK/harness.s"

say "3/4 逐版本构建与运行（qemu-arm-static）"
for v in orig step1 full; do
    echo "===== [$v] ====="
    cp "seg_norm_$v.bin" seg_norm.bin
    cp "seg_blk_$v.bin"  seg_blk.bin
    arm-linux-gnueabihf-as -o "h_$v.o" harness.s
    arm-linux-gnueabihf-ld -Ttext=0x10000 -e _start -o "h_$v.elf" "h_$v.o"
    set +e
    qemu-arm-static "./h_$v.elf" > "out_$v.bin" 2> "err_$v.txt"
    rc=$?
    set -e
    printf 'qemu exit=%s  out=%s B  stderr=%s B\n' "$rc" \
        "$(stat -c%s "out_$v.bin")" "$(stat -c%s "err_$v.txt")"
    if [ -s "err_$v.txt" ]; then sed -n '1,3p' "err_$v.txt"; fi
done

say "证据归档（out_*.bin / h_*.elf）"
mkdir -p "$SRC/logs"
cp -f out_orig.bin out_step1.bin out_full.bin h_orig.elf h_step1.elf h_full.elf "$SRC/logs/"

say "4/4 差分判定"
set +e
$PY "$SRC/check_a1_qemu.py" "$WK" | tee "$SRC/logs/check_report.txt"
rc=${PIPESTATUS[0]}
set -e
echo
echo "check rc=$rc"
exit $rc
