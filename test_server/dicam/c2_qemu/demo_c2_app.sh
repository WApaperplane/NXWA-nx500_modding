#!/bin/bash
# =====================================================================
# demo_c2_app.sh —— C-2 补丁「效果演示」（前台跑，过程可见）
#
# 演示链路（每一环都是真的，除了 App 本体）：
#   真 `st app film <命令> <参数>`
#     → sys_sndmsg(key=0x8828) → SysV 消息队列
#     → App 侧 shell 线程（harness 复刻：start_shellthread + ui_shell_command）
#     → App 命令表匹配 "film"
#     → 桩（补丁后的真字节）
#     → f.sh → 落盘证据
#
# 为什么不用"真 VM"：di-camera-app 真身依赖 DRIMe5 硬件（EP/SMA/ISP/IPCC），
#   在任何 QEMU 里都跑不起来（实测：真 VM 里 App 无法初始化）。
#   所以取最真实的可行环境 = 【相机 rootfs + qemu-arm-static】：真 st、真 libshell、
#   真 SysV 队列、真补丁字节；只有 App 用语义等价的 harness 顶替。
#
# 用法（WSL 内）: bash demo_c2_app.sh [rootfs]
# =====================================================================
RF=${1:-/opt/nxks2/rootfs-112}
SRC=/mnt/e/tmp/NXWA-nx500_modding/test_server/dicam/c2_qemu
C2=/mnt/e/tmp/dicam_strings/c2
CH=/tmp/dicam_c2
DEMO=/tmp/dicam_demo
LOG=$SRC/logs

mkdir -p "$LOG"
bar() { echo; echo "════════════════════════════════════════════════════════════════"; echo "  $*"; echo "════════════════════════════════════════════════════════════════"; }
step() { echo; echo "── $* ──"; }

bar "C-2 补丁效果演示   $(date '+%H:%M:%S')"
echo "rootfs : $RF"
echo "载体   : $SRC/out/c2_harness.arm"
echo "说明   : 真 st → 真队列 0x8828 → 真 libshell → 真补丁字节 → f.sh"

# ---------- 环境三件套 ----------
mkdir -p "$RF$CH" "$RF/tmp" "$RF/proc" "$RF/dev/shm" "$RF/opt/usr/nx-ks"
MP=0; MS=0
mountpoint -q "$RF/proc"    || { mount -t proc proc "$RF/proc" && MP=1; }
mountpoint -q "$RF/dev/shm" || { mount -t tmpfs -o mode=1777 tmpfs "$RF/dev/shm" && MS=1; }
RC=0
[ -f "$RF/usr/bin/save_crash_info.sh" ] && { mv "$RF/usr/bin/save_crash_info.sh" "$RF/usr/bin/save_crash_info.sh.off"; RC=1; }
cleanup() {
    [ "$RC" = 1 ] && mv "$RF/usr/bin/save_crash_info.sh.off" "$RF/usr/bin/save_crash_info.sh" 2>/dev/null
    [ "$MS" = 1 ] && umount "$RF/dev/shm" 2>/dev/null
    [ "$MP" = 1 ] && umount "$RF/proc" 2>/dev/null
    ipcrm -Q 0x8828 2>/dev/null
}
trap cleanup EXIT

# ---------- 部署「mod 侧脚本」f.sh ----------
step "部署 f.sh（模拟 mod 的 App 命令入口）"
cat > "$RF/opt/usr/nx-ks/f.sh" <<'FEOF'
#!/bin/sh
D=/tmp/dicam_demo
mkdir -p "$D"
{ echo "argv_count=$#"; i=1; for a in "$@"; do echo "  argv[$i]=$a"; i=$((i+1)); done; echo "---"; } >> "$D/calls.log"
case "$1" in
  apply)
      [ -n "$2" ] && { echo "$2" > "$D/applied_recipe.txt"; echo "[f.sh] 应用配方: $2" >> "$D/calls.log"; } ;;
  status)
      echo "[f.sh] 状态查询" >> "$D/calls.log" ;;
  *)
      echo "[f.sh] 未知命令: $1" >> "$D/calls.log" ;;
