#!/bin/bash
# =============================================================================
# selftest_mutation.sh —— 「测试的测试」：三个反例必须全被抓住（否则套件无区分力）
# =============================================================================
# 前置：先跑过 build_a1_qemu.sh（正常产物在 /tmp/a1_qemu_wk）。
# 反例（每例只篡改一个输入维度，其余保持正常）：
#   M1  full 的 blk 区清零      （模拟「特判块未刷入」）      → 期望判定 FAIL
#   M2  orig 的跳转表首项篡改    （模拟「表被破坏」）           → 期望判定 FAIL
#   M3  orig 的 norm + full 的块 （模拟「0x510b0 未重定向」）   → 期望判定 FAIL
# =============================================================================
set -e

REPO=/mnt/e/tmp/NXWA-nx500_modding
SRC=$REPO/test_server/slp/a1_qemu
S=/tmp/a1_qemu_wk
WK=/tmp/a1_qemu_mut
PY=${PY:-python3}

if [ ! -f "$S/seg_norm_orig.bin" ] || [ ! -f "$S/out_full.bin" ]; then
    echo "缺正常产物于 $S —— 请先运行 build_a1_qemu.sh"
    exit 2
fi

rm -rf "$WK"; mkdir -p "$WK"
cd "$WK"
cp "$SRC/harness.s" .

# ---- 造三个被破坏的输入 ----
cp "$S/seg_norm_full.bin" seg_norm_m1.bin
dd if=/dev/zero of=seg_blk_m1.bin bs=24 count=1 2>/dev/null
echo "[造例] M1: full 的 blk 区 → 24B 全零"

$PY - <<'EOF'
d = bytearray(open('/tmp/a1_qemu_wk/seg_norm_orig.bin', 'rb').read())
off = 0x510b4 - 0x51090
assert d[off:off + 4] == bytes.fromhex('88130580'), d[off:off + 4].hex()
d[off:off + 4] = bytes.fromhex('94130580')
open('/tmp/a1_qemu_mut/seg_norm_m2.bin', 'wb').write(d)
print('[造例] M2: 跳转表[0x100] 0x80051388 → 0x80051394（拒收）')
EOF
cp "$S/seg_blk_orig.bin" seg_blk_m2.bin

cp "$S/seg_norm_orig.bin" seg_norm_m3.bin
cp "$S/seg_blk_full.bin" seg_blk_m3.bin
echo "[造例] M3: norm=orig（无重定向）+ blk=full 块（无人调用）"

# ---- 逐反例运行 + 判定（必须 FAIL） ----
run_mut() { # $1=标签 $2=描述 $3=seg_norm $4=seg_blk $5=被替换的版本
    echo
    echo "########## $2 —— 篡改「$5」 ##########"
    cp "$S/out_orig.bin" "$S/out_step1.bin" "$S/out_full.bin" .
    cp "$3" seg_norm.bin
    cp "$4" seg_blk.bin
    arm-linux-gnueabihf-as -o mut.o harness.s
    arm-linux-gnueabihf-ld -Ttext=0x10000 -e _start -o mut.elf mut.o
    set +e
    timeout 30 qemu-arm-static ./mut.elf > out_mut.bin 2> err_mut.txt
    qrc=$?
    set -e
    printf 'qemu exit=%s  out=%s B  stderr=%s B\n' "$qrc" \
        "$(stat -c%s out_mut.bin)" "$(stat -c%s err_mut.txt)"
    cp out_mut.bin "out_$5.bin"
    set +e
    $PY "$SRC/check_a1_qemu.py" "$WK" > "mut_check_$1.txt" 2>&1
    crc=$?
    set -e
    grep -m2 "FAIL" "mut_check_$1.txt" || true
    if [ $crc -ne 0 ]; then
        echo ">>> $2: 被抓住 ✓（check rc=$crc）"
        return 0
    else
        echo ">>> ★★ $2: 未被抓住（check rc=0）—— 套件失明，不可接受！"
        return 1
    fi
}

FAILED=0
run_mut m1 "M1 blk=全零"    seg_norm_m1.bin seg_blk_m1.bin full || FAILED=1
run_mut m2 "M2 表首项篡改"  seg_norm_m2.bin seg_blk_m2.bin orig || FAILED=1
run_mut m3 "M3 重定向缺失"  seg_norm_m3.bin seg_blk_m3.bin full || FAILED=1

# ---- 归档 ----
mkdir -p "$SRC/logs"
cp -f mut_check_m1.txt "$SRC/logs/" 2>/dev/null || true
cp -f mut_check_m2.txt "$SRC/logs/" 2>/dev/null || true
cp -f mut_check_m3.txt "$SRC/logs/" 2>/dev/null || true

echo
if [ $FAILED -eq 0 ]; then
    echo "==== 反例演练: PASS —— 三个反例全部被抓住（套件具备区分能力） ===="
else
    echo "==== 反例演练: FAIL —— 存在未被抓住的反例 ===="
    exit 1
fi
