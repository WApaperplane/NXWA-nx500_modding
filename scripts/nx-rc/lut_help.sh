#!/bin/sh
#=====================================================================
# lut_help.sh — 导入自定义 LUT 的操作说明（相机端可读）
#=====================================================================

BB=/opt/usr/nx-ks/busybox
D=/mnt/mmc/luts

cat<< 'EOF'
====== 导入自定义 3D LUT ======

★ 相机不认识 .cube 文本格式，必须先在 PC 上转换。

【第1 步｜PC 端转换】
    cd test_server/filmsim
    python cube2nxks.py "Kodak Portra 400.cube" out.nxks.bin

    可选参数：
      --size N       每通道级数（默认 17）
      --layout hex|planar
                     hex= 0xXXXX 文本（p7 调试用，默认）
                     planar = 裸16-bit 二进制

【第 2 步｜放进SD 卡】
    把 out.nxks.bin 复制到 SD 卡 /mnt/mmc/luts/
    （FTP 根目录就是 SD 卡，可直接传）

【第 3 步｜相机端应用】
    菜单 → P7 固件 → 色彩方案 → 导入 LUT
    或 telnet:sh /opt/usr/nx-ks/lut_scan.sh
              sh /opt/usr/nx-ks/lut_scan.sh apply<名字>

【恢复出厂】
    /opt/usr/nx-ks/lutload.arm restore
    —— 随时可退回，画面立即恢复

---- 技术原理 ----
LUT 数据通过 /dev/d5_sma（CMA 内存）落地，
再由硬件 DMA（rw_Start 脉冲）搬进 3DLUT 内部 RAM。
★ 因此【不需要改固件】，也不碰任何分区。

---- 排错 ----
画面花屏 → lutload.arm restore
SIGBUS    → 相机不在拍摄态，先按快门进拍摄模式
LUT 无效  → 3dlut_set.sh 的 SelCbCr_ch 通道值可能不对
           （p7 用两个字段控制通道，我方当前一律写 0）
EOF

echo
echo "当前 LUT 库：$D"
ls -la "$D"/*.nxks.bin 2>/dev/null || echo "(空)"
echo
echo "当前激活："
cat /mnt/mmc/filmlab/lut_active.txt 2>/dev/null || echo "(出厂)"