#!/bin/sh
BB=/opt/usr/nx-ks/busybox
F=/mnt/mmc/filmlab/recipes.json
echo "== 1. 文件存在? =="
ls -la $F
echo
echo "== 2. 文件前 5 行 =="
head -5 $F
echo
echo "== 3. grep R_COLOR =="
$BB grep -n "R_COLOR" $F | head -4
echo
echo "== 4. awk index 能否找到 =="
$BB awk -v r="portra400" 'index($0, r) { print "FOUND at line " NR; exit }' $F
echo
echo "== 5. 完整 jval =="
$BB awk -v r="\"portra400\": {" -v f="\"R_COLOR\":" '
  index($0, r) { inr=1; next }
  inr && index($0, f) {
    s = substr($0, index($0,f) + length(f))
    gsub(/[^0-9-]/, "", s)
    if (s != "") { print "GOT=[" s "]"; exit }
  }
  inr && $0 ~ /^    \}/ { print "END-OF-REC"; exit }
' $F
