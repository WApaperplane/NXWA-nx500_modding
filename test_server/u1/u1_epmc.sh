#!/bin/sh
#=====================================================================
# u1_epmc.sh -- U1 ⑤：epmc 只读 EP 寄存器（ISP 参数块 / 3dlut 自证 / mc 块）
#=====================================================================
# ★ 生成物，勿手改：python test_server/tools/gate_pack_u1.py
# ★ epmc 源码在 test_server/sysarch/epmc.c，经 /dev/drime5_ep 只读 mmap；
#   idx 0..9 对应 top/ldc/mc/rsz/lvr/bblt/fd/jpeg/3dlut/nog（与 p7_ep_windows.py 的
#   OFFICIAL 表双源互证：idx8=0x2082b000=3dlut，idx2=0x20824000=mc，idx9=nog）。
# ★ 本脚本的每一条调用有效扫描量都 <= 768 regs（铁律 88）。
# ★★ nz 模式里 nreg 是【结束下标】不是个数（epmc.c: for (i = from/4; i < nreg; i++)）：
#      "从 0x1300 起扫 512 个"  =>  epmc 0 1728 nz 0x1300
#    写成 epmc 0 512 nz 0x1300 会得到负长度、一次都不扫，却仍打印 "NZ nonzero 0/-704"。
# @gate script=u1_epmc.sh opens=rdonly one_shot=1
# 计划内的调用（runbook 逐步驱动）：
#   epmc 8 4   -- 自证：3dlut 前 4 个，应与已知 OnOff=0x1 / Cfg=0x100 / Pulse=0x0 / LUT0=0x81115200 对上  [有效 4 regs]
#   epmc 0 1728 nz 0x1300   -- ISP 参数块 A+B 非零面（0x20821300 / 0x20821700，落在 top 块内）  [有效 512 regs]
#   epmc 2 768   -- mc 块前 768 regs 非零面（0x20824000）  [有效 768 regs]
# @seg name=epmc8_base addr=0x20820000+0 bytes=16 regs=4
# @seg name=epmc0_0x1300 addr=0x20820000+0x1300 bytes=2048 regs=512
# @seg name=epmc2_base addr=0x20820000+0 bytes=3072 regs=768
BB=/opt/usr/nx-ks/busybox
OUT=/mnt/mmc/u1/out
BIN=/mnt/mmc/u1/epmc.arm

if [ ! -x "$BIN" ]; then echo "epmc.arm 缺失或不可执行: $BIN"; exit 3; fi

$BB mkdir -p "$OUT"
IDX="$1"; NREG="$2"; MODE="$3"; FROM="$4"
if [ -z "$IDX" ] || [ -z "$NREG" ]; then echo "usage: sh u1_epmc.sh <idx 0..9> <nreg> [nz [from]]"; exit 2; fi

LOG="$OUT/epmc_${IDX}_${NREG}_${MODE:-plain}_${FROM:-0}.log"
{ nice -n 19 "$BIN" "$IDX" "$NREG" $MODE $FROM ; echo "epmc_rc=$?" ; } > "$LOG" 2>&1
$BB sync
echo "log=$LOG"
$BB tail -n 8 "$LOG"
exit 0
# ★ 以下超出铁律 88（>768 regs），**故意不放进本脚本**：
#     epmc 2 2048 nz 0xc00
#   epmc 作者称 nz 模式把输出量压住即可，但"1024/2048 regs 压死相机"是实测事实。
#   ⇒ 必须先用 epmc 2 768 nz 跑通、且本人在机身看着，再考虑升级。见 runbook 的 NOTE。
