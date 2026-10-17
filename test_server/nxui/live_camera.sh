#!/bin/sh
# Bounded physical trial. Selecting a recipe previews in the current PW field.
set -eu
D=/opt/usr/nx-ks
BB=$D/busybox
S=/mnt/mmc/stage/nxui-perf-20261017
export DISPLAY=:0 LC_ALL=C
if "$BB" pidof nxui.arm >/dev/null 2>&1; then echo UI_ALREADY_RUNNING; exit 1; fi
st cap capdtm getusr 20
"$BB" setsid "$S/nxui.arm" --live --root "$D" --engine "$S/filmlab.sh" --recipes /mnt/mmc/filmlab/recipes.txt --menu gui_ini.NX500 --lifetime-ms 120000 &
ui_pid=$!
( "$BB" sleep 135; kill -TERM "$ui_pid" 2>/dev/null; "$BB" sleep 1; kill -KILL "$ui_pid" 2>/dev/null ) &
guard=$!
wait "$ui_pid"
kill "$guard" 2>/dev/null || true
st cap capdtm getusr 20
"$BB" uptime
echo DONE
