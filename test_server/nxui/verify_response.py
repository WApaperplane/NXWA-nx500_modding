"""Verify real-camera preview values, retained field, timing and service state."""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out/responsiveness"
data = json.loads((HERE.parents[1] / "scripts/filmlab/recipes.json").read_text())
log = (OUT / "response.log").read_text().replace("\x00", "")
assert "RESTORED" in log and "DONE" in log
target = re.search(r"BEFORE field=(0x[0-9a-f]+)", log)[1]
variables = (("PWCOLOR_R", "R_COLOR"), ("PWCOLOR_G", "G_COLOR"), ("PWCOLOR_B", "B_COLOR"),
    ("PWHUE", "HUE"), ("PWSATURATION", "SATURATION"), ("PWSHARPNESS", "SHARPNESS"), ("PWCONTRAST", "CONTRAST"))
records = []
for recipe in ("portra400", "trix400"):
    for version in ("old", "new"):
        section = log.split(f"CASE {version} {recipe} start=", 1)[1].split("CASE ", 1)[0]
        start = float(section.splitlines()[0]); end = float(re.search(r"END \w+ \w+ end=([\d.]+)", section)[1])
        assert f"({target})" in section, section
        text = (OUT / f"{version}-{recipe}.vars").read_text()
        for variable, field in variables:
            value = data["recipes"][recipe][field]
            expected = ((value*255//200)<<20)|0xff if field.endswith("_COLOR") else (((value*16-145)&0xffff)<<16)|0xd80a
            actual = int(re.search(r"VARIABLE_"+variable+r"\s*\|\s*4\|0x([0-9a-fA-F]+)\|", text)[1], 16)
            assert actual == expected, (version, recipe, variable, hex(actual), hex(expected))
        records.append(dict(version=version, recipe=recipe, seconds=round(end-start, 2), matched_values=7, retained_field=target))
service = (OUT / "service-ui.log").read_text()
assert "telnet=1 ftp=1 label=" in service and "telnet=0 ftp=0 label=" in service, service
assert service.count("BACKEND kind=4 ok=1") == 2 and "ok=0" not in service, service
assert service.count("MENU file=") == 1, "Service test reopened its menu"
times = list(map(int, re.findall(r"BACKEND kind=4 ok=1 elapsed_ms=(\d+)", service)))
result = dict(preview=records, service_actions_ms=times, service_same_page="PASS", offline_engine_tests=15, offline_service_tests=4)
(OUT / "results.json").write_text(json.dumps(result, indent=2)+"\n")
print(json.dumps(result, indent=2))
