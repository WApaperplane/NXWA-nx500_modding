#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""u1_mem_compare.py - 从 U1 四点对照产物生成 raw8/gates/u1/mem_compare.json

★ 为什么要工具而不是手抄（铁律 94/119）：
  结论必须能被产物逐字节复核。gate_flow.py 的 G2 只读本 json 的
  addresses[addr]["readable"]，所以这个文件必须由 .bin/.log 推导，不能手写。

★ 判据（与 runbook [2] 写死一致）：
  idx=1 读成功 + idx=2 读失败  =>  方法可用
  idx=1 读失败                 =>  方法失效，禁止输出主结论
  idx=3/4 任一读成功           =>  G2a：读表差分，U11 直接解
  idx=3/4 都读失败             =>  G2b：才评估 lutmod，且必须重推目标地址

用法: python test_server/tools/u1_mem_compare.py
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
EV = os.path.join(REPO, "raw8", "gates", "u1")

# idx, 地址, 产物名, 角色, 预期
SEGS = [
    (1, "0x94000000", "ctl_dram_94000000", "阳性对照（Linux CMA 窗口）", "readable"),
    (2, "0x2082b000", "ctl_dev_2082b000", "阴性对照（设备寄存器区 MMIO）", "unreadable"),
    (3, "0x810fd100", "lut_a_810fd100", "问题本体 A（p7 LUT 缓冲）", "?"),
    (4, "0x81115200", "lut_b_81115200", "问题本体 B（p7 LUT 缓冲 = LUT0）", "?"),
]


def md5f(p):
    h = hashlib.md5()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def parse_log(p):
    """-> (dd_rc, err_line)"""
    txt = open(p, "r", errors="replace").read()
    m = re.search(r"dd_rc=(\d+)", txt)
    rc = int(m.group(1)) if m else None
    err = None
    for line in txt.splitlines():
        if "dd:" in line:
            err = line.strip()
            break
    return rc, err


def main():
    addrs = {}
    problems = []
    for idx, addr, name, role, expect in SEGS:
        binp = os.path.join(EV, name + ".bin")
        logp = os.path.join(EV, name + ".log")
        if not os.path.exists(binp) or not os.path.exists(logp):
            problems.append("idx=%d %s: 缺 .bin 或 .log" % (idx, name))
            continue
        size = os.path.getsize(binp)
        rc, err = parse_log(logp)
        readable = (rc == 0 and size > 0)
        rec = {
            "idx": idx,
            "name": name,
            "role": role,
            "expect": expect,
            "dd_rc": rc,
            "bytes": size,
            "readable": readable,
            "bin_md5": md5f(binp),
            "log_md5": md5f(logp),
        }
        if err:
            rec["err"] = err
        addrs[addr] = rec

    pos = addrs.get("0x94000000", {})
    neg = addrs.get("0x2082b000", {})
    lut = [addrs.get("0x810fd100", {}), addrs.get("0x81115200", {})]

    if pos.get("readable") and not neg.get("readable"):
        method_ok = True
        m_note = ("阳性对照可读 + 阴性对照失败 => /dev/mem 方法在本机可用，"
                  "'读不到' = 该地址面真的不可读（铁律 118/119 满足）")
    elif not pos.get("readable"):
        method_ok = False
        m_note = "阳性对照失败 => 整套方法失效，回到离机轨，禁止输出主结论"
    else:
        method_ok = None
        m_note = "对照形态异常（阴性也可读），需人工复核"

    lut_readable = any(r.get("readable") for r in lut)
    if not method_ok:
        verdict = "INVALID"
        concl = "方法失效：阳性对照未通过，四点对照结论不可用"
    elif lut_readable:
        verdict = "G2a"
        concl = ("LUT 缓冲可读 => 走读已知内容的表做差分，U11 直接解；"
                 "D1 降级为交叉验证；lutmod 补丁永久弃用")
    else:
        verdict = "G2b"
        concl = ("两个 LUT 缓冲均不可读（Bad address）=> 才评估 lutmod，且必须重推目标地址。"
                 "★ 修正既有认知：不只是 MMIO(0x2082b000) 读不到，p7 固件占用的 DRAM 子区间"
                 "(0x810fd100 / 0x81115200) 在 Linux 下同样 Bad address —— 它们不在 Linux 的 "
                 "memory map 内。因此 lutmod 把 LUT 缓冲搬到 Linux CMA(0x94000000-0xA6000000) "
                 "从'可选'变为'必需'。")

    out = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "source": "test_server/u1/u1_rd.sh idx=1..4（单段 768 regs，段间 90s）",
        "method_ok": method_ok,
        "method_note": m_note,
        "verdict": verdict,
        "conclusion": concl,
        "addresses": addrs,
    }
    dst = os.path.join(EV, "mem_compare.json")
    with open(dst, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    for a, r in addrs.items():
        print("  %-12s %-24s dd_rc=%s bytes=%-6d readable=%s"
              % (a, r["role"], r["dd_rc"], r["bytes"], r["readable"]))
    print("方法可用:", method_ok, "| 判定:", verdict)
    print("写入:", os.path.relpath(dst, REPO))
    if problems:
        print("问题:")
        for p in problems:
            print("  -", p)
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
