#!/bin/bash
# =====================================================================
# demo_fsh.sh —— f.sh（App 命令入口）的 QEMU 验证 + ★ 死锁实验
#
# 验证两件事：
#   A. 白名单分发真的工作：真 st → 队列 → 桩 → f.sh → 转发到引擎 / 拒绝非法入参
#   B. ★ 证明"f.sh 内不能发 st app"这条铁律 —— 用对照实验把死锁打出来
#
# 用法（WSL 内）: bash demo_fsh.sh [rootfs]
# =====================================================================
RF=${1:-/opt/nxks2/rootfs-112}
REPO=/mnt/e/tmp/NXWA-nx500_modding
SRC=$REPO/test_server/dicam/c2_qemu
C2=/mnt/e/tmp/dicam_strings/c2
CH=/tmp/dicam_c2
DEMO=/tmp/dicam_demo
LOG=$SRC/logs

mkdir -p "$LOG"
bar() { echo; echo "════════════════════════════════════════════════════════════════"; echo "  $*"; echo "════════════════════════════════════════════════════════════════"; }
step() { echo; echo "── $* ──"; }
say() { echo "   $*"; }

bar "f.sh（App 命令入口）验证   $(date '+%H:%M:%S')"

mkdir -p "$RF$CH" "$RF/tmp" "$RF/proc" "$RF/dev/shm" "$RF/opt/usr/nx-ks"
MP=0; MS=0; RC=0
mountpoint -q "$RF/proc"    || { mount -t proc proc "$RF/proc" && MP=1; }
mountpoint -q "$RF/dev/shm" || { mount -t tmpfs -o mode=1777 tmpfs "$RF/dev/shm" && MS=1; }
[ -f "$RF/usr/bin/save_crash_info.sh" ] && { mv "$RF/usr/bin/save_crash_info.sh" "$RF/usr/bin/save_crash_info.sh.off"; RC=1; }
cleanup() {
    [ -f "$RF/opt/usr/nx-ks/f.sh.dembak" ] && mv -f "$RF/opt/usr/nx-ks/f.sh.dembak" "$RF/opt/usr/nx-ks/f.sh"
    [ "$RC" = 1 ] && mv "$RF/usr/bin/save_crash_info.sh.off" "$RF/usr/bin/save_crash_info.sh" 2>/dev/null
    [ "$MS" = 1 ] && umount "$RF/dev/shm" 2>/dev/null
    [ "$MP" = 1 ] && umount "$RF/proc" 2>/dev/null
    ipcrm -Q 0x8828 2>/dev/null
}
trap cleanup EXIT

# ---------- 部署：真 f.sh + 引擎 stub ----------
step "部署（真 f.sh + 引擎 stub）"
install -m 755 "$REPO/scripts/f.sh" "$RF/opt/usr/nx-ks/f.sh"
cat > "$RF/opt/usr/nx-ks/filmlab.sh" <<'FEOF'
#!/bin/sh
mkdir -p /tmp/dicam_demo
echo "[stub-engine] argv: $*" >> /tmp/dicam_demo/engine.log
echo "stub-engine: $*"
FEOF
chmod +x "$RF/opt/usr/nx-ks/filmlab.sh"
rm -rf "$RF$DEMO"
# ★ 真机上 /opt/usr/nx-ks/busybox 由 mod 自带（提供 timeout）；chroot-112 是原始 rootfs ⇒ 补进去
[ -x "$RF/opt/usr/nx-ks/busybox" ] || install -m 755 "$REPO/scripts/busybox" "$RF/opt/usr/nx-ks/busybox" 2>/dev/null
say "f.sh       → $RF/opt/usr/nx-ks/f.sh（真身，$(wc -c < "$REPO/scripts/f.sh") B）"
say "busybox    → $([ -x "$RF/opt/usr/nx-ks/busybox" ] && echo '在位（为 f.sh 提供 timeout）' || echo '★缺失（f.sh 将降级为无超时）')"
say "filmlab.sh → 引擎 stub（记录收到的 argv，便于验证转发）"

