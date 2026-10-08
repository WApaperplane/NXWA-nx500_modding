#!/bin/sh
# ============================================================
# thumb-prewarm.sh - 后台预生成缩略图缓存
#
# 背景:
#   打开相册时,相机端需要现场跑 ImageMagick convert 生成缩略图,
#   单核 ARM 上约 0.5-2s/张。几百张照片时首屏要等几分钟,期间 CPU
#   打满,80 端口 daemon 的心跳被饿死,前端还会误报"相机已断开"。
#
# 作用:
#   在后台提前把缓存铺好(优先级最低,不影响拍摄与遥控),
#   浏览时全部命中缓存 -> 秒开,CPU 也不再有尖峰。
#
# 用法(相机端):
#   thumb-prewarm.sh start [宽] [质量] [最多张数] [大图宽] [大图质量] [大图张数]
#   thumb-prewarm.sh stop
#   thumb-prewarm.sh status            # 人类可读
#   thumb-prewarm.sh json              # JSON(供 prewarm CGI / 前端进度条读取)
#
# 例:
#   thumb-prewarm.sh start 320 75 300 1024 85 60
#     -> 最新 300 张生成 320px/q75(网格),其中最新 60 张再生成 1024px/q85(灯箱)
#   thumb-prewarm.sh start             # 默认 320 75 200 1024 85 40
#
# 接线(nx-rc.sh 中,web 遥控开启时自动拉起):
#   [ -x "$APP_PATH/thumb/thumb-prewarm.sh" ] && "$APP_PATH/thumb/thumb-prewarm.sh" start >/dev/null 2>&1 &
#
# 进度: /tmp/thumb_prewarm.progress (JSON),前端经 8080 cgi-bin/prewarm 读取
# ============================================================

# 注意:相机端实际布局是 /opt/usr/nx-ks/nx-rc/tools (install.sh 是
# cp -ar scripts/* -> /opt/usr/nx-ks/,脚本内引用必须带 nx-rc 层)。
TOOLS=/opt/usr/nx-ks/nx-rc/tools
CONVERT=$TOOLS/usr/bin/convert
LD_LIBRARY_PATH=$TOOLS/usr/lib
export LD_LIBRARY_PATH

PIDFILE=/tmp/thumb_prewarm.pid
LOGFILE=/tmp/thumb_prewarm.log
PROGRESS=/tmp/thumb_prewarm.progress

# ---- 定位 SD 卡 ----
# web 遥控刚开启时 nx-rc.sh 会立刻拉起本脚本,而 SD 卡挂载可能还没完成,
# 此时 [ -d "$SD/DCIM" ] 会失败导致预热静默退出(进度文件都不会生成)。
# 这里最多等 SD_WAIT 秒,等 DCIM 出现再继续。
SD_WAIT=${SD_WAIT:-30}
sd_ready() {
    for cand in /mnt/mmc /tmp/mmc /mnt/sd /tmp/sd; do
        if [ -d "$cand/DCIM" ]; then
            SD=$cand
            return 0
        fi
    done
    return 1
}

SD=""
i=0
while [ "$i" -lt "$SD_WAIT" ]; do
    if sd_ready; then
        break
    fi
    i=$((i + 1))
    sleep 1
done

log() {
    echo "$(date '+%H:%M:%S') $1" >> "$LOGFILE"
}

# 写进度 JSON: $1=状态 $2=已生成 $3=已跳过 $4=总数
write_progress() {
    printf '{"running":%s,"w":%s,"q":%s,"fw":%s,"fq":%s,"done":%s,"skipped":%s,"total":%s,"ts":%s}\n' \
        "$1" "$W" "$Q" "$FW" "$FQ" "$2" "$3" "$4" "$(date +%s)" \
        > "$PROGRESS.tmp" 2>/dev/null
    mv -f "$PROGRESS.tmp" "$PROGRESS" 2>/dev/null
}

case "$1" in
    stop)
        if [ -f "$PIDFILE" ]; then
            kill "$(cat "$PIDFILE")" 2>/dev/null
            rm -f "$PIDFILE"
            log "stopped by user"
        fi
        echo "thumb-prewarm stopped"
        exit 0
        ;;
    status)
        if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
            echo "running (pid $(cat "$PIDFILE"))"
        else
            echo "not running"
        fi
        echo "--- progress ---"
        cat "$PROGRESS" 2>/dev/null
        echo "--- last log ---"
        tail -5 "$LOGFILE" 2>/dev/null
        exit 0
        ;;
    json)
        # 供 CGI 读取:进程不在时把 running 置 0
        if [ -f "$PROGRESS" ]; then
            if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
                cat "$PROGRESS"
            else
                sed 's/"running":1/"running":0/' "$PROGRESS"
            fi
        else
            echo '{"running":0,"done":0,"skipped":0,"total":0}'
        fi
        exit 0
        ;;
