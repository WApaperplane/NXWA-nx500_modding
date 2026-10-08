#!/bin/sh
BB=/opt/usr/nx-ks/busybox
rd() { prefman get 0 "$(printf 0x%05x $1)" l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p'; }
wr() { prefman set 0 "$(printf 0x%05x $1)" l "$2" >/dev/null 2>&1; }
echo "=== 探测 WB_TYPE 合法值（set 0..15 看哪个被接受）==="
ORIG=$(rd 41872)
echo "原始 WB_TYPE = $ORIG"
for v in 0 1 2 3 4 5 6 7 8 9 10 11 12; do
  wr 41872 $v
  R=$(rd 41872)
  if [ "$R" = "$v" ]; then echo "  v=$v接受"; else echo "  v=$v 被拒(读回 $R)"; fi
done
wr 41872 $ORIG
echo "恢复 WB_TYPE = $(rd 41872)"
echo
echo "=== tint 编码验证：写 (A<<16)|B ==="
echo "当前 WB_CUSTOM_BA = $(rd 41916)  = hex $(printf 0x%06x $(rd 41916))"
echo "  拆A = $(( ($(rd 41916) >> 16) & 0xffff ))   B = $(( $(rd 41916) & 0xffff ))"
echo "  中性应为 0x00070007 -> A=7 B=7（记忆里的中性值）"
echo
echo "=== 试写 K + 强制 WB_TYPE=3(K 手动?) ==="
wr 41876 7500
wr 41872 3
echo "  WB_TYPE=$(rd 41872)  K=$(rd 41876)"
echo "  >>> 请看取景器：画面是否明显偏冷（7500K 应偏蓝）？ <<<<<"
echo "WB2_DONE"
