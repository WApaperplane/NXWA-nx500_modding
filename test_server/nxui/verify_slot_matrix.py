"""Compare device varlist values to the exact A2 encoding for three fields."""
from pathlib import Path
import json
import re
HERE = Path(__file__).resolve().parent
data = json.loads((HERE.parents[1] / "scripts/filmlab/recipes.json").read_text())
variables = [("PWCOLOR_R", "R_COLOR"), ("PWCOLOR_G", "G_COLOR"), ("PWCOLOR_B", "B_COLOR"),
             ("PWHUE", "HUE"), ("PWSATURATION", "SATURATION"), ("PWSHARPNESS", "SHARPNESS"), ("PWCONTRAST", "CONTRAST")]
results = []
log = (HERE / "out/slot-trial/matrix.log").read_text()
assert "DONE" in log and log.count("ENGINE_RC=0") == 3
for case, recipe, enum in [("standard", "portra400", "0x140000"), ("custom2", "trix400", "0x14000a"), ("custom3", "velvia50", "0x14000c")]:
    section = log.split(f"CASE_TARGET={enum}", 1)[1].split("CASE_TARGET=", 1)[0]
    assert re.search(r"UserData is PW_\w+ \(" + enum + r"\)", section)
    text = (HERE / f"out/slot-trial/vars-{case}.txt").read_text()
    count = 0
    for variable, field in variables:
        match = re.search(r"VARIABLE_" + variable + r"\s*\|\s*4\|0x([0-9A-Fa-f]+)\|", text)
        assert match, variable
        value = data["recipes"][recipe][field]
        expected = ((value * 255 // 200) << 20) | 0xff if field.endswith("_COLOR") else (((value * 16 - 145) & 0xffff) << 16) | 0xd80a
        assert int(match[1], 16) == expected, (case, variable, match[1], hex(expected))
        count += 1
    results.append({"field": case, "enum": enum, "recipe": recipe, "matched_values": count, "result": "PASS"})
(HERE / "out/slot-trial/results.json").write_text(json.dumps(results, indent=2) + "\n", newline="\n")
print(json.dumps(results, indent=2))
