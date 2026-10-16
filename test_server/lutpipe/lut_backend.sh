#!/bin/sh
# @gate script=lut_backend.sh opens=rw one_shot=1 gate=cmasafe
# =====================================================================
# lut_backend.sh — LUT 预览后端（T5 产品化 v1 · 2026-10-16）
#
#   定位：把 LUT1 预览链封装为符合 T2 协议的**适配器后端**
#         （probe / apply / rollback / status），供统一控制器调用。
#
#   ★ 关闭语义（依 FILMLAB_LUT_NATIVE_UI_GOALS §3，T1 §4）：
#       rollback = **停守护 + 恢复出厂表指针**（lutload.arm restore）
#       —— 绝不以「加载数学 identity 表」冒充关闭。
#       ⚠ 注意：现有 `lutpick.sh off` 的实现是「加载 _identity 表」
#       （LUT_PIPELINE §3.2），**语义上 ≠ 关闭**；本后端走 factory 路径。
#
#   ⛔ 禁 restart（卡死整机）；apply 前需前置「抢回态」（先对焦一次；U6 §2 规律）
#
#   用法（相机端）：
#     sh lut_backend.sh probe
#     sh lut_backend.sh apply <表名> [--dry]
#     sh lut_backend.sh rollback
#     sh lut_backend.sh status
#   输出：stdout = 单行 JSON（供控制器解析）；人类可读信息走 stderr。
#   v1 · 2026-10-16 · 离线编写（未上机验证）
# =====================================================================

D=/opt/usr/nx-ks
BB=$D/busybox
[ -x "$BB" ] || BB=/bin/busybox
[ -x "$BB" ] || BB=$(command -v busybox 2>/dev/null)
[ -x "$BB" ] || BB=""                    # 无 busybox ⇒ RUNNER 退化为系统 sh
if [ -n "$BB" ]; then RUNNER="$BB sh"; else RUNNER="sh"; fi
MOD=/mnt/mmc/filmlab
[ -d "$MOD" ] || MOD=$D
PICK=$MOD/lutpick.sh
LUTS=$MOD/luts
# ★ 上机实测（10-16）：工具实际部署在 SD $MOD/，不在 $D/（/opt/usr/nx-ks/）
LOAD=$D/lutload.arm
[ -f "$LOAD" ] || LOAD=$MOD/lutload.arm
SENTPID=/tmp/lutsentinel.pid

log(){ echo "$*" >&2; }

jstr(){ printf '"%s"' "$(printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g')"; }
has(){ [ -f "$1" ] && printf 1 || printf 0; }

guard_state(){
    # 1 = 守护在跑（以 pid 文件或进程名判断）
    if [ -f "$SENTPID" ] && kill -0 "$(cat "$SENTPID" 2>/dev/null)" 2>/dev/null; then
        echo 1; return
    fi
    if pidof lutsentinel.arm >/dev/null 2>&1; then echo 1; return; fi
    if ps 2>/dev/null | grep -q "[l]utsentinel"; then echo 1; return; fi
    echo 0
}

cmd_probe(){
    n=0
    if [ -d "$LUTS" ]; then
        n=$(ls "$LUTS" 2>/dev/null | grep -c '\.bin$')
    fi
    printf '{"ok":true,"tools":{"cmasafe":%s,"cmapick2":%s,"lutapi":%s,"lutload":%s,"lutsentinel":%s,"lutpick":%s},"luts_count":%s,"guard":%s,"precondition":"apply 前需前置抢回态（先对焦一次）"}\n' \
        "$(has "$MOD/cmasafe.arm")" "$(has "$MOD/cmapick2.arm")" "$(has "$MOD/lutapi.arm")" \
        "$(has "$LOAD")" "$(has "$MOD/lutsentinel.arm")" "$(has "$PICK")" "$n" "$(guard_state)"
}

cmd_apply(){
    name=$1; dry=$2
    [ -n "$name" ] || { printf '{"ok":false,"level":"failed","error":"no_name"}\n'; return 1; }
    [ -f "$PICK" ] || { printf '{"ok":false,"level":"failed","error":"lutpick_missing"}\n'; return 1; }
    [ -f "$LUTS/$name.bin" ] || { printf '{"ok":false,"level":"failed","error":"table_not_found","table":%s}\n' "$(jstr "$name")"; return 1; }
    [ -f "$LUTS/_identity.bin" ] || log "(提示：无 _identity.bin；诊断表缺省)"

    log "-- apply $name ${dry:+($dry)}（sel=1 通道）--"
    if [ "$dry" = "--dry" ]; then
        out=$($RUNNER "$PICK" apply "$name" --dry 2>&1); rc=$?
    else
        out=$($RUNNER "$PICK" apply "$name" 2>&1); rc=$?
    fi
    echo "$out" | sed 's/^/  /' >&2
    if [ "$rc" = "0" ]; then
        printf '{"ok":true,"level":"full","table":%s,"sel":1,"dry":%s,"note":"预览生效（LUT1）；成片走 postproc（E4 口径）"}\n' \
            "$(jstr "$name")" "$([ "$dry" = "--dry" ] && echo true || echo false)"
    else
        printf '{"ok":false,"level":"failed","table":%s,"rc":%s,"error":"lutpick_apply_failed"}\n' "$(jstr "$name")" "$rc"
    fi
}

cmd_rollback(){
    # ★ 关闭 = 停守护 + 恢复出厂表；不写 identity
    g=$(guard_state)
    if [ "$g" = "1" ]; then
        log "-- 停止守护 lutsentinel --"
        if [ -f "$SENTPID" ]; then
            kill "$(cat "$SENTPID" 2>/dev/null)" 2>/dev/null
            rm -f "$SENTPID"
        fi
        if [ -n "$BB" ]; then "$BB" pkill -f lutsentinel.arm 2>/dev/null; else pkill -f lutsentinel.arm 2>/dev/null; fi
    fi
    rc_r=255
    if [ -f "$LOAD" ]; then
        log "-- 恢复出厂表（lutload.arm restore）--"
        "$LOAD" restore >/dev/null 2>&1; rc_r=$?
    else
        log "!! 缺 lutload.arm —— 无法恢复出厂表（请用 SD 重刷/重启兜底）"
    fi
    printf '{"ok":%s,"path":"factory_restore","identity_used":false,"guard_stopped":%s,"restore_rc":%s,"note":"关闭=停守护+恢复出厂表指针（非 identity）"}\n' \
        "$([ "$rc_r" = "0" ] && echo true || echo false)" \
        "$([ "$g" = "1" ] && echo true || echo false)" "$rc_r"
}

cmd_status(){
    cur=""
    [ -f "$LUTS/current" ] && cur=$(cat "$LUTS/current" 2>/dev/null)
    printf '{"ok":true,"guard":%s,"current":%s,"sel":%s,"note":"current 为软件记账（非硬件读回）"}\n' \
        "$(guard_state)" "$(jstr "$cur")" "$([ -n "$cur" ] && echo 1 || echo 0)"
}

case "$1" in
    probe)    cmd_probe ;;
    apply)    cmd_apply "$2" "$3" ;;
    rollback) cmd_rollback ;;
    status)   cmd_status ;;
    *)        printf '{"ok":false,"error":"usage: lut_backend.sh probe|apply <name> [--dry]|rollback|status"}\n'; exit 2 ;;
esac
