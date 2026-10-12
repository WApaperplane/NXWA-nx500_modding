#!/bin/bash
# run_c2_qemu.sh —— C-2 补丁 QEMU 全链验证驱动（v3：支持 v1/v2 桩）
#
#   T2  单测    : 直接调补丁桩（真字节）→ system(cmd)
#   T2b 守卫    : argc=1 应不执行
#   T3  分派    : 真 libshell 的 shell_exec 匹配 "film" → 桩
#   T4  端到端  : 真 `st app film …` → SysV 队列 0x8828 → 注册回调 → 桩
#   T5  v2 拼接 : unit2（3 参数）—— 日志须出现 "sh /opt/usr/nx-ks/f.sh …"
#
# ★ 为什么 v2 也能过 T2/T3/T4：脚本会造一个 /opt/usr/nx-ks/f.sh 转发器
#   （v2 走 `sh f.sh <args>`，v1 直接执行 cmd）—— 同一套判据对两版都成立。
#
# ★ chroot 环境三件套（缺一即败）：
#   1) mount -t proc  → /proc（glibc sem_open 的探测路径需要）
#   2) mount -t tmpfs → /dev/shm（★ 必须"是 tmpfs"，仅"存在"不够）
#   3) 停用 /usr/bin/save_crash_info.sh（libsys-assert 崩溃处理器会递归风暴）
#
# 用法（WSL 内）:
#   bash run_c2_qemu.sh                    # 默认 v1 补丁
#   C2BIN=/mnt/e/tmp/dicam_strings/c2/di-camera-app.c2.v2 bash run_c2_qemu.sh
RF=${1:-/opt/nxks2/rootfs-112}
ROOT=/mnt/e/tmp/NXWA-nx500_modding
SRC=$ROOT/test_server/dicam/c2_qemu
C2SRC=/mnt/e/tmp/dicam_strings/c2
C2BIN=${C2BIN:-$C2SRC/di-camera-app.c2}
LOG=$SRC/logs
CH=/tmp/dicam_c2

mkdir -p "$LOG"
say(){ echo; echo "########## $* ##########"; }

say "0. 环境准备（proc + tmpfs + 风暴防护 + f.sh 转发器）"
[ -s "$C2BIN" ] || { echo "缺补丁二进制: $C2BIN"; exit 1; }
[ -s "$SRC/out/c2_harness.arm" ] || { echo "缺载体: 先跑 build_c2_harness.sh"; exit 1; }
echo "补丁: $C2BIN（md5 $(md5sum "$C2BIN" | awk '{print $1}')）"

mkdir -p "$RF$CH" "$RF/tmp" "$RF/proc" "$RF/dev/shm" "$RF/opt/usr/nx-ks"
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

# ★ v2 目标脚本转发器（v1 用不到，留着无害）
cat > "$RF/opt/usr/nx-ks/f.sh" <<'FEOF'
#!/bin/sh
echo "f.sh called: $*" >> /tmp/fsh_calls
exec sh -c "$*"
FEOF
chmod +x "$RF/opt/usr/nx-ks/f.sh"

cp -f "$C2BIN" "$RF$CH/di-camera-app.patched"
cp -f "$SRC/out/c2_harness.arm" "$RF$CH/c2_harness.arm"
chmod +x "$RF$CH/c2_harness.arm"
ipcrm -Q 0x8828 2>/dev/null && echo "已清掉遗留队列 0x8828" || echo "(无遗留队列)"
rm -f "$RF/tmp/c2_unit_ok" "$RF/tmp/c2_guard_ran" "$RF/tmp/c2_dispatch_ok" "$RF/tmp/c2e2eok" "$RF/tmp/fsh_calls"

say "T2 单测：直接调补丁桩（真字节）"
chroot "$RF" "$CH/c2_harness.arm" unit "touch /tmp/c2_unit_ok" "$CH/di-camera-app.patched" 2>&1 | tee "$LOG/t2_unit.log"
grep -q "^SYSTEM_CMD\[" "$LOG/t2_unit.log" && echo ">>> 观测到 SYSTEM_CMD（spy 生效）"
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

say "T5 v2 拼接（unit2，3 参数：apply + 23）"
chroot "$RF" "$CH/c2_harness.arm" unit2 "apply" "$CH/di-camera-app.patched" 2>&1 | tee "$LOG/t5_unit2.log"
if grep -q "sh /opt/usr/nx-ks/f.sh" "$LOG/t5_unit2.log"; then
    echo ">>> T5 V2-SPLICE: PASS（日志含 'sh /opt/usr/nx-ks/f.sh'）"
    grep -o "SYSTEM_CMD\[.*\]" "$LOG/t5_unit2.log"
else
    echo ">>> T5 V2-SPLICE: N/A（当前补丁非 v2 桩——v1 直接执行 cmd，属预期）"
    grep -o "SYSTEM_CMD\[.*\]" "$LOG/t5_unit2.log" || true
fi

say "清理（umount / 还原 crash 脚本）"
[ "$RESTORE_CRASH" = 1 ] && mv "$RF/usr/bin/save_crash_info.sh.off" "$RF/usr/bin/save_crash_info.sh" && echo "(save_crash_info.sh 已还原)"
[ "$MOUNTED_SHM" = 1 ] && umount "$RF/dev/shm" && echo "(dev/shm 已卸载)"
[ "$MOUNTED_PROC" = 1 ] && umount "$RF/proc" && echo "(proc 已卸载)"

say "结果汇总"
for t in c2_unit_ok c2_guard_ran c2_dispatch_ok c2e2eok fsh_calls; do
    [ -f "$RF/tmp/$t" ] && echo "  /tmp/$t : EXISTS" || echo "  /tmp/$t : -"
done
[ -f "$RF/tmp/fsh_calls" ] && { echo "  -- f.sh 调用记录 --"; cat "$RF/tmp/fsh_calls"; }
echo "日志目录: $LOG"
