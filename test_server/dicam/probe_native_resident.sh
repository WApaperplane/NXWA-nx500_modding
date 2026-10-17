#!/bin/sh
# @gate script=probe_native_resident.sh opens=rdonly one_shot=1
# NX500 1.12 only. At most 41 bytes from known App/catalog locations.
# No debugger/ptrace, no stop signal, no /dev/mem, no file or memory writes.
# Permission failure stays unavailable; never fall back to attach or injection.
echo NXWA_NATIVE_RESIDENT_V1
section() { printf '@@ %s\n' "$1"; }
section boot_id; cat /proc/sys/kernel/random/boot_id
section uptime; cat /proc/uptime
section loadavg; cat /proc/loadavg
section meminfo; cat /proc/meminfo
chosen=''; count=0
for process in /proc/[0-9]*; do
    case "$(readlink "$process/exe" 2>/dev/null)" in
        */di-camera-app) chosen=${process##*/}; count=$((count + 1)) ;;
    esac
done
section pid; echo "$chosen"
if [ "$count" != 1 ]; then section refusal; echo ambiguous_process; section end; exit 0; fi
section stat_before; cat "/proc/$chosen/stat"
app_md5=$(md5sum "/proc/$chosen/exe" 2>/dev/null | cut -d ' ' -f 1)
mo_md5=$(md5sum /usr/share/locale/zh_CN/LC_MESSAGES/di-camera-app.mo 2>/dev/null | cut -d ' ' -f 1)
section exe_md5; echo "$app_md5"
section locale_md5; echo "$mo_md5"
section file_identity
stat -L -c '%d %i %s %n' /usr/apps/com.samsung.di-camera-app/bin/di-camera-app /usr/share/locale/zh_CN/LC_MESSAGES/di-camera-app.mo
section locale_loop_backing
cat /sys/block/loop0/loop/backing_file 2>/dev/null
section app_maps
grep -E '/di-camera-app$|/di-camera-app.mo$' "/proc/$chosen/maps"
if [ "$app_md5" != ae44293e969101d1cf0a93cbe9b99f75 ] || [ "$mo_md5" != f2d60cd2f2687de43089729fb06f436c ]; then
    section refusal; echo unsupported_backing_file; section end; exit 0
fi
text_map=$(grep -E '^00008000-00441000 r-xp 00000000 .* /usr/apps/com.samsung.di-camera-app/bin/di-camera-app$' "/proc/$chosen/maps")
if [ -z "$text_map" ]; then section refusal; echo unexpected_text_map; section end; exit 0; fi
sample() {
    section "$1"
    printf 'address=%s count=%s\n' "$2" "$3"
    { dd if="/proc/$chosen/mem" bs=1 skip="$2" count="$3" 2>/dev/null; printf 'read_rc=%s\n' "$?" >&2; } | od -An -tx1
}
# Source: c2_bytepatch.v2.json. Code and command-name samples, NOT an App dump.
sample c2_name 3593948 6
sample c2_code 828328 16
mo_base=$(awk '$6 == "/usr/share/locale/zh_CN/LC_MESSAGES/di-camera-app.mo" && $3 == "00000000" {split($1, a, "-"); print a[1]}' "/proc/$chosen/maps")
case "$mo_base" in
    ''|*[!0-9a-f]*) section catalog_sample_refusal; echo ambiguous_or_missing_catalog_map ;;
    *)
        # Canonical zh_CN MO: CUSTOM1 trans descriptor @0x4a24, old string @104583.
        sample custom1_descriptor "$((0x$mo_base + 0x4a24))" 8
        sample custom1_old_string "$((0x$mo_base + 104583))" 11
        ;;
esac
section stat_after; cat "/proc/$chosen/stat"
section end
