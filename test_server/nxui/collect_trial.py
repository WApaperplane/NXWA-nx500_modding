"""Fetch only the known trial logs/backups from the camera SD over FTP."""
from pathlib import Path
import argparse
import ftplib
import io
import sys
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
parser = argparse.ArgumentParser()
parser.add_argument("--host", default="192.168.0.106")
parser.add_argument("--verbose", action="store_true")
args = parser.parse_args()
out = Path(__file__).resolve().parent / "out" / "device"
out.mkdir(exist_ok=True)
stage = "stage/nxui-poc-92d56b55"
with ftplib.FTP() as ftp:
    ftp.connect(args.host, 21, timeout=10); ftp.login("root", "")
    for name in ("snapshot.done", "original.md5", "slot9-before.txt", "pw-before.txt", "isp-before.txt", "demo.log", "live.log", "install.log", "formal.log", "original/filmlab.sh", "original/EV_AEL.sh", "original/loadgui.sh", "original/menu.sh"):
        buf = io.BytesIO()
        try: ftp.retrbinary("RETR " + stage + "/" + name, buf.write)
        except ftplib.error_perm as error:
            print(f"{name}: {error}"); continue
        target = out / name; target.parent.mkdir(exist_ok=True)
        target.write_bytes(buf.getvalue()); print(f"{name}: {len(buf.getvalue())} bytes")
        if name.endswith(".done") or name.endswith(".log") or name == "original.md5":
            text = buf.getvalue().decode("utf-8", "replace")
            print(text if args.verbose else "\n".join(text.splitlines()[-5:]))
