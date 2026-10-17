"""Archive response-speed evidence and verify the actual installed identities."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
OUT = HERE / "out/responsiveness"
DEST = REPO / "raw8/gates/nxui/responsiveness"
DEST.mkdir(exist_ok=True)
for name in ("response.log", "old-portra400.vars", "new-portra400.vars", "old-trix400.vars", "new-trix400.vars", "service.log", "service-ui.log", "install.log", "installation-confirmation.json", "results.json", "manual.log", "manual-confirmation.json"):
    if (OUT / name).is_file(): shutil.copyfile(OUT / name, DEST / name)
for name in ("display-results.json", "host-service-interaction.log", "arm-service-interaction.log"):
    shutil.copyfile(HERE / "out" / name, DEST / name)
installed = (OUT / "install.log").read_text() if (OUT / "install.log").exists() else ""
confirmation = json.loads((OUT / "installation-confirmation.json").read_text()) if (OUT / "installation-confirmation.json").exists() else None
assert "INSTALLED enabled=yes" in installed or (confirmation and confirmation["installed"] and confirmation["enabled"])
identities = {}
for relative, remote in (("scripts/nxui/nxui.arm", "/opt/usr/nx-ks/nxui/nxui.arm"),
                        ("scripts/filmlab.sh", "/opt/usr/nx-ks/filmlab.sh"),
                        ("scripts/nxui.sh", "/opt/usr/nx-ks/nxui.sh"),
                        ("scripts/telnet_toggle.sh", "/opt/usr/nx-ks/telnet_toggle.sh")):
    digest = hashlib.md5((REPO / relative).read_bytes()).hexdigest()
    assert f"{digest}  {remote}" in installed or (confirmation and confirmation["md5"].get(remote) == digest), remote
    identities[remote] = digest
metadata = dict(date="2026-10-17", installed=True, enabled=True, camera="192.168.0.106", md5=identities,
    package_sha256=hashlib.sha256((REPO.parent / "release/NXUI-Nuklear-20261017.zip").read_bytes()).hexdigest(),
    device=json.loads((OUT / "results.json").read_text()),
    manual=json.loads((OUT / "manual-confirmation.json").read_text()) if (OUT / "manual-confirmation.json").exists() else "pending installed-shortcut confirmation")
(DEST / "acceptance.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+"\n")
print(json.dumps(metadata, ensure_ascii=False, indent=2))
