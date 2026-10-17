"""Archive measured evidence and identities of the installed/released payload."""
import hashlib
import json
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
dest = REPO / "raw8/gates/nxui/performance"
dest.mkdir(exist_ok=True)
for name in ("performance.log", "old-idle.log", "new-idle.log", "results.json", "startup.log", "live.log"):
    shutil.copyfile(HERE / "out/performance-device" / name, dest / name)
for name in ("display-results.json", "host-performance.json", "arm-performance.json"):
    shutil.copyfile(HERE / "out" / name, dest / name)
startup = (dest / "startup.log").read_text()
assert "DONE" in startup
identities = {}
for local, remote in (("scripts/nxui/nxui.arm", "/opt/usr/nx-ks/nxui/nxui.arm"),
                      ("scripts/filmlab.sh", "/opt/usr/nx-ks/filmlab.sh"),
                      ("scripts/nxui.sh", "/opt/usr/nx-ks/nxui.sh"),
                      ("scripts/EV_EV.sh", "/opt/usr/nx-ks/EV_EV.sh")):
    digest = hashlib.md5((REPO / local).read_bytes()).hexdigest()
    assert f"{digest}  {remote}" in startup, remote
    identities[remote] = digest
archive = REPO.parent / "release/NXUI-Nuklear-20261017.zip"
sha = hashlib.sha256(archive.read_bytes()).hexdigest()
metadata = dict(camera="192.168.0.106", installed=True, enabled=True, md5=identities,
    package_sha256=sha, first_frame_ms=list(map(int, re.findall(r"FIRST_FRAME process_ms=\d+ launch_ms=(\d+)", startup))),
    manual_shortcut_confirmation="PASS after user reboot: opening clearly faster and operation normal; severe stutter persisted before reboot",
    manual_user_quote="重启之前仍然极其卡顿，但在重启之后打开明显加快，操作正常。",
    reboot_performed_by="user",
    limitations="Acceptance is for the post-reboot state. Root cause of severe pre-reboot stutter and long-term stability remain unverified. Timing starts in nxui.sh, before first X frame, excluding key recognition.")
(dest / "acceptance.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+"\n")
field = REPO / "raw8/gates/nxui/current-field/acceptance.json"
data = json.loads(field.read_text())
data.update(manual_visual_confirmation="User confirmed filter effect passes; after reboot UI opening clearly faster and operation normal", permanent_deployment="installed and enabled", package_sha256=sha)
field.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n")
print(json.dumps(metadata, ensure_ascii=False, indent=2))
