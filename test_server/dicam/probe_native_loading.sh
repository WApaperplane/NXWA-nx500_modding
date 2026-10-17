#!/bin/sh
# @gate script=probe_native_loading.sh opens=rdonly one_shot=1
# Read-only stdout collector. No camera commands, process control, mounts or writes.
# NXWA_SYS_ROOT is only for an offline fixture tree; default is the real filesystem.
# Redirect stdout on the caller side. Never interpret this report as UI acceptance.
SYS=${NXWA_SYS_ROOT:-}
PROC=$SYS/proc
TARGET=$SYS/usr/apps/com.samsung.di-camera-app/bin/di-camera-app
LOCALE=$SYS/usr/share/locale/zh_CN/LC_MESSAGES/di-camera-app.mo

section() { printf '@@ %s\n' "$1"; }
read_file() { if [ -r "$1" ]; then cat "$1"; printf '\n'; else echo '<unavailable>'; fi; }
hash_file() { md5sum "$1" 2>/dev/null | cut -d ' ' -f 1; }
is_app() {
    case "$1" in
        */di-camera-app|*/di-camera-app\ \(deleted\)) return 0 ;;
        *) return 1 ;;
    esac
}

echo 'NXWA_NATIVE_LOADING_V1'
section boot_id; read_file "$PROC/sys/kernel/random/boot_id"
section uptime; read_file "$PROC/uptime"
section loadavg; read_file "$PROC/loadavg"
section meminfo; read_file "$PROC/meminfo"
section version_info; read_file "$SYS/etc/version.info"
section ev_mobile_md5; hash_file "$SYS/opt/usr/nx-ks/EV_MOBILE.sh"
section bootmode; read_file "$SYS/sys/power/bootmode"
section candidates
chosen=''; count=0
for process in "$PROC"/[0-9]*; do
    link=$(readlink "$process/exe" 2>/dev/null)
    if is_app "$link"; then
        chosen=${process##*/}; count=$((count + 1)); echo "$chosen"
    fi
done
section selected_pid
if [ "$count" = 1 ]; then echo "$chosen"; else echo '<unavailable>'; chosen=''; fi
if [ -n "$chosen" ]; then
    section stat_before; read_file "$PROC/$chosen/stat"
    section exe_link_before; readlink "$PROC/$chosen/exe" 2>/dev/null
    section exe_md5; hash_file "$PROC/$chosen/exe"
    section language_environment
    if [ -r "$PROC/$chosen/environ" ]; then
        tr '\000' '\n' < "$PROC/$chosen/environ" | grep -E '^(LANG|LANGUAGE|LC_ALL|LC_MESSAGES|HIB)='
    fi
    section maps; read_file "$PROC/$chosen/maps"
    section mountinfo; read_file "$PROC/$chosen/mountinfo"
    section stat_after; read_file "$PROC/$chosen/stat"
    section exe_link_after; readlink "$PROC/$chosen/exe" 2>/dev/null
fi
section target_md5; hash_file "$TARGET"
section locale_target_md5; hash_file "$LOCALE"
section staged_app_md5; hash_file "$SYS/opt/usr/nx-ks/dicam/di-camera-app.c2"
section staged_locale_md5; hash_file "$SYS/opt/usr/nx-ks/locale/zh_CN/di-camera-app.mo"
section mounts; read_file "$PROC/mounts"
section app_unit; read_file "$SYS/usr/lib/systemd/system/di-camera-app.service"
section end
