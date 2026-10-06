#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""反查: 哪些 vtable 槽位指向给定函数; 以及某函数属于哪些 vtable。"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from armcap import fw, off

VT_LO, VT_HI = 0x00583000, 0x0058A000     # vtable 所在文件偏移区间


def scan_vtables(lo=VT_LO, hi=VT_HI):
    """返回 [(起始VA, [槽位VA...]), ...]"""
    d = fw()
    out = []
    o = lo
    while o < hi:
        w = struct.unpack_from("<I", d, o)[0]
        if 0x800F0000 <= w < 0x80600000:
            slots = []
            p = o
            while True:
                v = struct.unpack_from("<I", d, p)[0]
                if not (0x800F0000 <= v < 0x80600000):
                    break
                slots.append(v + 0x80000000)
                p += 4
                if len(slots) > 40:
                    break
            if len(slots) >= 4:
                out.append((o + 0x80000000, slots))
            o = p if p > o else o + 4
        else:
            o += 4
    return out


if __name__ == "__main__":
    d = fw()

    def st(va):
        o = off(va)
        if o < 0 or o >= len(d):
            return None
        e = d.find(b"\x00", o)
        try:
            t = d[o:e].decode("ascii")
        except Exception:
            return None
        return t if all(32 <= ord(c) < 127 for c in t) and len(t) < 90 else None

    vts = scan_vtables()
    print("扫到候选 vtable: %d 个\n" % len(vts))
    targets = [int(x, 0) for x in sys.argv[1:]] or [
        0x8011e20c, 0x8011e678, 0x8011ebbc, 0x8011e510, 0x8011e7b8, 0x8011e7ec]
    for t in targets:
        print("目标 0x%08x:" % t)
        hit = False
        for va0, slots in vts:
            if t in slots:
                hit = True
                print("   属于 vtable @0x%08x, slot%d (+0x%02x)"
                      % (va0, slots.index(t), 4 * slots.index(t)))
        if not hit:
            print("   未出现在任何扫到的 vtable 中")
        print()

    print("含 3DLUT 相关函数的 vtable:")
    for va0, slots in vts:
        rel = [s for s in slots if 0x8011c000 <= s <= 0x8011f000]
        if len(rel) >= 3:
            print("  vtable @0x%08x  (%d slots)" % (va0, len(slots)))
            for k, s in enumerate(slots):
                mark = " <<<" if 0x8011c000 <= s <= 0x8011f000 else ""
                print("     slot%-2d = 0x%08x%s" % (k, s, mark))