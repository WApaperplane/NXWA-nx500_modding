"""Stage or collect bounded, read-only UI performance trials on the NX500."""
import ftplib
import io
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out/performance-device"
REMOTE = "stage/nxui-perf-20261017"
OUT.mkdir(exist_ok=True)
sys.stdout.reconfigure(encoding="utf-8")
with ftplib.FTP() as ftp:
    ftp.connect("192.168.0.106", 21, timeout=10); ftp.login("root", "")
    if len(sys.argv) > 1 and sys.argv[1] == "baseline":
        target = HERE / "out/device/original/EV_EV.sh"
        with target.open("wb") as stream:
            ftp.retrbinary(f"RETR {REMOTE}/EV_EV-before.sh", stream.write)
        print("CAPTURED", target, target.stat().st_size)
    elif len(sys.argv) > 1 and sys.argv[1] == "package":
        base = HERE / "out/package"
        dest = REMOTE + "/package"
        for folder in (dest, dest+"/scripts", dest+"/scripts/nxui"):
            try: ftp.mkd(folder)
            except ftplib.error_perm: pass
        for local in sorted(p for p in base.rglob("*") if p.is_file()):
            remote = dest + "/" + local.relative_to(base).as_posix()
            with local.open("rb") as stream: ftp.storbinary("STOR " + remote, stream)
            assert ftp.size(remote) == local.stat().st_size
        print("STAGED package", dest)
    elif len(sys.argv) > 1 and sys.argv[1] == "stage":
        try: ftp.mkd(REMOTE)
        except ftplib.error_perm: pass
        for local, name in ((HERE / "out/nxui.arm", "nxui.arm"), (HERE / "performance_camera.sh", "performance_camera.sh"), (HERE / "live_camera.sh", "live_camera.sh"), (HERE / "startup_camera.sh", "startup_camera.sh"), (HERE.parent.parent / "scripts/filmlab.sh", "filmlab.sh")):
            with local.open("rb") as stream: ftp.storbinary(f"STOR {REMOTE}/{name}", stream)
            assert ftp.size(f"{REMOTE}/{name}") == local.stat().st_size
            print("STAGED", name, local.stat().st_size)
    else:
        for name in ("performance.log", "old-idle.log", "new-idle.log", "live.log", "startup.log"):
            buf = io.BytesIO()
            try: ftp.retrbinary(f"RETR {REMOTE}/{name}", buf.write)
            except ftplib.error_perm as error: print(name, error); continue
            (OUT / name).write_bytes(buf.getvalue())
            if name == "performance.log": print(name, len(buf.getvalue()), "bytes")
            else: print(name, buf.getvalue().decode("utf-8", "replace").replace("\x00", ""))
