#!/bin/sh
# filmlab-apply.sh — FilmLab 配方应用器 (NX500, 2026-10-04)
#
# 原理: 双通路写机内原生渲染维度, 全部由相机 ISP 自己渲染, CPU 成本为零
#   ① prefman  → PW 7 维参数块 + WB K/tint   (持久化, 重启后仍在)
#   ② setusr   → PW_TYPE 槽切换 + Smart Filter  (实时, ISP 立刻重渲)
#
# 用法:
#   sh filmlab-apply.sh list              列出全部配方
#   sh filmlab-apply.sh show <id>         显示配方详情 + 当前机内值
#   sh filmlab-apply.sh apply <id>        应用配方
#   sh filmlab-apply.sh reset             恢复中性/出厂
#   sh filmlab-apply.sh dump              导出机内当前 14 槽全表(诊断用)
#
# 备份: 每次 apply 前自动 prefman save_file 0, 覆盖 /opt/storage/sdcard/_pwtest/app.filmlab.bak

PREF=/opt/storage/sdcard/_pwtest
RECIPES=$PREF/filmlab.json
BAK=$PREF/app.filmlab.bak

# ---- PW 参数块 (实机 prefman info 0) ----
# 基址 0x0a3ec, 参数步进 52 (13风格×4B), 风格步进 4
# 风格 0..8=厂商, 9=CUSTOM_1, 10=CUSTOM_2, 11=CUSTOM_3
#★ 实机 13:58 定案（红/绿/蓝特征色验证）：UI 自定义1/2/3 = prefman slot 9/10/11
#
# ★★ 关键：prefman slot 编号与 setusr enum 编号是两个不同空间，不要混淆
#    slot 11完全有效（= 自定义3），被拒的是 enum 11(0x14000b) 而不是 slot 11
#    enum 12(0x14000c) → 实际指向 slot 11
#    enum: 0-8=厂商9个  9=自定义1  10=自定义2  12=自定义3（11 是空洞）
#    slot: 0-8=厂商9个 9=自定义1  10=自定义2  11=自定义3
PW_BASE=41964
P_COLOR=0                  # R/G/B 索引 0/1/2
P_HUE=3
P_SAT=4
P_SHARP=5
P_CONTRAST=6
# ---- 其它维度偏移 ----
WB_K=42132               # 0x0a394  WB_K_VALUE (真实 Kelvin)
WB_TINT=42172            # 0x0a3bc  WB_CUSTOM_DETAIL_BA_XY
TINT_NEUTRAL=458759      # 0x070007

# ---- setusr 索引与DATA ID 前缀 ----
I_PW=20
I_SFT=62
I_SFS=63
I_SRANGE=21
PFX_PW=1310720          # 0x140000  -> 0x140000+slot
PFX_SFT=4063232          # 0x3e0000
PFX_SFS=4128768          # 0x3f0000
PFX_SRANGE=1376256     # 0x150000

hex8() { printf "0x%02x" "$1"; }
data_id() { printf "0x%06x" $(( $1 + $2 )); }

rd() {
    # prefman 读 4 字节有符号
    prefman get 0 "$(printf 0x%05x $1)" l 2>/dev/null \
        | grep -o 'value = [-0-9]*' | sed 's/value = //'
}

wr() {
    prefman set 0 "$(printf 0x%05x $1)" l "$2" >/dev/null 2>&1
}

gusr() {
    st cap capdtm getusr $1 2>/dev/null | tr -d '\r' \
        | sed 's/.*UserData is //; s/ *(0x[0-9a-fA-F]*)$//'
}

susr() {
    # susr <索引> <DATA_ID>
    st cap capdtm setusr $1 $2 >/dev/null 2>&1
}

# ---- 配方表 (内嵌, 不依赖 SD 卡 JSON 解析) ----
# 格式: id|slot|r|g|b|hue|sat|sharp|contrast|K|tint_a|tint_b|sft|sfs|srange|tag
REC="
portra400|9|106|100|93|11|9|9|8|5900|9|4|0|0|1|人像暖调
velvia50|10|102|110|109|10|14|11|13|5500|5|6|0|0|1|风光高饱和
trix400|11|100|100|100|10|0|13|12|6300|7|7|0|0|0|黑白粗颗粒
ektachrome|11|96|105|108|12|13|10|11|7100|4|8|0|0|1|反转片冷调
hp5|10|100|100|100|10|0|11|10|6300|7|7|0|0|0|黑白中颗粒
superia400|11|103|99|104|13|11|9|9|6100|8|5|0|0|1|民用负片
monowarm|9|108|100|92|10|0|10|11|5000|12|2|0|0|0|暖调黑白
vignette|9|100|100|100|10|11|10|10|6300|7|7|1|1|0|暗角叠加
"

