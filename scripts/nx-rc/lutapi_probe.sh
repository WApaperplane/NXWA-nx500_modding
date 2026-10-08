#!/bin/sh
#=====================================================================
# lutapi_probe.sh — 官方 3D LUT API 零风险探测（★ 第一次必跑这个）
#=====================================================================
# 只做：dlopen + dlsym + d5_ep_open/close + 试映射 /dev/d5_sma
# 不做：任何寄存器写、任何 DMA、任何数据落盘到 CMA
#⇒ 结构上不可能花屏 / 卡死
#=====================================================================

BB=/opt/usr/nx-ks/busybox
API=/opt/usr/nx-ks/lutapi.arm

echo "==================================================="
echo " 官方 3D LUT API 探测（零风险）"
echo " 时间：$(date 2>/dev/null)"
echo "==================================================="

if [ ! -x "$API" ]; then
    echo "★ 找不到 $API"
    echo "  需先编译并放到 SD 卡 scripts/sysarch/"
    exit 1
fi

echo
echo ">>> [1/5] dlsym 符号解析"
"$API" info
rc=$?
if [ $rc -ne 0 ]; then
    echo "★ probe 失败（rc=$rc）"
    echo "  若提示 dlopen 失败，检查 libudd5.so 是否在 /usr/lib"
    exit $rc
fi

echo
echo ">>> [2/5] d5_ep_open + mmap/virt_to_phys 能力探测"
echo "  ★ 这一步决定 load 能不能用："
echo "    官方 API 内部第一件事就是 d5_ep_sma_virt_to_phys()，"
echo "    而它要求进程里有有效设备句柄（g_d5_dev_ctx >= 0）"
"$API" probe

echo
echo ">>> [3/5] 3D LUT 寄存器快照（只读）"
"$API" regdump

echo
echo ">>> [4/5] 生成 identity 测试表（纯本地计算，不碰硬件）"
mkdir -p /mnt/mmc/luts 2>/dev/null
"$API" idgen /mnt/mmc/luts/id17.bin 17 2

echo
echo ">>> [5/5] CMA 落点探测（★ 决定能不能load）"
if [ -x /opt/usr/nx-ks/cmapick.arm ]; then
    /opt/usr/nx-ks/cmapick.arm 2>&1 | tail -20
else
    echo "  (跳过：未部署 cmapick.arm)"
fi

echo
echo "==================================================="
echo " 探测完成"
echo "==================================================="
cat<< 'EOF'

★ 判读要点

1) ep_3dlut_reg_base
   非 0  ⇒ ★★ 官方 API 在我们进程可用，走 load 路线
   为 0  ⇒ d5_ep_open 没成功（相机可能在拍摄态，主程序持有设备）
            等回到菜单界面再跑一次

2) CMA 落点（cmapick 输出）
   出现"可用落点"  ⇒ 记下那个地址，load 时用
   "无可用落点"    ⇒ ★ CMA 已被 ISP 占满，此时导入【必然卡死】
                     ★ 不要尝试 load！等 ISP 空闲（或退出拍摄态）再试

3) 寄存器快照
   +0x00c = 0x81115200  ⇒ 出厂肤色档，p7 正常工作（正常现象）
   bit8 = 1             ⇒ LUT0 格式 = YCC420（★ load 时 fmt 要用 1）

---- 下一步 ----
# 有可用落点时：
/opt/usr/nx-ks/lutapi.arm verify /mnt/mmc/luts/id17.bin <可用落点> 2 1
  ↑ load + save 逐字节比对，这是判断"通路真的通了"的唯一办法
  ★ 不要跳过它直接看画面——画面变化可能是巧合

# 出问题立刻回滚：
/opt/usr/nx-ks/lutload.arm restore
EOF