#!/bin/bash
# ============================================================
# pw-snap.sh - NX500 prefman app 区快照/差异工具
#     (移植voxivoid/recipe-lab-sony-pmca 的 snapshot/diff 方法)
#
# 原理: Sony Recipe Lab 的26 个 settings-store 槽位是这样定位的 ——
#   开发者菜单里"Settings snapshot"全量读取存 snapshot.bin -> 退出菜单
#   -> 在机身 UI 上改一个设置 -> 再进"Settings diff" -> 输出 id:old>new。
#   槽位不是猜的，是 diff 出来的。
#   原文强调 "Change one thing at a time or the diff is useless"。
#
# NX500 等价物极简单: prefman 的 dump/get 就是全量读取。
#   用法(必须两步、两次插卡之间只在机身 UI 上改一个设置):
#     步骤 A: 插卡运行  -> 脚本自动 dump 到 SD 卡, 打印"现在去机身改一个设置"
#     步骤 B: 改完设置后再次插卡运行 -> 脚本 diff 两份 dump, 只打印变化项
#   带 --label<名字> 可保存多份基线, 便于对比不同参数档位。
#
# 用法:
#   sh pw-snap.sh snapshot [label]   # 阶段 A: 抓基线
#   sh pw-snap.sh diff  [label]      # 阶段 B: 与基线 diff
#   sh pw-snap.sh list[label]   # 阶段 B+: 连打多份基线(看参数怎么动)
#   sh pw-snap.sh show 0x0a3ec      # 单独读一个偏移的值
#   sh pw-snap.sh set   0x0a3ec12345# 写一个偏移(4字节小端) + save
#
# 安全: set 只写你指定的偏移; 每次 set 前自动把整个 app 区备份到
#       /mnt/mmc/pw_snap_bak/app-<时间戳>.bin, 并在日志里打印回滚命令。
#       绝不在本脚本里自动重算 checksum (未知行为, 宁可不动)。
# ============================================================

LOG=/mnt/mmc/pw-snap.log
DIR=/mnt/mmc/pw_snap
BAK=/mnt/mmc/pw_snap_bak
BB=/opt/usr/nx-ks/busybox

mkdir -p $DIR 2>/dev/null
mkdir -p $BAK 2>/dev/null

say() { echo "$*" >> "$LOG"; echo "$*"; }

if [ ! -x /usr/bin/prefman ]; then
    echo "prefman 不存在, 无法继续" | tee -a "$LOG"
    exit 1
fi

CMD="$1"
LABEL="${2:-base}"

# prefman dump 0 的输出本身就是一份可 diff 的文本快照
snap() {
    /usr/bin/prefman dump 0 2>&1
}

case "$CMD" in

snapshot)
    say "=== snapshot label=$LABEL $(date) ==="
    F="$DIR/app-$LABEL.txt"
    snap > "$F"
    # 顺手把当前 PW 参数块单独抽一份, 方便肉眼直接看 7 维向量
    {
        echo "--- PW block 0x0a3d0..0x0a560 ---"
        for off in 0x0a3d0 0x0a3d4 0x0a3ec 0x0a3f0 0x0a410 0x0a444 \
                   0x0a478 0x0a4ac 0x0a4e0 0x0a514 0x0a548; do
            v=$(/usr/bin/prefman get 0 $off 2>/dev/null | grep -i value | head -1)
            say "  $off  $v"
        done
    } >> "$F"
    say "基线已存: $F"
    say ""
    say ">>> 现在去机身 UI 上只改一个设置 (例如 Picture Wizard ->饱和度 +1),"
    say ">>> 改完拔卡, 重新插卡运行:  sh pw-snap.sh diff $LABEL"
    ;;

diff)
    F0="$DIR/app-$LABEL.txt"
    [ -f "$F0" ] || { say "没有基线 $F0, 先跑 snapshot"; exit 1; }
    F1="$DIR/app-now.txt"
    snap > "$F1"
    say "=== diff vs $LABEL $(date) ==="
    # 只打印变化的行 —— 这是整个工具的核心
    if diff "$F0" "$F1" > "$DIR/diff-$LABEL.txt" 2>&1; then
        say "无变化。"
        say "若你确实改了设置, 说明:"
        say "  1) 改的不是 app(pref id 0) 区 -> 试试 id 1 app_restore"
        say "  2) 改动没落盘-> UI 里可能需要按确认键"
        say "  3) 该设置在别的 pref 区"
    else
        say "变化项:"
        cat "$DIR/diff-$LABEL.txt"
        say ""
        say "上面每一行的偏移就是真实槽位。已变化的那个 = 你刚改的设置。"
    fi
    # 保持基线不变, 允许连续 diff 同一基线
    ;;

list)
    say "=== 全部基线 ==="
    ls -1 $DIR/ 2>/dev/null
    ;;

show)
    OFF="$2"
    [ -n "$OFF" ] || { say "用法: sh pw-snap.sh show <offset>"; exit 1; }
    say "offset $OFF:"
    /usr/bin/prefman get 0 "$OFF" 2>&1 | tee -a "$LOG"
    ;;

set)
    OFF="$2"
    VAL="$3"
    [ -n "$OFF" ] && [ -n "$VAL" ] || { say "用法: sh pw-snap.sh set <offset> <value>"; exit 1; }
    TS=$(date +%Y%m%d-%H%M%S)
    # 备份整个 app 区
    snap > "$BAK/app-$TS.txt"
    say "已备份 app 区 -> $BAK/app-$TS.txt"
    say "回滚命令:  prefman load_file 0 $BAK/app-$TS.bin && prefman save 0"
    say "写入 $OFF = $VAL (十进制) ..."
    /usr/bin/prefman set 0 "$OFF" l "$VAL" 2>&1 | tee -a "$LOG"
    say "prefman save ..."
    /usr/bin/prefman save 2>&1 | tee -a "$LOG"
    sync; sync
    say "复读校验:"
    /usr/bin/prefman get 0 "$OFF" 2>&1 | tee -a "$LOG"
    say ""
    say ">>> 现在拍一张, 与之前的同参数照片对比。若画面无变化 = 该偏移不是显示层参数。"
    say ">>> 若机身菜单里也变了 = 写入成功且被接受。"
    ;;

*)
    say "用法: sh pw-snap.sh {snapshot|diff|list|show|set} [args]"
    ;;
esac

sync
exit 0