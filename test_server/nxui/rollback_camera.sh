#!/bin/sh
set -eu
D=/opt/usr/nx-ks
BACKUP=$D/nxui/backup-20261017
[ -d "$BACKUP" ] || { echo 'Backup missing'; exit 1; }
sh "$D/nxui.sh" disable
if "$D/busybox" pidof nxui.arm >/dev/null 2>&1; then
    echo 'UI is finishing a backend operation. Run rollback again after it closes.'
    exit 1
fi
for name in filmlab.sh EV_AEL.sh EV_EV.sh loadgui.sh menu.sh telnet_toggle.sh; do
    [ -f "$BACKUP/$name" ] || { echo "Backup missing: $name"; exit 1; }
done
for name in filmlab.sh EV_AEL.sh EV_EV.sh loadgui.sh menu.sh telnet_toggle.sh; do
    cp "$BACKUP/$name" "$D/$name.nxui-old"
    chmod 755 "$D/$name.nxui-old"
    mv -f "$D/$name.nxui-old" "$D/$name"
done
sync
echo 'RESTORED original menu scripts. Current recipe is unchanged.'
