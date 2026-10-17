from pathlib import Path
import subprocess
base = Path(__file__).resolve().parent / "out" / "deps"
for package in base.glob("*.deb"):
    subprocess.run(["dpkg-deb", "-x", str(package), str(base)], check=True)
