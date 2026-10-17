#!/bin/sh
# No filter selection or prefman writes. Compare each UI with identical nice 19.
set -eu
D=/opt/usr/nx-ks
BB=$D/busybox
S=/mnt/mmc/stage/nxui-perf-20261017
export DISPLAY=:0 LC_ALL=C
if "$BB" pidof nxui.arm >/dev/null 2>&1; then echo UI_ALREADY_RUNNING; exit 1; fi
chmod 755 "$S/nxui.arm"
sample() {
    echo "SAMPLE $1"
    cat /proc/uptime
    "$BB" head -n 1 /proc/stat
    for sample_name in Xorg di-camera-app onscreen_ks nxui.arm; do
        for sample_pid in $("$BB" pidof "$sample_name" || true); do
            echo "PROCESS $sample_name"
            cat "/proc/$sample_pid/stat"
            "$BB" grep -E 'VmRSS|voluntary_ctxt_switches|nonvoluntary_ctxt_switches' "/proc/$sample_pid/status"
        done
    done
    "$BB" head -n 9 /proc/meminfo
}
run_idle() {
    name=$1
    binary=$2
    "$BB" setsid "$BB" nice -n 19 "$binary" --dry-run --root "$D" --recipes /mnt/mmc/filmlab/recipes.txt --lifetime-ms 10000 > "$S/$name.log" 2>&1 &
    ui_pid=$!
    ( "$BB" sleep 15; kill -TERM "$ui_pid" 2>/dev/null; "$BB" sleep 1; kill -KILL "$ui_pid" 2>/dev/null ) &
    guard=$!
    "$BB" sleep 2
    sample "$name-start"
    "$BB" sleep 6
    sample "$name-end"
    wait "$ui_pid"
    kill "$guard" 2>/dev/null || true
    cat "$S/$name.log"
}
sample baseline-start
"$BB" sleep 4
sample baseline-end
run_idle old-idle "$D/nxui/nxui.arm"
run_idle new-idle "$S/nxui.arm"
st cap capdtm getusr 20
echo DONE
