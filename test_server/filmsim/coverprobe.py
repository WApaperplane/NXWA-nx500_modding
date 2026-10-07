#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
coverprobe.py —— 用"全零/全FF 覆盖探针"测硬件表的真实长度与覆盖行为

★★★ 动机（2026-10-07 木一提出）
  "每次要单独测试，我怀疑数据无法覆盖"
  ⇒ 若硬件表比写入的长，则每次只覆盖前一段，后面是上次残留
  ⇒ 所有实验都被污染 ⇒ 必须先测出【真实表长】与【是否完整覆盖】

★★★ 为什么全零表能绕过"格式未知"问题
  全零表在任何轴序/通道/节点布局下都是同一张表（0 就是 0）
  ⇒ 不需要知道格式，只需要看画面

★★★ 三种探针
  zero : 全部 0x00→ 期望纯黑
  ff   : 全部 0xFF          → 期望纯白
  half : 前半 0xFF 后半 0x00  → 期望【边界处出现分界】
         ★ 这张能直接读出表长：分界线位置 = 表的真实长度

用法:
  python coverprobe.py --gen  <outdir>              # 生成全部探针
  python coverprobe.py --selftest# 自检
"""
import os
import sys

# 候选表长（17 级为主，附带 33 级与更大）
N17 = 17 ** 3          # 4913
N33 = 33 ** 3          # 35937
BYTES_17x3x1 = N17 * 3        # 14739  RGB×u8
BYTES_17x3x2 = N17 * 3 * 2    # 29478  RGB×u16
BYTES_17x4x2 = N17 * 4 * 2    # 39304  RGBA×u16
BYTES_17x4x1 = N17 * 4        # 19652  RGBA×u8


def build(kind, total):
    """kind: 'zero' | 'ff' | 'half'"""
    half = total // 2
    if kind == 'zero':
        return b'\x00' * total
    if kind == 'ff':
        return b'\xff' * total
    if kind == 'half':
        return b'\xff' * half + b'\x00' * (total - half)
    raise ValueError(kind)


def selftest():
    ok = True
    print("=== coverprobe 自检 ===")

    # 1) 长度必须精确
    cases = [(N17 * 3, 14739), (N17 * 3 * 2, 29478), (N17 * 4, 19652),
             (N17 * 4 * 2, 39304)]
    for n, exp in cases:
        d = build('zero', n)
        good = len(d) == exp
        ok &= good
        print("  zero %-7d -> %-7d %s" % (n, len(d), "OK" if good else "FAIL"))

    # 2) half 表必须前半全FF、后半全 0
    n = BYTES_17x3x2
    h = build('half', n)
    mid = n // 2
    a_ok = all(x == 0xff for x in h[:mid])
    b_ok = all(x == 0x00 for x in h[mid:])
    ok &= a_ok and b_ok
    print("  half %-7d -> 前半FF=%s 后半00=%s" % (n, a_ok, b_ok))
    if not (a_ok and b_ok):
        print("    ★ half 构造错误")

    # 3) ★ 关键性质：full 表的前 N 字节 == 前缀，与 longer 表一致
    #    这让"逐步加长"实验可增量进行
    short = build('ff', 1024)
    long_ = build('ff', 4096)
    c_ok = long_[:1024] == short
    ok &= c_ok
    print("  前缀一致性 = %s（增量实验前提）" % c_ok)

    # 4) 探针与布局无关性证明：任意字节对齐下全零表都相同
    d1 = build('zero', 29478)
    d2 = bytearray(29478)
    same = (d1 == bytes(d2))
    ok &= same
    print("  全零表布局无关 = %s" % same)

    print("=== %s ===" % ("全部通过" if ok else "★ 有失败"))
    return ok


def gen(outdir):
    os.makedirs(outdir, exist_ok=True)
    probes = [
        # (文件名, kind, 长度, 说明)
        ("pz_14739.bin", 'zero', BYTES_17x3x1, "17^3x3xu8  全零"),
        ("pz_19652.bin", 'zero', BYTES_17x4x1, "17^3x4xu8  全零"),
        ("pz_29478.bin", 'zero', BYTES_17x3x2, "17^3x3xu16 全零"),
        ("pz_39304.bin", 'zero', BYTES_17x4x2, "17^3x4xu16 全零"),
        ("pf_29478.bin", 'ff',   BYTES_17x3x2, "17^3x3xu16 全FF"),
        ("ph_29478.bin", 'half', BYTES_17x3x2, "17^3x3xu16 前半FF后半00"),
    ]
    print("=== 生成覆盖探针 ===")
    for fn, kind, n, desc in probes:
        d = build(kind, n)
        p = os.path.join(outdir, fn)
        with open(p, 'wb') as f:
            f.write(d)
        print("  %-16s %7d 字节  %s" % (fn, len(d), desc))
    print()
    print("★ 判读：")
    print("  pz_* 画面【没全黑】⇒ 你的怀疑成立，表没被完整覆盖")
    print("  ph_* 分界线= 硬件表真实长度（前提：前半被覆盖）")
    return True


if __name__ == '__main__':
    arg = sys.argv[1] if len(sys.argv) > 1 else '--selftest'
    if arg == '--selftest':
        sys.exit(0 if selftest() else 1)
    elif arg == '--gen':
        outdir = sys.argv[2] if len(sys.argv) > 2 else '../sysarch/verify'
        sys.exit(0 if gen(outdir) else 1)
    else:
        print(__doc__)
        sys.exit(1)
