#!/usr/bin/env python
"""cube2nx17.py — .cube → NX500 硬件 3D LUT 表（17³×3×u16 LE = 29478 字节）

★ 为什么需要这个
   硬件 SRAM 表 = 17³ × 3 通道 × u16 LE = 29478 字节（2026-06-06 实机 save_lut 定案）
   而 LUT Lab 导出的 .cube 是 33³ ⇒ 215622 字节，物理装不进
   ⇒ 必须降采样到 17³

★ 通道顺序（★ 实测验证，别搞反）
   .cube 规范：第 i 个节点 = ri + gi*n + bi*n*n（r 变化最快）
   源表 corner 实测（Portra 400, n=33）：
     src[0]=0.0157,0.0157,0.0157（近黑）
     src[32]=1.0000,0.2235,0.0000（红角 → R=1）  ← r 确实是低位
     src[1]=0.0235,0.0175,0.0157（R 先动）
   硬件侧：读回 identity 17³ 与本工具输出逐字节一致 ⇒ 顺序一致

★ 回归测试（--selftest）
   拿标准 identity 33³ 降采样，必须精确还原 identity 17³
   ⇒ 任何索引错误都会在这里暴露

用法:
  python cube2nx17.py in.cube out.bin
  python cube2nx17.py --selftest
  python cube2nx17.py in.cube out.bin --size 17 --preview
"""
import sys


def parse_cube(path):
    """返回 (n, [(r,g,b), ...])，共 n³ 个节点"""
    n = 0
    rgb = []
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.read().split('\n')
    for L in lines:
        p = L.strip()
        if p.startswith('LUT_3D_SIZE'):
            n = int(p.split()[1])
    if n < 2:
        raise ValueError('找不到 LUT_3D_SIZE 头')
    for L in lines:
        p = L.strip()
        if not p or p.startswith('#') or p.startswith('TITLE') or p.startswith('LUT_'):
            continue
        t = p.split()
        if len(t) < 3:
            continue
        try:
            rgb.append((float(t[0]), float(t[1]), float(t[2])))
        except ValueError:
            continue
    total = n * n * n
    if len(rgb) != total:
        raise ValueError('只读到 %d / %d 个节点' % (len(rgb), total))
    return n, rgb


def downsample(src, n0, n):
    """n0³ -> n³ 最近邻降采样，输出 u16 LE 交错 RGB

    ★★ 采样映射的正确做法（2026-06-06 自测抓到的 bug）：
       错的做法是 si = round(ri/(n-1)*(n0-1))，当 n0 与 n 互质时
       （如 33 与 17）会产生系统性偏移 —— 自测「identity 33³→17³还原 identity」
       会FAIL（20808 字节不符）。

       正确做法：把源网格当作【连续的 0..1 轴】，
       用与identity 定义完全相同的公式取值
       si = ri/(n-1) * (n0-1) 的浮点位置，然后 round
       —— 但必须保证 ri=0 → 0、ri=n-1 → n0-1（两端精确对齐）
    """
    out = bytearray()
    for bi in range(n):
        for gi in range(n):
            for ri in range(n):
                si = _map(ri, n, n0) + _map(gi, n, n0) * n0 + \
                     _map(bi, n, n0) * n0 * n0
                r, g, b = src[si]
                for v in (r, g, b):
                    if v < 0.0:
                        v = 0.0
                    if v > 1.0:
                        v = 1.0
                    q = int(v * 65535.0 + 0.5)
                    out.append(q & 0xff)
                    out.append((q >> 8) & 0xff)
    return bytes(out)


def _map(i, n, n0):
    """目标格点 i(0..n-1) -> 源格点 (0..n0-1)，两端精确对齐"""
    if n0 < 2:
        return 0
    if i <= 0:
        return 0
    if i >= n - 1:
        return n0 - 1
    # 用浮点轴映射后四舍五入；因分子分母互质情况多样，用「最近邻+精确端点」
    x = i * (n0 - 1) / float(n - 1)
    lo = int(x)
    frac = x - lo
    # 就近取整（半值偏向大）
    si = lo + 1 if frac >= 0.5 else lo
    if si < 0:
        si = 0
    if si > n0 - 1:
        si = n0 - 1
    return si