esac

# ---- start ----
W=${2:-320}
Q=${3:-75}
LIMIT=${4:-200}
FW=${5:-1024}
FQ=${6:-85}
FLIMIT=${7:-40}

[ -d "$SD/DCIM" ] || { echo "SD card / DCIM not found"; exit 1; }
[ -x "$CONVERT" ] || { echo "convert not found: $CONVERT"; exit 1; }

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "already running (pid $(cat "$PIDFILE"))"
    exit 0
fi

: > "$LOGFILE"
log "start: w=$W q=$Q limit=$LIMIT  full: w=$FW q=$FQ limit=$FLIMIT"

# 统计图片总数(轻量 ls,只读目录项),供前端算进度百分比
TOTAL=0
for d in $(ls -1 "$SD/DCIM" 2>/dev/null); do
    DD="$SD/DCIM/$d"
    [ -d "$DD" ] || continue
    for f in $(ls -1 "$DD" 2>/dev/null); do
        case "$f" in
            *.JPG|*.jpg|*.JPEG|*.jpeg|*.PNG|*.png) TOTAL=$((TOTAL + 1)) ;;
        esac
    done
done
write_progress 1 0 0 "$TOTAL"

# 后台执行
(
    echo $$ > "$PIDFILE"
    CACHE_ROOT="$SD/.thumbcache/${W}x${Q}"
    FULL_ROOT="$SD/.thumbcache/${FW}x${FQ}"
    DONE=0
    SKIP=0

    # 生成一张: $1=源 $2=缓存根 $3=宽 $4=质量 $5=相对路径(无扩展名)
    gen_one() {
        src=$1; root=$2; w=$3; q=$4; rel=$5
        cache="$root/$rel.jpg"
        if [ -f "$cache" ] && [ ! "$src" -nt "$cache" ]; then
            return 1
        fi
        mkdir -p "$(dirname "$cache")" 2>/dev/null
        tmp="$cache.tmp.$$"
        rm -f "$tmp"
        # nice -n 19:让位给拍摄/遥控,避免抢占 CPU
        if command -v nice >/dev/null 2>&1; then
            nice -n 19 "$CONVERT" -define "jpeg:size=${w}x${w}" \
                -auto-orient -thumbnail "${w}x${w}" -quality "$q" \
                "$src" "$tmp" 2>/dev/null
        else
            "$CONVERT" -define "jpeg:size=${w}x${w}" \
                -auto-orient -thumbnail "${w}x${w}" -quality "$q" \
                "$src" "$tmp" 2>/dev/null
        fi
        if [ -s "$tmp" ]; then
            mv -f "$tmp" "$cache" 2>/dev/null || rm -f "$tmp"
            return 0
        fi
        rm -f "$tmp"
        return 2
    }

    # 目录倒序 + 目录内文件名倒序 = 最新照片优先预热
    for d in $(ls -1r "$SD/DCIM" 2>/dev/null); do
        [ "$DONE" -ge "$LIMIT" ] && break
        DD="$SD/DCIM/$d"
        [ -d "$DD" ] || continue
        for f in $(ls -1r "$DD" 2>/dev/null); do
            [ "$DONE" -ge "$LIMIT" ] && break
            case "$f" in
                *.JPG|*.jpg|*.JPEG|*.jpeg|*.PNG|*.png) ;;
                *) continue ;;
            esac
            SRC="$DD/$f"
            [ -f "$SRC" ] || continue
            REL="$d/${f%.*}"

            gen_one "$SRC" "$CACHE_ROOT" "$W" "$Q" "$REL"
            rc=$?
            if [ "$rc" -eq 1 ]; then
                SKIP=$((SKIP + 1))
            else
                DONE=$((DONE + 1))
                # 最新若干张额外预热灯箱大图(全屏查看才需要)
                if [ "$DONE" -le "$FLIMIT" ]; then
                    gen_one "$SRC" "$FULL_ROOT" "$FW" "$FQ" "$REL"
                fi
            fi
            # 每 5 张更新一次进度文件(写 /tmp 很便宜,前端看着平滑)
            [ $((DONE % 5)) -eq 0 ] && write_progress 1 "$DONE" "$SKIP" "$TOTAL"
            [ $((DONE % 20)) -eq 0 ] && log "generated $DONE (skipped $SKIP)"
        done
    done

    write_progress 0 "$DONE" "$SKIP" "$TOTAL"
    log "finished: generated=$DONE skipped=$SKIP total=$TOTAL"
    rm -f "$PIDFILE"
) >> "$LOGFILE" 2>&1 &

sleep 1
echo "thumb-prewarm started (pid $(cat "$PIDFILE" 2>/dev/null))"
echo "progress: thumb-prewarm.sh status   log: $LOGFILE"
exit 0
