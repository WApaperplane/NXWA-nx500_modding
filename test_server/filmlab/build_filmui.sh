#!/bin/bash
#=====================================================================
# build_filmui.sh —— 编译 FilmLab 机内 UI（nxfilmui.arm）
#=====================================================================
# ★ 2026-10-08 v4（工作流 D7）：把本轮 CJK 离机结论反哺回 UI
#   v4 改动（相对 v3）：
#     ① ★ 每处 label 显式设字体：新增 apply_label_font()
#        （elm_object_part_text_get → evas_object_text_font_source_set/_font_set，
#         常量 FILMUI_FONT_FILE/FAM/SZ 见 nxfilmui.c）
#     ② ★ ASCII 降级默认关闭：g_ascii 1 → 0 ⇒ **直接显示中文标签**
#        （"相机无中文字体"这条旧前提已被离线证伪，证据 raw8/repro/nxlabel_probe.png）
#     ③ 参数新增 ascii 降级开关（实机出问题时一键退回 key 名）
#     ④ 状态栏/item 注释更正（不再声称"中文画不出"）
#   产物：nxfilmui_v4.arm（不覆盖 v3；部署件 deploy/filmlab/nxfilmui.arm 另行更新）
#   用法: bash build_filmui.sh
#
# ★ 2026-10-07 v3：输出 v3 产物，不覆盖已部署的 nxfilmui.arm
#   v3 改动：① force_reload() 借道修正 ② PW 写入逐维读回自证
#            ③ ASCII 降级默认开启（★ v4 已推翻此前提） ④ probe 只读模式
#            ⑤ apply 节流 ⑥ 选中项加 "  <" 前缀
#=====================================================================
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ZIG="D:/download/NX-KS2-88/.uploads/zig/zig-windows-x86_64-0.13.0/zig.exe"
EFL_WIN="D:/download/NX-KS2-88/test_server/filmlab/efl"
TARGET="arm-linux-gnueabi.2.15"   # Tizen 2.2 glibc ~2.15, EABI5 softfp
SRC_WIN="D:/download/NX-KS2-88/test_server/filmlab/src/nxfilmui.c"
# ★ 2026-10-08 v5（U2 上机排障）：主循环加 NXFUI_ELMRUN 开关
#   起因：U2 上机时 UI 进程起来了、相机也不卡（铁律 104 通过），但【屏幕看不到窗口】；
#         对照实验（铁律 118）证明 mod_gui（同为独立 EFL 进程、同样由 telnet 起）
#         在同 env / 同设备（/dev/dri/card0 + /dev/ump）下【能显示】。
#   v5 改动：NXFUI_ELMRUN=1 时走 elm_run()（elementary 正规主循环，内部驱动
#            evas render + 屏幕 flush）；不设则保持 ecore_main_loop_iterate 轮询（便于 A/B）。
#   产物：nxfilmui_v5.arm
OUT_WIN="D:/download/NX-KS2-88/test_server/filmlab/nxfilmui_v8.arm"

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
#
#★★ zig 0.13 + lld：`-L<Windows路径> -l:xxx` 组合找不到库（13:09-13:10 连续失败）
#   ★★★ 可靠做法：★ 直接把 .so 文件的绝对路径当普通参数传给链接器
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
echo "自检（关键三项）:"
echo "  1. NEEDED 必须含 libecore.so.1 + libecore_input.so.1（对齐 mod_gui）"
echo "     ★★缺任一⇒ 真机 elm_init FAILED（已实测过一次，13:08）"
echo "  2. 导入表里【不能】出现 ecore_event_handler_add（要靠 dlsym）"
echo "     ⇒ 出现它意味着静态绑定了，真机上会调到空函数，波轮无反应且不报错"
echo "  3. ★ v4：导入表应出现 evas_object_text_font_set / evas_object_text_font_source_set"
echo "     + elm_object_part_text_get（三条都已在真机等价 ELF 白名单里，见 check_abi.py）"
