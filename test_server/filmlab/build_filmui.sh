#!/bin/bash
#=====================================================================
# build_filmui.sh —— 编译 FilmLab 机内 UI（nxfilmui.arm）
#=====================================================================
# ★ 2026-10-07 v3：输出 v3 产物，不覆盖已部署的 nxfilmui.arm
#   v3 改动：
#     ① force_reload() 借道逻辑修正（照抄实机跑通的filmlab-apply.sh）
#     ② PW 写入后逐维读回自证
#     ③ ASCII 降级默认开启（相机无中文字体）
#     ④ probe 只读模式（不开 GUI、不写 prefman）
#     ⑤ apply 节流（同格 400ms 内只应用一次）
#     ⑥ 选中项 label 加 "  <" 前缀（保证高亮一定可见）
#   用法: bash build_filmui.sh
#=====================================================================
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ZIG="D:/download/NX-KS2-88/.uploads/zig/zig-windows-x86_64-0.13.0/zig.exe"
EFL_WIN="D:/download/NX-KS2-88/test_server/filmlab/efl"
TARGET="arm-linux-gnueabi.2.15"   # Tizen 2.2 glibc ~2.15, EABI5 softfp
SRC_WIN="D:/download/NX-KS2-88/test_server/filmlab/src/nxfilmui.c"
OUT_WIN="D:/download/NX-KS2-88/test_server/filmlab/nxfilmui_v3.arm"

[ -x "$ZIG" ] || { echo "zig 不在位: $ZIG"; exit 1; }
# ★★ 既查存在也查大小：FTP 传输失败会留下【0 字节文件】，
#    只查存在会让链接器报 "unable to find library" 而看不出真因（2026-10-07 踩过）
for f in libelementary.so libevas.so libecore_evas.so libecore.so libecore_input.so; do
  [ -f "$EFL_WIN/$f" ] || { echo "缺链接库: $EFL_WIN/$f"; exit 1; }
  SZ=$(stat -c %s "$EFL_WIN/$f" 2>/dev/null || echo 0)
  [ "$SZ" -gt 1000 ] || { echo "链接库 $f 只有 $SZ 字节 —— 是 FTP 传输失败留下的空文件，重新 dump"; exit 1; }
done

# ★★★ 链接期依赖：★ 必须与 mod_gui 的 NEEDED 对齐，否则 elm_init 直接失败。
#   mod_gui NEEDED: libelementary / libevas / libecore / libecore_input / libc / libpthread
#★ 首版只链了 elementary + evas ⇒ 真机 elm_init FAILED（2026-10-07 13:08 实测）
#   根因：elm_init 内部要ecore + ecore_evas 把 ecore 绑到 X11 backend，
#         缺依赖⇒ 初始化失败（不是缺符号，是根本没去 load 那两个 .so）
#
# ★★ libecore.so / libecore_input.so 于 13:08 从真机 dump 到本地 efl/
#    （167180 / 70288B，与 raw8/usr_lib_full.txt 记录一致）
# ★★ ecore_event_handler_add 仍走 dlsym（不静态绑定，见 nxfilmui.c 注释）
#
#★★ zig 0.13 + lld：`-L<Windows路径> -l:xxx` 组合找不到库（13:09-13:10 连续失败）
#   ★★★ 可靠做法：★ 直接把 .so 文件的绝对路径当普通参数传给链接器
#   （实测可用，2026-10-07 13:11 验证）
"$ZIG" cc -target $TARGET -O0 -mfloat-abi=soft -fno-stack-protector \
    "$SRC_WIN" \
    "$EFL_WIN/libelementary.so.1" \
    "$EFL_WIN/libevas.so.1" \
    "$EFL_WIN/libecore_evas.so.1" \
    "$EFL_WIN/libecore.so.1" \
    "$EFL_WIN/libecore_input.so.1" \
    -ldl \
    -s -Wl,--gc-sections \
    -o "$OUT_WIN"

echo "完成: $OUT_WIN"
ls -la "$OUT_WIN"
echo
echo "自检（关键两项）:"
echo "  1. NEEDED 必须含 libecore.so.1 + libecore_input.so.1（对齐 mod_gui）"
echo "     ★★缺任一⇒ 真机 elm_init FAILED（已实测过一次，13:08）"
echo "  2. 导入表里【不能】出现 ecore_event_handler_add（要靠 dlsym）"
echo "     ⇒ 出现它意味着静态绑定了，真机上会调到空函数，波轮无反应且不报错"
