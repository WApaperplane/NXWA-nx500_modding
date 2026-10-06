#!/bin/sh
#=====================================================================
# p7_recover_official.sh — 用官方固件恢复整机（★★ 最高危，最后手段）
#---------------------------------------------------------------------
# ★★★ 这不是"刷 p7"，是走【机身菜单 Firmware Update】的官方整机恢复流程。
#   与 p7_flash_slp 的区别：
#     p7_flash_slp = 只写 p7 分区（Linux 还活着，telnet 还能连）
#     本脚本      = 准备官方 .bin 放到 SD 卡，由机身菜单自己刷
#
# ★ 前置条件（缺一不可）：
#     ① SD 卡根目录已有官方固件，且【已改名为 nx500.bin】← ★ 名字必须对
#     ② 相机电池充足
#     ③ 机身菜单可操作（p7 坏时Linux UI 仍在，能进设置菜单）
#
# ★ SLP 不含 pref(p2)/adj(p1)/pcache(p12) ⇒ 刷官方固件【不覆盖 FilmLab 持久化】
#   但 p12 若已改坏则无退路（备份在手）。
#=====================================================================

BB=/opt/usr/nx-ks/busybox
SD=/mnt/mmc
OFFICIAL=$SD/nx500.bin

echo "==== 官方固件恢复 ===="

if [ ! -f "$OFFICIAL" ]; then
  echo "!! SD 卡根目录缺 $OFFICIAL"
  echo
  echo "操作步骤："
  echo "  1. 从 PC 把官方固件 .bin 复制到 SD 卡根目录"
  echo "  ★ 2. 【必须改名】为 nx500.bin  ← 机身菜单只认这个名字"
  echo "  3. 相机开机 → 设置 → 固件更新 → 选择该文件"
  echo
  echo "★ 同版本 1.12 已验证刷成功（本项目实测）。"
  exit 1
fi

SZ=$(wc -c < "$OFFICIAL")
echo "找到: $OFFICIAL  ($SZ 字节)"

if [ "$SZ" -lt 1000000 ]; then
  echo "!! 文件过小，可能不完整。SD 卡复制中断的常见症状。"
  exit 1
fi

cat <<'EOF'

★ 下一步是机身菜单操作，本脚本无法代劳：
     设置 → 固件更新(Firmware Update) → 选择 nx500.bin → 确认
★ 刷写期间不要断电。
★ 完成后机身会重启，mod 会消失（SLP 不含 mod 所在分区？）
  —— 若 mod 消失，走SD 卡 info.tg 触发链重装。
EOF

# ---- 二次确认 ----
printf "已确认要走机身菜单恢复流程? type yes: "
read A
[ "$A" = "yes" ] || { echo "已取消。"; exit 0; }

echo
echo "★ 请现在转到机身菜单执行固件更新。"
echo "★ telnet 保持可用即可（Linux 侧未受影响）。"
