#!/bin/sh
# @gate script=u6_lut.sh opens=rw one_shot=1 gate=cmasafe
# u6_lut.sh - U6 3D LUT 写表/读回包装（相机端，busybox sh）
# =====================================================================
# ★ opens=rw 说明：pick/check 为只读；load/save 为写类。
#   写类子命令【内嵌 cmasafe 安全闸】（范围+黑名单+对齐+全零四查），
#   且每个子命令一次调用只做一件事（one_shot）。
# =====================================================================
# 定位：把"cmapick 探测 -> cmasafe 安全闸 -> lutapi load/save"串成
#       一条 telnet 命令，减少会话数；全部输出落 $OUT/（PC 侧 FTP 拉）。
#
# 子命令：
#   pick                               探测 CMA 落点（只读，零风险）
#   check <phys>                       单跑安全闸（只读，零风险）
#   load  <表.bin> <phys> [sel] [fmt] [cbcr] [settle]
#                                      安全闸 -> 灌表 -> regdump
#   save  <out.bin> <phys> [sel] [fmt] [bytes]
#                                      安全闸 -> 读回（dump 探路）
#
# 硬纪律：
#   * 一次只跑一条子命令；看清输出再跑下一条（单核相机）
#   * 写类操作（load/save）前必过 cmasafe（范围+黑名单+对齐+全零）
#   * 路径全部自包含 $D（不依赖 /opt 部署版本，避免版本混淆）
# =====================================================================

BB=/opt/usr/nx-ks/busybox
[ -x "$BB" ] || BB=/bin/busybox
[ -x "$BB" ] || BB=/usr/bin/busybox
if [ ! -x "$BB" ]; then
    echo "ERR: 找不到 busybox（试过 /opt/usr/nx-ks /bin /usr/bin）"
    exit 1
fi

D=/mnt/mmc/u6
OUT=$D/out
CMAP=$D/cmapick2.arm
SAFE=$D/cmasafe.arm
API=$D/lutapi.arm

usage() {
    echo "用法:"
    echo "  $0 pick"
    echo "  $0 check <phys>"
    echo "  $0 load  <表.bin> <phys> [sel=0] [fmt=1] [cbcr=0] [settle=300]"
    echo "  $0 save  <out.bin> <phys> [sel=0] [fmt=1] [bytes=19712]"
    echo
    echo "  sel: 0=LUT0(★主试) 1=LUT1 2=LUT_EXT(历史曾花屏，B计划)"
    echo "  phys 必须来自 pick 输出的『4KB 粒度命中』行"
}

[ -x "$CMAP" ] || { echo "ERR: 缺 $CMAP"; exit 1; }
[ -x "$SAFE" ] || { echo "ERR: 缺 $SAFE"; exit 1; }
[ -x "$API" ]  || { echo "ERR: 缺 $API";  exit 1; }

"$BB" mkdir -p "$OUT"

case "$1" in

pick)
    LOG=$OUT/cmapick.log
    echo "=== cmapick2 探测（只读） ==="
    "$CMAP" --need19652 > "$LOG" 2>&1
    RC=$?
    "$BB" cat "$LOG"
    echo "cmapick rc=$RC"
    echo
    if [ $RC -ne 0 ]; then
        echo "★★ cmapick 未找到候选落点（rc=$RC）"
        echo "   ⇒ 此刻 load【必然卡死整机】—— 绝对不要 load。"
        echo "   ⇒ 退出拍摄态让 ISP 释放内存，再重跑本命令。"
        exit 2
    fi
    HIT=$("$BB" grep "4KB 粒度命中" "$LOG" | "$BB" head -n 1)
    if [ -z "$HIT" ]; then
        echo "★★ 无『4KB 粒度命中』行。"
        echo "   ⇒ 不要用『可用落点候选』的区起点（0x94000000 是历史事故地址）。"
        echo "   ⇒ 退出拍摄态重跑，或等待更好的探测时机。"
        exit 3
    fi
    echo "=== 落点（把下面这行里的 0x........ 抄给 load 的第 2 个参数） ==="
    echo "$HIT"
    echo
    echo "★ 提醒：pick 与 load 之间不要间隔很久（内存状态会变）。"
    ;;

check)
    if [ -z "$2" ]; then usage; exit 1; fi
    "$SAFE" "$2"
    echo "cmasafe rc=$?"
    ;;

load)
    TAB=$2
    PHYS=$3
    SEL=${4:-0}
    FMT=${5:-1}
    CBCR=${6:-0}
    SETTLE=${7:-300}
    if [ -z "$TAB" ] || [ -z "$PHYS" ]; then usage; exit 1; fi
    if [ ! -f "$TAB" ]; then echo "★ 表文件不存在: $TAB"; exit 1; fi

    echo "=== [1/3] 安全闸 cmasafe ==="
    "$SAFE" "$PHYS"
    RC=$?
    if [ $RC -ne 0 ]; then
        echo "★★ 安全闸拒绝（rc=$RC）—— 未做任何写入，直接停。"
        exit 2
    fi
    echo
    echo "=== [2/3] lutapi load（表=$TAB sel=$SEL fmt=$FMT cbcr=$CBCR settle=$SETTLE） ==="
    TN=$("$BB" basename "$TAB")
    LOG=$OUT/load_$TN.log
    "$API" load "$TAB" "$PHYS" "$SEL" "$FMT" 17 2 "$SETTLE" "$CBCR" > "$LOG" 2>&1
    RC=$?
    "$BB" cat "$LOG"
    echo "lutapi rc=$RC"
    echo
    echo "=== [3/3] 下一步 ==="
    echo "  切到拍摄模式看取景器："
    echo "    R3-A(identity) 应中性（≈不加 LUT）；R3-B(Portra) 应有胶片风格。"
    echo "  ★ 不要半按快门（会触发 p7 抢回指针，表被覆盖）。"
    echo "  ★ 想回滚：/opt/usr/nx-ks/lutload.arm restore 然后半按快门。"
    exit $RC
    ;;

save)
    OUTBIN=$2
    PHYS=$3
    SEL=${4:-0}
    FMT=${5:-1}
    BYTES=${6:-19712}
    if [ -z "$OUTBIN" ] || [ -z "$PHYS" ]; then usage; exit 1; fi
    BN=$("$BB" basename "$OUTBIN")
    OUTBIN=$OUT/$BN

    echo "=== [1/2] 安全闸 cmasafe ==="
    "$SAFE" "$PHYS"
    RC=$?
    if [ $RC -ne 0 ]; then
        echo "★★ 安全闸拒绝（rc=$RC）—— 未做任何写入，直接停。"
        exit 2
    fi
    echo
    echo "=== [2/2] lutapi save（读回内部表 -> $OUTBIN） ==="
    LOG=$OUT/save_$BN.log
    "$API" save "$OUTBIN" "$PHYS" "$SEL" "$FMT" "$BYTES" > "$LOG" 2>&1
    RC=$?
    "$BB" cat "$LOG"
    echo "lutapi rc=$RC"
    echo
    echo "★ 下一步：PC 侧 pull 拉回 $BN，与源表逐字节比对。"
    exit $RC
    ;;

*)
    usage
    exit 1
    ;;
esac
