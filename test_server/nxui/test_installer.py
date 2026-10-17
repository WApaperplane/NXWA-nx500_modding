"""Exercise the real camera installer against an isolated local layout."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent

class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="nxui-install-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = self.root / "payload"
        shutil.copytree(HERE / "out/package", self.payload)
        self.installed = self.root / "installed"; self.installed.mkdir()
        for file in (HERE / "out/device/original").glob("*.sh"):
            shutil.copyfile(file, self.installed / file.name)
        version = self.root / "version.info"; version.write_text("1.12\nNX500\n")
        busybox = self.installed / "busybox"
        busybox.write_text('#!/bin/sh\ncmd="$1"; shift\n[ "$cmd" != pidof ] || exit 1\nexec "$cmd" "$@"\n')
        busybox.chmod(0o755)
        self.runner = self.payload / "test-runner.sh"
        self.runner.write_text((HERE / "install_camera.sh").read_text().replace("/opt/usr/nx-ks", str(self.installed)).replace("/etc/version.info", str(version)))
        fake = self.root / "bin"; fake.mkdir()
        (fake / "sync").write_text("#!/bin/sh\nexit 0\n"); (fake / "sync").chmod(0o755)
        self.env = dict(os.environ, PATH=f"{fake}:{os.environ['PATH']}")

    def run_install(self):
        return subprocess.run(["sh", str(self.runner)], env=self.env, text=True, capture_output=True)

    def test_original_install_keeps_backup(self):
        before = (self.installed / "filmlab.sh").read_bytes()
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.installed / "filmlab.sh").read_bytes(), (self.payload / "scripts/filmlab.sh").read_bytes())
        self.assertEqual((self.installed / "nxui/backup-20261017/filmlab.sh").read_bytes(), before)

    def test_preceding_nxui_engine_is_a_valid_upgrade_source(self):
        shutil.copyfile(HERE / "out/slot-trial/filmlab-before.sh", self.installed / "filmlab.sh")
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_unknown_change_is_rejected_before_any_install(self):
        file = self.installed / "filmlab.sh"
        file.write_bytes(file.read_bytes() + b"\n# unrelated edit\n")
        before = (self.installed / "EV_AEL.sh").read_bytes()
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Changed since baseline", result.stdout)
        self.assertEqual((self.installed / "EV_AEL.sh").read_bytes(), before)
        self.assertFalse((self.installed / "nxui").exists())

    def test_current_field_engine_is_a_valid_upgrade_source(self):
        shutil.copyfile(HERE / "out/responsiveness/before/filmlab.sh", self.installed / "filmlab.sh")
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertTrue((self.installed / "nxui/backup-20261017/telnet_toggle.sh").exists())

    def test_unknown_service_switch_is_rejected_before_any_install(self):
        file = self.installed / "telnet_toggle.sh"; file.write_bytes(file.read_bytes()+b"\n# another edit\n")
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Changed since baseline: telnet_toggle.sh", result.stdout)
        self.assertFalse((self.installed / "nxui").exists())

if __name__ == "__main__": unittest.main(verbosity=2)