neutral_pw() {
    wr $(slot_off 0 13) 100; wr $(slot_off 1 13) 100; wr $(slot_off 2 13) 100
    wr $(slot_off 3 13) 10;  wr $(slot_off 4 13) 10
    wr $(slot_off 5 13) 10;  wr $(slot_off 6 13) 10
}
# 注意: 参数 i 在偏移 PW_BASE + i*52, 风格 s 在 + s*4
# 所以 slot S 的 R 偏移 = PW_BASE + 0*52 + S*4

slot_off() {
    # $1=参数索引 $2=slot
    echo $(( PW_BASE + $1 * 52 + $2 * 4 ))
}

backup() {
    [ -d "$PREF" ] || mkdir -p "$PREF" 2>/dev/null
    prefman save_file 0 "$BAK" >/dev/null 2>&1 && echo "  [备份] $BAK"
}

apply_recipe() {
    _id=$1
    _line=$(echo "$REC" | grep "^$_id|")
    [ -z "$_line" ] && { echo "  配方不存在: $_id"; return 1; }

    _slot=$(echo "$_line" | cut -d'|' -f2)
    _r=$(echo   "$_line" | cut -d'|' -f3)
    _g=$(echo   "$_line" | cut -d'|' -f4)
    _b=$(echo   "$_line" | cut -d'|' -f5)
    _hue=$(echo "$_line" | cut -d'|' -f6)
    _sat=$(echo "$_line" | cut -d'|' -f7)
    _shp=$(echo "$_line" | cut -d'|' -f8)
    _con=$(echo "$_line" | cut -d'|' -f9)
    _k=$(echo   "$_line" | cut -d'|' -f10)
    _ta=$(echo  "$_line" | cut -d'|' -f11)
    _tb=$(echo  "$_line" | cut -d'|' -f12)
    _sft=$(echo "$_line" | cut -d'|' -f13)
    _sfs=$(echo "$_line" | cut -d'|' -f14)
    _sr=$(echo  "$_line" | cut -d'|' -f15)
    _tag=$(echo "$_line" | cut -d'|' -f16)
    _name=$_id

    echo "应用配方: $_name  ($_tag)"
    echo "  slot=$_slot  R=$_r G=$_g B=$_b  HUE=$_hue SAT=$_sat SHARP=$_shp CONTRAST=$_con"
    echo "  K=$_k  tint=A:$_ta B:$_tb  sft=$_sft/$_sfs  srange=$_sr"
    echo

    backup

    # ---- ① prefman: 写 PW 7 维 ----
    wr $(slot_off 0 $_slot) $_r
    wr $(slot_off 1 $_slot) $_g
    wr $(slot_off 2 $_slot) $_b
    wr $(slot_off 3 $_slot) $_hue
    wr $(slot_off 4 $_slot) $_sat
    wr $(slot_off 5 $_slot) $_shp
    wr $(slot_off 6 $_slot) $_con
    prefman save >/dev/null 2>&1
    sync

    # ---- ①b prefman: 写 WB K 值 + tint ----
    wr $WB_K $_k
    wr $WB_TINT $(( (_ta << 16) | _tb ))
    prefman save >/dev/null 2>&1
    sync

    # ---- ② setusr: 实时切换 ----
    susr $I_PW $(data_id $PFX_PW $_slot)       # PW 槽
    susr $I_SFT $(data_id $PFX_SFT $_sft)     # Smart Filter 类型
    susr $I_SFS $(data_id $PFX_SFS $_sfs)     # 强度
    susr $I_SRANGE $(data_id $PFX_SRANGE $_sr) # SmartRange

    echo "  [实时] PW = $(gusr $I_PW)"
    echo "  [实时] SmartFilter = $(gusr $I_SFT) / $(gusr $I_SFS)"
    echo "  [持久] K = $(rd $WB_K)   tint = $(rd $WB_TINT) (0x$(printf %06x $(rd $WB_TINT)))"
    echo "  [回读] slot$_slot R=$(rd $(slot_off 0 $_slot)) G=$(rd $(slot_off 1 $_slot)) B=$(rd $(slot_off 2 $_slot)) SAT=$(rd $(slot_off 4 $_slot))"
}

