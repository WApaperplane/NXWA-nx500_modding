#!/bin/bash
# run_m2_qemu.sh — M2 配方名「上机前 VM 预演」（对应上机批 U5 的机制层）
#
# 目标：在 rootfs-112 chroot（qemu-arm-static）里，用**相机自己的 glibc 2.13** 跑 gettext 探针，
#       双轮对照验证：
#         基线轮（官方 .mo）  → CAP_MENU_CUSTOM_MODE_1 = 「自定义 1」
#         样机轮（m2sample）  → CAP_MENU_CUSTOM_MODE_1 = 「Portra 400」
#       —— 即「改后 .mo 被相机同版本 gettext 运行时正确读取」的预演证据。
#
# 环境闭环（三个「相机自带」）：
#   ① localedef = 相机 rootfs 自带（/usr/bin/localedef）  ② i18n 源 = 相机 rootfs 自带（293 locales）
#   ③ glibc    = 相机 rootfs 自带（libc-2.13.so，探针直链）
#
# 用法（WSL 内）: bash run_m2_qemu.sh [rootfs]
# 证据产出：logs/baseline.txt、logs/sample.txt、logs/run.log（tee 汇总）
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
RF=${1:-/opt/nxks2/rootfs-112}
LOG="$HERE/logs"
mkdir -p "$LOG"

ORIG_MO=/mnt/e/tmp/dicam_zh_CN.mo
SAMPLE_MO="$ROOT/fw/v1.12/dicam/locale/di-camera-app.zh_CN.m2sample.mo"
PROBE="$HERE/out/m2_probe.arm"
LOCDIR="$RF/usr/lib/locale"
DICT="$RF/usr/share/locale/zh_CN/LC_MESSAGES"
CH=/tmp/m2_probe

exec > >(tee "$LOG/run.log") 2>&1

say(){ echo; echo "########## $* ##########"; }

say "0. 前置检查"
[ -s "$PROBE" ]     || { echo "!! 缺探针：先跑 build_m2_probe.sh"; exit 1; }
[ -s "$ORIG_MO" ]   || { echo "!! 缺官方件 $ORIG_MO"; exit 1; }
[ -s "$SAMPLE_MO" ] || { echo "!! 缺样机 $SAMPLE_MO"; exit 1; }
echo "探针   : $(md5sum "$PROBE" | cut -d' ' -f1)  $PROBE"
echo "官方件 : $(md5sum "$ORIG_MO" | cut -d' ' -f1)  $ORIG_MO"
echo "样机   : $(md5sum "$SAMPLE_MO" | cut -d' ' -f1)  $SAMPLE_MO"

say "1. zh_CN.UTF-8 locale（用相机自带 localedef + 自带 i18n 源；幂等）"
# 1a. charmaps 就位：rootfs 的 localedef 不读 .gz，用提取流程留下的解压副本
for cm in UTF-8 ANSI_X3.4-1968; do
    if [ ! -f "$RF/usr/share/i18n/charmaps/$cm" ]; then
        if [ -f "$RF/usr/share/i18n/charmaps/$cm.gz_extract/gzip.uncompressed" ]; then
            cp "$RF/usr/share/i18n/charmaps/$cm.gz_extract/gzip.uncompressed" \
               "$RF/usr/share/i18n/charmaps/$cm"
            echo "charmap 就位：$cm（来自 gzip.uncompressed 副本）"
        else
            echo "!! 缺 charmap $cm 及其解压副本"; exit 1
        fi
    else
        echo "charmap 已在位：$cm"
    fi
done
# 1b. 生成 locale（幂等判据：LC_MESSAGES 子文件存在才算完整——空目录视为未生成）
if [ -f "$LOCDIR/zh_CN.UTF-8/LC_MESSAGES" ] || [ -f "$LOCDIR/zh_CN.utf8/LC_MESSAGES" ]; then
    echo "已存在且完整（跳过生成）：$(ls -d "$LOCDIR"/zh_CN.* 2>/dev/null)"
