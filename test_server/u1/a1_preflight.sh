#!/bin/bash
# @gate script=a1_preflight.sh opens=rdonly one_shot=1
# =====================================================================
# A1 刷机前检查单（PC 侧 / Git Bash · 只读：仅校验本地包与资产，不接触相机）
#   出处：TASKFLOW_2026-10-12.md 离机轨 O4
#   全绿（或 MAN 项已人工确认）才允许进 W-2 刷机
# 用法: bash test_server/u1/a1_preflight.sh [相机IP]
# =====================================================================
cd "$(dirname "$0")/../.." || exit 1
ROOT=$(pwd)
A1DIR="E:/NXWA/fw/v1.12/a1"
S1="$A1DIR/slp_a1_p7_g_step1_v116.bin"
F1="$A1DIR/slp_a1_p7_g_v116.bin"
EXP_SIZE=352121435
EXP_S1_MD5=f515581f0b683ad804cf25618e6394af
EXP_F1_MD5=be2a908baf46261fd07ef1dd5b73951c
EXP_P7_S1=1e0be7df0ed54c4b71cd6a6a0ea3b243
EXP_P7_F1=2ee98811a60059353a82c46ee2d836bc
EXP_OFFICIAL_P7=f19441df58f8c2b0116ce99773bd5143
PY="C:/Users/31623/.workbuddy/binaries/python/versions/3.13.12/python.exe"

pass=0; fail=0; man=0
ok()   { echo "  [ OK ] $1"; pass=$((pass+1)); }
bad()  { echo "  [FAIL] $1"; fail=$((fail+1)); }
mm()   { echo "  [MAN ] $1"; man=$((man+1)); }

echo "=============================================="
echo " A1 刷机前检查单   $(date '+%Y-%m-%d %H:%M:%S')"
echo " 仓库根: $ROOT"
echo "=============================================="

echo "[1] 两个待刷包：存在 / 等长 / md5"
for pair in "$S1|$EXP_S1_MD5|step1" "$F1|$EXP_F1_MD5|full"; do
    f=${pair%%|*}; rest=${pair#*|}; exp=${rest%%|*}; nm=${rest#*|}
    if [ ! -f "$f" ]; then bad "$nm 缺席：$f"; continue; fi
    sz=$(stat -c%s "$f" 2>/dev/null || wc -c <"$f")
    m=$(md5sum "$f" | awk '{print $1}')
    [ "$sz" = "$EXP_SIZE" ] && ok "$nm 等长 $sz" || bad "$nm 长度 $sz ≠ $EXP_SIZE"
    [ "$m" = "$exp" ] && ok "$nm md5 匹配" || bad "$nm md5 $m ≠ $exp"
done

echo "[2] 包内 p7 镜像 md5（决定刷进去的到底是什么）"
for pair in "$S1|$EXP_P7_S1|step1" "$F1|$EXP_P7_F1|full"; do
    f=${pair%%|*}; rest=${pair#*|}; exp=${rest%%|*}; nm=${rest#*|}
    [ -f "$f" ] || { bad "$nm 包缺席，跳过"; continue; }
    got=$("$PY" - "$f" <<'EOF' 2>/dev/null
import struct,sys,hashlib
d=open(sys.argv[1],'rb').read()
l,c,o,m,e=struct.unpack('<IIII8s', d[0x40+5*24:0x40+5*24+24])
print(hashlib.md5(d[o:o+l]).hexdigest())
EOF
)
    [ "$got" = "$exp" ] && ok "$nm 包内 p7 = $exp" || bad "$nm 包内 p7 = $got ≠ $exp"
done

echo "[3] 回滚资产"
[ -f "raw8/emmcbak/p12_pristine.bin" ] && ok "纯净基线 p12_pristine.bin 在位" || bad "缺 p12_pristine.bin（纯净基线）"
[ -f "raw8/emmcbak/p7.bin" ] || [ -f "raw8/emmcbak/p7_orig.bin" ] \
    && ok "p7 分区原始态备份在位" || bad "缺 emmcbak/p7.bin（或 p7_orig.bin）"
[ -f "raw8/emmcbak/MANIFEST.txt" ] && ok "emmcbak/MANIFEST.txt 在位" || mm "缺 emmcbak MANIFEST（建 议补）"
ls .uploads/fw/*1.12* >/dev/null 2>&1 && ok "官方 1.12 完整件在位" || mm "未在 .uploads/fw/ 找到官方 1.12 完整件（回滚路径 2 需要）"
for b in boot0 boot1; do
    ls raw8/emmcbak/$b* >/dev/null 2>&1 && ok "$b 备份在位" || bad "缺 $b 备份（绝不碰，但必须有）"
done

echo "[4] 危险样本隔离"
ls raw8/p7/quarantine/*DO-NOT* >/dev/null 2>&1 && ok "危险样本已隔离" || mm "未检出隔离标记（对照 G4-0b）"

echo '[5] 设备固件版本 < 1.16（UI 只放行"文件版本 > 设备版本"）'
IP="${1:-}"
if [ -z "$IP" ]; then
    mm "未提供相机 IP ⇒ 请上机后手查（机身 MENU→Setting→Device Information）"
else
    v=$("$PY" test_server/telnet_run.py "$IP" "cat /etc/version.info" 2>/dev/null | tr -d '\r')
    echo "      /etc/version.info => $(echo "$v" | tr '\n' ' ')"
    echo "      ★ 注意：这是型号/固件版本，非 SLP 刷写器比对的那个 version。"
    mm "SLP 版本须在机身 Firmware Update 界面或包内比对（A1 包内已是 1.16）"
fi

echo
echo "----------------------------------------------"
echo " 汇总: OK=$pass  FAIL=$fail  MAN=$man"
if [ "$fail" -gt 0 ]; then
    echo " ⇒ 有 FAIL，禁止刷机（红门下不开机身）"
    exit 1
fi
[ "$man" -gt 0 ] && echo " ⇒ 无 FAIL；MAN 项请人工确认后再刷" || echo " ⇒ 全绿，可进 W-2"
exit 0