cmd_list() {
    echo "=== FilmLab 配方 (NX500 原生维度) ==="
    printf "  %-12s %-6s %-10s %s\n" ID SLOT TAG "PW(R/G/B/HUE/SAT/SHP/CON)  K  tint"
    echo "$REC" | while IFS='|' read -r id slot r g b h s sh c k ta tb sft sfs sr tag; do
        [ -z "$id" ] && continue
        printf "  %-12s %-6s %-10s %s/%s/%s %s/%s/%s/%s  %s  %s:%s\n" \
            "$id" "C$((slot-9))" "$tag" "$r" "$g" "$b" "$h" "$s" "$sh" "$c" "$k" "$ta" "$tb"
    done
}

cmd_show() {
    _id=$1
    _line=$(echo "$REC" | grep "^$_id|")
    [ -z "$_line" ] && { echo "配方不存在: $_id"; return 1; }
    _slot=$(echo "$_line" | cut -d'|' -f2)
    echo "$_line" | awk -F'|' '{printf "  %-10s %s\n", $1, "全部字段:"}'
    echo "$_line" | tr '|' '\n' | awk '{printf "    [%d] %s\n", NR-1, $0}'
    echo
    echo "  --- 机内当前值 (slot $_slot) ---"
    printf "    R=%s G=%s B=%s\n" "$(rd $(slot_off 0 $_slot))" "$(rd $(slot_off 1 $_slot))" "$(rd $(slot_off 2 $_slot))"
    printf "    HUE=%s SAT=%s SHARP=%s CONTRAST=%s\n" \
        "$(rd $(slot_off 3 $_slot))" "$(rd $(slot_off 4 $_slot))" "$(rd $(slot_off 5 $_slot))" "$(rd $(slot_off 6 $_slot))"
    printf "    K=%s  tint=%s (0x%06x)\n" "$(rd $WB_K)" "$(rd $WB_TINT)" "$(rd $WB_TINT)"
    echo "  --- 实时 userdata ---"
    printf "    PW=%s\n    SmartFilter=%s / %s\n    SmartRange=%s\n" \
        "$(gusr $I_PW)" "$(gusr $I_SFT)" "$(gusr $I_SFS)" "$(gusr $I_SRANGE)"
}

cmd_reset() {
    echo "恢复中性..."
    backup
    # OFF 槽 (13) 写中性
    wr $(slot_off 0 13) 100; wr $(slot_off 1 13) 100; wr $(slot_off 2 13) 100
    wr $(slot_off 3 13) 10; wr $(slot_off 4 13) 10; wr $(slot_off 5 13) 10; wr $(slot_off 6 13) 10
    wr $WB_K 6300
    wr $WB_TINT $TINT_NEUTRAL
    prefman save >/dev/null 2>&1; sync
    susr $I_PW $(data_id $PFX_PW 0)
    susr $I_SFT $(data_id $PFX_SFT 0)
    susr $I_SFS $(data_id $PFX_SFS 0)
    susr $I_SRANGE $(data_id $PFX_SRANGE 1)
    echo "  PW = $(gusr $I_PW)"
    echo "  SmartFilter = $(gusr $I_SFT)"
    echo "  K = $(rd $WB_K)  tint = $(rd $WB_TINT)"
}

cmd_dump() {
    echo "=== 机内 PW 14 槽全表 ==="
    printf "%-4s" "参数"
    _s=0
    while [ $_s -le 13 ]; do printf "%7d" $_s; _s=$(( _s + 1 )); done
    echo
    _p=0
    while [ $_p -le 6 ]; do
        case $_p in
            0) n=R_COLOR;; 1) n=G_COLOR;; 2) n=B_COLOR;;
            3) n=HUE;; 4) n=SAT;; 5) n=SHARP;; 6) n=CONTRAST;;
        esac
        printf "%-4s" "$n"
        _s=0
        while [ $_s -le 13 ]; do printf "%7s" "$(rd $(slot_off $_p $_s))"; _s=$(( _s + 1 )); done
        echo
        _p=$(( _p + 1 ))
    done
    echo
    echo "  槽位: 0-8=厂商(STD/VIVID/PORTRAIT/LANDSCAPE/FOREST/RETRO/COOL/CALM/CLASSIC)"
    echo "        9-12=CUSTOM_1..4   13=OFF(中性基线)"
    echo
    printf "  WB_K      = %s\n" "$(rd $WB_K)"
    printf "  WB_TINT   = %s (0x%06x)\n" "$(rd $WB_TINT)" "$(rd $WB_TINT)"
}

case "$1" in
    list)cmd_list ;;
    show)     cmd_show "$2" ;;
    apply)    apply_recipe "$2" ;;
    reset)    cmd_reset ;;
    dump)     cmd_dump ;;
    *)        echo "用法: sh filmlab-apply.sh list|show|apply|reset|dump"; exit 1 ;;
esac
