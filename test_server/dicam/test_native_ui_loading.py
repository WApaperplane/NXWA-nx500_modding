#!/usr/bin/env python3
"""Fixture-only collector/parser regression. No camera connection or device IO."""
import hashlib
import importlib.util
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SPEC = importlib.util.spec_from_file_location("native_ui_loading", REPO / "tools/native_ui_loading.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
OFFICIAL = "ae44293e969101d1cf0a93cbe9b99f75"
PATCH = "48d94bd63e4479fc931ae1a1fee4e94b"


def stat(pid=247, ticks=1224, name="di-camera-app"):
    return "%s (%s) %s\n" % (pid, name, " ".join(["S"] + ["0"] * 18 + [str(ticks)]))


def capture(**overrides):
    sections = {"boot_id": "boot-a", "candidates": "247", "selected_pid": "247",
                "stat_before": stat(), "stat_after": stat(),
                "exe_link_before": "/usr/apps/com.samsung.di-camera-app/bin/di-camera-app",
                "exe_link_after": "/usr/apps/com.samsung.di-camera-app/bin/di-camera-app",
                "target_md5": PATCH, "exe_md5": OFFICIAL,
                "locale_target_md5": PATCH, "staged_locale_md5": PATCH,
                "app_unit": "ExecStartPre=-/opt/usr/nx-ks/dicam/t2_premount.sh"}
    sections.update(overrides)
    return "NXWA_NATIVE_LOADING_V1\n" + "".join("@@ %s\n%s\n" % pair for pair in sections.items()) + "@@ end\n"


class ParserTests(unittest.TestCase):
    def test_different_backing_files_are_not_reported_as_activated(self):
        result = MODULE.parse_probe(capture())
        self.assertTrue(result["process_stable"])
        self.assertFalse(result["exe_file_matches_target"])
        self.assertEqual(result["process_exe_file"]["variant"], "official_v1.12")
        self.assertEqual(result["target_file"]["variant"], "c2_v2")
        self.assertEqual(result["fresh_exec"], "unknown")

    def test_matching_files_unit_and_locale_do_not_prove_native_ui(self):
        result = MODULE.parse_probe(capture(exe_md5=PATCH))
        self.assertTrue(result["exe_file_matches_target"])
        self.assertTrue(result["unit_contains_premount"])
        self.assertTrue(result["locale"]["path_matches_staged"])
        self.assertFalse(result["running_code_verified"])
        self.assertFalse(result["native_ui_verified"])
        self.assertFalse(result["locale"]["visible_labels_verified"])

    def test_pid_start_ticks_cannot_prove_fresh_exec(self):
        for boot in ("boot-a", "boot-b"):
            result = MODULE.parse_probe(capture(boot_id=boot))
            self.assertEqual(result["fresh_exec"], "unknown")

    def test_process_change_during_capture_is_unknown(self):
        for overrides in ({"stat_after": stat(ticks=9999)}, {"exe_link_after": ""},
                          {"stat_after": stat(pid=248)}, {"stat_before": "truncated"}):
            with self.subTest(overrides=overrides):
                result = MODULE.parse_probe(capture(**overrides))
                self.assertFalse(result["process_stable"])
                self.assertIsNone(result["exe_file_matches_target"])
                self.assertIsNone(result["process_exe_file"]["md5"])

    def test_comm_with_spaces_and_parentheses(self):
        self.assertEqual(MODULE.parse_stat(stat(name="a b) c")), {"pid": 247, "start_ticks": 1224})

    def test_multiple_processes_are_unknown(self):
        result = MODULE.parse_probe(capture(candidates="247\n248"))
        self.assertFalse(result["process_stable"])

    def test_missing_metadata_stays_unknown(self):
        result = MODULE.parse_probe("NXWA_NATIVE_LOADING_V1\n@@ boot_id\n<unavailable>\n@@ end\n")
        self.assertIsNone(result["boot_id"])
        self.assertIsNone(result["unit_contains_premount"])
        self.assertIsNone(result["locale"]["path_matches_staged"])

    def test_incomplete_or_duplicate_capture_is_rejected(self):
        for raw in ("", "NXWA_NATIVE_LOADING_V1\n@@ maps\nx\n",
                    "NXWA_NATIVE_LOADING_V1\n@@ maps\n@@ maps\n@@ end\n"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                MODULE.parse_probe(raw)


class CollectorTests(unittest.TestCase):
    def test_collector_reads_only_fixture_and_ignores_cmdline_false_positive(self):
        with tempfile.TemporaryDirectory(prefix="nxwa-loading-fixture-") as directory:
            root = Path(directory)
            binary = root / "usr/apps/com.samsung.di-camera-app/bin/di-camera-app"
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b"fixture App, not executable ARM code")
            proc = root / "proc/247"
            proc.mkdir(parents=True)
            (proc / "exe").symlink_to(binary)
            (proc / "stat").write_text(stat())
            (proc / "maps").write_text("00010000-00020000 r-xp 0 b3:0a 43 /usr/apps/com.samsung.di-camera-app/bin/di-camera-app\n")
            # The old cmdline substring search would choose this shell instead.
            shell = root / "proc/2"
            shell.mkdir()
            (shell / "cmdline").write_bytes(b"sh\0probe di-camera-app\0")
            (shell / "exe").symlink_to("/bin/sh")
            before = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file() and not p.is_symlink()}
            run = subprocess.run(["sh", str(HERE / "probe_native_loading.sh")],
                                 env=dict(os.environ, NXWA_SYS_ROOT=str(root)),
                                 check=True, capture_output=True, text=True, timeout=10)
            result = MODULE.parse_probe(run.stdout)
            self.assertEqual(result["pid_candidates"], [247])
            self.assertTrue(result["process_stable"])
            self.assertEqual(result["target_file"]["md5"], hashlib.md5(binary.read_bytes()).hexdigest())
            self.assertTrue(result["exe_file_matches_target"])
            after = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file() and not p.is_symlink()}
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
