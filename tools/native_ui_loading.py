#!/usr/bin/env python3
"""Interpret saved native loading probe stdout; never contact or modify a camera.

File hashes identify backing files, NOT resident code or rendered native labels.
PID/starttime and boot_id comparisons do NOT prove fresh exec on a snapshot device.
"""
import argparse
import json
from pathlib import Path
import re
import sys

APP_HASHES = {"ae44293e969101d1cf0a93cbe9b99f75": "official_v1.12",
              "0e1da8b326f49728e9394f98a53ffd35": "c2_v1",
              "48d94bd63e4479fc931ae1a1fee4e94b": "c2_v2"}


def parse_stat(raw):
    # comm can contain spaces and ')'; fields after its final ')' start at #3.
    if ") " not in raw:
        return None
    tail = raw.rsplit(") ", 1)[1].split()
    try:
        return {"pid": int(raw.split(" ", 1)[0]), "start_ticks": int(tail[19])}
    except (ValueError, IndexError):
        return None


def parse_probe(raw):
    lines = raw.splitlines()
    try:
        start = lines.index("NXWA_NATIVE_LOADING_V1")
    except ValueError as error:
        raise ValueError("Missing native loading probe header") from error
    sections = {}
    key = None
    for line in lines[start + 1:]:
        if line.startswith("@@ "):
            key = line[3:]
            if key in sections:
                raise ValueError("Duplicate probe section: " + key)
            sections[key] = []
            if key == "end":
                break
        elif key:
            sections[key].append(line)
    if "end" not in sections:
        raise ValueError("Incomplete native loading probe")
    def value(name):
        return "\n".join(sections.get(name, [])).strip()

    def optional(name):
        result = value(name)
        return result if result and result != "<unavailable>" else None

    def file_hash(name):
        result = value(name)
        return result if re.fullmatch(r"[0-9a-f]{32}", result) else None

    candidates = [int(line) for line in sections.get("candidates", []) if line.isdecimal()]
    before, after = parse_stat(value("stat_before")), parse_stat(value("stat_after"))
    selected = value("selected_pid")
    stable = bool(len(candidates) == 1 and selected == str(candidates[0]) and before and after
                  and before == after and before["pid"] == candidates[0]
                  and value("exe_link_before") == value("exe_link_after")
                  and value("exe_link_before"))
    target, exe = file_hash("target_md5"), file_hash("exe_md5")
    locale, staged_locale = file_hash("locale_target_md5"), file_hash("staged_locale_md5")
    warnings = ["Backing-file identity is not resident-code verification.",
                "PID/starttime/boot_id do not prove fresh exec on this snapshot device.",
                "Catalog path/mount/hash do not prove gettext cache reload or visible labels."]
    if not stable:
        warnings.append("No single stable App process was captured; process-file identity is unknown.")
    maps = [line for line in sections.get("maps", []) if "di-camera-app" in line]
    catalog_maps = [line for line in sections.get("maps", []) if "/locale/" in line or ".mo" in line]
    return {"schema": "nxwa.native-loading/1", "scope": "saved_readonly_probe",
            "boot_id": optional("boot_id"), "uptime": optional("uptime"),
            "loadavg": optional("loadavg"), "meminfo": optional("meminfo"),
            "version_info": optional("version_info"), "ev_mobile_md5": file_hash("ev_mobile_md5"),
            "language_environment": sections.get("language_environment", []),
            "pid_candidates": candidates, "process_stable": stable,
            "process": before if stable else None,
            "target_file": {"md5": target, "variant": APP_HASHES.get(target, "unknown")},
            "process_exe_file": {"md5": exe if stable else None,
                                 "variant": APP_HASHES.get(exe, "unknown") if stable else "unknown"},
            "exe_file_matches_target": (exe == target) if stable and exe and target else None,
            "app_map_lines": maps,
            "catalog_map_lines": catalog_maps,
            "locale": {"target_md5": locale, "staged_md5": staged_locale,
                       "path_matches_staged": (locale == staged_locale) if locale and staged_locale else None,
                       "visible_labels_verified": False},
            "unit_contains_premount": ("t2_premount.sh" in value("app_unit")) if optional("app_unit") else None,
            "fresh_exec": "unknown", "running_code_verified": False,
            "native_ui_verified": False, "warnings": warnings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    options = parser.parse_args()
    try:
        report = parse_probe(options.capture.read_text(encoding="utf-8"))
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
