#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_a1_qemu.py —— 解析 A1 包级 QEMU 三版本输出（orig/step1/full）并做差分判定。

输入: <workdir>/out_{orig,step1,full}.bin
      每份布局 = 64 × u32×3 {id, ret, conv} + 尾部 u32（日志桩调用计数）

判定:
  A. orig 基线 = 设计基线（47 项表：45 映射 + 0x119/0x11a 拒收；域外 17 项拒收）
     拒收特征: ret = -1(0xFFFFFFFF), conv = 0xff
  B. step1 ≡ orig ：全 64 例 {ret, conv} 逐项相同
  C. full：非目标 ≡ orig；0x130..0x133 → ret=0, conv=id（恒等放行）
  D. 日志桩计数：orig=19 / step1=19 / full=15（每个拒收 case 恰一次）

用法: python3 check_a1_qemu.py <workdir>
"""
from __future__ import annotations

import struct
import sys
import os

# 47 项跳转表设计基线（A1_p7_normalizer_patch_design §2 表；已与 objdump 逐项核对）
# None = 拒收（走 0x80051394；0x119/0x11a 两项）
NORM_EXPECT = {
    0x100: 0x100, 0x101: 0x101, 0x102: 0x102, 0x103: 0x103,
    0x104: 0x104, 0x105: 0x105, 0x106: 0x106, 0x107: 0x107,
    0x108: 0x10a, 0x109: 0x10b, 0x10a: 0x10d, 0x10b: 0x112,
    0x10c: 0x113, 0x10d: 0x114,
    0x10e: 0x11a, 0x10f: 0x10e, 0x110: 0x10f, 0x111: 0x110,
    0x112: 0x111, 0x113: 0x118, 0x114: 0x119,
    0x115: 0x11b, 0x116: 0x11c, 0x117: 0x11d, 0x118: 0x11e,
    0x119: None, 0x11a: None,
    0x11b: 0x11f, 0x11c: 0x120, 0x11d: 0x121, 0x11e: 0x122,
    0x11f: 0x123, 0x120: 0x124, 0x121: 0x125,
    0x122: 0x126, 0x123: 0x127, 0x124: 0x128, 0x125: 0x129,
    0x126: 0x12a, 0x127: 0x12b, 0x128: 0x12c,
    0x129: 0x12e, 0x12a: 0x10c, 0x12b: 0x139, 0x12c: 0x13a,
    0x12d: 0x108, 0x12e: 0x13f,
}
TARGETS = (0x130, 0x131, 0x132, 0x133)
NCASE_EXPECT = 64
LOG_EXPECT = {"orig": 19, "step1": 19, "full": 15}

fails = []


def load(path):
    d = open(path, "rb").read()
    n = NCASE_EXPECT
    if len(d) != n * 12 + 4:
        raise ValueError("%s 大小 = %d B，期望 %d B" % (path, len(d), n * 12 + 4))
    cases = []
    for i in range(n):
        cid, ret, conv = struct.unpack_from("<III", d, i * 12)
        if ret >= 0x80000000:
            ret -= 0x100000000
        cases.append((cid, ret, conv))
    logcnt = struct.unpack_from("<I", d, n * 12)[0]
    return cases, logcnt


def expect_behavior(variant, cid):
    """按设计给出该版本应有的 (ret, conv)。"""
    if cid in TARGETS:
        if variant in ("orig", "step1"):
            return (-1, 0xFF, "拒收")
        return (0, cid, "恒等放行")
    v = NORM_EXPECT.get(cid)
    if v is not None:
        return (0, v, "→%#x" % v)
    return (-1, 0xFF, "拒收")


def main():
    wk = sys.argv[1] if len(sys.argv) > 1 else "."
    data = {}
    for v in ("orig", "step1", "full"):
        p = os.path.join(wk, "out_%s.bin" % v)
        if not os.path.exists(p):
            print("缺文件: %s" % p)
            return 2
        try:
            data[v] = load(p)
        except ValueError as e:
            print("[FAIL] %s" % e)
            print("==== 总判定: FAIL（输出尺寸异常 —— 载体大概率在坏输入下崩溃/走飞）====")
            return 3
    cases_o, log_o = data["orig"]
    cases_s, log_s = data["step1"]
    cases_f, log_f = data["full"]

    # ---- A. orig 基线 ----
    print("########## A. orig 基线（对照设计表） ##########")
    o_fail = 0
    for cid, ret, conv in cases_o:
        er, ec, why = expect_behavior("orig", cid)
        if (ret, conv) != (er, ec):
            o_fail += 1
            print("  [FAIL] orig id=%#x 实得 (%d, %#x) 期望 (%d, %#x) %s"
                  % (cid, ret, conv, er, ec, why))
    if o_fail == 0:
        print("  [OK] 64/64 例与设计基线一致（45 映射 + 19 拒收）")
    else:
        fails.append("orig 基线 %d 例不符" % o_fail)

    # ---- B. step1 ≡ orig ----
    print("\n########## B. step1 ≡ orig（全 64 例逐字段） ##########")
    s_fail = 0
    for i, ((cid, r1, c1), (cid2, r2, c2)) in enumerate(zip(cases_s, cases_o)):
        if (r1, c1) != (r2, c2):
            s_fail += 1
            print("  [FAIL] step1 id=%#x (%d, %#x) != orig (%d, %#x)" % (cid, r1, c1, r2, c2))
    if s_fail == 0:
        print("  [OK] step1 与 orig 逐项一致（绕行路径 ⇒ 零行为变化）")
    else:
        fails.append("step1 与 orig 差 %d 例" % s_fail)

    # ---- C. full：除 4 目标外 ≡ orig；目标 → (0, id) ----
    print("\n########## C. full：除 0x130..0x133 外 ≡ orig；目标恒等放行 ##########")
    f_fail = 0
    for i, ((cid, r1, c1), (cid2, r2, c2)) in enumerate(zip(cases_f, cases_o)):
        if cid in TARGETS:
            if (r1, c1) != (0, cid):
                f_fail += 1
                print("  [FAIL] full(id=%#x) 目标应 (0, %#x) 实得 (%d, %#x)" % (cid, cid, r1, c1))
        else:
            if (r1, c1) != (r2, c2):
                f_fail += 1
                print("  [FAIL] full(id=%#x) 非目标应同 orig (%d, %#x) 实得 (%d, %#x)"
                      % (cid, r2, c2, r1, c1))
    if f_fail == 0:
        print("  [OK] full 除目标四维外逐项同 orig；0x130..0x133 均 (ret=0, conv=id)")
    else:
        fails.append("full 差 %d 例" % f_fail)

    # ---- D. 日志桩计数 ----
    print("\n########## D. 拒收路径日志计数（每拒收恰一次） ##########")
    for v, lc in (("orig", log_o), ("step1", log_s), ("full", log_f)):
        exp = LOG_EXPECT[v]
        ok = lc == exp
        print("  [%s] %-5s 计数 = %d（期望 %d）" % ("OK  " if ok else "FAIL", v, lc, exp))
        if not ok:
            fails.append("%s 日志计数 %d != %d" % (v, lc, exp))

    # ---- 总差分表（紧凑） ----
    print("\n########## 差分总表（64 cases） ##########")
    print("  %-6s | %-13s | %-13s | %-13s | 判定" % ("id", "orig r/c", "step1 r/c", "full r/c"))
    for i in range(NCASE_EXPECT):
        cid = cases_o[i][0]
        _, r2, c2 = cases_s[i]
        _, r1, c1 = cases_o[i]
        _, r3, c3 = cases_f[i]
        tag = ""
        if cid in TARGETS:
            tag = "★目标"
        if (r1, c1) != expect_behavior("orig", cid)[:2]:
            tag += " ORIG!" 
        print("  %#06x | %4d / %#06x | %4d / %#06x | %4d / %#06x | %s"
              % (cid, r1, c1, r2, c2, r3, c3, tag))

    print()
    if fails:
        print("==== 总判定: FAIL —— %s ====" % "；".join(fails))
        return 1
    print("==== 总判定: PASS —— 3 版本 × 64 例全绿；full 的唯一行为差异 = 0x130..0x133 放行 ====")
    return 0


if __name__ == "__main__":
    sys.exit(main())
