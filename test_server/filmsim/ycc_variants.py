#!/usr/bin/env python
"""ycc_variants.py — 生成多套候选 identity LUT，用于实机判定硬件的真实布局

★ 为什么要这个
   实机灌YCbCr 版 Portra400 后取景器出现【洋红/绿分离 + 色阶断裂】，
   比 RGB 版更糟 ⇒ 说明我的 YCbCr 转换在某处错了。
   ⇒ 但不能靠猜，必须让硬件自己告诉我们答案。

★ 判据原理
   identity 表在【正确的布局】下必然【零色彩变化】。
   ⇒ 灌 identity 看是否中性，就能一刀切开假设空间：
       中性 ⇒ 布局对、范围对，问题在转换函数
       非中性 ⇒ 布局或数值范围错

★ 候选布局（全部输出 29478 字节）
   A: interleaved (Y,Cb,Cr)，Y 变化最快，full-range
   B: planar（Y 平面 / Cb 平面 / Cr 平面），Y 变化最快
   C: interleaved (Cr,Cb,Y) 反序，full-range
   D: planar + studio swing（Y 16..235, C 16..240）
   E: interleaved (Cb,Cr,Y)（Cb 打头，EP 参数名的顺序）

用法:
  python ycc_variants.py --gen   # 生成全部到 verify/
  python ycc_variants.py --show  # 只打印各变体的角点值
"""
import os

N = 17
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   '..', 'sysarch', 'verify')

KR, KB = 0.299, 0.114
KG = 1.0 - KR - KB


def rgb2ycc(r, g, b):
    y = KR * r + KG * g + KB * b
    cb = (b - y) / (2.0 * (1.0 - KB)) + 0.5
    cr = (r - y) / (2.0 * (1.0 - KR)) + 0.5
    return y, cb, cr


def q(v):
    """16 位量化，带 clamp"""
    if v < 0.0:
        v = 0.0
    elif v > 1.0:
        v = 1.0
    return int(v * 65535.0 + 0.5)


def q_studio(v, ch):
    """studio swing 量化：Y 16..235，C 16..240"""
    if ch == 0:
        lo, hi = 16.0 / 255.0, 235.0 / 255.0
    else:
        lo, hi = 16.0 / 255.0, 240.0 / 255.0
    if v < 0.0:
        v = 0.0
    elif v > 1.0:
        v = 1.0
    return int((lo + v * (hi - lo)) * 65535.0 + 0.5)


def gen_interleaved(axis_order, studio=False):
    """axis_order: (0,1,2) 指出 内存三元组里第 0/1/2 位放哪���通道
       通道 0=Y 1=Cb 2=Cr。索引按 Y 变化最快遍历。
    """
    out = bytearray()
    for cr_i in range(N):
        for cb_i in range(N):
            for y_i in range(N):
                ycc = [y_i / (N - 1.0), cb_i / (N - 1.0), cr_i / (N - 1.0)]
                triple = [ycc[a] for a in axis_order]
                for c, v in enumerate(triple):
                    qq = q_studio(v, c) if studio else q(v)
                    out.append(qq & 0xff)
                    out.append((qq >> 8) & 0xff)
    return bytes(out)


def gen_planar(studio=False):
    """planar：三个平面顺序排列，Y 平面在前"""
    planes = [[], [], []]
    for cr_i in range(N):
        for cb_i in range(N):
            for y_i in range(N):
                planes[0].append(y_i / (N - 1.0))
                planes[1].append(cb_i / (N - 1.0))
                planes[2].append(cr_i / (N - 1.0))
    out = bytearray()
    for c in range(3):
        for v in planes[c]:
            qq = q_studio(v, c) if studio else q(v)
            out.append(qq & 0xff)
            out.append((qq >> 8) & 0xff)
    return bytes(out)


def show(name, d, n=3):
    print('  %-22s len=%d  前6节点: %s' % (
        name, len(d), ' '.join('%02x' % x for x in d[:6 * n])))


if __name__ == '__main__':
    variants = {
        'idA_ycc_inter':   gen_interleaved((0, 1, 2)),
        'idB_ycc_planar':  gen_planar(),
        'idC_cry_inter':   gen_interleaved((2, 1, 0)),
        'idD_studio':      gen_interleaved((0, 1, 2), studio=True),
        'idE_cbcy_inter':  gen_interleaved((1, 2, 0)),
    }
    print('=== identity 候选表（正确布局下应零色彩变化）===')
    for k, v in variants.items():
        show(k, v)
        p = os.path.join(OUT, k + '.bin')
        open(p, 'wb').write(v)
    print()
    print('已写入 %s' % os.path.abspath(OUT))
    print()
    print('★ 上机顺序建议：先A（我的假设），再 B（planar），再 D（studio）')
    print('   哪一个【完全无色彩变化】，哪个就是正确布局')