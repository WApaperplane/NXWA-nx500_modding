#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""u1_input_map.py - 解析 U1 ③④ 抓到的 input_event 流，产出 raw8/gates/u1/input_map.json

★ 为什么要工具（铁律 94）：手抄/目测不能支撑统计。这里逐事件解析 16 字节
  struct input_event —— 32 位 ARM 上 timeval = tv_sec(4) + tv_usec(4)，
  随后 type(u16) / code(u16) / value(s32)，合计 16 字节 ⇒ struct '<IIHHi'。

★ 已证设备（u1_probe.sh 的 /proc/bus/input/devices）：
  event0 = Drime5 GPIO Keyboard   (kbd)
  event1 = Drime5 ADC Keyboard    (kbd)
  event2 = Melfas MMS100s Touchscreen (mouse0, MT protocol B)

用法: python test_server/tools/u1_input_map.py
"""
from __future__ import annotations

import collections
import json
import os
import struct
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
EV = os.path.join(REPO, "raw8", "gates", "u1")

ST_MAX_EVENTS = 256          # u1_input.sh 的 dd bs=16 count=256 ⇒ 上限
DEVS = [
    (0, "Drime5 GPIO Keyboard", "kbd"),
    (1, "Drime5 ADC Keyboard", "kbd"),
    (2, "Melfas MMS100s Touchscreen", "mouse0"),
]
EVNAMES = {0: "EV_SYN", 1: "EV_KEY", 2: "EV_REL", 3: "EV_ABS"}
KEYNAMES = {
    72: "KEY_UP", 75: "KEY_LEFT", 77: "KEY_RIGHT", 80: "KEY_DOWN",
    125: "KEY_LEFTMETA", 126: "KEY_RIGHTMETA",
    163: "KEY_NEXTSONG", 165: "KEY_PREVIOUSSONG",
    177: "KEY_PAGEDOWN", 178: "KEY_PAGEUP",
}
ABSNAMES = {53: "ABS_MT_POSITION_X", 54: "ABS_MT_POSITION_Y",
            57: "ABS_MT_TRACKING_ID", 58: "ABS_MT_PRESSURE"}


def name(t, c):
    if t == 1:
        return KEYNAMES.get(c, "KEY_%d" % c)
    if t == 3:
        return ABSNAMES.get(c, "ABS_%d" % c)
    return "0x%x" % c


def parse(path):
    d = open(path, "rb").read()
    n = len(d) // 16
    evs = [struct.unpack("<IIHHi", d[i * 16:i * 16 + 16])[2:] for i in range(n)]
    return d, evs


def main():
    out = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "source": "test_server/u1/u1_input.sh <eventN> 20（有界：dd bs=16 count=256）",
        "note": "用户手动操作机身期间抓取；event2 触达 count 上限 ⇒ 见 truncated 标志",
        "devices": {},
    }
    problems = []
    for idx, devname, handler in DEVS:
        p = os.path.join(EV, "input_event%d.bin" % idx)
        if not os.path.exists(p):
            problems.append("event%d: 缺 input_event%d.bin" % (idx, idx))
            continue
        d, evs = parse(p)
        cnt = collections.Counter((t, c) for t, c, _ in evs)
        codes = []
        for (t, c), num in sorted(cnt.items()):
            vs = [v for tt, cc, v in evs if tt == t and cc == c]
            codes.append({
                "type": t, "type_name": EVNAMES.get(t, "?"),
                "code": c, "code_name": name(t, c),
                "count": num,
                "value_min": min(vs), "value_max": max(vs),
            })
        is_key = any(t == 1 for t, _, _ in evs)
        has_rel = any(t == 2 for t, _, _ in evs)
        out["devices"]["event%d" % idx] = {
            "name": devname,
            "handler": handler,
            "bytes": len(d),
            "events": len(evs),
            "truncated": len(evs) >= ST_MAX_EVENTS,
            "has_ev_key": is_key,
            "has_ev_rel": has_rel,
            "codes": codes,
        }

    # ---- 汇总：输入通道形态 ----
    keys = {k: v for k, v in out["devices"].items()}
    out["summary"] = {
        "ev_rel_present_anywhere": any(v.get("has_ev_rel") for v in keys.values()),
        "verdict": ("未在任何 eventN 观测到 EV_REL 相对轴事件 ⇒ 机身不存在独立的"
                    "'相对轴'输入设备；旋钮/波轮若存在，是被 drime5 驱动映射成 EV_KEY 的。"),
        "input_channels": {
            "event0": "GPIO 键盘：125/126(左/右Meta)、163/165(Next/Prev)、177/178(PageDown/PageUp)，全按下-释放型",
            "event1": "ADC 键盘：72(UP)/75(LEFT)/77(RIGHT)/80(DOWN) 四向，全按下-释放型",
            "event2": "Melfas 触摸：MT protocol B（ABS_MT_TRACKING_ID 触点 27/28 + POSITION_X/Y + PRESSURE）",
        },
    }

    dst = os.path.join(EV, "input_map.json")
    with open(dst, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    for k, v in out["devices"].items():
        print("  %s  %-32s %5d B  %3d events  truncated=%s  rel=%s"
              % (k, v["name"], v["bytes"], v["events"], v["truncated"], v["has_ev_rel"]))
        for c in v["codes"]:
            print("      %-5s %-22s x%-3d value=[%s,%s]"
                  % (c["type_name"], c["code_name"], c["count"], c["value_min"], c["value_max"]))
    print("全集有 EV_REL:", out["summary"]["ev_rel_present_anywhere"])
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
