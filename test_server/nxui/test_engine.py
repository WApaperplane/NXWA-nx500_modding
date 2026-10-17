"""Exercise real filmlab.sh against local prefman/st/pwsend doubles."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="nxui-engine-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.bin = self.base / "bin"; self.bin.mkdir()
        self.lab = self.base / "lab"; self.lab.mkdir()
        self.log = self.base / "calls"
        self.current = self.base / "current-pw"
        self.current.write_text("0x140009\n")
        self.env = os.environ.copy()
        self.env.update(PATH=f"{self.bin}:{os.environ['PATH']}", CALLS=str(self.log), CURRENT_PW_FILE=str(self.current))
        self.stub("busybox", 'cmd="$1"; shift; exec "$cmd" "$@"')
        self.stub("prefman", 'echo "prefman $*" >> "$CALLS"; if [ "$1" = get ]; then p=$((($3-41964)/52)); v=10; [ "$p" -ge 3 ] || v=100; echo "value = $v"; fi; exit 0')
        self.stub("st", '''echo "st $*" >> "$CALLS"
case "$3" in
  getusr) echo "UserData is CURRENT ($(cat "$CURRENT_PW_FILE"))" ;;
  setusr) [ "${RESTORE_FAIL:-0}" != 1 ] || exit 8; echo "$5" > "$CURRENT_PW_FILE" ;;
esac
exit 0''')
        self.stub("pwsend.arm", 'echo "pwsend $*" >> "$CALLS"; echo 0x140009 > "$CURRENT_PW_FILE"; exit 0')
        self.stub("sync", 'echo "sync" >> "$CALLS"')
        (self.lab / "recipes.json").write_bytes((REPO / "scripts/filmlab/recipes.json").read_bytes())
        self.engine = self.bin / "filmlab.sh"
        self.engine.write_text((REPO / "scripts/filmlab.sh").read_text().replace("/opt/usr/nx-ks", str(self.bin)).replace("/mnt/mmc/filmlab", str(self.lab)))

    def stub(self, name, source):
        p = self.bin / name; p.write_text("#!/bin/sh\n" + source + "\n"); p.chmod(0o755)

    def run_engine(self, cmd, conf):
        (self.lab / "filmlab.conf").write_text("FILMLAB_PW=1\n" + conf)
        r = subprocess.run(["sh", str(self.engine), cmd, "portra400"], env=self.env, capture_output=True, text=True)
        return r, self.log.read_text() if self.log.exists() else ""

    def test_preview_never_saves_even_if_conf_requests_save(self):
        r, calls = self.run_engine("preview", "FILMLAB_SAVE=1\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("prefman save", calls)
        self.assertIn("pwsend seq 0x134 106", calls)

    def test_commit_saves_even_if_conf_disables_save(self):
        r, calls = self.run_engine("commit", "FILMLAB_SAVE=0\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(calls.count("prefman save 0"), 1)

    def test_missing_backend_rejects_before_slot_writes(self):
        (self.bin / "pwsend.arm").unlink()
        r, calls = self.run_engine("preview", "")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("prefman set", calls)

    def test_backend_failure_is_not_reported_as_success(self):
        self.stub("pwsend.arm", "exit 9")
        r, calls = self.run_engine("preview", "")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("REJECT", r.stdout)
        self.assertNotIn("prefman save", calls)

    def test_commit_does_not_save_if_backend_fails(self):
        self.stub("pwsend.arm", "exit 9")
        r, calls = self.run_engine("commit", "")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("prefman save", calls)

    def test_slot_write_failure_stops_before_backend(self):
        directory = self.lab / "slot-backups"; directory.mkdir()
        (directory / "slot-9.txt").write_text("9|100|100|100|10|10|10|10\n")
        self.stub("prefman", 'echo "prefman $*" >> "$CALLS"; exit 4')
        r, calls = self.run_engine("preview", "")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("pwsend seq", calls)

    def test_every_visible_field_is_preserved_and_custom1_is_untouched(self):
        mappings = [(f"0x14000{i:x}", i) for i in range(11)] + [("0x14000c", 11)]
        for enum, slot in mappings:
            with self.subTest(enum=enum, slot=slot):
                self.current.write_text(enum + "\n")
                self.log.write_text("")
                r, calls = self.run_engine("preview", "")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(self.current.read_text().strip(), enum)
                written = [line for line in calls.splitlines() if line.startswith("prefman set")]
                self.assertEqual(len(written), 7)
                actual = {int(line.split()[3], 16) for line in written}
                expected = {41964 + p*52 + slot*4 for p in range(7)}
                self.assertEqual(actual, expected)
                backup = self.lab / f"slot-backups/slot-{slot}.txt"
                self.assertEqual(backup.read_text().strip(), f"{slot}|100|100|100|10|10|10|10")
                if enum != "0x140009":
                    self.assertNotIn("st cap capdtm setusr 20 0x140009", calls)
                    self.assertLess(calls.index("pwsend seq"), calls.index(f"st cap capdtm setusr 20 {enum}"))

    def test_unknown_or_unreadable_field_rejected_before_writes(self):
        for enum in ("", "0x14000b", "0x14000d", "unreadable"):
            with self.subTest(enum=enum):
                self.current.write_text(enum + "\n"); self.log.write_text("")
                r, calls = self.run_engine("preview", "")
                self.assertNotEqual(r.returncode, 0)
                self.assertNotIn("prefman set", calls)
                self.assertNotIn("pwsend seq", calls)

    def test_restore_failure_does_not_save(self):
        self.current.write_text("0x14000c\n")
        self.env["RESTORE_FAIL"] = "1"
        r, calls = self.run_engine("commit", "")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("VERIFY-FAIL", r.stdout)
        self.assertNotIn("prefman save", calls)

    def test_failed_send_still_restores_original_field(self):
        self.current.write_text("0x14000a\n")
        self.stub("pwsend.arm", 'echo 0x140009 > "$CURRENT_PW_FILE"; exit 9')
        r, calls = self.run_engine("preview", "")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.current.read_text().strip(), "0x14000a")
        self.assertNotIn("prefman save", calls)

    def test_backup_failure_prevents_any_write(self):
        self.stub("prefman", 'echo "prefman $*" >> "$CALLS"; exit 4')
        r, calls = self.run_engine("preview", "")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("prefman set", calls)

    def test_recipe_out_of_range_is_rejected_before_writes(self):
        data = (self.lab / "recipes.json").read_text().replace('"HUE": 11', '"HUE": 21')
        (self.lab / "recipes.json").write_text(data)
        r, calls = self.run_engine("preview", "")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("prefman set", calls)

    def test_commit_standard_saves_only_after_restoring_standard(self):
        self.current.write_text("0x140000\n")
        r, calls = self.run_engine("commit", "FILMLAB_SAVE=0\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.current.read_text().strip(), "0x140000")
        self.assertLess(calls.index("st cap capdtm setusr 20 0x140000"), calls.index("prefman save 0"))

    def test_ready_readback_does_not_wait_one_second(self):
        self.current.write_text("0x140000\n")
        self.stub("busybox", 'cmd="$1"; shift; [ "$cmd" != sleep ] || { echo WAITED >> "$CALLS"; exit 9; }; exec "$cmd" "$@"')
        r, calls = self.run_engine("preview", "")
        self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
        self.assertNotIn("WAITED", calls)

    def test_delayed_readback_is_polled_until_confirmed(self):
        self.current.write_text("0x140000\n")
        self.stub("st", '''echo "st $*" >> "$CALLS"
case "$3" in
  setusr) echo "$5" > "$CURRENT_PW_FILE.pending" ;;
  getusr)
    if [ -f "$CURRENT_PW_FILE.pending" ]; then
      if [ -f "$CURRENT_PW_FILE.waited" ]; then mv "$CURRENT_PW_FILE.pending" "$CURRENT_PW_FILE";
      else touch "$CURRENT_PW_FILE.waited"; fi
    fi
    echo "UserData is CURRENT ($(cat "$CURRENT_PW_FILE"))"
    ;;
esac
''')
        r, calls = self.run_engine("preview", "")
        self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
        self.assertEqual(self.current.read_text().strip(), "0x140000")
        self.assertGreaterEqual(calls.count("getusr 20"), 4)

if __name__ == "__main__": unittest.main(verbosity=2)
