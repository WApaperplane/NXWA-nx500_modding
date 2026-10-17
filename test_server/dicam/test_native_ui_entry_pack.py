#!/usr/bin/env python3
"""Self-contained native entry pack regression; no hardware or network."""
import gettext
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
import native_ui_entry_pack as pack
from mo_patch_smoke_test import build_mo


class EntryPackTests(unittest.TestCase):
    def setUp(self):
        self.source = build_mo([(b"", b"Content-Type: text/plain; charset=UTF-8\n"),
                                (b"CAP_FN_PW", "图片向导".encode()),
                                *[(f"CAP_MENU_CUSTOM_MODE_{i}".encode(), f"自定义 {i}".encode())
                                  for i in range(1, 4)]])
        self.recipes = {"recipes": {"portra400": {"label": "Portra 400", "R_COLOR": 106,
                        "G_COLOR": 100, "B_COLOR": 93, "HUE": 11, "SATURATION": 9,
                        "SHARPNESS": 9, "CONTRAST": 8}}}
        self.expected = hashlib.md5(self.source).hexdigest()

    def build(self, recipe_id="portra400"):
        return pack.make_bundle(self.source, json.dumps(self.recipes).encode(), recipe_id, self.expected)

    def test_only_custom1_is_renamed(self):
        bundle = self.build()
        translation = gettext.GNUTranslations(io.BytesIO(bundle["di-camera-app.mo"]))
        self.assertEqual(translation.gettext("CAP_MENU_CUSTOM_MODE_1"), "Portra 400")
        for i in (2, 3):
            self.assertEqual(translation.gettext(f"CAP_MENU_CUSTOM_MODE_{i}"), f"自定义 {i}")
        self.assertEqual(translation.gettext("CAP_FN_PW"), "图片向导")

    def test_label_and_values_share_one_stable_id_without_claiming_success(self):
        bundle = self.build()
        preset = json.loads(bundle["preset.json"])
        manifest = json.loads(bundle["entry_manifest.json"])
        self.assertEqual(preset["id"], manifest["recipe_id"])
        self.assertEqual(preset["display_name"], manifest["entry"]["display_name"])
        self.assertEqual(preset["pw"], {"R": 106, "G": 100, "B": 93, "HUE": 11, "SAT": 9, "SHARP": 9, "CON": 8})
        self.assertFalse(preset["slot_map"]["verified"])
        self.assertFalse(preset["capability"]["lut"])
        self.assertFalse(preset["capability"]["still_verified"])
        self.assertEqual(manifest["delivery"]["automatic_actions"], [])
        self.assertFalse(manifest["delivery"]["installer_included"])
        self.assertTrue(all(not result for name, result in manifest["verification"].items()
                            if name != "catalog_other_entries_unchanged"))

    def test_checksums_cover_every_other_member(self):
        bundle = self.build()
        seen = set()
        for line in bundle["SHA256SUMS"].decode().splitlines():
            digest, name = line.split("  ")
            self.assertEqual(digest, hashlib.sha256(bundle[name]).hexdigest())
            seen.add(name)
        self.assertEqual(seen, bundle.keys() - {"SHA256SUMS"})

    def test_reproducible_output(self):
        self.assertEqual(self.build(), self.build())

    def test_unknown_catalog_and_unknown_id_are_rejected(self):
        with self.assertRaises(ValueError):
            pack.make_bundle(self.source, json.dumps(self.recipes).encode(), "portra400")
        with self.assertRaises(ValueError):
            self.build("unknown")

    def test_invalid_stable_id_and_label_are_rejected(self):
        for recipe_id in ("../x", "demo; touch x", "UPPER"):
            with self.subTest(recipe_id=recipe_id), self.assertRaises(ValueError):
                self.build(recipe_id)
        for label in ("", "bad\nname", "bad\x00name"):
            self.recipes["recipes"]["portra400"]["label"] = label
            with self.subTest(label=label), self.assertRaises(ValueError):
                self.build()

    def test_raw_pw_range_and_extra_unmapped_fields_are_rejected(self):
        recipe = self.recipes["recipes"]["portra400"]
        for value in (-1, 201, True, "106"):
            recipe["R_COLOR"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.build()
        recipe["R_COLOR"] = 106
        recipe["WB_K"] = 5500
        with self.assertRaises(ValueError):
            self.build()

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory(prefix="nxwa-entry-pack-") as temporary:
            output = Path(temporary) / "candidate"
            pack.write_bundle(output, self.build())
            before = (output / "di-camera-app.mo").read_bytes()
            with self.assertRaises(FileExistsError):
                pack.write_bundle(output, self.build())
            self.assertEqual(before, (output / "di-camera-app.mo").read_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=2)
