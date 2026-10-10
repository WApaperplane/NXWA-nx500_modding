#!/bin/sh
#=====================================================================
# u1_rd.sh -- U1 ①/②：按 idx 只读一段 /dev/mem（一次调用只读一段）
#=====================================================================
# ★ 生成物，勿手改：python test_server/tools/gate_pack_u1.py
# ★ 为什么按 idx 拆：铁律 88 说危险的不是"读了多少字节"，
#   是【单次运行的循环总量】。所以扫描必须由人一段一段驱动。
# ★ 为什么 skip 是十进制字面量：busybox ash 的 $(( )) 可能是 32 位，
#   0x810fd100 会溢出 —— 地址算术一律在 PC 侧算好。
# @gate script=u1_rd.sh opens=rdonly one_shot=1
# @seg name=ctl_dram_94000000 addr=0x94000000 bytes=3072 regs=768  # 阳性对照：Linux CMA 窗口，已知 dd 可读
# @seg name=ctl_dev_2082b000 addr=0x2082b000 bytes=3072 regs=768  # 阴性对照：设备寄存器区，预期 dd 失败
# @seg name=lut_a_810fd100 addr=0x810fd100 bytes=3072 regs=768  # 问题本体：p7 LUT 缓冲 A
# @seg name=lut_b_81115200 addr=0x81115200 bytes=3072 regs=768  # 问题本体：p7 LUT 缓冲 B（= LUT0）
# @seg name=ipc_20800000 addr=0x20800000 bytes=3072 regs=768  # IPC 区第 1/43 段
# @seg name=ipc_20800c00 addr=0x20800c00 bytes=3072 regs=768  # IPC 区第 2/43 段
# @seg name=ipc_20801800 addr=0x20801800 bytes=3072 regs=768  # IPC 区第 3/43 段
# @seg name=ipc_20802400 addr=0x20802400 bytes=3072 regs=768  # IPC 区第 4/43 段
# @seg name=ipc_20803000 addr=0x20803000 bytes=3072 regs=768  # IPC 区第 5/43 段
# @seg name=ipc_20803c00 addr=0x20803c00 bytes=3072 regs=768  # IPC 区第 6/43 段
# @seg name=ipc_20804800 addr=0x20804800 bytes=3072 regs=768  # IPC 区第 7/43 段
# @seg name=ipc_20805400 addr=0x20805400 bytes=3072 regs=768  # IPC 区第 8/43 段
# @seg name=ipc_20806000 addr=0x20806000 bytes=3072 regs=768  # IPC 区第 9/43 段
# @seg name=ipc_20806c00 addr=0x20806c00 bytes=3072 regs=768  # IPC 区第 10/43 段
# @seg name=ipc_20807800 addr=0x20807800 bytes=3072 regs=768  # IPC 区第 11/43 段
# @seg name=ipc_20808400 addr=0x20808400 bytes=3072 regs=768  # IPC 区第 12/43 段
# @seg name=ipc_20809000 addr=0x20809000 bytes=3072 regs=768  # IPC 区第 13/43 段
# @seg name=ipc_20809c00 addr=0x20809c00 bytes=3072 regs=768  # IPC 区第 14/43 段
# @seg name=ipc_2080a800 addr=0x2080a800 bytes=3072 regs=768  # IPC 区第 15/43 段
# @seg name=ipc_2080b400 addr=0x2080b400 bytes=3072 regs=768  # IPC 区第 16/43 段
# @seg name=ipc_2080c000 addr=0x2080c000 bytes=3072 regs=768  # IPC 区第 17/43 段
# @seg name=ipc_2080cc00 addr=0x2080cc00 bytes=3072 regs=768  # IPC 区第 18/43 段
# @seg name=ipc_2080d800 addr=0x2080d800 bytes=3072 regs=768  # IPC 区第 19/43 段
# @seg name=ipc_2080e400 addr=0x2080e400 bytes=3072 regs=768  # IPC 区第 20/43 段
# @seg name=ipc_2080f000 addr=0x2080f000 bytes=3072 regs=768  # IPC 区第 21/43 段
# @seg name=ipc_2080fc00 addr=0x2080fc00 bytes=3072 regs=768  # IPC 区第 22/43 段
# @seg name=ipc_20810800 addr=0x20810800 bytes=3072 regs=768  # IPC 区第 23/43 段
# @seg name=ipc_20811400 addr=0x20811400 bytes=3072 regs=768  # IPC 区第 24/43 段
# @seg name=ipc_20812000 addr=0x20812000 bytes=3072 regs=768  # IPC 区第 25/43 段
# @seg name=ipc_20812c00 addr=0x20812c00 bytes=3072 regs=768  # IPC 区第 26/43 段
# @seg name=ipc_20813800 addr=0x20813800 bytes=3072 regs=768  # IPC 区第 27/43 段
# @seg name=ipc_20814400 addr=0x20814400 bytes=3072 regs=768  # IPC 区第 28/43 段
# @seg name=ipc_20815000 addr=0x20815000 bytes=3072 regs=768  # IPC 区第 29/43 段
# @seg name=ipc_20815c00 addr=0x20815c00 bytes=3072 regs=768  # IPC 区第 30/43 段
# @seg name=ipc_20816800 addr=0x20816800 bytes=3072 regs=768  # IPC 区第 31/43 段
# @seg name=ipc_20817400 addr=0x20817400 bytes=3072 regs=768  # IPC 区第 32/43 段
# @seg name=ipc_20818000 addr=0x20818000 bytes=3072 regs=768  # IPC 区第 33/43 段
# @seg name=ipc_20818c00 addr=0x20818c00 bytes=3072 regs=768  # IPC 区第 34/43 段
# @seg name=ipc_20819800 addr=0x20819800 bytes=3072 regs=768  # IPC 区第 35/43 段
# @seg name=ipc_2081a400 addr=0x2081a400 bytes=3072 regs=768  # IPC 区第 36/43 段
# @seg name=ipc_2081b000 addr=0x2081b000 bytes=3072 regs=768  # IPC 区第 37/43 段
# @seg name=ipc_2081bc00 addr=0x2081bc00 bytes=3072 regs=768  # IPC 区第 38/43 段
# @seg name=ipc_2081c800 addr=0x2081c800 bytes=3072 regs=768  # IPC 区第 39/43 段
# @seg name=ipc_2081d400 addr=0x2081d400 bytes=3072 regs=768  # IPC 区第 40/43 段
# @seg name=ipc_2081e000 addr=0x2081e000 bytes=3072 regs=768  # IPC 区第 41/43 段
# @seg name=ipc_2081ec00 addr=0x2081ec00 bytes=3072 regs=768  # IPC 区第 42/43 段
# @seg name=ipc_2081f800 addr=0x2081f800 bytes=2048 regs=512  # IPC 区尾段
BB=/opt/usr/nx-ks/busybox
OUT=/mnt/mmc/u1/out
IDX="$1"

