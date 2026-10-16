#!/bin/bash
# run_p5_qemu.sh — P5 投递链「上机前 VM 预演」（对应上机批 U1 的机制层）
#
# 覆盖：
#   A) t2_premount.sh 三态：正常挂载（T2+M2 两条目）/ 幂等 / 独立禁用 + 清场
#   B) dicam_p5_install.sh：真 unit（rootfs-112 自带）注入 / 幂等 / 备份
#   C) dicam_p5_rollback.sh：互逆移除 / 与原始逐字节一致
#   D) 异常 unit（无 ExecStart=）：报错退出、不修改、无残留
#
# ★ 安全设计：全部在**私有 mount namespace**（unshare --mount --propagation private）里跑：
#   - 脚本内含 `mount -o remount,rw|ro /` 与 bind-mount ⇒ 只在私有 namespace 生效，退出自动清
#   - 绝不会波及 WSL 宿主的挂载状态
#
# 用法（WSL 内）: bash run_p5_qemu.sh [rootfs]
# 证据产出：logs/run.log（全量 tee）
if [ "${P5Q_INNER:-0}" != "1" ]; then
    export P5Q_INNER=1
    exec unshare --mount --propagation private bash "$0" "$@"
fi
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
RF=${1:-/opt/nxks2/rootfs-112}
LOG="$HERE/logs"
mkdir -p "$LOG"
exec > >(tee "$LOG/run.log") 2>&1

# ---- 路径（宿主视角 = chroot 视角加 $RF 前缀）----
D="$RF/opt/usr/nx-ks/dicam"
L="$RF/opt/usr/nx-ks/locale/zh_CN"
T2SRC="$D/di-camera-app.c2"
T2DST="$RF/usr/apps/com.samsung.di-camera-app/bin/di-camera-app"
M2SRC="$L/di-camera-app.mo"
M2DST="$RF/usr/share/locale/zh_CN/LC_MESSAGES/di-camera-app.mo"
UNIT="$RF/usr/lib/systemd/system/di-camera-app.service"
BACKUP="/tmp/p5q_unit.orig"
# rootfs-112 是符号链接；mount 表以【真实路径】记录挂载点 ⇒ 判定/umount 用真实路径版
REAL="$(readlink -f "$RF")"
T2DST_R="$REAL/usr/apps/com.samsung.di-camera-app/bin/di-camera-app"
M2DST_R="$REAL/usr/share/locale/zh_CN/LC_MESSAGES/di-camera-app.mo"

FAIL=0
ok(){  echo "  OK   $1"; }
bad(){ echo "  FAIL $1"; FAIL=1; }
say(){ echo; echo "########## $* ##########"; }
rw(){ mount -o remount,rw / 2>/dev/null || true; }   # 每段写操作前确保 rw（namespace 内）

