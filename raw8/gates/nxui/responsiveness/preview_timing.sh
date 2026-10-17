S=/opt/usr/nx-ks/busybox
ts() { read U _ < /proc/uptime; echo "$U"; }
echo "conf_pw=$(grep '^FILMLAB_PW' /mnt/mmc/filmlab/filmlab.conf 2>/dev/null)"
echo "pw_before=$(st cap capdtm getusr 20 2>/dev/null | tr -d '\r')"
A=$(ts); /opt/usr/nx-ks/filmlab.sh preview portra400 >/tmp/p1.log 2>&1; RC1=$?; B=$(ts)
echo "P1_a=$A P1_b=$B rc=$RC1"
C=$(ts); /opt/usr/nx-ks/filmlab.sh preview trix400 >/tmp/p2.log 2>&1; RC2=$?; D=$(ts)
echo "P2_a=$C P2_b=$D rc=$RC2"
echo "tail1=$(tail -1 /tmp/p1.log)"
echo "tail2=$(tail -1 /tmp/p2.log)"
echo "pw_after_preview=$(st cap capdtm getusr 20 2>/dev/null | tr -d '\r')"
st cap capdtm setusr 20 0x140000 >/dev/null 2>&1
echo "pw_restored=$(st cap capdtm getusr 20 2>/dev/null | tr -d '\r')"
echo "done"
