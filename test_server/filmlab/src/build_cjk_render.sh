#!/bin/bash
# build_cjk_render.sh —— 编译离线 CJK 光栅化验证程序（ARM，相机 ABI）
#
# 与 nxfilmui 同源约束（都是真机踩出来的）：
#   ① -O0：-O1+ 的 ARM 代码在 NX500 真机段错误(139)
#   ② 链接 EFL 必须【把 .so 绝对路径当普通参数传给链接器】
#      （zig 0.13 + lld 的 `-L<Windows路径> -l:xxx` 组合找不到库）
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ZIG="D:/download/NX-KS2-88/.uploads/zig/zig-windows-x86_64-0.13.0/zig.exe"
EFL="D:/download/NX-KS2-88/test_server/filmlab/efl"
TARGET="arm-linux-gnueabi.2.15"
OUT="$HERE/out/cjk_render.arm"

[ -x "$ZIG" ] || { echo "zig 不在位: $ZIG"; exit 1; }
for f in libecore_evas.so.1 libevas.so.1 libecore.so.1; do
  [ -s "$EFL/$f" ] || { echo "缺链接库: $EFL/$f"; exit 1; }
done
mkdir -p "$HERE/out"

"$ZIG" cc -target $TARGET -O0 -mfloat-abi=soft -fno-stack-protector \
    "$HERE/cjk_render.c" \
    "$EFL/libecore_evas.so.1" \
    "$EFL/libevas.so.1" \
    "$EFL/libecore.so.1" \
    -s -Wl,--gc-sections \
    -o "$OUT"

echo "完成: $OUT"
ls -la "$OUT"
echo "--- DT_NEEDED / 导入符号自证 ---"
python "$HERE/readelf_needed.py" "$OUT" 2>/dev/null | sed 's/^/  /' || true
python "$HERE/dynsym.py" "$OUT" 2>/dev/null | sed 's/^/  /' | head -20 || true
