#!/bin/sh
# Run from the extracted NXUI package on the SD card. No reboot/firmware edits.
set -eu
SOURCE=$(CDPATH= cd "$(dirname "$0")" && pwd)
D=/opt/usr/nx-ks
BACKUP=$D/nxui/backup-20261017
BB=$D/busybox
/bin/grep -q '^NX500$' /etc/version.info || { echo 'NX500 only'; exit 1; }
[ -f "$SOURCE/scripts/nxui/nxui.arm" ] || exit 1
cd "$SOURCE"
md5sum -c manifest.md5 || exit 1
if $BB pidof nxui.arm >/dev/null 2>&1; then echo 'Close the UI before installing'; exit 1; fi
# Reject concurrent changes: current scripts must equal the captured baseline or
# this exact package. This check happens before modifying any installed file.
for name in filmlab.sh EV_AEL.sh EV_EV.sh loadgui.sh menu.sh telnet_toggle.sh; do
    actual=$(md5sum "$D/$name"); actual=${actual%% *}
    next=$(md5sum "$SOURCE/scripts/$name"); next=${next%% *}
    [ "$actual" = "$next" ] || "$BB" awk -v file="$name" -v hash="$actual" \
        '$1 == hash && $2 == file { ok=1 } END { exit !ok }' expected-original.md5 \
        || { echo "Changed since baseline: $name"; exit 1; }
done
mkdir -p "$BACKUP"
for name in filmlab.sh EV_AEL.sh EV_EV.sh loadgui.sh menu.sh telnet_toggle.sh nxui.sh; do
    if [ -f "$D/$name" ] && [ ! -f "$BACKUP/$name" ]; then cp -p "$D/$name" "$BACKUP/$name"; fi
done
for name in filmlab.sh EV_AEL.sh EV_EV.sh loadgui.sh menu.sh telnet_toggle.sh nxui.sh; do
    cp "$SOURCE/scripts/$name" "$D/$name.nxui-new"
    chmod 755 "$D/$name.nxui-new"
    mv -f "$D/$name.nxui-new" "$D/$name"
done
cp "$SOURCE/scripts/nxui/nxui.arm" "$D/nxui/nxui.arm.new"
chmod 755 "$D/nxui/nxui.arm.new"
mv -f "$D/nxui/nxui.arm.new" "$D/nxui/nxui.arm"
cp "$SOURCE/scripts/nxui/NUKLEAR-LICENSE" "$D/nxui/NUKLEAR-LICENSE"
cp "$SOURCE/rollback_camera.sh" "$D/nxui/rollback.sh"
chmod 755 "$D/nxui/rollback.sh"
if [ "${1:-}" = --enable ]; then sh "$D/nxui.sh" enable; fi
sync
echo "INSTALLED enabled=$([ -f "$D/nxui/enabled" ] && echo yes || echo no) backup=$BACKUP"
md5sum "$D/nxui/nxui.arm" "$D/filmlab.sh" "$D/nxui.sh" "$D/telnet_toggle.sh"
