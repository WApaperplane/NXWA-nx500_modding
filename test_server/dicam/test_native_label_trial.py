#!/usr/bin/env python3
"""Camera dd 6.9 under QEMU + mocked identity + sparse temporary data file.

Tests positioning, bounded writes and rollback, NOT camera /proc write support.
No hardware connection. No rootfs writes. All mock files are disposable fixtures.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
from native_label_trial import build_script, OLD_HEX, NEW_HEX

ROOTFS = Path("/opt/nxks2/rootfs-112")
ADDRESS = 1890060423
CONTEXT = {"pid": 247, "ticks": 1224, "boot": "dbb7e6ce-8b5e-4d2a-ba3e-bf5ea16d54bc",
           "base": "70a67000-70a92000:07:00:651", "address": ADDRESS}


class TrialTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="nxwa-label-trial-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        proc = self.root / "proc/247"
        proc.mkdir(parents=True)
        self.memory = proc / "mem"
        with self.memory.open("wb") as stream:
            stream.seek(ADDRESS - 16)
            stream.write(b"A" * 16 + bytes.fromhex(OLD_HEX) + b"B" * 16)
        boot = self.root / "proc/sys/kernel/random/boot_id"
        boot.parent.mkdir(parents=True)
        boot.write_text(CONTEXT["boot"] + "\n")
        (proc / "stat").write_text("247 (di-camera-app) " + " ".join(["S"] + ["0"] * 18 + ["1224"]) + "\n")
        (proc / "exe").symlink_to("/unused/di-camera-app")
        (proc / "maps").write_text("70a67000-70a92000 r--p 00000000 07:00 651 /usr/share/locale/zh_CN/LC_MESSAGES/di-camera-app.mo\n")
        self.log = self.root / "dd.log"
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                        NXWA_TEST_DD_LOG=str(self.log), NXWA_TEST_FAIL_MARK=str(self.root / "failed"))
        self.tool("md5sum", """case "$1" in
*/exe) printf 'ae44293e969101d1cf0a93cbe9b99f75  %s\\n' "$1" ;;
*) printf 'f2d60cd2f2687de43089729fb06f436c  %s\\n' "$1" ;;
esac
""")
        self.tool("dd", """printf '%s\\n' "$*" >> "$NXWA_TEST_DD_LOG"
case "$*" in
*'ibs=1 obs=11 count=11'*)
 if [ "${NXWA_TEST_FAIL_WRITE:-0}" = 1 ] && [ ! -e "$NXWA_TEST_FAIL_MARK" ]; then
   touch "$NXWA_TEST_FAIL_MARK"; exit 7
 fi ;;
esac
exec env LC_ALL=C LANG=C qemu-arm-static -L /opt/nxks2/rootfs-112 /opt/nxks2/rootfs-112/bin/dd "$@"
""")

    def tool(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(0o755)

    def run_trial(self, mode="trial"):
        return subprocess.run(["sh"], input=build_script(CONTEXT, mode=mode, window=0, fixture_root=str(self.root)),
                              env=self.env, capture_output=True, text=True, timeout=15)

    def neighborhood(self):
        with self.memory.open("rb") as stream:
            stream.seek(ADDRESS - 16)
            return stream.read(43)

    def writes(self):
        lines = self.log.read_text().splitlines() if self.log.exists() else []
        return [line for line in lines if "ibs=1 obs=11 count=11" in line]

    def test_exact_eleven_byte_blocks_and_verified_restore(self):
        before = self.neighborhood()
        size = self.memory.stat().st_size
        result = self.run_trial()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("phase=label_patched", result.stdout)
        self.assertIn("rollback=verified_original_11_bytes", result.stdout)
        self.assertEqual(before, self.neighborhood())
        self.assertEqual(self.memory.stat().st_size, size)
        self.assertEqual(len(self.writes()), 2)
        self.assertTrue(all("obs=11 count=11 conv=notrunc" in line for line in self.writes()))

    def test_wrong_boot_identity_never_writes(self):
        (self.root / "proc/sys/kernel/random/boot_id").write_text("different\n")
        result = self.run_trial()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.writes(), [])

    def test_changed_original_bytes_never_writes(self):
        with self.memory.open("r+b") as stream:
            stream.seek(ADDRESS)
            stream.write(b"x" * 11)
        result = self.run_trial()
        self.assertEqual(result.returncode, 11)
        self.assertEqual(self.writes(), [])

    def test_write_failure_runs_rollback(self):
        before = self.neighborhood()
        size = self.memory.stat().st_size
        self.env["NXWA_TEST_FAIL_WRITE"] = "1"
        result = self.run_trial()
        self.assertEqual(result.returncode, 20)
        self.assertIn("rollback=verified_original_11_bytes", result.stdout)
        self.assertEqual(before, self.neighborhood())
        self.assertEqual(self.memory.stat().st_size, size)

    def test_restore_only_does_not_reapply_trial(self):
        with self.memory.open("r+b") as stream:
            stream.seek(ADDRESS)
            stream.write(bytes.fromhex(NEW_HEX))
        result = self.run_trial("restore")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("phase=label_patched", result.stdout)
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(self.neighborhood()[16:27], bytes.fromhex(OLD_HEX))


if __name__ == "__main__":
    unittest.main(verbosity=2)
