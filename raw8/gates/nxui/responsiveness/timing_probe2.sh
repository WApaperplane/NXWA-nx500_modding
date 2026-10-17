BB=/opt/usr/nx-ks/busybox
S() { $BB date +%s; }
T0=$(S); st cap capdtm getusr 20 >/dev/null 2>&1; T1=$(S); echo "getusr_1_s=$((T1-T0))"
T0=$(S); st cap capdtm getusr 20 >/dev/null 2>&1; T1=$(S); echo "getusr_2_s=$((T1-T0))"
T0=$(S); st cap capdtm getusr 20 >/dev/null 2>&1; T1=$(S); echo "getusr_3_s=$((T1-T0))"
T0=$(S); $BB awk -v want=portra400 'BEGIN{n=0}{n++}END{}' /mnt/mmc/filmlab/recipes.json >/dev/null 2>&1; T1=$(S); echo "awk_json_s=$((T1-T0))"
T0=$(S); /opt/usr/nx-ks/pwsend.arm seq 0x134 106 0x135 100 0x136 93 0x137 11 0x138 9 0x139 9 0x13A 8 0x13B 1 >/dev/null 2>&1; T1=$(S); echo "pwsend_dry_s=$((T1-T0))"
V=$(prefman get 0 0x0a3ec l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p')
T0=$(S); prefman set 0 0x0a3ec l "${V:-100}" >/dev/null 2>&1; T1=$(S); echo "prefman_set_1_s=$((T1-T0))"
T0=$(S); i=0; while [ $i -lt 7 ]; do prefman set 0 0x0a3ec l "${V:-100}" >/dev/null 2>&1; i=$((i+1)); done; T1=$(S); echo "prefman_set_x7_s=$((T1-T0))"
echo "slot9_r=$(prefman get 0 0x0a3ec l 2>/dev/null | tr -d '\r')"
echo "loadavg=$(cat /proc/loadavg)"
echo "engine_md5=$(md5sum /opt/usr/nx-ks/filmlab.sh 2>/dev/null | cut -d' ' -f1)"
echo "nxui_md5=$(md5sum /opt/usr/nx-ks/nxui/nxui.arm 2>/dev/null | cut -d' ' -f1)"
echo "DONE"
