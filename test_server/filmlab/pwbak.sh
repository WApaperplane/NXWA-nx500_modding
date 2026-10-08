#!/bin/sh
# pwbak.sh — 备份 / 恢复 FilmLab 主用的 slot 9（UI「自定义1」）的 7 维 PW 值
#
# ★★ 为什么需要备份：nxfilmui 的 apply 恒定写 slot 9
#    （这是"一键"的实现：UI 恒显示「自定义1」，按一下取景器立刻变）
#    ⇒ 如果用户原本在 slot 9 里设了自己的自定义风格，会被配方覆盖。
#    ⇒ 上机前先 dump 一次。
#
# ★★ 全程只读（dump）/ 只写 prefman（restore），不碰任何分区与硬件寄存器。
#
# 用法:
#   sh pwbak.sh save  [file]   只读 dump 当前 slot 9 的 7 个值 → file（默认 pwbak.txt）
#   sh pwbak.sh show  [file]   只读打印 file 里的值
#   sh pwbak.sh restore <file> ★★ 唯一会写 prefman 的子命令
#   sh pwbak.sh slot            只读：打印 slot 9 在UI 里对应哪个 enum
#
# ★ 铁律：restore 之前会先 dump 当前值到 <file>.before-restore，
#   以便"恢复错了还能再恢复回去"（双保险）。

BB=/opt/usr/nx-ks/busybox
# PW_BASE/PSTEP/SSTEP 三个常量逐项照抄 nxfilmui.c 与 filmlab-apply.sh，两处必须一致
PW_BASE=41964        # 0xa3ec APPPREF_EFFECT_STANDARD_R_COLOR
PSTEP=52
SSTEP=4
SLOT=9
ENUM9=0x140009      # slot9 <-> enum 0x140009（UI「自定义1」）

# ★ 与 filmlab-apply.sh:68 逐字一致的读法（该表达式已实机验证）
getr() {
    prefman get 0 "$(printf 0x%05x $((PW_BASE + $1 * PSTEP + SLOT * SSTEP)))" l 2>/dev/null \
      | /opt/usr/nx-ks/busybox tr -d '\r' \
      | /opt/usr/nx-ks/busybox sed -n 's/.*value = \([-0-9]*\).*/\1/p'
}

cmd_save() {
    F="${1:-/mnt/mmc/filmlab/pwbak.txt}"
    NAMES="R G B HUE SAT SHARP CON"
    echo "# FilmLab slot$SLOT (enum $ENUM9) PW dump" > "$F"
    echo "# $(date '+%Y-%m-%d %H:%M:%S')" >> "$F"
    # ★★★ 索引必须 0-based：与 nxfilmui.c 的 set_pw(idx) / filmlab-apply.sh 的
    #   PW_BASE + idx*PSTEP + SLOT*SSTEP 完全一致。
    #   ★ 首版误用 i=1 起始 ⇒ 读成 PW[1..7]、漏掉 PW[0]、多读了 PW[7]（越界）
    i=0
    for n in $NAMES; do
        v=$(getr $i)
        echo "$i $n $v" >> "$F"
        echo "  PW[$i] $n = $v"
        i=$((i + 1))
    done
    echo "已保存 -> $F"
}

cmd_show() {
    F="${1:-/mnt/mmc/filmlab/pwbak.txt}"
    [ -f "$F" ] || { echo "找不到 $F"; return 1; }
    /opt/usr/nx-ks/busybox cat "$F"
}

cmd_restore() {
    F="$1"
    [ -f "$F" ] || { echo "找不到 $F"; return 1; }
    # ★ 双保险：先存当前值
    cmd_save "${F}.before-restore"
    echo "正在恢复（先切到 slot9 让 ISP 认这组值）..."
    st cap capdtm setusr 20 0x140009 >/dev/null 2>&1
    $BB sleep 1
    while read idx nm val; do
        case "$idx" in \#*|"") continue ;; esac
        # ★★ 越界防护：idx 必须是 0..6，否则会写到错误的 PW 维
        case "$idx" in
            0|1|2|3|4|5|6) : ;;
            *) echo "  ★ 跳过越界 idx=$idx（只接受 0..6）"; continue ;;
        esac
        addr=$(printf 0x%05x $((PW_BASE + idx * PSTEP + SLOT * SSTEP)))
        prefman set 0 "$addr" l "$val" >/dev/null 2>&1
        got=$(getr "$idx")
        if [ "$got" = "$val" ]; then
            echo "  PW[$idx] $nm = $val  OK"
        else
            echo "  ★ PW[$idx] $nm 写 $val 但读回 $got"
        fi
    done < "$F"
    echo "恢复完成。"
}

cmd_slot() {
    echo "slot $SLOT <-> enum $ENUM9（UI 显示「自定义1」）"
    echo -n "当前 capdtm 20 = "
    st cap capdtm getusr 20 2>/dev/null | /opt/usr/nx-ks/busybox tr -d '\r'
}

case "$1" in
    save)    shift; cmd_save "$@" ;;
    show)    shift; cmd_show "$@" ;;
    restore) shift; cmd_restore "$@" ;;
    slot)    cmd_slot ;;
    *) echo "用法: sh pwbak.sh save|show|restore|slot"; exit 2 ;;
esac
