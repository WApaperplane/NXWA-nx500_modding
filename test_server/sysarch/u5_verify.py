#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""U5 回滚演练收尾验证（只读）：把 p12 整块拉回，与基线逐字节比对。

用法: python u5_verify.py <ip>
产出: raw8/gates/u5/p12_readback.bin + rollback_drill.json
"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, "test_server/sysarch")
from fwprobe import T  # noqa: E402
from ftpx import ftp_get  # noqa: E402

SD_DIR = "/opt/storage/sdcard"
REMOTE = SD_DIR + "/u5verify"
OUTDIR = Path("raw8/gates/u5")
BASELINE = Path("raw8/emmcbak/p12.bin")


def md5f(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main():
    host = sys.argv[1]
    OUTDIR.mkdir(parents=True, exist_ok=True)
    local = OUTDIR / "p12_readback.bin"

    t = T(host, timeout=25)
    t.login()
    print("uptime:", t.send("cat /proc/uptime", 4.0).strip()[:40])
    print("version:", t.send("cat /etc/version.info 2>/dev/null | head -2", 5.0).strip()[:120])

    t.send("mkdir -p %s" % REMOTE, 3.0)
    t.send("dd if=/dev/mmcblk0p12 of=%s/p12.bin 2>/dev/null" % REMOTE, 12.0)
    remote_md5 = t.send(
        "/opt/usr/nx-ks/busybox md5sum %s/p12.bin 2>/dev/null || md5sum %s/p12.bin"
        % (REMOTE, REMOTE), 20.0)
    print("remote md5 line:", remote_md5.strip().splitlines()[-1][:90] if remote_md5.strip() else "?")
    t.close()

    print("FTP 拉回 ...")
    for attempt in range(3):
        if ftp_get(host, "/u5verify/p12.bin", str(local), timeout=600):
            break
        print("  重试", attempt + 1)
        time.sleep(3)

    base = bytearray(BASELINE.read_bytes())
    cur = bytearray(local.read_bytes())
    diffs = [i for i in range(min(len(base), len(cur))) if base[i] != cur[i]]

    res = {
        "drill": "u5-rollback",
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "host": host,
        "p12_size_local": len(cur),
        "p12_size_baseline": len(base),
        "p12_md5_readback": md5f(local),
        "p12_md5_baseline": md5f(BASELINE),
        "first_byte_readback": "0x%02x" % cur[0],
        "first_byte_baseline": "0x%02x" % base[0],
        "diff_count_vs_baseline": len(diffs),
        "diff_offsets": diffs[:32],
        "restored_to_pristine": (cur[0] == 0x00 and all(
            base[i] == cur[i] for i in range(1, min(len(base), len(cur))))),
    }
    (OUTDIR / "rollback_drill.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
