S=/opt/usr/nx-ks/busybox
ts() { read U _ < /proc/uptime; echo "$U"; }
echo "start=$(ts)"
T=$(ts); st cap capdtm getusr 20 >/dev/null 2>&1; echo "T_getusr=$(ts) <start $T>"
T=$(ts); st cap capdtm setusr 20 0x140000 >/dev/null 2>&1; echo "T_setusr=$(ts) <start $T>"
T=$(ts); st cap capdtm getusr 20 >/dev/null 2>&1; echo "T_getusr2=$(ts) <start $T>"
T=$(ts); i=0; while [ $i -lt 7 ]; do prefman get 0 0x0a3ec l >/dev/null 2>&1; i=$((i+1)); done; echo "T_prefman_get7=$(ts) <start $T>"
T=$(ts); /opt/usr/nx-ks/pwsend.arm seq 0x134 106 0x135 100 0x136 93 0x137 11 0x138 9 0x139 9 0x13A 8 >/dev/null 2>&1; echo "T_pwsend_dry=$(ts) <start $T>"
T=$(ts); i=0; while [ $i -lt 20 ]; do /bin/true; i=$((i+1)); done; echo "T_true20=$(ts) <start $T>"
echo "end=$(ts)"
echo "loadavg=$(cat /proc/loadavg)"
