S=/opt/usr/nx-ks/busybox
echo "=== start $(cat /proc/uptime) ==="
echo "--- busy procs ---"
ps -eo pid,etime,pcpu,comm 2>/dev/null | $S sort -k3 -nr 2>/dev/null | head -8
echo "--- st getusr x1 (timeout 15) ---"
T0=$($S date +%s)
$S timeout 15 st cap capdtm getusr 20
echo "RC=$? D=$(( $($S date +%s) - T0 ))"
echo "--- st getusr x1 again ---"
T0=$($S date +%s)
$S timeout 15 st cap capdtm getusr 20
echo "RC=$? D=$(( $($S date +%s) - T0 ))"
echo "--- prefman get x1 ---"
T0=$($S date +%s)
prefman get 0 0x0a3ec l
echo "RC=$? D=$(( $($S date +%s) - T0 ))"
echo "--- pwsend dry x1 ---"
T0=$($S date +%s)
/opt/usr/nx-ks/pwsend.arm seq 0x134 106 0x135 100 0x136 93 0x137 11 0x138 9 0x139 9 0x13A 8 0x13B 1
echo "RC=$? D=$(( $($S date +%s) - T0 ))"
echo "=== end $(cat /proc/uptime) ==="
