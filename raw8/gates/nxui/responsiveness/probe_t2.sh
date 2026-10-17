S=/opt/usr/nx-ks/busybox
ts() { read U _ < /proc/uptime; echo "$U"; }
echo "=== START $(ts) ==="
echo "--- backup slot-9 (if any) ---"
cat /mnt/mmc/filmlab/slot-backups/slot-9.txt 2>&1
echo "--- slot0 (standard) 7 dims ---"
i=0
while [ $i -lt 7 ]; do
  A=$(printf '0x%05x' $((41964 + 0*52 + i*4)))
  echo -n "s0.$i@$A="
  prefman get 0 "$A" l 2>/dev/null | $S sed -n 's/.*value = \([-0-9]*\).*/\1/p'
  i=$((i+1))
done
echo "--- slot9 (custom1) 7 dims ---"
i=0
while [ $i -lt 7 ]; do
  A=$(printf '0x%05x' $((41964 + 9*52 + i*4)))
  echo -n "s9.$i@$A="
  prefman get 0 "$A" l 2>/dev/null | $S sed -n 's/.*value = \([-0-9]*\).*/\1/p'
  i=$((i+1))
done
echo "--- st cap getusr 20 (no timeout, watch t) ---"
T0=$(ts); echo "T0=$T0"
st cap capdtm getusr 20
echo "T1=$(ts) RC=$?"
echo "=== END $(ts) ==="
