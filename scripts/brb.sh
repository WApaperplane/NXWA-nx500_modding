#!/bin/bash
# [同构 批次1] 录像启动：优先 App 官方命令，失败退回按键注入（行为最坏等于改前）
#   依据：docs/current/SHELL_TO_APP_ISOMORPHISM_2026-10-12.md §4 批次 1
nx_rec_start() {
    /usr/bin/st app nx record start >/dev/null 2>&1 && return 0
    /usr/bin/st key click rec
}
renice -n -10 -p $$
nx_rec_start
sleep 0.5
renice -n +10 -p $(pgrep di-camera-app)
