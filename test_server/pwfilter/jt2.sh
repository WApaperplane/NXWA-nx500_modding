#!/bin/sh
BB=/opt/usr/nx-ks/busybox
F=/mnt/mmc/filmlab/recipes.json
jval() {
  $BB awk -v r="\"$1\": {" -v f="\"$2\":" '
    index($0, r) { inr=1; next }
    inr && index($0, f) {
      s = substr($0, index($0,f) + length(f))
      gsub(/[^0-9-]/, "", s)
      if (s != "") { print s; exit }
    }
    inr && $0 ~ /^    \}/ { exit }
  ' $F 2>/dev/null
}
jlist() {
  $BB awk '
    /"recipes"/ { inr=1; next }
    inr && /^    "[a-z0-9_]+": *\{/ {
      gsub(/^ +"/,""); gsub(/".*/,""); print
    }
  ' $F 2>/dev/null
}
echo "== jlist 原始输出（带 od 看隐藏字符）=="
jlist | head -3 | $BB od -c | head -6
echo
echo "== jlist 第一个 key 传给 jval =="
K=$(jlist | head -1)
echo "K=[$K] len=${#K}"
echo "jval K R_COLOR = [$(jval "$K" R_COLOR)]"
echo
echo "== 管道 while 版本 =="
jlist | while read k; do
  echo "  k=[$k] -> R=[$(jval "$k" R_COLOR)]"
  break
done
