S=/opt/usr/nx-ks/busybox
ts() { read U _ < /proc/uptime; echo "$U"; }
VARS='PWCOLOR_R|PWCOLOR_G|PWCOLOR_B|PWHUE|PWSATURATION|PWSHARPNESS|PWCONTRAST'
echo "pw_start=$(st cap capdtm getusr 20 2>/dev/null | tr -d '\r')"
run() {
  A=$(ts)
  /opt/usr/nx-ks/filmlab.sh preview "$1" >/tmp/pv.log 2>&1
  R=$?
  B=$(ts)
  echo "### $1  A=$A B=$B rc=$R  $(tail -1 /tmp/pv.log)"
  st cap capdtm varlist 2>/dev/null | $S grep -E "$VARS" | $S sed 's/  */ /g'
}
run portra400
run trix400
run portra800
echo "pw_end=$(st cap capdtm getusr 20 2>/dev/null | tr -d '\r')"
st cap capdtm setusr 20 0x140000 >/dev/null 2>&1
echo "pw_restored=$(st cap capdtm getusr 20 2>/dev/null | tr -d '\r')"
echo "done"
