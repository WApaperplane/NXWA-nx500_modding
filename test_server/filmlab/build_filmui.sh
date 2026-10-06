#!/bin/bash
#=====================================================================
# build_filmui.sh —— 编译 FilmLab 机内 UI（nxfilmui.arm）
#=====================================================================
# 用法: bash build_filmui.sh
# 产物: test_server/filmlab/nxfilmui.arm
#
# ★ -O0 是铁律：-O1/-O2 编的 ARM 代码在 NX500 真机段错误(139)，-O0 稳定
#   （项目历史实测 2026-08-15）
# ★ EFL 头文件 sysroot 里没有（只有 .so），所以 nxfilmui.c 里全部手写 ABI 声明
#★ 链接期靠 test_server/filmlab/efl/ 下的 .so 副本（2026-10-03 从真机 dump）
#=====================================================================
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
HERE_WIN="$(echo "$HERE" | sed 's#^/\([a-z]\)/#\U\1:/#')"
ZIG="D:/download/NX-KS2-88/.uploads/zig/zig-windows-x86_64-0.13.0/zig.exe"
EFL_WIN="D:/download/NX-KS2-88/test_server/filmlab/efl"
TARGET="arm-linux-gnueabi.2.15"   # Tizen 2.2 glibc ~2.15, EABI5 softfp
SRC_WIN="D:/download/NX-KS2-88/test_server/filmlab/src/nxfilmui.c"
OUT_WIN="D:/download/NX-KS2-88/test_server/filmlab/nxfilmui.arm"

[ -x "$ZIG" ] || { echo "zig 不在位: $ZIG"; exit 1; }
for f in libelementary.so libevas.so; do
  [ -f "$EFL_WIN/$f" ] || { echo "缺链接库: $EFL_WIN/$f"; exit 1; }
done

# ★ 不链接 libecore.so.1（本地没有该库）——
#   ecore_event_handler_add 在源码里用 dlsym 运行时解析，见 nxfilmui.c 文件头。
#   千万【不要】加链接期 stub：那会让符号被静态解析进二进制，
#   真机上 ecore_event_handler_add 变成空函数 → 窗口能开但波轮完全无反应。
"$ZIG" cc -target $TARGET -O0 -mfloat-abi=soft -fno-stack-protector \
    "$SRC_WIN" \
    -L"$EFL_WIN" -lelementary -levas -ldl \
    -o "$OUT_WIN"

echo "完成: $OUT_WIN"
ls -la "$(echo "$OUT_WIN" | sed 's#^\([A-Z]\):#/\L\1#')" 2>/dev/null || true
echo
echo "自检（关键三项）:"
echo "  1. NEEDED 里【不能】出现 libecore.so.1"
echo "  2. 导入表里【不能】出现 ecore_event_handler_add（要靠 dlsym）"
echo "  3. 导入表里必须有 dlsym / dlerror"
echo "  → 上面三条任何一条不满足，波轮在真机上就是死的。"
