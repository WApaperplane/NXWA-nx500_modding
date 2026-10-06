#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""定位 VA 所属 Ghidra 函数(读 02_functions.txt)。"""
import bisect

FP = r"D:/download/NX-KS2-88/raw8/p7/ghidra/02_functions.txt"
_fns = None


def load():
    global _fns
    if _fns is None:
        fns = []
        for ln in open(FP, encoding="utf-8", errors="replace"):
            ln = ln.rstrip("\n")
            if ln.startswith("addr") or ln.startswith("==="):
                continue
            p = ln.split("\t")
            if len(p) >= 3:
                try:
                    # 列序: addr / size / name
                    fns.append((int(p[0], 16), int(p[1]), p[2]))
                except ValueError:
                    pass
        fns.sort()
        _fns = fns
    return _fns


def func_of(va):
    fns = load()
    starts = [f[0] for f in fns]
    i = bisect.bisect_right(starts, va) - 1
    if i < 0:
        return None
    st, sz, nm = fns[i]
    if va >= st + sz:
        return None
    return nm, st, sz