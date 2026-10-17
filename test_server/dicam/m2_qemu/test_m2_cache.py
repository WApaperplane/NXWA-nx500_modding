#!/usr/bin/env python3
"""Offline ARM/QEMU tests using camera libc, without chroot/rootfs writes.

Build products and catalog replacements live in TemporaryDirectory only.
Requires an already provisioned zh_CN.UTF-8 locale in the saved rootfs.
This tests gettext cache behavior, not camera App execution or native UI display.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools"))
from mo_patch import MOFile

OPTIONS = None
OLD = ["自定义 1", "自定义 2", "自定义 3", "图片向导"]
KEYS = ["CAP_MENU_CUSTOM_MODE_1", "CAP_MENU_CUSTOM_MODE_2",
        "CAP_MENU_CUSTOM_MODE_3", "CAP_FN_PW"]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory(prefix="nxwa-m2-cache-")
        cls.addClassCleanup(cls.workspace.cleanup)
        cls.base = Path(cls.workspace.name)
        cls.rf = OPTIONS.rootfs.resolve()
        cls.original = OPTIONS.original.resolve()
        cls.sample = OPTIONS.sample.resolve()
        cls.libc = cls.rf / "lib/libc-2.13.so"
        cls.crt = REPO / "test_server/filmlab/src/crt0_arm.S"
        cls.source = HERE / "m2_cache_probe.c"
        for path in (cls.original, cls.sample, cls.libc, cls.crt, cls.source):
            if not path.is_file():
                raise RuntimeError("Required offline input missing: %s" % path)
        sample_mo = MOFile(cls.sample)
        cls.expected_new = [sample_mo.msgstr(sample_mo.find(key)).decode("utf-8") for key in KEYS]
        if cls.expected_new[0] == OLD[0]:
            raise RuntimeError("Probe sample must actually rename CUSTOM1")
        cls.binary = cls.base / "m2_cache_probe.arm"
        command = ["arm-linux-gnueabi-gcc", "-O0", "-mfloat-abi=soft",
                   "-fno-stack-protector", "-fno-pic", "-no-pie", "-Wall", "-Wextra",
                   "-Werror", "-nostdlib", "-nostartfiles", "-Wl,-e,_start",
                   "-Wl,--dynamic-linker=/lib/ld-linux.so.3", "-Wl,--allow-shlib-undefined",
                   "-Wl,-rpath-link," + str(cls.rf / "usr/lib"),
                   "-Wl,-rpath-link," + str(cls.rf / "lib"), "-o", str(cls.binary),
                   str(cls.source), str(cls.crt), str(cls.libc), "-lgcc"]
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=60)
        versions = subprocess.run(["arm-linux-gnueabi-readelf", "--version-info", str(cls.binary)],
                                  check=True, capture_output=True, text=True, timeout=10).stdout
        cls.evidence = {"schema": "nxwa.gettext-cache/1", "scope": "offline_qemu_camera_libc",
                        "hardware_verified": False, "rootfs": str(cls.rf),
                        "sha256": {"original_mo": digest(cls.original), "sample_mo": digest(cls.sample),
                                   "camera_libc": digest(cls.libc), "probe_source": digest(cls.source),
                                   "probe_binary": digest(cls.binary)},
                        "build_command": command, "symbol_versions": versions,
                        "expected_translations": dict(zip(KEYS, cls.expected_new)), "runs": {}}
        cls.warm_dir = cls.fixture("warm")
        cls.warm = cls.run_probe("warm", cls.warm_dir)
        cls.fresh = cls.run_probe("fresh", cls.warm_dir)
        cls.cold = cls.run_probe("cold", cls.fixture("cold"))

    @classmethod
    def fixture(cls, name):
        root = cls.base / name
        for directory, catalog in (("a", cls.original), ("b", cls.sample)):
            destination = root / directory / "zh_CN/LC_MESSAGES/di-camera-app.mo"
            destination.parent.mkdir(parents=True)
            shutil.copyfile(catalog, destination)
        shutil.copyfile(cls.sample, root / "staged.mo")
        return root

    @classmethod
    def run_probe(cls, mode, fixture):
        command = ["qemu-arm-static", "-L", str(cls.rf), str(cls.binary), mode,
                   str(fixture / "a"), str(fixture / "b"), str(fixture / "staged.mo")]
        environment = dict(os.environ, LC_ALL="zh_CN.UTF-8", LANG="zh_CN.UTF-8",
                           LOCPATH=str(cls.rf / "usr/lib/locale"))
        environment.pop("LANGUAGE", None)
        result = subprocess.run(command, env=environment, capture_output=True,
                                text=True, encoding="utf-8", timeout=15)
        cls.evidence["runs"][mode] = {"command": command, "returncode": result.returncode,
                                       "stdout": result.stdout, "stderr": result.stderr}
        if result.returncode:
            raise RuntimeError("Probe failed: " + result.stdout + result.stderr)
        rows = {}
        for line in result.stdout.splitlines():
            if line.startswith("#"):
                continue
            phase, key, value = line.split("|", 2)
            rows.setdefault(phase, {})[key] = value
        return rows

    def phase(self, run, phase, expected):
        self.assertEqual(run[phase], dict(zip(KEYS, expected)))

    def test_cold_first_lookup_sees_replacement(self):
        self.phase(self.cold, "cold_first_lookup", self.expected_new)

    def test_warm_catalog_remains_old_after_path_replacement(self):
        self.phase(self.warm, "warm_before_replace", OLD)
        self.phase(self.warm, "warm_after_replace", OLD)

    def test_same_textdomain_and_directory_do_not_reload(self):
        self.phase(self.warm, "same_textdomain", OLD)
        self.phase(self.warm, "same_directory", OLD)

    def test_language_round_trip_does_not_reload_old_catalog(self):
        self.phase(self.warm, "locale_C", KEYS)
        self.phase(self.warm, "locale_round_trip", OLD)

    def test_different_binding_directory_loads_new_catalog(self):
        self.phase(self.warm, "different_directory", self.expected_new)

    def test_fresh_process_sees_replacement(self):
        self.phase(self.fresh, "fresh_process", self.expected_new)


def main():
    global OPTIONS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rootfs", type=Path, default=Path("/opt/nxks2/rootfs-112"))
    parser.add_argument("--original", type=Path, default=Path("/mnt/e/tmp/dicam_zh_CN.mo"))
    parser.add_argument("--sample", type=Path,
                        default=REPO / "fw/v1.12/dicam/locale/di-camera-app.zh_CN.m2sample.mo")
    parser.add_argument("--report", type=Path, required=True)
    OPTIONS = parser.parse_args()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CacheTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    evidence = getattr(CacheTests, "evidence", {})
    evidence.update(tests_run=result.testsRun, passed=result.wasSuccessful(),
                    failures=len(result.failures), errors=len(result.errors))
    OPTIONS.report.parent.mkdir(parents=True, exist_ok=True)
    OPTIONS.report.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, run in evidence.get("runs", {}).items():
        print("== %s ==\n%s" % (name, run["stdout"]))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
