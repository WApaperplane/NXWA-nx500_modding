#!/bin/sh
BB=/opt/usr/nx-ks/busybox
rd() { prefman get 0 "$(printf 0x%05x $1)" l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p'; }
rdw() { prefman get 0 "$(printf 0x%05x $1)" w 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p'; }
rdb() { prefman get 0 "$(printf 0x%05x $1)" b 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p'; }
PB=41964
A() { echo $(( PB + $1 * 52 + $2 * 4 )); }
echo "=== prefman get 的 type 参数对同一地址的读数（验证是否跨条目）==="
for d in 0 1 2 3 4 5 6; do
  AD=$(A $d 0)
  echo "  dim=$d addr=0x$(printf %04x $AD)  l(long)=$(rd $AD)  w(word)=$(rdw $AD)  b(byte)=$(rdb $AD)"
done
echo
echo "=== 各厂商风格 7 维（long 读法）==="
for st in 0 1 2 3 4 5 6 7 8; do
  printf "  slot %-2s R=%-6s G=%-6s B=%-6s HUE=%-8s SAT=%-8s SHARP=%-6s CON=%-6s\n" $st \
    "$(rd $(A 0 $st))" "$(rd $(A 1 $st))" "$(rd $(A 2 $st))" "$(rd $(A 3 $st))" \
    "$(rd $(A 4 $st))" "$(rd $(A 5 $st))" "$(rd $(A 6 $st))"
done
echo "VT_DONE"
