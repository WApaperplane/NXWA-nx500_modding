#!/bin/sh
# UI mode returns verified listener state; legacy callers retain the popup.
D=/opt/usr/nx-ks
BB=$D/busybox
UI=0
if [ "${1:-}" = --ui ]; then UI=1; shift; fi
ACTION=${1:-toggle}
listeners() {
    set -- /proc/net/tcp
    [ -r "$1" ] || return 1
    [ ! -r /proc/net/tcp6 ] || set -- "$@" /proc/net/tcp6
    "$BB" awk '
      $4 == "0A" {
        if ($2 ~ /:0017$/) t=1
        if ($2 ~ /:0015$/) f=1
      }
      END { printf "%d %d\n", t, f }
    ' "$@" 2>/dev/null
}
read_state() {
    STATE=$(listeners) || return 1
    set -- $STATE
    TN=${1:-0}; FTP=${2:-0}
}
read_state || { echo 'Cannot read service listeners'; exit 1; }
case "$ACTION" in
  toggle) if [ "$TN" = 1 ] && [ "$FTP" = 1 ]; then ACTION=disable; else ACTION=enable; fi ;;
  enable|disable) ;;
  *) echo 'telnet_toggle.sh [--ui] [enable|disable|toggle]'; exit 2 ;;
esac
if [ "$ACTION" = disable ]; then
    "$BB" killall -q telnetd 2>/dev/null
    # When invoked as `busybox tcpsvd`, /proc names it busybox, so killall
    # tcpsvd misses it. Match this binary, applet and FTP bind port precisely.
    FTP_PIDS=$("$BB" ps -o pid,args | "$BB" awk -v bb="$BB" '
      $2 == bb && $3 == "tcpsvd" {
        for (i=4; i<NF; i++) if ($i == "0.0.0.0" && $(i+1) == "21") { print $1; break }
      }')
    for service_pid in $FTP_PIDS; do "$BB" kill -TERM "$service_pid" 2>/dev/null; done
    WANT=0
else
    # Daemons must not inherit the UI's output pipe or hold an action open.
    if [ "$TN" != 1 ]; then
        "$BB" nice -n 10 "$D/telnetd" </dev/null >/dev/null 2>&1 &
    fi
    if [ "$FTP" != 1 ]; then
        "$BB" nice -n 10 "$BB" tcpsvd -u root -vE 0.0.0.0 21 \
            "$BB" ftpd -w -v /opt/storage/sdcard </dev/null >/dev/null 2>&1 &
    fi
    WANT=1
fi
ATTEMPT=0
while :; do
    read_state || { echo 'Cannot read service listeners'; exit 1; }
    [ "$TN" = "$WANT" ] && [ "$FTP" = "$WANT" ] && break
    [ "$ATTEMPT" -lt 20 ] || break
    "$BB" sleep 0.1
    ATTEMPT=$((ATTEMPT + 1))
done
echo "SERVICES telnet=$TN ftp=$FTP requested=$ACTION"
if [ "$TN" != "$WANT" ] || [ "$FTP" != "$WANT" ]; then
    echo 'Service state did not reach the requested setting'
    exit 1
fi
if [ "$UI" = 0 ]; then
    if [ "$WANT" = 0 ]; then
        "$D/popup_timeout" 'Telnet/FTP 已关闭' 3
    else
        IP=$("$BB" ip addr ls 2>/dev/null | "$BB" awk '/inet/ && /mlan0/ { for(i=1;i<=NF;i++) if($i ~ /^[0-9]+\./) { sub(/\/.*/, "", $i); print $i; exit } }')
        "$D/popup_timeout" "Telnet/FTP: ${IP:-WiFi未开}" 5
    fi
fi
exit 0
