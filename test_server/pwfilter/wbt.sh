#!/bin/sh
BB=/opt/usr/nx-ks/busybox
rd() { prefman get 0 "$(printf 0x%05x $1)" l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p'; }
echo "=== WB 段当前值 ==="
echo "  WB_TYPE            (0xa390) = $(rd 41872)"
echo "  WB_K_VALUE         (0xa394) = $(rd 41876)"
echo "  WB_AUTO_BA         (0xa398) = $(rd 41880)"
echo "  WB_DAYLIGHT_BA     (0xa39c) = $(rd 41884)"
echo "  WB_CUSTOM_BA       (0xa3bc) = $(rd 41916)"
echo "  WB_K_BA            (0xa3c0) = $(rd 41920)"
echo "  CWB_RED            (0xa3c4) = $(rd 41924)"
echo "  CWB_GREEN          (0xa3c8) = $(rd 41928)"
echo "  CWB_BLUE           (0xa3cc) = $(rd 41932)"
echo
echo "=== setusr 层的 WB 索引 ==="
for i in 1 2 3 4 34 37; do
  R=$($BB sh -c "st cap capdtm getusr $i 2>/dev/null" | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p')
  echo "  idx $i = $R"
done
echo "WB_DONE"
