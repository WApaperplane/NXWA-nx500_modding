#!/usr/bin/env python3
"""One explicitly authorized 11-byte native label trial, then automatic restore.

Requires a complete saved resident capture/receipt. No arbitrary address, label,
length, code patch, disk upload, service control or firmware operation is exposed.
Default is dry-run. Live execution requires --execute-approved.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
from datetime import datetime, timezone

from capture_native_loading import collect, CaptureError, clean_lines
from native_ui_loading import parse_stat

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "test_server/dicam/native_label_trial.sh.in"
OLD_HEX = "e887aae5ae9ae4b9892031"
NEW_HEX = "4e58574120546573742031"


def read_context(directory):
    data = (directory / "capture.txt").read_bytes()
    receipt = json.loads((directory / "receipt.json").read_text(encoding="utf-8"))
    if receipt.get("capture_sha256") != hashlib.sha256(data).hexdigest() or receipt.get("framed_remote_rc") != 0:
        raise ValueError("Resident capture receipt mismatch")
    raw = data.decode("utf-8").splitlines()
    start = raw.index("NXWA_NATIVE_RESIDENT_V1")
    sections, key = {}, None
    for line in raw[start + 1:]:
        if line.startswith("@@ "):
            key = line[3:]
            if key in sections:
                raise ValueError("Duplicate resident section")
            sections[key] = []
            if key == "end":
                break
        elif key:
            sections[key].append(line)
    if "end" not in sections or "refusal" in sections:
        raise ValueError("Incomplete/refused resident capture")
    value = lambda name: "\n".join(sections.get(name, [])).strip()
    before, after = parse_stat(value("stat_before")), parse_stat(value("stat_after"))
    if not before or before != after or str(before["pid"]) != value("pid"):
        raise ValueError("Unstable resident process")
    if not re.fullmatch(r"[0-9a-f-]{36}", value("boot_id")):
        raise ValueError("Invalid boot identity")
    if value("exe_md5") != "ae44293e969101d1cf0a93cbe9b99f75" or value("locale_md5") != "f2d60cd2f2687de43089729fb06f436c":
        raise ValueError("Unsupported backing files")
    maps = [line.split() for line in sections["app_maps"] if line.endswith("/di-camera-app.mo")]
    if len(maps) != 1 or maps[0][1:3] != ["r--p", "00000000"]:
        raise ValueError("Expected one private read-only catalog map")
    mapping = maps[0]
    base, end = [int(part, 16) for part in mapping[0].split("-")]
    if base + 104583 + 11 > end:
        raise ValueError("Label outside mapping")

    def sample(name, address, count, expected):
        lines = sections.get(name, [])
        header = "address=%s count=%s" % (address, count)
        hex_data = "".join("".join(line.split()) for line in lines if re.fullmatch(r"(?:\s*[0-9a-f]{2})+\s*", line))
        if header not in lines or "read_rc=0" not in lines or hex_data != expected:
            raise ValueError("Resident sample mismatch: " + name)
    sample("c2_name", 3593948, 6, "7573636f6d00")
    sample("c2_code", 828328, 16, "f8452de9010050e3350000da040091e5")
    sample("custom1_descriptor", base + 0x4a24, 8, "0b00000087980100")
    sample("custom1_old_string", base + 104583, 11, OLD_HEX)
    return {"pid": before["pid"], "ticks": before["start_ticks"], "boot": value("boot_id"),
            "base": mapping[0] + ":" + mapping[3] + ":" + mapping[4], "address": base + 104583}


def build_script(context, mode="trial", window=30, fixture_root=""):
    if mode not in ("trial", "restore") or not 0 <= window <= 30:
        raise ValueError("Invalid trial mode/window")
    script = TEMPLATE.read_text(encoding="utf-8")
    fields = {"ROOT": shlex.quote(fixture_root), "PID": str(context["pid"]), "TICKS": str(context["ticks"]),
              "BOOT": shlex.quote(context["boot"]), "BASE": shlex.quote(context["base"]),
              "ADDR": str(context["address"]), "MODE": mode, "WINDOW": str(window)}
    for name, value in fields.items():
        script = script.replace("@@" + name + "@@", value)
    return script


def persist(directory, body, transcript, nonce, script):
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "capture.txt").write_bytes(body)
    (directory / "transcript.txt").write_bytes(transcript)
    (directory / "executed.sh").write_bytes(script.encode("utf-8"))
    marker = re.compile(("NXWA_CAPTURE_END_" + nonce + ":([0-9]+)").encode())
    statuses = [int(match.group(1)) for line in clean_lines(transcript) if (match := marker.fullmatch(line))]
    receipt = {"schema": "nxwa.native-label-trial/1", "captured_utc": datetime.now(timezone.utc).isoformat(),
               "nonce": nonce, "script_sha256": hashlib.sha256(script.encode()).hexdigest(),
               "capture_sha256": hashlib.sha256(body).hexdigest(), "authorized_length": 11,
               "label": "NXWA Test 1", "scope": "private_catalog_label_only_automatic_restore",
               "remote_exit_code": statuses[0] if len(statuses) == 1 else None,
               "human_authorization": "11-byte temporary native label experiment and restoration only"}
    (directory / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--execute-approved", action="store_true")
    parser.add_argument("--restore-only", action="store_true")
    options = parser.parse_args()
    context = read_context(options.baseline)
    script = build_script(context, mode="restore" if options.restore_only else "trial")
    if not options.execute_approved:
        print(json.dumps({"dry_run": True, "context": context, "length": 11,
                          "script_sha256": hashlib.sha256(script.encode()).hexdigest()}, indent=2))
        return 0
    if options.out.exists():
        parser.error("Output must not already exist")
    try:
        body, transcript, nonce = collect(script, timeout=45, allow_remote_error=True)
    except CaptureError as error:
        persist(options.out, b"", error.transcript, error.nonce, script)
        # Restore is already inside the explicitly approved trial scope. Never retry the trial.
        rescue = build_script(context, mode="restore")
        body, transcript, nonce = collect(rescue, timeout=20, allow_remote_error=True)
        persist(options.out / "recovery", body, transcript, nonce, rescue)
        print(body.decode("utf-8", "replace"))
        return 2
    receipt = persist(options.out, body, transcript, nonce, script)
    text = body.decode("utf-8", "replace")
    print(text)
    if "rollback=FAILED" in text.splitlines():
        rescue = build_script(context, mode="restore")
        body, transcript, nonce = collect(rescue, timeout=20, allow_remote_error=True)
        persist(options.out / "recovery", body, transcript, nonce, rescue)
        print(body.decode("utf-8", "replace"))
        return 2
    # Do not treat a remote shell return code as rollback evidence.
    return 0 if receipt["remote_exit_code"] == 0 and "rollback=verified_original_11_bytes" in text.splitlines() and "after_hex=" + OLD_HEX in text.splitlines() else 2


if __name__ == "__main__":
    raise SystemExit(main())
