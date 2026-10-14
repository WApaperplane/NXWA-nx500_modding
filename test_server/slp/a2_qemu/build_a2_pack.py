#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_a2_pack.py —— A2 p7 补丁 SLP 出包（版本 1.17）。

与 build_a1_pack.py 的差别：A2 的 p7_a2.bin 已含全部 4 处改动，
本器只做三步：替换 idx5 → version=1.17 → CRC 重算 → 出包 + 回读自检。

用法:
  python build_a2_pack.py <官方.bin> <p7_a2.bin> <out.bin> [--version 1.17] [--write]
"""
import argparse
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import slp_tool  # noqa: E402

P7_IDX = 5
P7_A2_MD5 = "712c6fd0a49371ec05ce94c367b0d5c7"


def main():
    ap = argparse.ArgumentParser(description="A2 SLP 出包")
    ap.add_argument("official")
    ap.add_argument("p7a2")
    ap.add_argument("out")
    ap.add_argument("--version", default="1.17")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    meta, parts = slp_tool.parse(a.official, verbose=False)
    p7 = open(a.p7a2, "rb").read()
    md5 = hashlib.md5(p7).hexdigest()
    print("官方容器: %s（版本 %s）" % (a.official, meta["version"]))
    print("p7_a2   : %d B  md5 %s %s" % (len(p7), md5, "==" if md5 == P7_A2_MD5 else "!="))
    assert md5 == P7_A2_MD5, "p7_a2.bin md5 与出包基准不符！"
    assert parts[P7_IDX]["img_len"] == len(p7), "idx5 长度不符"

    newparts = [dict(p) for p in parts]
    newparts[P7_IDX] = dict(newparts[P7_IDX])
    newparts[P7_IDX]["data"] = p7
    newmeta = dict(meta)
    newmeta["version"] = a.version
    buf, warn = slp_tool.build(newmeta, newparts, a.out, write=False)
    print("新容器  : %d B  md5 %s" % (len(buf), hashlib.md5(buf).hexdigest()))
    print("idx5 JAMCRC = %08x" % slp_tool.crc_jamcrc(p7))
    for w in warn:
        print("  [warn] %s" % w)

    if a.write:
        open(a.out, "wb").write(buf)
        # 回读自检
        chk = open(a.out, "rb").read()
        base = chk.find(p7[:32])
        ok1 = base > 0 and chk[base:base + len(p7)] == p7
        m2, p2 = slp_tool.parse(a.out, verbose=False)
        ok2 = m2["version"] == a.version
        ok3 = p2[P7_IDX]["data"] == p7
        print("回读自检: idx5 定位=%s 版本=%s idx5 一致=%s" %
              (ok1, ok2, ok3))
        assert ok1 and ok2 and ok3, "回读自检失败"
        print("★ 已写 %s" % a.out)
    else:
        print("(dry-run；加 --write 落盘)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
