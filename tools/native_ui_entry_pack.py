#!/usr/bin/env python3
"""Build an OFFLINE one-entry native PW candidate, not an installer.

Only CUSTOM1 is renamed. CUSTOM2/3 stay official until their independent
runtime storage/apply path is verified. Reuses the existing append-only MO tool.
No camera, firmware, rootfs or existing output directory is modified.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import mo_patch

REPO = Path(__file__).resolve().parents[1]
SOURCE_MD5 = "f2d60cd2f2687de43089729fb06f436c"
APP_SHA256 = "55dcc78143724435a2e38b9e0d809960bd728668634bbcf7532ce137f882eb04"
FIELDS = {"R": "R_COLOR", "G": "G_COLOR", "B": "B_COLOR", "HUE": "HUE",
          "SAT": "SATURATION", "SHARP": "SHARPNESS", "CON": "CONTRAST"}
MSGID = "CAP_MENU_CUSTOM_MODE_1"


def json_bytes(data):
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def make_bundle(original, recipes_bytes, recipe_id, expected_md5=SOURCE_MD5):
    if hashlib.md5(original).hexdigest() != expected_md5:
        raise ValueError("Unsupported source catalog identity; refusing to patch")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,63}", recipe_id):
        raise ValueError("Invalid stable recipe ID")
    recipes = json.loads(recipes_bytes)["recipes"]
    if recipe_id not in recipes:
        raise ValueError("Unknown recipe ID: " + recipe_id)
    recipe = recipes[recipe_id]
    if set(recipe) != set(FIELDS.values()) | {"label"}:
        raise ValueError("This first candidate supports exactly the seven PW fields and label")
    label = recipe["label"]
    if not isinstance(label, str) or not label.strip() or any(ord(c) < 32 or ord(c) == 127 for c in label):
        raise ValueError("Display label must be nonempty text without control characters")
    pw = {}
    for short, field in FIELDS.items():
        number = recipe[field]
        maximum = 200 if short in ("R", "G", "B") else 20
        if type(number) is not int or not 0 <= number <= maximum:
            raise ValueError("Invalid raw PW field: " + field)
        pw[short] = number
    patched, changes = mo_patch._apply_replacements(original, {MSGID: label})
    issues = mo_patch._verify(original, patched, {MSGID: label})
    if issues:
        raise ValueError("MO verification failed: " + "; ".join(issues))
    preset = {"schema": "nxwa.preset/1", "id": recipe_id, "display_name": label,
              "pw": pw, "capability": {"pw": True, "lut": False, "preview": True,
                                         "still": "native", "still_verified": False,
                                         "requires_firmware": "A2"},
              "slot_map": {"slot": 1, "verified": False},
              "meta": {"scope": "offline_pw_only_native_entry_candidate"}}
    members = {"di-camera-app.mo": patched, "preset.json": json_bytes(preset)}
    manifest = {"schema": "nxwa.native-entry/1", "status": "offline_candidate_not_deployable",
                "camera": "NX500", "firmware": "1.12", "language": "zh_CN",
                "official_app_sha256": APP_SHA256, "recipe_id": recipe_id,
                "source": {"catalog_md5": hashlib.md5(original).hexdigest(),
                           "catalog_sha256": hashlib.sha256(original).hexdigest(),
                           "recipes_sha256": hashlib.sha256(recipes_bytes).hexdigest()},
                "entry": {"msgid": MSGID, "display_name": label, "custom_slot": 1,
                          "other_slots_unchanged": [2, 3], "changes": changes,
                          "text_width_verified": False, "long_label_warning": len(label.encode("utf-8")) > 24},
                "verification": {"catalog_other_entries_unchanged": True,
                                 "delivery_verified": False, "slot_content_verified": False,
                                 "native_input_verified": False, "preview_verified": False,
                                 "still_verified": False, "rollback_verified": False},
                "delivery": {"installer_included": False, "automatic_actions": [],
                             "blockers": ["P5 failed on device; fresh exec is unproven",
                                          "Loaded gettext catalog can survive path replacement",
                                          "Native CUSTOM1 reselect and content consistency require device evidence"]},
                "files_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in members.items()}}
    members["entry_manifest.json"] = json_bytes(manifest)
    members["README.md"] = ("# 原生 UI 单入口离线候选\n\n"
        + "仅把原厂 CUSTOM1 的显示名改为 **" + label + "**，附同一稳定 ID 的七维 PW 预设。\n\n"
        + "CUSTOM2/3 保持官方名称；不含 LUT、App 补丁、安装器或启动钩子。\n"
        + "本包没有写槽，也没有接通确认事件；名称和 preset 一致不代表机内槽内容一致。\n"
        + "当前不可直接部署：P5 已失败，App fresh-exec 与字典重载边界尚待补证。\n"
        + "勿把本包单独复制进旧 m2-locale 部署链；也不要 restart/stop-start App。\n\n"
        + "后续须逐项验收：加载边界、CUSTOM1 内容/重选、焦点不提交、确认/触摸/返回、\n"
        + "预览、JPEG、手工改参、正常关开机及撤销；各项状态均保留未验证。\n").encode("utf-8")
    members["SHA256SUMS"] = ("".join(hashlib.sha256(data).hexdigest() + "  " + name + "\n"
                                        for name, data in sorted(members.items()))).encode("ascii")
    return members


def write_bundle(output, members):
    output.mkdir(parents=True, exist_ok=False)
    for name, data in members.items():
        (output / name).write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-mo", type=Path, required=True)
    parser.add_argument("--recipes", type=Path, default=REPO / "scripts/filmlab/recipes.json")
    parser.add_argument("--recipe", default="portra400")
    parser.add_argument("--out", type=Path, required=True, help="new offline directory; must not exist")
    options = parser.parse_args()
    try:
        members = make_bundle(options.source_mo.read_bytes(), options.recipes.read_bytes(), options.recipe)
        write_bundle(options.out, members)
    except (OSError, ValueError, KeyError, mo_patch.MoError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print("Offline candidate only: " + str(options.out))
    for name, data in members.items():
        print("%s  %s" % (hashlib.sha256(data).hexdigest(), name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
