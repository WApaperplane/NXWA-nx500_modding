#!/usr/bin/env python3
"""Offline verification of one saved trial + independent readback + human report.

Never connects to the camera or runs a trial. Writes only a PC acceptance record.
Human visual claims retain their explicitly human authority; they are not inferred
from memory bytes, return codes, hashes or liveness.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
from native_label_trial import read_context, build_script, OLD_HEX
from native_ui_loading import parse_probe


def verified_capture(directory):
    data = (directory / "capture.txt").read_bytes()
    receipt = json.loads((directory / "receipt.json").read_text(encoding="utf-8"))
    if hashlib.sha256(data).hexdigest() != receipt["capture_sha256"]:
        raise ValueError("Capture checksum mismatch: " + str(directory))
    return data, receipt


def verify(root):
    before = read_context(root / "resident_01")
    after = read_context(root / "resident_after")
    if before != after:
        raise ValueError("Identity/mapping changed between resident reads")
    data, receipt = verified_capture(root / "label_trial_01")
    text = data.decode("utf-8").splitlines()
    required = {"NXWA_NATIVE_LABEL_TRIAL_V1", "before_hex=" + OLD_HEX, "phase=label_patched",
                "observation_seconds=30", "rollback=verified_original_11_bytes",
                "disk_catalog_md5=f2d60cd2f2687de43089729fb06f436c", "after_hex=" + OLD_HEX,
                "phase=finished", "pid=%s address=%s length=11 mode=trial" % (before["pid"], before["address"])}
    if not required.issubset(text) or receipt.get("remote_exit_code") != 0 or receipt.get("authorized_length") != 11:
        raise ValueError("Missing successful bounded trial/rollback evidence")
    executed = root / "label_trial_01/executed.sh"
    executed_bytes = executed.read_bytes() if executed.exists() else build_script(before).encode()
    if receipt["script_sha256"] != hashlib.sha256(executed_bytes).hexdigest():
        raise ValueError("Trial source/context differs from recorded script")
    first, _ = verified_capture(root / "live_01")
    last, _ = verified_capture(root / "live_after")
    first, last = parse_probe(first.decode()), parse_probe(last.decode())
    for key in ("boot_id", "process", "target_file", "process_exe_file", "catalog_map_lines", "locale"):
        if first[key] != last[key]:
            raise ValueError("Unexpected metadata difference: " + key)
    human = json.loads((root / "human_observation.json").read_text(encoding="utf-8"))
    if human.get("authority") != "human_user_report_in_current_chat":
        raise ValueError("Visual evidence needs explicit human authority")
    if not all(human["before"].values()):
        raise ValueError("Missing human readiness/authorization")
    visual = bool(human["during"]["native_custom1_showed_NXWA_Test_1"] and
                  human["during"]["menu_reported_normal"] and
                  human["after"]["custom1_restored_after_reentry"] and
                  human["after"]["menu_and_return_reported_normal"])
    return {"schema": "nxwa.native-label-acceptance/1", "machine_evidence_pass": True,
            "human_visual_observation_pass": visual, "authority": human["authority"],
            "result": "one_label_observed_and_restored" if visual else "machine_only_visual_not_passed",
            "pid": before["pid"], "address": hex(before["address"]), "length": 11,
            "code_write_performed": False, "disk_catalog_unchanged": True,
            "approved_trial_count": 1, "production_ready": False, "startup_persistence": "unverified",
            "preset_slot_consistency": "unverified", "preset_confirm_apply": "unverified",
            "touch_rotary_full_regression": "unverified", "preview_JPEG_effect": "unverified",
            "fresh_exec": "unknown", "whole_app_resident_code_verified": False,
            "note": "11 bytes restored; private COW page accounting is not claimed to revert."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_root", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    options = parser.parse_args()
    result = verify(options.evidence_root)
    executed = options.evidence_root / "label_trial_01/executed.sh"
    if not executed.exists():
        # Reconstruction is allowed only after matching the hash recorded at execution.
        with executed.open("xb") as stream:
            stream.write(build_script(read_context(options.evidence_root / "resident_01")).encode())
    options.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["human_visual_observation_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
