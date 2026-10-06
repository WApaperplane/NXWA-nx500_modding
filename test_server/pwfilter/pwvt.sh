#!/bin/sh
# pwvt.sh — 7 维多类型读取器（long/byte 双读，识别厂商槽垃圾值）
BB=/opt/usr/nx-ks/busybox
PB=41964
A() { echo $(( PB + $1 * 52 + $2 * 4 )); }
rdl() { prefman get 0 "$(printf 0x%05x $1)" l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p'; }
rdb() { prefman get 0 "$(printf 0x%05x $1)" b 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p'; }
STY="STANDARD VIVID PORTRAIT LANDSCAPE FOREST RETRO COOL CALM CLASSIC CUSTOM_1 CUSTOM_2 CUSTOM_3 CUSTOM_4"
i=0
printf "%-10s %-16s %-16s %-16s %s\n" "slot" "R/G/B" "HUE(l/b)" "SAT(l/b)" "SHARP/CON(l)"
for st in 0 1 2 3 4 5 6 7 8 9 10 11 12; do
  S=$(echo $STY | cut -d' ' -f$((st+1)))
  R=$(rdl $(A 0 $st)); G=$(rdl $(A 1 $st)); B=$(rdl $(A 2 $st))
  HL=$(rdl $(A 3 $st)); HB=$(rdb $(A 3 $st))
  SL=$(rdl $(A 4 $st)); SB=$(rdb $(A 4 $st))
  P=$(rdl $(A 5 $st));  C=$(rdl $(A 6 $st))
  FLAG=""
  [ "$HB" -gt 100 ] 2>/dev/null && FLAG="$FLAG HUE?"
  [ "$SB" -gt 100 ] 2>/dev/null && FLAG="$FLAG SAT?"
  printf "%-10s %-16s %-16s %-16s %s/%s %s\n" "$st:$S" "$R/$G/$B" "$HL/$HB" "$SL/$SB" "$P" "$C" "$FLAG"
  i=$((i+1))
done
echo "PWVT_DONE"
