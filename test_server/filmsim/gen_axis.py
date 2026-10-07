#!/usr/bin/env python
"""gen_axis.py — 生成不同【轴顺序】的 identity LUT，用于定位硬件的真实轴序

★ 2026-10-07 上午的关键推理
  现象：17³ 和 33³ 的 identity 表灌进去，症状【完全一样】—— 都是
        品红/绿分离 + 严重色阶断裂，且机身颜色正常。
  ⇒ 排除"表尺寸不足"
  ⇒ ★★★ 指向【轴顺序错】：identity 表在任何正确解释下都不该有断裂
  ⇒ 断裂 = 查表读到了错位的偏移 = 三维的排列顺序与硬件期望不符

★ 关键假设
  我一直假设 linear index = idx0 + idx1*n + idx2*n*n （idx0 最快）
  但 ISP 的 3D LUT 惯例是 **Y 变化最慢**（Y 空间平滑，便于压缩）
  ⇒ 若硬件是 (Y慢, Cb中, Cr快)，而我写的是 (Y快, Cb中, Cr慢)
  ⇒ ★★ Y 与 Cb/Cr 被互换 ⇒ 亮度变成色度 ⇒ 品红/绿 + 断裂

★ 6 种排列一次性定位
  运行: python gen_axis.py --selftest
        python gen_axis.py <outdir>
"""
import sys
import os

N = 17
BYTES = N * N * N * 3 * 2

AXES = [(0, 1, 2), (1, 0, 2), (2, 1, 0),
        (2, 0, 1), (1, 2, 0), (0, 2, 1)]

AX_NAME = {0: 'Y', 1: 'Cb', 2: 'Cr'}


def iter_nodes(perm, n=N):
    """按 perm 生成 (线性索引, (i0,i1,i2)) 序列
       perm[k] = 维度 k 的权重位（0=最快，2=最慢）
    """
    # 嵌套顺序：从最慢维到最快维
    order = sorted(range(3), key=lambda k: perm[k], reverse=True)
    idx = [0, 0, 0]
    # 显式三层循环（3! = 6 种，展开最清晰且无递归开销）
    s0, s1, s2 = order
    for v0 in range(n):
        idx[s0] = v0
        for v1 in range(n):
            idx[s1] = v1
            for v2 in range(n):
                idx[s2] = v2
                # 线性索引 = Σ idx[k] * n**perm[k]
                lin = (idx[0] * (n ** perm[0]) +
                       idx[1] * (n ** perm[1]) +
                       idx[2] * (n ** perm[2]))
                yield lin, (idx[0], idx[1], idx[2])


def q16(v, n=N):
    return int(v / (n - 1.0) * 65535.0 + 0.5)


def gen_perm(perm, n=N):
    """生成该轴序下的 identity 表"""
    out = bytearray(BYTES)
    for lin, idx in iter_nodes(perm, n):
        base = lin * 6
        for ch in range(3):
            q = q16(idx[ch], n)
            out[base + ch * 2] = q & 0xff
            out[base + ch * 2 + 1] = (q >> 8) & 0xff
    return bytes(out)


def describe(perm):
    f = [AX_NAME[perm[0]], AX_NAME[perm[1]], AX_NAME[perm[2]]]
    return '%s最快 → %s → %s最慢' % (f[0], f[1], f[2])


def selftest():
    print('=== gen_axis 自测 ===')
    ok = True

    print('  [1] identity 语义校验（每位置的三通道值 = 该位置的三个网格坐标）')
    for perm in AXES:
        d = gen_perm(perm)
        if len(d) != BYTES:
            print('    perm=%s 长度 %d ★FAIL' % (perm, len(d)))
            ok = False
            continue
        bad = 0
        for lin, idx in iter_nodes(perm):
            for ch in range(3):
                q = d[lin * 6 + ch * 2] | (d[lin * 6 + ch * 2 + 1] << 8)
                if q != q16(idx[ch]):
                    bad += 1
        print('    perm=%-10s %-28s 不符 %d %s'
              % (perm, describe(perm), bad, 'OK' if bad == 0 else 'FAIL'))
        if bad:
            ok = False

    print('\n  [2] 各排列的前 5 个节点（应只有"最快维"在变）')
    for perm in AXES:
        d = gen_perm(perm)
        rows = []
        for lin, idx in iter_nodes(perm):
            if len(rows) >= 5:
                break
            q = [d[lin * 6 + c * 2] | (d[lin * 6 + c * 2 + 1] << 8)
                 for c in range(3)]
            rows.append([round(v / 65535.0 * 16) for v in q])
        print('    perm=%-10s %s' % (perm, rows))

    print('\n  [3] 端点检查')
    for perm in AXES[:1]:
        d = gen_perm(perm)
        print('    全零位置数=%d（应= 1，只有一个角）'
              % sum(1 for i in range(0, BYTES, 6) if d[i:i + 6] == b'\x00' * 6))
        print('    全FF位置数=%d（应= 1）'
              % sum(1 for i in range(0, BYTES, 6) if d[i:i + 6] == b'\xff' * 6))

    print('=== 自测%s ===' % ('通过' if ok else '失败'))
    return ok


if __name__ == '__main__':
    if '--selftest' in sys.argv[1:] or len(sys.argv) < 2:
        selftest()
        sys.exit(0)

    outdir = sys.argv[1]
    os.makedirs(outdir, exist_ok=True)
    for i, perm in enumerate(AXES):
        d = gen_perm(perm)
        name = 'ax%d_%d%d%d' % (i, perm[0], perm[1], perm[2])
        p = os.path.join(outdir, name + '.bin')
        open(p, 'wb').write(d)
        print('%-10s perm=%-10s %-28s %d 字节'
              % (name, perm, describe(perm), len(d)))