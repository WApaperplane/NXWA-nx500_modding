"""Summarize /proc CPU ticks and wakeups without confusing overall camera load."""
import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out/performance-device"
text = (OUT / "performance.log").read_text().replace("\x00", "")
assert "DONE" in text, "Trial did not finish"
samples = {}
for block in text.split("SAMPLE ")[1:]:
    lines = block.splitlines(); name = lines[0]
    total = sum(map(int, lines[2].split()[1:]))
    processes = {}
    for index, line in enumerate(lines):
        if not line.startswith("PROCESS "): continue
        stat = lines[index+1].rsplit(")", 1)[1].split()
        following = "\n".join(lines[index+2:index+5])
        processes[line[8:]] = dict(ticks=int(stat[11])+int(stat[12]), nice=int(stat[16]),
            rss_kb=int(re.search(r"VmRSS:\s+(\d+)", following)[1]),
            voluntary=int(re.search(r"voluntary_ctxt_switches:\s+(\d+)", following)[1]))
    samples[name] = dict(seconds=float(lines[1].split()[0]), total=total, processes=processes)
records = []
for label in ("baseline", "old-idle", "new-idle"):
    a, b = samples[label+"-start"], samples[label+"-end"]
    elapsed = b["seconds"] - a["seconds"]
    record = dict(case=label, seconds=round(elapsed, 2), processes={})
    for name, pb in b["processes"].items():
        pa = a["processes"][name]
        record["processes"][name] = dict(cpu_percent=round(100*(pb["ticks"]-pa["ticks"])/(b["total"]-a["total"]), 3),
            rss_kb=pb["rss_kb"], nice=pb["nice"], voluntary_wakeups=pb["voluntary"]-pa["voluntary"])
    records.append(record)
(OUT / "results.json").write_text(json.dumps(records, indent=2))
print(json.dumps(records, indent=2))