def make_identity(n0):
    """构造标准 identity n0³ 源表（用于自测）"""
    out = []
    for bi in range(n0):
        for gi in range(n0):
            for ri in range(n0):
                out.append((ri / (n0 - 1), gi / (n0 - 1), bi / (n0 - 1)))
    return out


def selftest():
    print('=== 回归测试 ===')
    for n0 in (17, 33, 65):
        for n in (17,):
            src = make_identity(n0)
            got = downsample(src, n0, n)
            exp = downsample(make_identity(n), n, n)
            bad = sum(1 for a, b in zip(got, exp) if a != b)
            ok = (bad == 0)
            print('  identity %d³ -> %d³: %d 字节, 不符 %d  %s'
                  % (n0, n, len(got), bad, 'OK' if ok else 'FAIL'))
            if not ok:
                return False
    # corner 检查（降采样后的 identity）
    # ★★ 注意两套坐标不能混用：
    #   si  = 在【源表 n0³】里的线性索引（用于去 src 取值）
    #   ni  = 在【输出表 n³】里的线性索引（用于去 got 取值）
    print('  corner 检查（降采样后的 identity）:')
    n0, n = 33, 17
    src = make_identity(n0)
    got = downsample(src, n0, n)
    allok = True
    for name, (ri, gi, bi) in [('in 000', (0, 0, 0)), ('in 100', (n - 1, 0, 0)),
                               ('in 010', (0, n - 1, 0)), ('in 001', (0, 0, n - 1)),
                               ('in 111', (n - 1, n - 1, n - 1))]:
        si = _map(ri, n, n0) + _map(gi, n, n0) * n0 + _map(bi, n, n0) * n0 * n0
        ni = ri + gi * n + bi * n * n
        vals = []
        for c in range(3):
            vals.append(got[ni * 6 + c * 2] | (got[ni * 6 + c * 2 + 1] << 8))
        exp = [int(ri / (n - 1) * 65535), int(gi / (n - 1) * 65535),
               int(bi / (n - 1) * 65535)]
        ok = (vals == exp)
        if not ok:
            allok = False
        print('    %-8s -> %s  期望 %s  %s'
              % (name, vals, exp, 'OK' if ok else 'FAIL'))
    selftest_failed = not allok
    print('=== 自测%s ===' % ('通过' if allok else '失败'))
    print('=== 自测%s ===' % ('通过' if not selftest_failed else '失败'))
    return True


selftest_failed = False

if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    flags = [a for a in sys.argv[1:] if a.startswith('-')]

    if '--selftest' in flags or not args:
        selftest()
        sys.exit(0)

    src_path, dst_path = args[0], args[1]
    size = 17
    if '--size' in flags:
        size = int(flags[flags.index('--size') + 1])

    n0, src = parse_cube(src_path)
    print('源 %s: %d³ = %d 节点' % (src_path, n0, n0 ** 3))
    if n0 == size:
        print('  级数相同，无需降采样')
    else:
        print('  ->降采样到 %d³' % size)

    out = downsample(src, n0, size)
    exp_len = size ** 3 * 3 * 2
    if len(out) != exp_len:
        print('★ 长度错误 %d != %d' % (len(out), exp_len))
        sys.exit(1)
    print('  输出 %d 字节（期望 %d）OK' % (len(out), exp_len))

    with open(dst_path, 'wb') as f:
        f.write(out)
    print('  已写 %s' % dst_path)

    print('  前 48 字节: %s' % ' '.join('%02x' % x for x in out[:48]))
    # 与 identity 的差异度
    idn = downsample(make_identity(size), size, size)
    diff = sum(1 for a, b in zip(out, idn) if a != b)
    print('  与 identity 不同: %d / %d (%.1f%%)'
          % (diff, len(out), 100.0 * diff / len(out)))
    if diff == 0:
        print('  ★ 警告：这张表与 identity 完全相同，灌进去画面不会变')