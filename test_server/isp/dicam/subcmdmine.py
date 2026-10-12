#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""App 命令处理器「子命令树」挖掘器（di-camera-app / NX500 v1.12）

输入 dicam.asm（objdump 全反汇编，带符号）+ 目标二进制，
对给定 handler（符号名 或 0x地址）扫描函数体，输出：
  ① 该 handler 认的子命令名（= 相邻 movw/movt r1 常量指向的字符串）
  ② 它调用的具名函数（= 子命令落点）

用法:
  python subcmdmine.py nx_cmd_handler cmd_capture_handler
  python subcmdmine.py 0xcb198 0xcd0bc 0xcbc60     # 无符号区用地址
"""
import re
import sys
from pathlib import Path

ASM = Path(r"E:/tmp/dicam_strings/dicam.asm")
BIN = Path(r"E:/NXWA/fw/v1.12/extract/di-camera-app/com.samsung.di-camera-app/bin/di-camera-app")
THRESH = 0x4484AC

SYM_RE = re.compile(r"^([0-9a-f]{8}) <([^>]+)>:$")
MOVW_RE = re.compile(r"movw\s+r1,\s*#(\d+)\s*@\s*(0x[0-9a-f]+)")
MOVT_RE = re.compile(r"movt\s+r1,\s*#(\d+)\s*@\s*(0x[0-9a-f]+)")
BL_RE = re.compile(r"\bbl\s+([0-9a-f]+)\s+<([^>]+)>")


def v2f(v):
    return v - (0x8000 if v < THRESH else 0x10000)


def cstr(data, vaddr, maxlen=64):
    off = v2f(vaddr)
    if off < 0 or off >= len(data):
        return "<out>"
    blob = data[off:off + maxlen]
    nul = blob.find(b"\x00")
    if nul < 0:
        nul = maxlen
    try:
        s = blob[:nul].decode("ascii")
    except UnicodeDecodeError:
        return "<non-ascii>"
    return s if s else "<empty>"


def body_of(lines, start):
    out = []
    for ln in lines[start + 1:]:
        if SYM_RE.match(ln):
            break
        out.append(ln)
    return out


def body_by_addr(lines, addr):
    """地址定位（无符号区）：从 `  ADDR:` 行起，上限 800 行或遇符号行止。"""
    pat = re.compile(r"^\s*%x:\t" % addr)
    start = None
    for i, ln in enumerate(lines):
        if pat.match(ln):
            start = i
            break
    if start is None:
        return []
    out = []
    for ln in lines[start:start + 800]:
        if SYM_RE.match(ln):
            break
        out.append(ln)
    return out


def dump(data, body):
    subs = []
    for i, ln in enumerate(body):
        mw = MOVW_RE.search(ln)
        if mw and i + 1 < len(body):
            mt = MOVT_RE.search(body[i + 1])
            if mt:
                v = ((int(mt.group(2), 16) << 16) | int(mw.group(2), 16)) & 0xFFFFFFFF
                subs.append((cstr(data, v), v))
    seen = set()
    print("  子命令串:")
    for s, v in subs:
        if (s, v) in seen:
            continue
        seen.add((s, v))
        if " " in s or "%" in s or "\\n" in s or len(s) > 28 or s.startswith("<"):
            continue
        print("    %-26r @0x%08x" % (s, v))
    calls = []
    for ln in body:
        for _a, nm in BL_RE.findall(ln):
            nm = nm.split("@@")[0]
            if nm not in calls and "plt" not in nm:
                calls.append(nm)
    print("  调用:")
    print("    " + (", ".join(calls) if calls else "(none)"))
    print()


def main():
    data = BIN.read_bytes()
    lines = ASM.read_text(errors="replace").splitlines()
    idx, addr = {}, {}
    for i, ln in enumerate(lines):
        m = SYM_RE.match(ln)
        if m:
            full = m.group(2)
            base = full.split("@@")[0]
            idx.setdefault(base, i)
            idx.setdefault(full, i)
            addr.setdefault(base, int(m.group(1), 16))

    targets = sys.argv[1:] or ["nx_cmd_handler"]
    for t in targets:
        if t.lower().startswith("0x"):
            a = int(t, 16)
            body = body_by_addr(lines, a)
            if not body:
                print("!! 未定位 0x%x" % a)
                continue
            print("=" * 88)
            print("=== [addr] %s  (body %d 行)" % (t, len(body)))
            print("=" * 88)
            dump(data, body)
            continue
        key = t
        if key not in idx:
            cand = [k for k in idx if k.startswith(t)]
            if not cand:
                print("!! 未找到符号 %s" % t)
                continue
            key = cand[0]
        body = body_of(lines, idx[key])
        print("=" * 88)
        print("=== %s @0x%x  (body %d 行)" % (key, addr[key], len(body)))
        print("=" * 88)
        dump(data, body)


if __name__ == "__main__":
    main()
