"""Bounded X11 event storms: repaint budget, idle wakeups and fast-tap delivery."""
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"

def run_performance(prefix, env, label):
    records = []
    for event, count, interval in (("motion", 500, 2), ("expose", 500, 2), ("key", 500, 2), ("idle", 0, 0)):
        with tempfile.TemporaryDirectory(prefix="nxui-perf-") as temp:
            log = Path(temp) / "run.log"
            with log.open("w") as stream:
                p = subprocess.Popen(prefix + ["--dry-run", "--recipes", str(OUT / "recipes.txt"), "--lifetime-ms", "2400"], env=env, stdout=stream, stderr=subprocess.STDOUT)
                try:
                    for _ in range(100):
                        if "READY" in log.read_text(): break
                        assert p.poll() is None, log.read_text()
                        time.sleep(.025)
                    else: raise AssertionError("UI not ready")
                    if event != "idle":
                        args = ["key", "Right", str(count), str(interval)] if event == "key" else [event, str(count), str(interval)]
                        subprocess.run([str(OUT / "test_input")] + args, env=env, check=True, timeout=10)
                    assert p.wait(timeout=10) == 0, log.read_text()
                finally:
                    if p.poll() is None: p.kill(); p.wait()
            text = log.read_text()
            (OUT / f"{label}-perf-{event}.log").write_text(text)
            match = re.search(r"EXIT renders=(\d+) elapsed_ms=(\d+) wakeups=(\d+) blits=(\d+) max_draw_ms=(\d+)", text)
            assert match, text
            rendered, elapsed, wakeups, blits, draw_ms = map(int, match.groups())
            assert elapsed < 4000, text  # a burst must not postpone the lifetime deadline
            assert rendered + blits <= elapsed // 100 + 2, text
            if event in ("motion", "idle", "expose"): assert rendered == 1, text
            if event == "idle": assert wakeups <= 4, text
            records.append(dict(event=event, renders=rendered, elapsed_ms=elapsed, wakeups=wakeups, blits=blits, max_draw_ms=draw_ms))
    (OUT / f"{label}-performance.json").write_text(json.dumps(records, indent=2))
    print(f"PASS {label}: motion/expose do not rerasterize, <=10 Hz under 500-key burst, blocking idle")
    return records
