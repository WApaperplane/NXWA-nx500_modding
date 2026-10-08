#!/bin/sh
#=====================================================================
# lutapi_help.sh — 3D LUT 官方 API 路线（相机端可读）
#=====================================================================
# ★ 2026-10-07 重写：只保留实机验证过的内容
#=====================================================================

BB=/opt/usr/nx-ks/busybox
API=/opt/usr/nx-ks/lutapi.arm
D=/mnt/mmc/luts

cat<< 'EOF'
====== 3D LUT：官方 API 路线 ======

★★★ 结论：可以用户态导入，不需要改固件 ★★★

★ 为什么以前会花屏？
   我改了硬件的表地址寄存器，让 ISP 去读一个
   "数据口袋体系"之外的地址 → 花屏。
   ★ 用【厂商自己的通道】灌（sel=0）就完全正常。

---- 快速上手 ----

第 1 步｜探测落点（★ 每次必跑，绝不能跳过）
    /opt/usr/nx-ks/cmapick2.arm 1024 32
    记下 "4KB 粒度命中：0x........ 起连续 XX KB"

第 2 步｜灌表（★ sel 必须用 0）
    /opt/usr/nx-ks/lutapi.arm load /mnt/mmc/luts/<表>.bin 0x........ 0 1 17 2 300 0
                                             ↑地址       ↑sel
    参数：<file> <phys> [sel=0] [fmt=1] [size=17] [stride=2] [settle=200] [cbcr=0]
      sel  0=LUT0（★用这个） 1=LUT1 2=外部通道（★会花屏）
      fmt  0=YCC422 1=YCC420

第 3 步｜看取景器
    ★★ 不要半按快门！★★

---- 为什么不能半按快门 ----
  实测：半按对焦后 p7 会把表地址抢回出厂值。
  ⇒ 我的表就被覆盖了。
  ⇒ 这不是出错，是 p7 正常工作。

---- 回滚 ----
    /opt/usr/nx-ks/lutload.arm restore
  然后半按快门对焦（让 p7 重新灌入出厂表）

---- 排错 ----
安全闸拦住        ep_3dlut_reg_base == 0
                  ⇒ 相机在拍摄态。等它回菜单界面再试。
花屏              ★ 用了 sel=2。改成 sel=0。
半按后恢复        ★ 正常现象，p7 抢回指针了。
偏色/色阶断裂     ★★ 已知未解决（色彩空间未匹配），见下。

---- 已知问题：偏色 ----
  RGB 的 .cube 灌进去会偏色（Portra 偏红、Kodachrome 偏蓝紫）。
  ★ 怀疑是色彩空间问题：官方头文件写的是 YCC420/422，
    而且参数名就叫 CBCR —— 硬件很可能在 YCbCr 空间运算。
  ★ 但【还没验证】，连identity 表灌进去都不中性。
  ⇒ 目前只能判别，不能正常使用。

---- 工具清单 ----
  lutapi.arm      官方 API 封装（load/save/verify/opinit/probe）
  lutload.arm     旧的手写寄存器路线（仅用于 restore 回滚）
  cmapick2.arm    CMA 落点探测（双区 + 可调粒度）
  eptest_open.arm 测 d5_ep_open 能否工作
  v2p.arm         virt_to_phys 裸 ioctl 测试

---- PC 端转换 ----
  .cube 是 33³ RGB，硬件需要 17³×3×u16：
    cd test_server/filmsim
    python cube2nx17.py "Kodak Portra 400.cube" out.bin
EOF

echo
echo "=========================================="
echo " 当前 LUT 库：$D"
ls -la "$D"/*.bin 2>/dev/null | head -20 || echo "(空)"
echo
echo " 第一次使用请先跑：sh /opt/usr/nx-ks/lutapi_probe.sh"
echo "=========================================="