cp -f "$C2/di-camera-app.c2.v2" "$RF$CH/di-camera-app.patched"
cp -f "$SRC/out/c2_harness.arm" "$RF$CH/c2_harness.arm"; chmod +x "$RF$CH/c2_harness.arm"
ipcrm -Q 0x8828 2>/dev/null

step "起 App 侧（harness）"
chroot "$RF" "$CH/c2_harness.arm" server x "$CH/di-camera-app.patched" > "$LOG/demo_fsh_server.log" 2>&1 &
SRV=$!
sleep 2
grep -E "server up|trampoline" "$LOG/demo_fsh_server.log" | sed 's/^/   /'

send() {   # send <描述> <命令参数...>
    echo
    echo ">>> st app film $*"
    timeout 20 chroot "$RF" /usr/bin/st app film "$@"
    echo "    rc=$?"
}
# 注意：send 会把参数原样传给 st（不做 shell 再解释）

echo
echo "── A. 白名单分发 ──"
send help
send bogus
send recipe list
send recipe apply portra400
send recipe apply fast-400 fast
send 'recipe apply bad;name'          # 注入尝试（整串当一个参数，含 ; 与空格）
send recipe apply 'bad;name'          # 正常拆分传入：净化后应仍能分发（元字符→_）
send pw 9
send log 4

step "★ f.log（真身写的日志）"
cat "$RF/opt/usr/nx-ks/f.log" 2>/dev/null | sed 's/^/   /' || echo "   (无)"

step "★ 引擎 stub 收到什么（= 转发成功的证据）"
cat "$RF$DEMO/engine.log" 2>/dev/null | sed 's/^/   /' || echo "   (无)"

# ---------- B. 死锁实验 ----------
bar "B. ★ 死锁实验：让 f.sh 在 App 线程内发 st app"
step "把 f.sh 临时换成「探针」（内部调 st app mode m）"
[ -f "$RF/opt/usr/nx-ks/f.sh" ] && cp -f "$RF/opt/usr/nx-ks/f.sh" "$RF/opt/usr/nx-ks/f.sh.dembak"
cat > "$RF/opt/usr/nx-ks/f.sh" <<'PEOF'
#!/bin/sh
echo "[probe] 我在 App 的 shell 线程里，现在尝试 st app mode m ..."
/usr/bin/st app mode m &
P=$!
sleep 8
if kill -0 $P 2>/dev/null; then
    echo "[probe] ★ 8s 后 st app 仍在等待 ⇒ 队列无人服务（阻塞/死锁证实）"
    kill -9 $P 2>/dev/null
else
    echo "[probe] st app 已返回 ⇒ 未阻塞"
fi
PEOF
chmod +x "$RF/opt/usr/nx-ks/f.sh"
say "预期：st app 的消息进了 0x8828，但唯一服务该队列的线程正阻塞在 system(f.sh) 里"
say "      ⇒ 无人处理 ⇒ 内层 8s 超时（rc=124）；外层 st app film 也被拖住"

echo
echo ">>> 触发（外层 20s 兜底）"
S=$(date +%s)
timeout 20 chroot "$RF" /usr/bin/st app film probe
echo "    外层 rc=$?  耗时 $(( $(date +%s) - S ))s"
if grep -q "队列无人服务" "$LOG/demo_fsh_server.log" 2>/dev/null; then
    echo "   ★ 结论：已证实 —— App 线程在 system(f.sh) 期间无法服务队列 0x8828（铁律一成立）"
else
    echo "   ★ 结论：未观测到阻塞（需复查；注意外层耗时不等于内层行为，以内层探针输出为准）"
fi
echo
echo "── 探针在 App 线程里的实际输出（来自 harness server 日志）──"
grep -E "\[probe\]" "$LOG/demo_fsh_server.log" | tail -5 | sed 's/^/   /' || echo "   (无)"

step "还原真 f.sh"
mv -f "$RF/opt/usr/nx-ks/f.sh.dembak" "$RF/opt/usr/nx-ks/f.sh" 2>/dev/null && say "已还原"

kill $SRV 2>/dev/null; ipcrm -Q 0x8828 2>/dev/null
bar "结束   日志: $LOG/demo_fsh_server.log"