esac
FEOF
chmod +x "$RF/opt/usr/nx-ks/f.sh"
echo "  → $RF/opt/usr/nx-ks/f.sh 已就位"
echo '  → 它会把收到的 argv 逐条记到 /tmp/dicam_demo/calls.log'

# ---------- 单个桩版本的完整演示 ----------
demo_one() {
    local BIN="$1" TAG="$2" TITLE="$3"     # TAG 必须是纯 ASCII 短标识（用于日志文件名）
    bar "演示：$TITLE"
    [ -s "$BIN" ] || { echo "!! 缺补丁: $BIN"; return 1; }
    echo "补丁: $BIN"
    echo "md5 : $(md5sum "$BIN" | awk '{print $1}')"

    cp -f "$BIN" "$RF$CH/di-camera-app.patched"
    cp -f "$SRC/out/c2_harness.arm" "$RF$CH/c2_harness.arm"
    chmod +x "$RF$CH/c2_harness.arm"
    rm -rf "$RF$DEMO"
    ipcrm -Q 0x8828 2>/dev/null

    step "起 App 侧（harness 复刻 shell 线程 + 命令表）"
    chroot "$RF" "$CH/c2_harness.arm" server x "$CH/di-camera-app.patched" > "$LOG/demo_${TAG}_server.log" 2>&1 &
    SRV=$!
    sleep 2
    sed -n '1,12p' "$LOG/demo_${TAG}_server.log"

    step "发真命令①：st app film apply portra400"
    timeout 15 chroot "$RF" /usr/bin/st app film apply portra400
    echo "   st rc=$?"

    step "发真命令②：st app film status"
    timeout 15 chroot "$RF" /usr/bin/st app film status
    echo "   st rc=$?"

    sleep 1
    kill $SRV 2>/dev/null; ipcrm -Q 0x8828 2>/dev/null
    sleep 0.5

    step "★ 桩交给 system() 的完整命令行（spy_system 捕获）"
    grep -o "SYSTEM_CMD\[.*\]" "$LOG/demo_${TAG}_server.log" 2>/dev/null | sed 's/^/  /' \
        || echo "  （未捕获到）"

    step "★ f.sh 实际收到什么（= 补丁效果的直接证据）"
    if [ -f "$RF$DEMO/calls.log" ]; then cat "$RF$DEMO/calls.log"; else echo "  （无记录 —— 说明本次未经过 f.sh）"; fi
    [ -f "$RF$DEMO/applied_recipe.txt" ] && echo "  ⇒ 落盘: applied_recipe.txt = $(cat "$RF$DEMO/applied_recipe.txt")"
}

demo_one "$C2/di-camera-app.c2"    "v1" "v1 桩（16B，只执行 argv[1]）"
demo_one "$C2/di-camera-app.c2.v2" "v2" "v2 桩（156B，拼接 sh f.sh + 全参数）"

# ---------- 对照 ----------
bar "对照结论"
echo "同一句  st app film apply portra400  ："
echo '  v1 桩 → system("apply")'
echo "          ⇒ 只在 PATH 里找名为 apply 的东西：portra400 被丢弃，且【绕过 mod 脚本】"
echo "  v2 桩 → system(\"sh /opt/usr/nx-ks/f.sh apply portra400\")"
echo "          ⇒ 参数完整送达 mod 脚本（落盘 applied_recipe.txt = portra400）"
echo
echo "这就是 v2 的存在理由：v1 要短路径符号链接 + 只能带一个参数；"
echo "v2 零 PATH 依赖、可带多参数、直达 mod 脚本。"
echo "日志: $LOG/demo_v1_server.log / demo_v2_server.log"
