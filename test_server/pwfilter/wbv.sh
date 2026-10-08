#!/bin/sh
BB=/opt/usr/nx-ks/busybox
rd() { prefman get 0 "$(printf 0x%05x $1)" l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p'; }
wr() { prefman set 0 "$(printf 0x%05x $1)" l "$2" >/dev/null 2>&1; }

echo "=== 实验：CUSTOM 模式下tint 写哪个地址有效 ==="
echo "起始: CUSTOM_BA(0xa3bc)=$(rd 41916)  K_BA(0xa3c0)=$(rd 41920)  K=$(rd 41876)"
echo
echo "--- 只写 0xa3bc = (15<<16)|3 = A15/B3 ---"
wr 41916 $(( (15<<16) | 3 ))
echo "  0xa3bc = $(rd 41916)   0xa3c0 = $(rd 41920)"
echo "  >>> 看画面：是否变成【强烈的绿/品红偏移】？（A15 B3 是极端值，必然可见）"
echo
echo "--- 再只写 0xa3c0 = (3<<16)|15 ---"
wr 41920 $(( (3<<16) | 15 ))
echo "  0xa3bc = $(rd 41916)   0xa3c0 = $(rd 41920)"
echo "  >>> 看画面：是否有变化？与上面相比哪个更强？"
echo
echo "=== 恢复中性 ==="
wr 41916 $(( (7<<16) | 7 ))
wr 41920 $(( (7<<16) | 7 ))
echo "  0xa3bc = $(rd 41916)  0xa3c0 = $(rd 41920)"
echo "WBV_DONE"
