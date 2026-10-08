#!/bin/sh
#=====================================================================
# u1_iqr.sh -- U1 ⑤：st cap iqr 全量 dump（184 个 eIQ_ID_*）
#=====================================================================
# ★ 生成物，勿手改：python test_server/tools/gate_pack_u1.py
# ★ 这是固件级改动"改了生效没有"的**唯一客观判据**（铁律 86 / 门 G5）。
#   离线跑必然失败（IPCC UDD open is failed），只有机上能拿到。
# ★ 只读：st cap iqr 是查询，不下发任何参数。
# @gate script=u1_iqr.sh opens=rdonly one_shot=1
BB=/opt/usr/nx-ks/busybox
OUT=/mnt/mmc/u1/out

$BB mkdir -p "$OUT"
{ echo "== st cap iqr"; st cap iqr ; echo "iqr_rc=$?" ; } > "$OUT/iqr_dump.txt" 2>&1

$BB sync
echo "iqr lines=$($BB wc -l < "$OUT/iqr_dump.txt" 2>/dev/null)"
echo "iqr ids=$($BB grep -o 'eIQ_ID_[A-Za-z0-9_]*' "$OUT/iqr_dump.txt" 2>/dev/null | $BB sort -u | $BB wc -l)"
exit 0