say "A0. 布置（脚本/补丁体/样机/目标/日志）"
[ -f "$UNIT" ] || { echo "!! rootfs 缺 unit：$UNIT"; exit 1; }
mkdir -p "$D" "$L" "$RF/usr/share/locale/zh_CN/LC_MESSAGES" "$RF/proc" "$RF/tmp"
cp -f "$ROOT/scripts/dicam/t2_premount.sh"        "$D/t2_premount.sh"
cp -f "$ROOT/scripts/dicam/dicam_p5_install.sh"   "$D/dicam_p5_install.sh"
cp -f "$ROOT/scripts/dicam/dicam_p5_rollback.sh"  "$D/dicam_p5_rollback.sh"
cp -f "$ROOT/fw/v1.12/dicam/di-camera-app.c2.v2"  "$T2SRC"
cp -f "$ROOT/fw/v1.12/dicam/locale/di-camera-app.zh_CN.m2sample.mo" "$M2SRC"
touch "$M2DST"
chmod +x "$D"/*.sh
# ★ 使 rootfs 成为独立挂载点（模拟真机 rootfs 分区；chroot 内 `mount -o remount,rw /` 才能成立）
mountpoint -q "$RF" || mount -o bind "$RF" "$RF"
# ★ bind-self 是非递归 bind，会屏蔽原有子挂载（proc 等）——在其视图内重确保 proc 可见
if ! chroot "$RF" /bin/sh -c 'cat /proc/uptime >/dev/null 2>&1'; then
    mount -t proc proc "$RF/proc"
fi
rm -f "$RF/tmp/dicam_p5_mount.log"
echo "T2 补丁体 : $(md5sum "$T2SRC" | cut -d' ' -f1)  (期望 48d94bd6…)"
echo "M2 样机   : $(md5sum "$M2SRC" | cut -d' ' -f1)  (期望 e531bd5f…)"
echo "T2 目标   : $(ls -la "$T2DST" | awk '{print $5}')B  $T2DST"
echo "日志文件  : $RF/tmp/dicam_p5_mount.log"

say "A1. premount 正常态（两条目应挂载）"
chroot "$RF" /bin/sh /opt/usr/nx-ks/dicam/t2_premount.sh
mount | grep -qF "$T2DST_R" && ok "T2 条目已挂载" || bad "T2 条目未挂载"
mount | grep -qF "$M2DST_R" && ok "M2 条目已挂载" || bad "M2 条目未挂载"
echo "-- chroot 内 mount 表（相机视角） --"
chroot "$RF" /bin/sh -c 'mount | grep -F "di-camera"' | sed 's/^/   /'
echo "-- /tmp/dicam_p5_mount.log --"
cat "$RF/tmp/dicam_p5_mount.log" 2>/dev/null | sed 's/^/   /'
ML1=$(mount | wc -l); LL1=$(wc -l < "$RF/tmp/dicam_p5_mount.log" 2>/dev/null || echo 0)
[ "$LL1" = "2" ] && ok "日志恰 2 行（[T2]+[M2]）" || bad "日志行数=$LL1（期望 2）"

say "A2. premount 幂等态（无新增）"
chroot "$RF" /bin/sh /opt/usr/nx-ks/dicam/t2_premount.sh
ML2=$(mount | wc -l); LL2=$(wc -l < "$RF/tmp/dicam_p5_mount.log" 2>/dev/null || echo 0)
[ "$ML1" = "$ML2" ] && ok "挂载表无变化（$ML1）" || bad "挂载表变化 $ML1→$ML2"
[ "$LL1" = "$LL2" ] && ok "日志无新增（$LL1）" || bad "日志新增 $LL1→$LL2"

say "A3. 独立禁用（移除 T2 源 ⇒ 只 M2 挂载）"
umount "$T2DST_R" 2>/dev/null || true; umount "$M2DST_R" 2>/dev/null || true
mv "$T2SRC" "$T2SRC.off"
chroot "$RF" /bin/sh /opt/usr/nx-ks/dicam/t2_premount.sh
mount | grep -qF "$T2DST_R" && bad "T2 不应挂载（源已移除）" || ok "T2 正确未挂（禁用语义）"
mount | grep -qF "$M2DST_R" && ok "M2 独立挂载不受影响" || bad "M2 未挂载"
mv "$T2SRC.off" "$T2SRC"

say "A4. 清场（umount 全部）"
umount "$T2DST_R" 2>/dev/null || true; umount "$M2DST_R" 2>/dev/null || true
mount | grep -qF "$T2DST_R" && bad "T2 仍挂载" || ok "T2 已清"
mount | grep -qF "$M2DST_R" && bad "M2 仍挂载" || ok "M2 已清"

say "B1. P5 install（真 unit 注入）"
rw
cp -f "$UNIT" "$BACKUP"
echo "-- 注入前 [Service] 段 --"
sed -n '/\[Service\]/,/^$/p' "$UNIT" | head -8 | sed 's/^/   /'
chroot "$RF" /bin/sh /opt/usr/nx-ks/dicam/dicam_p5_install.sh | sed 's/^/   /'
N=$(grep -c "t2_premount.sh" "$UNIT" || true)
[ "$N" = "1" ] && ok "注入命中数=1" || bad "注入命中数=$N"
L1=$(grep -n "ExecStartPre=-/opt/usr/nx-ks/dicam/t2_premount.sh" "$UNIT" | cut -d: -f1)
L2=$(grep -n "^ExecStart=" "$UNIT" | cut -d: -f1)
if [ -n "$L1" ] && [ -n "$L2" ] && [ "$L1" -lt "$L2" ]; then ok "注入行位于 ExecStart= 之前（$L1 < $L2）"; else bad "注入位置异常（L1=$L1 L2=$L2）"; fi
if [ -f "$D/di-camera-app.service.p5.bak" ] && cmp -s "$D/di-camera-app.service.p5.bak" "$BACKUP"; then ok "备份与原始 unit 一致"; else bad "备份缺失或不一致"; fi

say "B2. P5 install 幂等"
rw
if chroot "$RF" /bin/sh /opt/usr/nx-ks/dicam/dicam_p5_install.sh | grep -q "已含"; then ok "二次运行跳过（幂等）"; else bad "二次运行未按幂等处理"; fi

say "C1. P5 rollback（互逆）"
rw
chroot "$RF" /bin/sh /opt/usr/nx-ks/dicam/dicam_p5_rollback.sh | sed 's/^/   /'
N=$(grep -c "t2_premount.sh" "$UNIT" || true)
[ "$N" = "0" ] && ok "移除后 0 命中" || bad "移除后仍命中 $N"
cmp -s "$UNIT" "$BACKUP" && ok "与原始 unit 逐字节一致" || bad "与原始 unit 不一致"

say "D1. 异常 unit（无 ExecStart=）——应报错且不修改"
rw
grep -v "^ExecStart=" "$BACKUP" > "$UNIT"
set +e
OUT=$(chroot "$RF" /bin/sh /opt/usr/nx-ks/dicam/dicam_p5_install.sh 2>&1); RC=$?
set -e
echo "$OUT" | tail -3 | sed 's/^/   /'
[ "$RC" != "0" ] && ok "退出码非 0（rc=$RC）" || bad "应失败却退出 0"
echo "$OUT" | grep -q "未找到 ExecStart=" && ok "报错信息正确" || bad "报错信息缺失"
N=$(grep -c "^ExecStart=" "$UNIT" || true)
[ "$N" = "0" ] && ok "坏 unit 未被改（仍无 ExecStart=）" || bad "unit 被意外修改"
[ ! -f "$UNIT.p5.new" ] && ok "无临时文件残留" || bad "残留 $UNIT.p5.new"

say "D2. 还原原始 unit（保持 rootfs 副本干净）"
rw
cp -f "$BACKUP" "$UNIT"
cmp -s "$UNIT" "$BACKUP" && ok "unit 已还原" || bad "还原失败"

say "E. 汇总"
echo "-- 最终 unit [Service] 段 --"
sed -n '/\[Service\]/,/^$/p' "$UNIT" | head -8 | sed 's/^/   /'
echo
if [ "$FAIL" = "0" ]; then
    MSG="== P5 VM 预演：PASS（A/B/C/D 全绿） =="
else
    MSG="== P5 VM 预演：FAIL（见上 OK/FAIL 行） =="
fi
echo "$MSG"
echo "$MSG" >> "$LOG/summary.txt"   # 独立落盘（不经异步 tee，防尾部竞态）
[ "$FAIL" = "0" ] || exit 2
