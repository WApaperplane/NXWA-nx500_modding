"""The same open menu must show actual service changes, including partial failure."""
import os
import subprocess
import tempfile
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
HEADER = "  sl local_address rem_address st\n"
BOTH = HEADER + "0: 00000000:0017 00000000:0000 0A\n1: 00000000:0015 00000000:0000 0A\n"
PARTIAL = HEADER + "0: 00000000:0017 00000000:0000 0A\n"

def run_service_interaction(prefix, env, label):
    with tempfile.TemporaryDirectory(prefix="nxui-service-ui-") as folder:
        root = Path(folder); net = root / "net"; net.mkdir(); (net / "tcp").write_text(HEADER)
        log = root / "ui.log"; calls = root / "calls"
        (root / "gui_ini.NX500").write_text("".join(f"button|占位{i}| \n" for i in range(6)) + "button|旧的静态状态|telnet_toggle.sh\nbutton|确认页面|mark.sh\n")
        switch = root / "telnet_toggle.sh"
        switch.write_text(f'''#!/bin/sh
echo "$*" >> "{calls}"
[ "$1" = --ui ] || exit 8
sleep 0.12
if [ "$2" = enable ]; then
  if [ -e "{root}/fail" ]; then printf '{PARTIAL}' > "{net}/tcp"; exit 7; fi
  printf '{BOTH}' > "{net}/tcp"
else printf '{HEADER}' > "{net}/tcp"
fi
'''); switch.chmod(0o755)
        mark = root / "mark.sh"; mark.write_text(f'#!/bin/sh\necho MARK >> "{calls}"\n'); mark.chmod(0o755)
        runenv = dict(env, NXUI_NET_DIR=str(net))
        with log.open("w") as stream:
            p = subprocess.Popen(prefix + ["--live", "--root", str(root), "--menu", "gui_ini.NX500", "--lifetime-ms", "10000"], env=runenv, stdout=stream, stderr=subprocess.STDOUT)
            def send(*args): subprocess.run([str(OUT / "test_input")] + list(args), env=runenv, check=True, timeout=5)
            def until(fragment, count=1):
                for _ in range(100):
                    if log.read_text().count(fragment) >= count: return
                    assert p.poll() is None, log.read_text()
                    time.sleep(.025)
                raise AssertionError(log.read_text())
            try:
                until("READY")
                send("click", "590", "244", "5")
                until("telnet=0 ftp=0 label=")
                send("click", "160", "65", "5"); until("telnet=1 ftp=1 label=")
                send("click", "160", "65", "5"); until("telnet=0 ftp=0 label=", 2)
                # A change outside this menu must appear without reopening it.
                (net / "tcp").write_text(PARTIAL); until("telnet=1 ftp=0 label=")
                (root / "fail").touch()
                send("click", "160", "65", "5"); until("BACKEND kind=4 ok=0")
                (root / "fail").unlink()
                send("click", "160", "65", "5"); until("telnet=1 ftp=1 label=", 2)
                send("click", "535", "65", "5")
                for _ in range(50):
                    if "MARK" in calls.read_text(): break
                    time.sleep(.025)
                assert calls.read_text().splitlines() == ["--ui enable", "--ui disable", "--ui enable", "--ui enable", "MARK"]
                send("key", "Escape"); assert p.wait(timeout=5) == 0
                text = log.read_text()
                assert text.count("MENU file=") == 1, text
                assert "Telnet:开 FTP:关" in text and "Telnet:开 FTP:开" in text
                (OUT / f"{label}-service-interaction.log").write_text(text)
            finally:
                if p.poll() is None: p.kill(); p.wait()
    print(f"PASS {label}: same-page service on/off, external change, partial failure and retry")
