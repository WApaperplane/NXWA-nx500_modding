#!/bin/sh
# Compare old/new preview latency on the current field; restore its initial values.
set -eu
D=/opt/usr/nx-ks
BB=$D/busybox
S=/mnt/mmc/stage/nxui-response-20261017
"$BB" pidof nxui.arm >/dev/null 2>&1 && { echo UI_RUNNING; exit 1; }
PW=$(st cap capdtm getusr 20 | "$BB" sed -n 's/.*(\(0x[0-9a-f]*\)).*/\1/p')
case "$PW" in
  0x14000[0-8]) SLOT=$((PW - 0x140000)) ;;
  0x140009) SLOT=9 ;; 0x14000a) SLOT=10 ;; 0x14000c) SLOT=11 ;;
  *) echo UNKNOWN_FIELD; exit 1 ;;
esac
VALUES=
for param in 0 1 2 3 4 5 6; do
    addr=$(printf '0x%05x' $((41964 + param*52 + SLOT*4)))
    value=$(prefman get 0 "$addr" l | "$BB" sed -n 's/.*value = \([0-9]*\).*/\1/p')
    case "$value" in ''|*[!0-9]*) echo BAD_BACKUP; exit 1 ;; esac
    maximum=20; [ "$param" -ge 3 ] || maximum=200
    [ "$value" -le "$maximum" ] || exit 1
    VALUES="$VALUES $value"
done
printf 'BEFORE field=%s slot=%s values=%s\n' "$PW" "$SLOT" "$VALUES"
restore() {
    trap - EXIT HUP INT TERM
    param=0
    for value in $VALUES; do
        addr=$(printf '0x%05x' $((41964 + param*52 + SLOT*4)))
        prefman set 0 "$addr" l "$value" >/dev/null 2>&1
        param=$((param+1))
    done
    set -- $VALUES
    "$D/pwsend.arm" seq 0x134 "$1" 0x135 "$2" 0x136 "$3" 0x137 "$4" 0x138 "$5" 0x139 "$6" 0x13a "$7" 0x13b 1 --yes
    st cap capdtm setusr 20 "$PW"
    echo RESTORED
    st cap capdtm getusr 20
}
trap restore EXIT HUP INT TERM
for recipe in portra400 trix400; do
    for version in old new; do
        engine="$S/filmlab.sh"; [ "$version" != old ] || engine="$S/before/filmlab.sh"
        read start unused < /proc/uptime
        echo "CASE $version $recipe start=$start"
        "$BB" nice -n 19 /bin/sh "$engine" preview "$recipe"
        read end unused < /proc/uptime
        echo "END $version $recipe end=$end"
        st cap capdtm getusr 20
        st cap capdtm varlist > "$S/$version-$recipe.vars"
    done
done
restore
echo DONE
