"""Read the bounded slot-preservation experiment output; no remote commands."""
from pathlib import Path
import ftplib
import io
import sys
sys.stdout.reconfigure(encoding="utf-8")
out = Path(__file__).resolve().parent / "out/slot-trial"
out.mkdir(exist_ok=True)
with ftplib.FTP() as ftp:
    ftp.connect("192.168.0.106", 21, timeout=10); ftp.login("root", "")
    for name in ("live.log", "trial.log", "vars-before.txt", "vars-a2.txt", "vars-standard.txt", "matrix.log", "vars-custom2.txt", "vars-custom3.txt", "filmlab-before.sh"):
        buf = io.BytesIO()
        try: ftp.retrbinary("RETR stage/nxui-slot-20261017/" + name, buf.write)
        except ftplib.error_perm as error:
            print(name, error); continue
        (out / name).write_bytes(buf.getvalue())
        text = buf.getvalue().decode("utf-8", "replace").replace("\x00", "")
        print(name, len(buf.getvalue()), "bytes")
        if name.endswith(".log"):
            if name == "matrix.log":
                print("\n".join(line for line in text.splitlines() if any(s in line for s in ("CASE_TARGET", "UserData is PW_", "ENGINE_RC", "REJECT", "RESTORED_PREFMAN", "✓", "DONE"))))
            else: print("\n".join(line for line in text.splitlines() if any(s in line for s in ("FIELD", "READY", "BACKEND", "REJECT", "✓", "UserData is PW_", "UI_RC", "DONE"))))
        elif name.endswith(".txt"): print("\n".join(line for line in text.splitlines() if "VARIABLE_PW" in line))
