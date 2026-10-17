#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 U1 §2 的产物如实汇总 → raw8/gates/u1/mem_compare.json（门控 G2-1 的唯一输入）

★ 只做"如实汇总"：每个字段都来自落盘的 .log / .bin / .md5，不做任何推断性填充。
  判据（runbook §2 写死）由 gate_flow.py 依本文件判定。

用法: python test_server/u1/gen_mem_compare.py
"""
import hashlib
import json
import re
from pathlib import Path

D = Path("raw8/gates/u1")

# (地址, 产物前缀, 角色, 说明)
SPEC = [
    ("0x94000000", "ctl_dram_94000000", "positive_control", "CMA 窗口（已知 dd 可读，证明方法在本机可用）"),
    ("0x2082b000", "ctl_dev_2082b000", "negative_control", "设备寄存器区（预期 dd 失败）"),
    ("0x810fd100", "lut_a_810fd100", "target", "p7 LUT 缓冲 A"),
    ("0x81115200", "lut_b_81115200", "target", "p7 LUT 缓冲 B（= LUT0）"),
]


def md5f(p):
    return hashlib.md5(p.read_bytes()).hexdigest() if p.exists() else None


def main():
    addrs = {}
    for addr, pre, role, desc in SPEC:
        log = D / (pre + ".log")
        binf = D / (pre + ".bin")
        txt = log.read_text(errors="replace") if log.exists() else ""
        m_rc = re.search(r"dd_rc=(-?\d+)", txt)
        rc = int(m_rc.group(1)) if m_rc else None
        size = binf.stat().st_size if binf.exists() else 0
        rec = {
            "role": role,
            "desc": desc,
            "readable": (rc == 0 and size > 0),
            "dd_rc": rc,
            "bytes": size,
            "md5_bin": md5f(binf),
            "log_lines": txt.strip().splitlines()[:6],
        }
        if rc != 0:
            m_err = re.search(r"dd:\s*(.+)$", txt, re.M)
            rec["err"] = m_err.group(1).strip() if m_err else None
        addrs[addr] = rec

    lut_ok = any(addrs[a]["readable"] for a in ("0x810fd100", "0x81115200"))
    pos_ok = addrs["0x94000000"]["readable"]
    neg_ok = not addrs["0x2082b000"]["readable"]

    if not pos_ok:
        verdict = "INVALID"
        concl = "阳性对照失败 ⇒ 整套方法在本机失效，禁止输出主结论（runbook §2 判据）"
    elif lut_ok:
        verdict = "G2a"
        concl = ("阳性对照通过 + 至少一个 p7 LUT 缓冲可读 ⇒ 走「读已知内容的表做差分」；"
                 "D1 降级为交叉验证，lutmod 补丁【永久弃用】")
    else:
        verdict = "G2b"
        concl = ("阳性对照通过（方法可用）+ 阴性对照如预期失败 + 两个 p7 LUT 缓冲均 dd 失败 "
                 "⇒ 「读不到」= 该地址面真的不可读；评估 p7_full.lutmod.bin 前【必须重推目标地址】"
                 "（CMA 窗口会变）")

    out = {
        "_note": "U1 §2 /dev/mem 四点对照（铁律 118：先阳性对照→再阴性对照→最后问题本体）",
        "host": "192.168.0.106",
        "method": "dd if=/dev/mem（u1_rd.sh，768 regs/段 = 3072 B，段间等待 90s）",
        "collected_at": "2026-10-12 19:10-19:16 (+08)",
        "addresses": addrs,
        "positive_control_ok": pos_ok,
        "negative_control_ok": neg_ok,
        "verdict": verdict,
        "conclusion": concl,
    }
    p = D / "mem_compare.json"
    p.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("已写出: %s" % p)
    print("  判定: %s" % verdict)
    print("  %s" % concl)
    for a, r in addrs.items():
        print("  %s  %-17s readable=%-5s rc=%s bytes=%s"
              % (a, r["role"], r["readable"], r["dd_rc"], r["bytes"]))


if __name__ == "__main__":
    main()