case "$IDX" in
  1) NAME=ctl_dram_94000000; SKIP=620756992; COUNT=768 ;;
  2) NAME=ctl_dev_2082b000; SKIP=136358912; COUNT=768 ;;
  3) NAME=lut_a_810fd100; SKIP=541324352; COUNT=768 ;;
  4) NAME=lut_b_81115200; SKIP=541348992; COUNT=768 ;;
  5) NAME=ipc_20800000; SKIP=136314880; COUNT=768 ;;
  6) NAME=ipc_20800c00; SKIP=136315648; COUNT=768 ;;
  7) NAME=ipc_20801800; SKIP=136316416; COUNT=768 ;;
  8) NAME=ipc_20802400; SKIP=136317184; COUNT=768 ;;
  9) NAME=ipc_20803000; SKIP=136317952; COUNT=768 ;;
  10) NAME=ipc_20803c00; SKIP=136318720; COUNT=768 ;;
  11) NAME=ipc_20804800; SKIP=136319488; COUNT=768 ;;
  12) NAME=ipc_20805400; SKIP=136320256; COUNT=768 ;;
  13) NAME=ipc_20806000; SKIP=136321024; COUNT=768 ;;
  14) NAME=ipc_20806c00; SKIP=136321792; COUNT=768 ;;
  15) NAME=ipc_20807800; SKIP=136322560; COUNT=768 ;;
  16) NAME=ipc_20808400; SKIP=136323328; COUNT=768 ;;
  17) NAME=ipc_20809000; SKIP=136324096; COUNT=768 ;;
  18) NAME=ipc_20809c00; SKIP=136324864; COUNT=768 ;;
  19) NAME=ipc_2080a800; SKIP=136325632; COUNT=768 ;;
  20) NAME=ipc_2080b400; SKIP=136326400; COUNT=768 ;;
  21) NAME=ipc_2080c000; SKIP=136327168; COUNT=768 ;;
  22) NAME=ipc_2080cc00; SKIP=136327936; COUNT=768 ;;
  23) NAME=ipc_2080d800; SKIP=136328704; COUNT=768 ;;
  24) NAME=ipc_2080e400; SKIP=136329472; COUNT=768 ;;
  25) NAME=ipc_2080f000; SKIP=136330240; COUNT=768 ;;
  26) NAME=ipc_2080fc00; SKIP=136331008; COUNT=768 ;;
  27) NAME=ipc_20810800; SKIP=136331776; COUNT=768 ;;
  28) NAME=ipc_20811400; SKIP=136332544; COUNT=768 ;;
  29) NAME=ipc_20812000; SKIP=136333312; COUNT=768 ;;
  30) NAME=ipc_20812c00; SKIP=136334080; COUNT=768 ;;
  31) NAME=ipc_20813800; SKIP=136334848; COUNT=768 ;;
  32) NAME=ipc_20814400; SKIP=136335616; COUNT=768 ;;
  33) NAME=ipc_20815000; SKIP=136336384; COUNT=768 ;;
  34) NAME=ipc_20815c00; SKIP=136337152; COUNT=768 ;;
  35) NAME=ipc_20816800; SKIP=136337920; COUNT=768 ;;
  36) NAME=ipc_20817400; SKIP=136338688; COUNT=768 ;;
  37) NAME=ipc_20818000; SKIP=136339456; COUNT=768 ;;
  38) NAME=ipc_20818c00; SKIP=136340224; COUNT=768 ;;
  39) NAME=ipc_20819800; SKIP=136340992; COUNT=768 ;;
  40) NAME=ipc_2081a400; SKIP=136341760; COUNT=768 ;;
  41) NAME=ipc_2081b000; SKIP=136342528; COUNT=768 ;;
  42) NAME=ipc_2081bc00; SKIP=136343296; COUNT=768 ;;
  43) NAME=ipc_2081c800; SKIP=136344064; COUNT=768 ;;
  44) NAME=ipc_2081d400; SKIP=136344832; COUNT=768 ;;
  45) NAME=ipc_2081e000; SKIP=136345600; COUNT=768 ;;
  46) NAME=ipc_2081ec00; SKIP=136346368; COUNT=768 ;;
  47) NAME=ipc_2081f800; SKIP=136347136; COUNT=512 ;;
  *) echo "usage: sh u1_rd.sh <idx 1..47>"; exit 2 ;;
esac

$BB mkdir -p "$OUT"

# ---- 一次连续的只读 + 落盘，屏幕只回一行 ----
nice -n 19 $BB dd if=/dev/mem of="$OUT/$NAME.bin" bs=4 count="$COUNT" skip="$SKIP" > "$OUT/$NAME.log" 2>&1
RC=$?
echo "dd_rc=$RC" >> "$OUT/$NAME.log"

$BB md5sum "$OUT/$NAME.bin" > "$OUT/$NAME.md5" 2>/dev/null
$BB sync
SZ=$($BB wc -c < "$OUT/$NAME.bin" 2>/dev/null)
echo "idx=$IDX name=$NAME skip=$SKIP count=$COUNT bytes=$SZ dd_rc=$RC"
$BB cat "$OUT/$NAME.log"
exit $RC
# 注：dd 失败（如设备寄存器区 /dev/mem 对 MMIO 被拒）时 dd_rc != 0，且 .bin 可能为 0 字节
#     —— 这本身就是结论，必须原样记录，不许因为"读不到"就跳过（铁律 118）。
#     退出码原样传递，便于由人/脚本判"这段到底读成了没有"。