else
    [ -d "$LOCDIR/zh_CN.UTF-8" ] && { echo "清除不完整残留目录 $LOCDIR/zh_CN.UTF-8"; rm -rf "$LOCDIR/zh_CN.UTF-8"; }
    chroot "$RF" /usr/bin/localedef -i zh_CN -f UTF-8 /usr/lib/locale/zh_CN.UTF-8
    echo "生成完成："
fi
ls -la "$LOCDIR/zh_CN.UTF-8/" 2>/dev/null | head -12

say "2. 布置（探针入 chroot + 字典目录 + proc）"
mkdir -p "$RF$CH" "$DICT"
cp -f "$PROBE" "$RF$CH/m2_probe.arm"
chmod +x "$RF$CH/m2_probe.arm"
[ -e "$RF/dev/null" ] || { mkdir -p "$RF/dev"; mknod -m 666 "$RF/dev/null" c 1 3 || true; }
mountpoint -q "$RF/proc" || mount -t proc proc "$RF/proc"

say "3. 基线轮：官方 .mo（期望：自定义 1/2/3）"
cp -f "$ORIG_MO" "$DICT/di-camera-app.mo"
chroot "$RF" /usr/bin/env LC_ALL=zh_CN.UTF-8 LANG=zh_CN.UTF-8 "$CH/m2_probe.arm" | tee "$LOG/baseline.txt"

say "4. 样机轮：m2sample .mo（期望：Portra 400 / Gold 200 / TriX 400）"
cp -f "$SAMPLE_MO" "$DICT/di-camera-app.mo"
chroot "$RF" /usr/bin/env LC_ALL=zh_CN.UTF-8 LANG=zh_CN.UTF-8 "$CH/m2_probe.arm" | tee "$LOG/sample.txt"

say "5. 断言"
FAIL=0
ck(){ if grep -qF "$1" "$2"; then echo "  OK   $3"; else echo "  FAIL $3"; FAIL=1; fi; }
nck(){ if grep -qF "$1" "$2"; then echo "  FAIL $3"; FAIL=1; else echo "  OK   $3"; fi; }

ck "CAP_MENU_CUSTOM_MODE_1|自定义 1"     "$LOG/baseline.txt" "基线轮 CUSTOM1=旧名（证明翻译链工作）"
ck "CAP_MENU_CUSTOM_MODE_2|自定义 2"     "$LOG/baseline.txt" "基线轮 CUSTOM2=旧名"
ck "CAP_FN_PW|图片向导"                  "$LOG/baseline.txt" "基线轮 CAP_FN_PW=图片向导"
ck "CAP_MENU_CUSTOM_MODE_1|Portra 400"   "$LOG/sample.txt"   "样机轮 CUSTOM1=新名"
ck "CAP_MENU_CUSTOM_MODE_2|Gold 200"     "$LOG/sample.txt"   "样机轮 CUSTOM2=新名"
ck "CAP_MENU_CUSTOM_MODE_3|TriX 400"     "$LOG/sample.txt"   "样机轮 CUSTOM3=新名"
ck "CAP_FN_PW|图片向导"                  "$LOG/sample.txt"   "样机轮 CAP_FN_PW 未动（仍=图片向导）"
nck "CAP_MENU_CUSTOM_MODE_1|自定义 1"    "$LOG/sample.txt"   "样机轮无旧名残留"

echo
if [ "$FAIL" = "0" ]; then
    MSG="== M2 VM 预演：PASS（gettext 双轮对照全绿） =="
else
    MSG="== M2 VM 预演：FAIL（见上） =="
fi
echo "$MSG"
echo "$MSG" >> "$LOG/summary.txt"   # 独立落盘（不经异步 tee，防尾部竞态）
[ "$FAIL" = "0" ] || exit 2
