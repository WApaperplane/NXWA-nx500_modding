#!/bin/sh
# FilmLab WiFi 键直达 —— 把FilmLab 挂到机身顶部 WiFi 连接键上，消灭三层菜单
#
# 本脚本只做【部署 + 自证】，不做安装（安装走 install.sh 的 cp -ar）。
# 用法（PC 端 Git Bash）：
#     cd /d/download/NX-KS2-88
#     python test_server/filmlab/src/deploy_wifi.sh
#
# 相机侧形态：
#   单击 WiFi 键      → 不触发任何东西（keyscan 无此分支，见下方说明）
#   双击 WiFi 键      → 无UI 直接轮换配方 + popup 显示当前配方名   ← 真一键
#   按住 EV + WiFi 键 → 打开 FilmLab 配方选择页（mod_gui 版，波轮不可用）
#   EV 键+ 弹nxfilmui → 打开 FilmLab 配方选择页（EFL 版，波轮 + 触屏都可用）
#
# ★ 关于「单击 WiFi 键」为什么做不到（不是偷懒，是keyscan 二进制的硬限制）：
#   scripts/keyscan 里能构造shell 名的格式串只有三个：
#       'EV_%s'   ← 按住 EV 时按其他键
#       '%s_%s'   ← 双击同一键
#       'MODE_SAS'← 模式盘松开（特例，无前缀）
#   没有「无前缀的普通单击」分支。而且门槛是 strlen(shell_name) > 4，
#   连 'MOBILE'（6 字符）都够长，纯粹是**没有这条分支**而非长度问题。
#   → 想实现单击必须重新编译 keyscan，风险见 docs/FILMLAB_ONEKEY_VERIFY.md。
BB=/opt/usr/nx-ks/busybox
D=/opt/usr/nx-ks

echo "== FilmLab WiFi 键直达：部署检查 =="

# ---------- 1. 引擎（不在 install.sh 部署链，必须单独 FTP 投递）----------
if [ -x "$D/filmlab.sh" ]; then
  echo "  ✓ 引擎       $D/filmlab.sh"
else
  echo "  ✗ 缺引擎     $D/filmlab.sh"
  echo "    ★ 跑 install.sh 无用（母本 scripts/ 下本来就没有它）"
  echo "    ★ 需 FTP 投递 test_server/filmsim/filmlab-apply.sh → $D/filmlab.sh"
  exit 1
fi

# ---------- 2. 配方库 ----------
if [ -f /mnt/mmc/filmlab/recipes.json ]; then
  N=$($BB grep -c '"key"' /mnt/mmc/filmlab/recipes.json 2>/dev/null || echo 0)
  echo "  ✓ 配方库     /mnt/mmc/filmlab/recipes.json（$N 条）"
else
  echo "  ✗ 无配方库   /mnt/mmc/filmlab/recipes.json（未插卡？）"
  exit 1
fi

# ---------- 3. 触发脚本 ----------
for f in EV_MOBILE.sh MOBILE_MOBILE.sh; do
  if [ -f "$D/nx-rc/$f" ]; then echo "  ✓ 脚本       $D/nx-rc/$f"
  else echo "  ✗ 缺脚本     $D/nx-rc/$f"; exit 1; fi
done

# ---------- 4. EFL 版 UI（可选，波轮要靠它）----------
if [ -x "$D/nx-rc/nxfilmui.arm" ]; then
  echo "  ✓ EFL UI     $D/nx-rc/nxfilmui.arm（波轮+触屏）"
else
  echo "  - EFL UI 未装（只有 mod_gui 版 UI，波轮不可用；不阻塞其它功能）"
fi

# ---------- 5. 重建 mod_gui 菜单（配方变了要刷新）----------
"$D/filmlab.sh" mkgui >/dev/null 2>&1
if [ -f "$D/gui_filmlab1b.NX500" ]; then
  echo "  ✓ mod_gui 菜单 $D/gui_filmlab1b.NX500"
else
  echo "  ✗ 菜单未生成"
  exit 1
fi

# ---------- 6. 功能自证：真的能写进去吗 ----------
echo ""
echo "== 自证：不写 PW，只读回当前状态 =="
$BB sh "$D/nx-rc/flab-verify.sh" pre 2>&1 | sed 's/^/  /'
echo ""
echo "== 全部就绪。触发方式：双击 WiFi 键= 无UI 轮换；EV+WiFi = 配方列表 =="
