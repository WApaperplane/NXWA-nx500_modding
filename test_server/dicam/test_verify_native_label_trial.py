#!/usr/bin/env python3
"""Offline acceptance checks using copies of the saved one-trial evidence."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from verify_native_label_trial import verify

REPO = Path(__file__).resolve().parents[2]
EVIDENCE = REPO / "raw8/gates/dicam/ondevice_loading_2026-10-16"


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="nxwa-label-acceptance-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "evidence"
        self.root.mkdir()
        for name in ("resident_01", "resident_after", "label_trial_01", "live_01", "live_after"):
            shutil.copytree(EVIDENCE / name, self.root / name)
        shutil.copyfile(EVIDENCE / "human_observation.json", self.root / "human_observation.json")

    def change_human(self, update):
        path = self.root / "human_observation.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        update(data)
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_current_scoped_evidence_passes_without_production_claim(self):
        result = verify(self.root)
        self.assertTrue(result["machine_evidence_pass"])
        self.assertTrue(result["human_visual_observation_pass"])
        self.assertFalse(result["production_ready"])
        self.assertEqual(result["preset_confirm_apply"], "unverified")

    def test_visual_failure_does_not_become_success_from_bytes(self):
        self.change_human(lambda data: data["during"].update(native_custom1_showed_NXWA_Test_1=False))
        self.assertFalse(verify(self.root)["human_visual_observation_pass"])

    def test_authorization_and_authority_are_required(self):
        self.change_human(lambda data: data["before"].update(execution_explicitly_authorized=False))
        with self.assertRaises(ValueError):
            verify(self.root)

    def test_changed_capture_fails_checksum(self):
        with (self.root / "label_trial_01/capture.txt").open("ab") as stream:
            stream.write(b"altered")
        with self.assertRaises(ValueError):
            verify(self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
