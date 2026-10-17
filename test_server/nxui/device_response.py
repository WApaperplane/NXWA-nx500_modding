"""Stage/collect the response-speed trial; every write stays in its SD stage."""
import ftplib
import io
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out/responsiveness"
REMOTE = "stage/nxui-response-20261017"
OUT.mkdir(exist_ok=True)
sys.stdout.reconfigure(encoding="utf-8")
mode = sys.argv[1] if len(sys.argv) > 1 else "collect"
with ftplib.FTP() as ftp:
    ftp.connect("192.168.0.106", 21, timeout=10); ftp.login("root", "")
    if mode == "before":
        (OUT / "before").mkdir(exist_ok=True)
        for name in ("filmlab.sh", "telnet_toggle.sh"):
            with (OUT / "before" / name).open("wb") as stream:
                ftp.retrbinary(f"RETR {REMOTE}/before/{name}", stream.write)
        original = HERE / "out/device/original/telnet_toggle.sh"
        if not original.exists(): original.write_bytes((OUT / "before/telnet_toggle.sh").read_bytes())
        print("CAPTURED before scripts")
    elif mode in ("stage", "package"):
        if mode == "package":
            base = HERE / "out/package"
            files = [(p, "package/"+p.relative_to(base).as_posix()) for p in base.rglob("*") if p.is_file()]
        else:
            files = [(HERE / "out/nxui.arm", "nxui.arm"), (HERE / "out/test_input.arm", "test_input.arm"),
                     (HERE.parent.parent / "scripts/filmlab.sh", "filmlab.sh"),
                     (HERE.parent.parent / "scripts/telnet_toggle.sh", "telnet_toggle.sh"),
                     (HERE / "response_camera.sh", "response_camera.sh"), (HERE / "service_camera.sh", "service_camera.sh")]
        for local, name in files:
            path = REMOTE+"/"+name
            parent = path.rsplit("/", 1)[0]
            parts = parent.split("/")
            for i in range(1, len(parts)+1):
                try: ftp.mkd("/".join(parts[:i]))
                except ftplib.error_perm: pass
            with local.open("rb") as stream: ftp.storbinary("STOR "+path, stream)
            assert ftp.size(path) == local.stat().st_size
        print("STAGED", mode, len(files), "files")
    else:
        for name in ("response.log", "old-portra400.vars", "new-portra400.vars", "old-trix400.vars", "new-trix400.vars", "service.log", "service-ui.log", "install.log", "manual.log"):
            buf = io.BytesIO()
            try: ftp.retrbinary(f"RETR {REMOTE}/{name}", buf.write)
            except ftplib.error_perm: continue
            (OUT / name).write_bytes(buf.getvalue())
            text = buf.getvalue().decode("utf-8", "replace").replace("\x00", "")
            if name.endswith(".vars"): print(name, len(buf.getvalue()), "bytes")
            elif name == "response.log":
                print(name, "\n".join(line for line in text.splitlines() if line.startswith(("BEFORE", "CASE", "END", "RESTORED", "UserData is PW_", "DONE"))))
            else: print(name, text[-14000:])
