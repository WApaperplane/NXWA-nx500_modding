#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ramp.py —— 【阶梯探针表】：一次定位硬件 LUT 的中性值与值域

★★★ 起因（2026-10-07）
  单色填充实验三张结果：
    0x0000 → 粉红/洋红
    0xFFFF → 青绿/品偏
    0x8000 → 品红← 不是中性！
  ⇒ 值域不是 [0,1] 均匀映射，中性点未知
  ⇒ 逐张试常量太慢（本项目已证明：每张都要用户肉眼判读）

★★★ 本表设计（★ 一次实验出答案）
  把表按索引顺序分成 17 段（第 3 维最慢），每段填一个不同常量。
  画面会显示一条 **17 步颜色渐变带**：
    ・哪一段最接近"无色偏" ⇒ 那一段就是中性点
    ・整条带的色相走向  ⇒ 直接读出 Cb / Cr 的相对关系
    ・带子有几处突变    ⇒ 提示索引轴顺序或段边界
  ⇒ 不需要逐张测试，一次看图就能定位

★★★ 为什么有效
  LUT 的语义是"索引 → 输出"。这里每个节点的三个通道都填同一常量，
  所以不管索引是什么，输出都是那个常量 ⇒ 画面颜色 = 常量的颜色映射
  ⇒ 渐变带的颜色序列 = 硬件值域 → 颜色 的完整查找表
"""
import os
import sys

N = 17                      # 硬件 17 级（已由 29478 字节 / (17^3*6) 交叉验证）
NODE_BYTES = 6              # 每节点 3 通道 × u16
TOTAL = N ** 3 * NODE_BYTES  # 29478


def build_ramp(levels=None):
    """每段填一个常量；段边界沿第3 维（最慢轴）切分"""
    if levels is None:
        # 17 段，均匀覆盖 0..65535
        levels = [int(i * 65535 / (N - 1)) for i in range(N)]
    out = bytearray()
    per = N * N * NODE_BYTES       # 每段 = 一个 b 平面 = 17*17 个节点
    assert per * N == TOTAL, (per, N, TOTAL)
    for lv in levels:
        blk = bytearray()
        for _ in range(N * N):
            blk += (lv & 0xff).to_bytes(1, 'little')
            blk += ((lv >> 8) & 0xff).to_bytes(1, 'little')
            blk += (lv & 0xff).to_bytes(1, 'little')
            blk += ((lv >> 8) & 0xff).to_bytes(1, 'little')
            blk += (lv & 0xff).to_bytes(1, 'little')
            blk += ((lv >> 8) & 0xff).to_bytes(1, 'little')
        out += blk
    return bytes(out), levels


def build_ramp8(levels=None):
    """8bit 版：每节点 3×u8（若硬件是8bit 分辨率）
    ★ 段数由 levels 决定，每段 = 17*17 个节点 = 289 节点 × 3 字节"""
    if levels is None:
        levels = [int(i * 255 / 7) for i in range(8)]
    out = bytearray()
    per = N * N * 3          # 每段 289 节点 × 3 字节
    for lv in levels:
        out += bytes([lv & 0xff]) * per
    return bytes(out), levels


def selftest():
    ok = True
    print("=== ramp 自检 ===")

    d, lv = build_ramp()
    good = len(d) == TOTAL
    ok &= good
    print("  ramp16 长度 %d (期望 %d) %s" % (len(d), TOTAL, "OK" if good else "FAIL"))
    if not good:
        return False

    # 段边界必须严格递增
    mono = all(lv[i] < lv[i + 1] for i in range(len(lv) - 1))
    ok &= mono
    print("  17 段常量递增 = %s" % mono)
    if not mono:
        return False
    print("  段常量: %s" % " ".join("0x%04x" % v for v in lv))
    print("  ★ 若硬件值域含中性点，它一定落在【某一段】里")

    # 逐字节核对第 0 段前 6 字节
    exp = b'\x00\x80' * 3# 0x8000 LE
    got = d[0:6]
    e2 = (lv[0] & 0xff).to_bytes(2, 'little') * 3
    g_ok = (got == e2)
    ok &= g_ok
    print("  段0 前 6 字节 = %s (期望 %s) %s"
          % (" ".join("%02x" % x for x in got),
             " ".join("%02x" % x for x in e2), "OK" if g_ok else "FAIL"))

    # 第 16 段应为 0xFFFF
    tail = d[-6:]
    t_ok = (tail == b'\xff\xff' * 3)
    ok &= t_ok
    print("  末段 后 6 字节 = %s (期望 ffffffff ffff) %s"
          % (" ".join("%02x" % x for x in tail), "OK" if t_ok else "FAIL"))

    # 8bit 版
    d8, lv8 = build_ramp8()
    g8 = len(d8) == len(lv8) * N * N * 3
    ok &= g8
    print("  ramp8 长度 %d (期望 %d) %s" % (len(d8), len(lv8) * N * N * 3,
                                           "OK" if g8 else "FAIL"))

    print("=== %s ===" % ("全部通过" if ok else "★ 有失败"))
    return ok


def gen(outdir):
    os.makedirs(outdir, exist_ok=True)
    out = []

    d, lv = build_ramp()
    p = os.path.join(outdir, "ramp16.bin")
    open(p, 'wb').write(d)
    out.append(("ramp16.bin", p, len(d), "17 段 u16 渐变 %s" %
                " ".join("0x%02x" % v for v in lv[::4])))

    # ★★重点：16 级稀疏版（更容易数出段数）
    d2, lv2 = build_ramp([int(i * 65535 / 15) for i in range(16)])
    p2 = os.path.join(outdir, "ramp16x16.bin")
    open(p2, 'wb').write(d2)
    out.append(("ramp16x16.bin", p2, len(d2), "16 段 u16"))

    d3, lv3 = build_ramp8()
    p3 = os.path.join(outdir, "ramp8.bin")
    open(p3, 'wb').write(d3)
    out.append(("ramp8.bin", p3, len(d3), "8 段 u8"))

    print("=== 生成阶梯探针 ===")
    for fn, path, n, desc in out:
        print("  %-16s %6d 字节  %s" % (fn, n, desc))
    print()
    print("★ 判读：")
    print("  画面出现【渐变色带】⇒ 硬件在消费这张表（表语义确认）")
    print("  带中最接近无色偏的那一段 ⇒ 中性点常量值")
    print("  带子整体偏 ⇒ 索引轴顺序或值域仍需修正")
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
