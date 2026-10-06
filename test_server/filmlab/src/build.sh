#!/bin/bash
# nxfilmui 构建脚本 —— FilmLab配方选择器（EFL 版，NX500/NX1 机内）
#
# 用法: bash build.sh [ui|abi|all|clean]
#
# 两条铁律（都是真机踩出来的）
#   1. -O0：-O1+ 编译的 ARM 代码在 NX500 真机段错误 139
#   2. EFL 用【链接期 stub 库】：本地 sysroot 无 EFL .so，
#      真机上的库靠 soname 匹配在运行时解析（见 efl_stub.c 头部说明）
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
HERE_WIN="$(echo "$HERE" | sed 's#^/\([a-z]\)/#\U\1:/#')"
ZIG="D:/download/NX-KS2-88/.uploads/zig/zig-windows-x86_64-0.13.0/zig.exe"
ROOTFS="D:/download/NX-KS2-88/.uploads/nx1_open/rootfs_dev/standard-armv7l/usr"
TARGET="arm-linux-gnueabi.2.15"

STUB="$HERE/stublib"
OUT="$HERE/out"

CFLAGS="-target $TARGET -O0 -I$ROOTFS/include -mfloat-abi=soft -fno-stack-protector"

mkdir -p "$HERE_WIN/stublib" "$HERE_WIN/out"

# ---- 建桩库：libelementary.so.1 / libevas.so.1（soname 必须与真机一致）----
build_stubs() {
    echo "== 建链接期 EFL 桩库 =="
    for lib in elementary evas; do
        if [ -f "$STUB/lib$lib.so.1" ]; then
            echo "  lib$lib.so.1 已存在，跳过"
            continue
        fi
        "$ZIG" cc -target $TARGET -O0 -fPIC -shared \
            -Wl,-soname,lib$lib.so.1 \
            "$HERE_WIN/efl_stub.c" -o "$HERE_WIN/stublib/lib$lib.so.1"
        echo "  -> stublib/lib$lib.so.1"
    done
}

build_ui() {
    echo "== 编译 nxfilmui（FilmLab 配方UI，EFL 版）=="
    build_stubs
    "$ZIG" cc $CFLAGS \
        "$HERE_WIN/nxfilmui.c" \
        "$HERE_WIN/stublib/libelementary.so.1" \
        "$HERE_WIN/stublib/libevas.so.1" \
        -ldl \
        -o "$HERE_WIN/out/nxfilmui.arm"
    echo "  -> out/nxfilmui.arm"
    # 打印 DT_NEEDED 自证：必须正好是 libelementary.so.1 / libevas.so.1，
    # 出现libstub 之类的名字就说明 soname 没生效，真机会加载失败。
    echo "  --- DT_NEEDED 自证 ---"
    python "$HERE_WIN/readelf_needed.py" "$HERE_WIN/out/nxfilmui.arm" | sed 's/^/  /'
    echo "  --- 未定义符号（应无 ecore_*，因它走 dlsym）---"
    python "$HERE_WIN/dynsym.py" "$HERE_WIN/out/nxfilmui.arm" | sed 's/^/  /'
}

build_abi() {
    echo "== ABI 符号查证（nxfilmui.c 引用的每个 EFL 符号 vs 真机证据）=="
    python "$HERE_WIN/check_abi.py" || true
}

case "${1:-all}" in
    ui)   build_ui ;;
    abi)  build_abi ;;
    all)  build_abi; build_ui ;;
    clean) rm -rf "$HERE_WIN/out" "$HERE_WIN/stublib"; echo "已清理" ;;
    *) echo "usage: build.sh [ui|abi|all|clean]"; exit 1 ;;
esac
echo "完成。"
