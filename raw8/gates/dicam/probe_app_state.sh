# App 运行态只读探测（U1 前置；一行一条命令）
echo ===PS_EF===
ps -ef 2>&1 | head -60
echo ===PGREP_CAMERA===
pgrep -l camera 2>&1
echo ===PGREP_ALL===
pgrep -l . 2>&1 | head -60
echo ===PROC_COUNT===
ls /proc | grep -cE ^[0-9]+$
echo ===CMDLINE_SCAN===
for p in /proc/[0-9]*; do c=$(cat $p/cmdline 2>/dev/null | tr '\0' ' '); if [ -n "$c" ]; then echo "$p $c"; fi; done | head -80
echo ===APP_RESULT_FILE===
ls -l /tmp/app_result 2>&1
echo ===APP_RESULT_CONTENT===
cat /tmp/app_result 2>&1 | head -5
echo ===ST_APP_HELP===
st app help 2>&1 | head -25
echo ===UNIT_STATE===
systemctl is-active di-camera-app 2>&1
systemctl status di-camera-app 2>&1 | head -20
echo ===END===
