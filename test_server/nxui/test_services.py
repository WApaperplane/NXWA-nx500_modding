"""Run the real service switch against isolated daemons and listener fixtures."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
HEADER = "  sl local_address rem_address st\n"
TELNET = HEADER + "0: 00000000:0017 00000000:0000 0A\n"
FTP = HEADER + "0: 00000000:0015 00000000:0000 0A\n"

class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="nxui-service-switch-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("tcp", "tcp6"): (self.root / name).write_text(HEADER)
        self.env = dict(os.environ, TEST_ROOT=str(self.root))
        def script(name, source):
            path = self.root / name; path.write_text("#!/bin/sh\n"+source); path.chmod(0o755)
        script("telnetd", 'echo TELNET >> "$TEST_ROOT/calls"\n[ "${FAIL_TELNET:-0}" != 1 ] || exit 7\nprintf "  sl local_address rem_address st\\n0: 00000000:0017 00000000:0000 0A\\n" > "$TEST_ROOT/tcp"\n')
        script("popup_timeout", 'echo POPUP >> "$TEST_ROOT/calls"\n')
        script("busybox", '''cmd="$1"; shift
case "$cmd" in
nice) shift 2; exec "$@" ;;
tcpsvd) echo FTP >> "$TEST_ROOT/calls"; printf '  sl local_address rem_address st\n0: 00000000:0015 00000000:0000 0A\n' > "$TEST_ROOT/tcp6" ;;
killall) printf '  sl local_address rem_address st\n' > "$TEST_ROOT/tcp" ;;
ps) printf 'PID COMMAND\n4242 %s/busybox tcpsvd -u root -vE 0.0.0.0 21 %s/busybox ftpd\n4243 %s/busybox tcpsvd 0.0.0.0 22 handler\n' "$TEST_ROOT" "$TEST_ROOT" "$TEST_ROOT" ;;
kill) [ "$2" = 4242 ] || exit 9; echo "KILL $2" >> "$TEST_ROOT/calls"; printf '  sl local_address rem_address st\n' > "$TEST_ROOT/tcp6" ;;
sleep) exit 0 ;;
*) exec "$cmd" "$@" ;;
esac
''')
        source = (REPO / "scripts/telnet_toggle.sh").read_text().replace("/opt/usr/nx-ks", str(self.root)).replace("/proc/net/tcp", str(self.root / "tcp"))
        self.runner = self.root / "switch.sh"; self.runner.write_text(source)

    def run_switch(self, action):
        return subprocess.run(["sh", str(self.runner), "--ui", action], env=self.env, text=True, capture_output=True, timeout=5)

    def test_enable_disable_without_popup_and_without_restart(self):
        result = self.run_switch("enable")
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn("telnet=1 ftp=1", result.stdout)
        self.assertNotIn("POPUP", (self.root / "calls").read_text())
        before = (self.root / "calls").read_text()
        self.assertEqual(self.run_switch("enable").returncode, 0)
        self.assertEqual((self.root / "calls").read_text(), before)
        result = self.run_switch("disable")
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn("telnet=0 ftp=0", result.stdout)
        self.assertIn("KILL 4242", (self.root / "calls").read_text())
        self.assertNotIn("KILL 4243", (self.root / "calls").read_text())

    def test_partial_state_enables_only_missing_service(self):
        (self.root / "tcp").write_text(TELNET)
        result = self.run_switch("toggle")
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertEqual((self.root / "calls").read_text().splitlines(), ["FTP"])

    def test_start_failure_reports_actual_partial_state(self):
        self.env["FAIL_TELNET"] = "1"
        result = self.run_switch("enable")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("telnet=0 ftp=1", result.stdout)

    def test_unreadable_state_is_not_reported_as_closed(self):
        (self.root / "tcp").unlink(); (self.root / "tcp6").unlink()
        result = self.run_switch("disable")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Cannot read", result.stdout)

if __name__ == "__main__": unittest.main(verbosity=2)
