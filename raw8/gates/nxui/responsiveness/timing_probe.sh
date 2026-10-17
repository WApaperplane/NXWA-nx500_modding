BB=/opt/usr/nx-ks/busybox
S() { $BB date +%s; }
T0=$(S); i=0; while [ $i -lt 20 ]; do prefman get 0 0x0a3ec l >/dev/null 2>&1; i=$((i+1)); done; T1=$(S)
echo "prefman_get_x20_s=$((T1-T0))"
T2=$(S); i=0; while [ $i -lt 20 ]; do /bin/true; i=$((i+1)); done; T3=$(S)
echo "true_x20_s=$((T3-T2))"
T4=$(S); i=0; while [ $i -lt 3 ]; do st cap capdtm getusr 20 >/dev/null 2>&1; i=$((i+1)); done; T5=$(S)
echo "getusr20_x3_s=$((T5-T4))"
T6=$(S); i=0; while [ $i -lt 20 ]; do $BB md5sum /mnt/mmc/filmlab/recipes.json >/dev/null 2>&1; i=$((i+1)); done; T7=$(S)
echo "md5_x20_s=$((T7-T6))"
T8=$(S); i=0; while [ $i -lt 10 ]; do $BB awk -F'|' '{n++} END{}' /mnt/mmc/filmlab/recipes.txt >/dev/null 2>&1; i=$((i+1)); done; T9=$(S)
echo "awk_x10_s=$((T9-T8))"
T10=$(S); i=0; while [ $i -lt 10 ]; do prefman get 0 0x0a3ec l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p' >/dev/null; i=$((i+1)); done; T11=$(S)
echo "prefman_get_pipe_x10_s=$((T11-T10))"
echo "slot9_now=$(prefman get 0 0x0a3ec l 2>/dev/null | tr -d '\r')"
echo "pw_now=$(st cap capdtm getusr 20 2>/dev/null | tr -d '\r')"
echo "loadavg=$(cat /proc/loadavg)"
echo "engine_md5=$(md5sum /opt/usr/nx-ks/filmlab.sh 2>/dev/null | cut -d' ' -f1)"
echo "nxui_md5=$(md5sum /opt/usr/nx-ks/nxui/nxui.arm 2>/dev/null | cut -d' ' -f1)"
