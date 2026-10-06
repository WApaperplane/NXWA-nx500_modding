#!/bin/sh
# 3D LUT 调用者定位·快速版（限定目录 + 只扫常规文件，单核相机可跑）
BB=/opt/usr/nx-ks/busybox
O=/mnt/mmc/_xfer/odd3l
R=/mnt/mmc/_pwtest
mkdir -p $O

# 只扫这些目录，且只扫 <4MB 的（跳过大的 locale/字体/固件）
scan() {
  for d in /usr/bin /usr/sbin /usr/lib /lib; do
    [ -d $d ] || continue
    for f in $(find $d -maxdepth 2 -type f 2>/dev/null); do
      sz=$($BB stat -c %s $f 2>/dev/null || echo 99999999)
      [ "$sz" -gt 4194304 ] && continue
      if grep -qa "$1" $f 2>/dev/null; then
        echo "HIT[$1] $f ($sz)"
        cp $f $O/ 2>/dev/null
      fi
    done
  done
}

echo "=== [1] d5_ep_3dl ==="
scan d5_ep_3dl
echo "=== [2] ep_3dlut_reg_base ==="
scan ep_3dlut_reg_base
echo "=== [3] yccmixer ==="
scan yccmixer
echo "=== [4] ipcc_write_pkt ==="
scan ipcc_write_pkt
echo "=== [5] 已搬运 ==="
$BB ls -la $O
echo SCAN_DONE
