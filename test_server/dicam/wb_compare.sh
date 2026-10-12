#!/bin/bash
# =====================================================================
# WB 双路对照实验（同构批次 2 的判据脚本 · 相机端运行 · 只读+可逆）
#
# 目的：判定 `st app nx capture wb <name>`（App 命令通道）与
#       本地 `st cap capdtm setusr 6 0x0600<enum>`（属性直写）是否**语义等价**。
#
# 背景：静态解出的 App 名↔enum 映射与本地 WB_TYPE 真值表疑差 1：
#   本地  WB_TYPE: 0=AUTO 1=AUTO_TUNGSTEN 2=DAYLIGHT 3=CLOUDY 4=FLUORESCENTW 8=FLASH 9=CUSTOM 10=MANUAL
#   App   wb name: (无)=0  auto-tungsten=1  tungsten=2  day=3  cloud=4  f-w=5 f-n=6 f-d=7  flash=8  custom=9
#   ⇒ 必须实机对照，不能凭静态推断改默认路径。
#
# 用法（相机上，root）:
#   sh /opt/usr/nx-ks/wb_compare.sh            # 输出到 stdout（跑完请重启相机复位）
#   sh /opt/usr/nx-ks/wb_compare.sh /tmp/wb.tsv
#
# 判据：同一条 name 的"App 路读回" == "原路读回" ⇒ 两路等价
# 还原：脚本结束前会写回 auto（0x060000），并提示重启
# =====================================================================

OUT="${1:-/dev/stdout}"
WB_TYPE_OFF=0x0a390        # APPPREF_WB_TYPE

read_userdata6() {   # capdtm 侧
    st cap capdtm getusr 6 2>/dev/null | tr -d '\r' | sed -n 's/.*UserData is \(.*\)/\1/p'
}
read_pref_wbtype() { # prefman 侧
    prefman get 0 "$WB_TYPE_OFF" l 2>/dev/null | tr -d '\r' | sed -n 's/.*value = \([-0-9]*\).*/\1/p'
}

emit() { printf '%s\n' "$*" >> "$OUT"; }

emit "# WB 双路对照  $(date '+%Y-%m-%d %H:%M:%S')  uptime=$(cut -d' ' -f1 /proc/uptime)s"
emit "# 列: name | app_enum | app_getusr6 | app_wbtype | raw_hex | raw_getusr6 | raw_wbtype | 判定"

# name = App 名; hex = 本地 setusr 6 的魔数; expected_enum = 本地真值表认为的 enum
TABLE="
auto|0x060000|0
auto-tungsten|0x060001|1
tungsten|0x060002|2
day|0x060002|2
cloud|0x060003|3
fluorescent-w|0x060004|4
fluorescent-n|0x060005|5
fluorescent-d|0x060006|6
flash|0x060008|8
custom|0x060009|9
"

echo "$TABLE" | while IFS='|' read -r name hex exp; do
    [ -z "$name" ] && continue

    # ---- 路 A：App 命令通道 ----
    if [ "$name" = "auto" ]; then
        st app nx capture wb >/dev/null 2>&1
    else
        st app nx capture wb "$name" >/dev/null 2>&1
    fi
    ap_rc=$?
    sleep 1
    ap_u6=$(read_userdata6)
    ap_wt=$(read_pref_wbtype)

    # ---- 路 B：属性直写（原路）----
    st cap capdtm setusr 6 "$hex" >/dev/null 2>&1
    rw_rc=$?
    sleep 1
    rw_u6=$(read_userdata6)
    rw_wt=$(read_pref_wbtype)

    if [ "$ap_u6" = "$rw_u6" ] && [ "$ap_wt" = "$rw_wt" ]; then
        verdict="等价"
    else
        verdict="★不等价"
    fi
    emit "$name|$exp|rc=$ap_rc:$ap_u6|$ap_wt|$hex|rc=$rw_rc:$rw_u6|$rw_wt|$verdict"
done

# ---- 还原到 auto ----
st cap capdtm setusr 6 0x060000 >/dev/null 2>&1
emit "# 已写回 auto(0x060000)。★ 建议随后重启相机一次，确保 App/ISP 状态干净。"

[ "$OUT" != "/dev/stdout" ] && { echo "已写出: $OUT"; cat "$OUT"; }
exit 0
