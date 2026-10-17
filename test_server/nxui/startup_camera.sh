#!/bin/sh
# Actual installed shortcut scripts, without selecting a filter or saving.
set -eu
D=/opt/usr/nx-ks
BB=$D/busybox
S=/mnt/mmc/stage/nxui-perf-20261017
if "$BB" pidof nxui.arm >/dev/null 2>&1; then echo UI_ALREADY_RUNNING; exit 1; fi
for entry in EV_EV.sh EV_AEL.sh EV_EV.sh; do
    read stamp unused < /proc/uptime
    echo "TRIGGER $entry uptime=$stamp"
    /bin/bash "$D/$entry"
    "$BB" sleep 1
    ui_pid=$("$BB" pidof nxui.arm)
    echo "$ui_pid"
    sh "$D/nxui.sh" stop
    attempts=0
    while kill -0 "$ui_pid" 2>/dev/null; do
        attempts=$((attempts + 1))
        [ "$attempts" -le 30 ] || { echo STOP_TIMEOUT; exit 1; }
        "$BB" sleep 0.1
    done
done
"$BB" tail -n 35 /tmp/nxui.log
md5sum "$D/EV_EV.sh" "$D/nxui/nxui.arm" "$D/filmlab.sh" "$D/nxui.sh"
echo DONE
