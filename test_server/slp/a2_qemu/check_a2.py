#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_a2.py —— 解析 a2_harness 输出并逐用例判定（A2 补丁 QEMU 验证）。

输入: <workdir>/out.bin
  布局: u32 ncase | ncase×{id,ret,before,after} | u32 nevent | nevent×{type,a,b,c}
事件类型: 1=写槽(slot,val) 2=应用(51ab8) 3=变量发送(id,val,obj) 4=日志
"""
import os
import struct
import sys

EXP = [
    # (id, val, ret, [events...])
    (0x134, 106,    0, [(1, 0xdc, 106, 0)]),
    (0x135, 97,     0, [(1, 0xdd, 97, 0)]),
    (0x136, 107,    0, [(1, 0xde, 107, 0)]),
    (0x137, 14,     0, [(1, 0xdf, 14, 0)]),
    (0x138, 13,     0, [(1, 0xe0, 13, 0)]),
    (0x139, 10,     0, [(1, 0xe1, 10, 0)]),
    (0x13a, 12,     0, [(1, 0xe2, 12, 0)]),
    (0x13b, 0,      0, [(1, 0xda, 10, 0), (2, 0, 0, 0)]),
    (0x110, 0x003FD80A, 0, [(3, 0x10f, 0x003FD80A, 0x8142AB20)]),
    (0x100, 0x12345678, 0, [(3, 0x100, 0x12345678, 0x8142AB20)]),
    (0x130, 0x00000ABC, 0, [(3, 0x130, 0x00000ABC, 0x8142AB20)]),
    (0x12f, 0,     -1, [(4, 0, 0, 0), (4, 0, 0, 0)]),
    (0x13c, 0,     -1, [(4, 0, 0, 0), (4, 0, 0, 0)]),
]


def main():
    wk = sys.argv[1] if len(sys.argv) > 1 else "."
    d = open(os.path.join(wk, "out.bin"), "rb").read()
    if len(d) < 12:
        print("★ out.bin 过小（%d B）——载具可能崩溃（查 err.txt）" % len(d))
        return 3
    ncase = struct.unpack_from("<I", d, 0)[0]
    off = 4
    results = []
    for _ in range(ncase):
        results.append(struct.unpack_from("<IIII", d, off))
        off += 16
    nevent = struct.unpack_from("<I", d, off)[0]
    off += 4
    events = []
    for _ in range(nevent):
        events.append(struct.unpack_from("<IIII", d, off))
        off += 16
    print("ncase=%d nevent=%d" % (ncase, nevent))
    fails = 0
    total_exp = 0
    for i, (eid, eval_, eret, eevs) in enumerate(EXP):
        if i >= ncase:
            print("[FAIL] case#%d 缺失" % i)
            fails += 1
            continue
        cid, ret, before, after = results[i]
        got = events[before:after]
        total_exp += len(eevs)
        rr = ret if ret < 0x80000000 else ret - 0x100000000
        ok = (cid == eid) and (rr == eret) and (got == eevs)
        if ok:
            print("[OK  ] case#%2d id=%#05x val=%#x ret=%d events=%s" %
                  (i, cid, eval_, rr, got))
        else:
            fails += 1
            print("[FAIL] case#%2d id=%#05x val=%#x ret=%d（期望 %d）" %
                  (i, cid, eval_, rr, eret))
            print("       实得事件: %s" % (got,))
            print("       期望事件: %s" % (eevs,))
    if nevent != total_exp:
        print("[FAIL] 事件总数 %d != 期望 %d（有多余/缺失事件）" % (nevent, total_exp))
        fails += 1
    print()
    if fails == 0:
        print("==== 总判定: PASS（%d/%d 用例全绿；%d 事件全对）====" %
              (len(EXP), len(EXP), nevent))
        return 0
    print("==== 总判定: FAIL（%d 处）====" % fails)
    return 1


if __name__ == "__main__":
    sys.exit(main())
