#!/bin/sh
# Exercise the real staged UI. Restore both services independently if the test exits.
set -eu
D=/opt/usr/nx-ks
BB=$D/busybox
S=/mnt/mmc/stage/nxui-response-20261017
export DISPLAY=:0 LC_ALL=C
"$BB" pidof nxui.arm >/dev/null 2>&1 && { echo UI_RUNNING; exit 1; }
chmod 755 "$S/nxui.arm" "$S/test_input.arm" "$S/telnet_toggle.sh"
printf 'button|Telnet/FTP|telnet_toggle.sh\n' > "$S/gui_services.NX500"
( "$BB" sleep 12; sh "$S/telnet_toggle.sh" --ui enable >> "$S/recovery.log" 2>&1 ) &
guard=$!
trap 'sh "$S/telnet_toggle.sh" --ui enable; kill "$guard" 2>/dev/null || true' EXIT
"$BB" setsid "$S/nxui.arm" --live --root "$S" --engine "$S/filmlab.sh" --recipes /mnt/mmc/filmlab/recipes.txt --menu gui_services.NX500 --lifetime-ms 10000 > "$S/service-ui.log" 2>&1 &
ui_pid=$!
"$BB" sleep 1
"$S/test_input.arm" click 160 65 5
wait_action() {
    n=0
    while [ "$("$BB" grep -c 'BACKEND kind=4 ok=1' "$S/service-ui.log" || true)" -lt "$1" ]; do
        n=$((n+1)); [ "$n" -lt 60 ] || { echo ACTION_TIMEOUT; exit 1; }
        "$BB" sleep 0.1
    done
}
wait_action 1
"$S/test_input.arm" click 160 65 5
wait_action 2
kill -TERM "$ui_pid"
wait "$ui_pid"
cat "$S/service-ui.log"
echo DONE
