#!/bin/bash
# run_c2_qemu.sh —— C-2 补丁 QEMU 全链验证驱动（v2：修复 chroot 环境）
#
#   T2  单测    : 直接调补丁桩（真字节）→ system(cmd)
#   T2b 守卫    : argc=1 应不执行
#   T3  分派    : 真 libshell 的 shell_exec 匹配 "film" → 桩
#   T4  端到端  : 真 `st app film …` → SysV 队列 0x8828 → 注册回调 → 桩
#
# ★ chroot 环境三件套（v2 实测；缺一即败）：
#   1) mount -t proc  → /proc（glibc sem_open 的探测路径需要）
#   2) mount -t tmpfs → /dev/shm（★ 必须"是 tmpfs"，仅"存在"不够：
#      否则 sem_open 走 mount 探测失败 → errno=38 ENOSYS → sem_init(-1) 段错误）
#   3) 停用 /usr/bin/save_crash_info.sh（libsys-assert 崩溃处理器会调 st cap……
#      → 递归崩溃风暴；测试期间临时改名，结束还原）
#
# 用法（WSL 内）: bash run_c2_qemu.sh [rootfs]
RF=${1:-/opt/nxks2/rootfs-112}
ROOT=/mnt/e/tmp/NXWA-nx500_modding
SRC=$ROOT/test_server/dicam/c2_qemu
C2SRC=/mnt/e/tmp/dicam_strings/c2
LOG=$SRC/logs
CH=/tmp/dicam_c2

mkdir -p "$LOG"
say(){ echo; echo "########## $* ##########"; }

say "0. 环境准备（proc + tmpfs + 风暴防护）"
[ -s "$C2SRC/di-camera-app.c2" ] || { echo "缺补丁二进制: $C2SRC/di-camera-app.c2"; exit 1; }
[ -s "$SRC/out/c2_harness.arm" ] || { echo "缺载体: 先跑 build_c2_harness.sh"; exit 1; }

mkdir -p "$RF$CH" "$RF/tmp" "$RF/proc" "$RF/dev/shm"
MOUNTED_PROC=0; MOUNTED_SHM=0
mountpoint -q "$RF/proc"    || { mount -t proc proc "$RF/proc" && MOUNTED_PROC=1; }
mountpoint -q "$RF/dev/shm" || { mount -t tmpfs -o mode=1777 tmpfs "$RF/dev/shm" && MOUNTED_SHM=1; }
echo "proc mounted(new)=$MOUNTED_PROC  dev/shm tmpfs(new)=$MOUNTED_SHM"

RESTORE_CRASH=0
if [ -f "$RF/usr/bin/save_crash_info.sh" ]; then
    mv "$RF/usr/bin/save_crash_info.sh" "$RF/usr/bin/save_crash_info.sh.off"
    RESTORE_CRASH=1
    echo "(save_crash_info.sh 已临时停用)"
fi

cp -f "$C2SRC/di-camera-app.c2" "$RF$CH/di-camera-app.patched"
cp -f "$SRC/out/c2_harness.arm" "$RF$CH/c2_harness.arm"
chmod +x "$RF$CH/c2_harness.arm"
ipcrm -Q 0x8828 2>/dev/null && echo "已清掉遗留队列 0x8828" || echo "(无遗留队列)"
rm -f "$RF/tmp/c2_unit_ok" "$RF/tmp/c2_guard_ran" "$RF/tmp/c2_dispatch_ok" "$RF/tmp/c2e2eok"

say "T2 单测：直接调补丁桩（真字节）"
chroot "$RF" "$CH/c2_harness.arm" unit "touch /tmp/c2_unit_ok" "$CH/di-camera-app.patched" 2>&1 | tee "$LOG/t2_unit.log"
if [ -f "$RF/tmp/c2_unit_ok" ]; then echo ">>> T2 UNIT: PASS"; else echo ">>> T2 UNIT: FAIL"; fi

say "T2b 守卫：argc=1，应不执行"
chroot "$RF" "$CH/c2_harness.arm" guard "touch /tmp/c2_guard_ran" "$CH/di-camera-app.patched" 2>&1 | tee "$LOG/t2b_guard.log"
if [ -f "$RF/tmp/c2_guard_ran" ]; then echo ">>> T2b GUARD: FAIL (不该执行却执行了)"; else echo ">>> T2b GUARD: PASS (未执行)"; fi

say "T3 分派：真 libshell shell_exec 匹配 'film' → 桩"
chroot "$RF" "$CH/c2_harness.arm" dispatch "touch /tmp/c2_dispatch_ok" "$CH/di-camera-app.patched" 2>&1 | tee "$LOG/t3_dispatch.log"
if [ -f "$RF/tmp/c2_dispatch_ok" ]; then echo ">>> T3 DISPATCH: PASS"; else echo ">>> T3 DISPATCH: FAIL"; fi

say "T4 端到端：真 st app film → 队列 0x8828 → 回调 → 桩"
chroot "$RF" "$CH/c2_harness.arm" server x "$CH/di-camera-app.patched" > "$LOG/t4_server.log" 2>&1 &
SRVPID=$!
sleep 2
echo "-- server 日志:"; cat "$LOG/t4_server.log"
timeout 15 chroot "$RF" /usr/bin/st app film "touch /tmp/c2e2eok" > "$LOG/t4_st.log" 2>&1
echo "st rc=$?"; cat "$LOG/t4_st.log"
sleep 1
if [ -f "$RF/tmp/c2e2eok" ]; then echo ">>> T4 E2E: PASS"; else echo ">>> T4 E2E: FAIL"; fi
kill $SRVPID 2>/dev/null || true
ipcrm -Q 0x8828 2>/dev/null || true

say "清理（umount / 还原 crash 脚本）"
[ "$RESTORE_CRASH" = 1 ] && mv "$RF/usr/bin/save_crash_info.sh.off" "$RF/usr/bin/save_crash_info.sh" && echo "(save_crash_info.sh 已还原)"
[ "$MOUNTED_SHM" = 1 ] && umount "$RF/dev/shm" && echo "(dev/shm 已卸载)"
[ "$MOUNTED_PROC" = 1 ] && umount "$RF/proc" && echo "(proc 已卸载)"

say "结果汇总"
for t in c2_unit_ok c2_guard_ran c2_dispatch_ok c2e2eok; do
    [ -f "$RF/tmp/$t" ] && echo "  /tmp/$t : EXISTS" || echo "  /tmp/$t : -"
done
echo "日志目录: $LOG"
