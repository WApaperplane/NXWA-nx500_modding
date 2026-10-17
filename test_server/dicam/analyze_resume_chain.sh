#!/usr/bin/env bash
# Offline only: inspect saved camera files, never run camera hibernation tools.
set -euo pipefail
ROOTFS=${1:-/opt/nxks2/rootfs-112}
OUT=${2:?usage: analyze_resume_chain.sh ROOTFS NEW_EVIDENCE_DIRECTORY}
REA=${NXWA_REA_WRAPPER:-/mnt/e/NXWA/tools/rea-wsl.sh}
LIB="$ROOTFS/usr/lib/libhibernation.so"
APP="$ROOTFS/usr/apps/com.samsung.di-camera-app/bin/di-camera-app"
test -f "$LIB"
test -f "$APP"
mkdir -p "$OUT"
sha256sum "$LIB" "$ROOTFS/usr/bin/hib_exjob" "$APP" > "$OUT/subjects.sha256"
for path in usr/bin/hibernation.sh usr/bin/hib_tmp.sh \
    usr/lib/systemd/system/hib_post.path usr/lib/systemd/system/hib_post.service \
    usr/lib/systemd/system/hibernation.service usr/lib/systemd/system/di-camera-app.service; do
    printf '\nSOURCE %s\n' "$path"
    sha256sum "$ROOTFS/$path"
    sed -n '1,240p' "$ROOTFS/$path"
done > "$OUT/scripts_and_units.txt"
arm-linux-gnueabi-objdump -d "$APP" |
    grep -B 5 -A 4 -E '<hib_post@plt>|<hib@plt>' > "$OUT/app_hib_call_sites.txt"
arm-linux-gnueabi-objdump -d "$APP" |
    grep -B 14 -A 12 -E 'bl.*1c175c|bl.*1c1740' > "$OUT/app_hib_wrappers_callers.txt"
arm-linux-gnueabi-objdump -d --disassemble=hib_post "$LIB" > "$OUT/hib_post.disasm.txt"
arm-linux-gnueabi-objdump -d --disassemble=hib "$LIB" > "$OUT/hib.disasm.txt"
arm-linux-gnueabi-objdump -d --start-address=0x1970 --stop-address=0x1b20 "$LIB" > "$OUT/marker_and_snapshot_helpers.disasm.txt"
for proc in hib_post hib; do
    printf 'REA: %s\n' "$proc"
    if [ "${NXWA_RESUME_REUSE:-0}" != 1 ]; then
        "$REA" function "$LIB" "$proc" --provider ghidra --format json > "$OUT/$proc.json"
    fi
    python3 - "$OUT/$proc.json" "$LIB" "$proc" <<'PY'
import hashlib
import json
import sys
with open(sys.argv[1], encoding="utf-8") as stream:
    evidence = json.load(stream)
with open(sys.argv[2], "rb") as stream:
    digest = hashlib.sha256(stream.read()).hexdigest()
if evidence.get("subject", {}).get("digest", {}).get("sha256") != digest:
    raise SystemExit("Saved REA evidence does not match the current library")
if evidence.get("parameters", {}).get("procedure") != sys.argv[3]:
    raise SystemExit("Saved REA evidence does not match the requested function")
result = evidence.get("normalized_result", {})
print("evidence_id:", evidence.get("evidence_id"))
print("subject:", evidence.get("subject"))
print("pseudocode:", result.get("pseudocode"))
print("limitations:", result.get("limitations"))
if not evidence.get("evidence_id") or not result.get("pseudocode"):
    raise SystemExit("REA did not return function evidence")
PY
done
