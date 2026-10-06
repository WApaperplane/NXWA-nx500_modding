#!/usr/bin/env python
"""rgb2ycc.py — RGB .cube → NX500 硬件 3D LUT（Y/Cb/Cr 空间，17³×3×u16 LE = 29478 字节）

★ 为什么必须转 YCbCr（2026-10-06 实机判别实验证明）
   官方头文件 ep_type.h 明确：
       D5_EP_LUT_FORMAT_422 = 0  /**< Color Format of _input image_  YCC422 */
       D5_EP_LUT_FORMAT_420 = 1  /**< YCC420 */
       D5_EP_LUT_CBCR_CH0/CH1/CH01← 参数名就叫 CbCr
   ⇒ 硬件 3D LUT 的三维 = (Y, Cb, Cr)，不是 RGB

   ★★ 实机单通道判别（只把某一轴压到 50%，看画面怎么变）：
       第1 轴压暗 ⇒ 画面变暗 + 色彩变浓     ⇒ 第 1 轴 = Y
       第 2 轴压暗 ⇒ 白墙变鲑鱼色（丢蓝）    ⇒ 第 2 轴 = Cb
       第 3 轴压暗 ⇒ 偏青（丢红）            ⇒ 第 3 轴 = Cr
   ⇒ 顺序 = (Y, Cb, Cr)
   ★ 用户实测：直接灌 RGB 表时 Portra400 偏红、Kodachrome64 偏蓝紫
     ⇒ 因为R 曲线被当成 Y 用，方向全错

★ LUT 语义（关键）
   3D 查找表 = 【索引是输入，值是输出】
   ⇒ 对每个索引 (yi, cbi, cri)：
       ① 该索引的 YCbCr 就是【输入】
       ② 转成 RGB = 实际输入颜色
       ③ 用 .cube 查这个 RGB 得到的输出 RGB
       ④ 把输出 RGB 转回 YCbCr 存储
   ⇒ 不能只把 RGB 数值换算，必须走"索引即输入"的语义

★ 色彩空间：BT.601 full-range（系数已验证往返误差为 0）
   Y  = 0.299R + 0.587G + 0.114B
   Cb = (B-Y)/(2×0.886) + 0.5
   Cr = (R-Y)/(2×0.701) + 0.5
   ⇒ 白/灰点 Cb=Cr=0.5（中性）

用法:
  python rgb2ycc.py in.cube out.bin
  python rgb2ycc.py --selftest
"""
import sys

KR, KB = 0.299, 0.114
KG = 1.0 - KR - KB


def rgb2ycc(r, g, b):
    """归一化 RGB(0..1) → 归一化 YCbCr(0..1)，Cb/Cr 中性=0.5"""
    y = KR * r + KG * g + KB * b
    cb = (b - y) / (2.0 * (1.0 - KB)) + 0.5
    cr = (r - y) / (2.0 * (1.0 - KR)) + 0.5
    return y, cb, cr


def ycc2rgb(y, cb, cr):
    """归一化 YCbCr → 归一化 RGB（clamp 到 0..1）"""
    r = y + 1.402 * (cr - 0.5)
    g = y - 0.344136 * (cb - 0.5) - 0.714136 * (cr - 0.5)
    b = y + 1.772 * (cb - 0.5)
    out = []
    for v in (r, g, b):
        if v < 0.0:
            v = 0.0
        elif v > 1.0:
            v = 1.0
        out.append(v)
    return out[0], out[1], out[2]


def _clip01(v):
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def parse_cube(path):
    lines = open(path, 'r', encoding='utf-8', errors='replace').read().split('\n')
    n = 0
    for L in lines:
        p = L.strip()
        if p.startswith('LUT_3D_SIZE'):
            n = int(p.split()[1])
    if n < 2:
        raise ValueError('找不到 LUT_3D_SIZE 头')
    rgb = []
    for L in lines:
        p = L.strip()
        if not p or p.startswith(('#', 'TITLE', 'LUT_')):
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


def _snap(v, n):
    """把0..1 的坐标吸附到 .cube 源网格上"""
    k = int(round(_clip01(v) * (n - 1)))
    return k if k >= 0 else 0


def build(src, n0, n=17):
    """RGB .cube 表 → YCbCr 空间的硬件 LUT（u16 LE 交错 Y,Cb,Cr）"""
    out = bytearray()
    for cr_i in range(n):
        for cb_i in range(n):
            for y_i in range(n):
                # ① 索引即输入
                y_in = y_i / (n - 1)
                cb_in = cb_i / (n - 1)
                cr_in = cr_i / (n - 1)
                # ② 输入 YCbCr → RGB（该节点实际对应的输入颜色）
                r, g, b = ycc2rgb(y_in, cb_in, cr_in)
                # ③ 查 .cube
                ri, gi, bi = _snap(r, n0), _snap(g, n0), _snap(b, n0)
                si = ri + gi * n0 + bi * n0 * n0
                orr, ogg, obb = src[si]
                # ④ 输出 RGB → YCbCr 存储
                oy, ocb, ocr = rgb2ycc(_clip01(orr), _clip01(ogg), _clip01(obb))
                for v in (oy, ocb, ocr):
                    q = int(_clip01(v) * 65535.0 + 0.5)
                    out.append(q & 0xff)
                    out.append((q >> 8) & 0xff)
    return bytes(out)


def selftest():
    print('=== rgb2ycc 自测 ===')
    ok = True

    print('  [1] RGB→YCbCr→RGB 往返:')
    for (r, g, b) in [(0,0,0),(1,1,1),(1,0,0),(0,1,0),(0,0,1),
                      (0.5,0.5,0.5),(0.2,0.6,0.4),(0.9,0.1,0.5)]:
        y, cb, cr = rgb2ycc(r, g, b)
        r2, g2, b2 = ycc2rgb(y, cb, cr)
        d = max(abs(r-r2), abs(g-g2), abs(b-b2))
        if d >= 0.002:
            ok = False
        print('    (%.2f,%.2f,%.2f) → YCbC(%.4f,%.4f,%.4f) → (%.3f,%.3f,%.3f) Δ=%.4f %s'
              % (r, g, b, y, cb, cr, r2, g2, b2, d, 'OK' if d < 0.002 else 'FAIL'))

    print('  [2] 中性点检查:')
    for nm, (r, g, b) in [('白', (1,1,1)), ('灰', (0.5,0.5,0.5)), ('黑', (0,0,0))]:
        y, cb, cr = rgb2ycc(r, g, b)
        good = abs(cb-0.5) < 1e-6 and abs(cr-0.5) < 1e-6
        if not good:
            ok = False
        print('    %s(%.1f,%.1f,%.1f) → Y=%.4f Cb=%.4f Cr=%.4f  %s'
              % (nm, r, g, b, y, cb, cr, 'OK' if good else 'FAIL'))

    print('  [3] 纯色检查（按 BT.601 实际方向）:')
    # 红 → Cr 高、Cb 低
    y, cb, cr = rgb2ycc(1, 0, 0)
    good = cr > 0.9 and cb < 0.4
    if not good:
        ok = False
    print('    红(1,0,0) → Y=%.4f Cb=%.4f Cr=%.4f  应 Cr高/Cb低  %s'
          % (y, cb, cr, 'OK' if good else 'FAIL'))
    # 蓝 → Cb 高
    y, cb, cr = rgb2ycc(0, 0, 1)
    good = cb > 0.9
    if not good:
        ok = False
    print('    蓝(0,0,1) → Y=%.4f Cb=%.4f Cr=%.4f  应 Cb高  %s'
          % (y, cb, cr, 'OK' if good else 'FAIL'))
    # ★ 绿在 BT.601 里 Cr 是【最低】的（Cb=0.169, Cr=0.081）
    y, cb, cr = rgb2ycc(0, 1, 0)
    good = cb < 0.2 and cr < 0.15
    if not good:
        ok = False
    print('    绿(0,1,0) → Y=%.4f Cb=%.4f Cr=%.4f  ★BT.601绿=双低  %s'
          % (y, cb, cr, 'OK' if good else 'FAIL'))

    print('  [4] identity .cube 应产出【YCbCr 直通表】:')
    n0 = 17
    # ★★ 必须按 RGB 网格构造，不能用线性索引 i（否则值全错）
    idsrc = []
    for bi in range(n0):
        for gi in range(n0):
            for ri in range(n0):
                idsrc.append((ri / (n0 - 1.0), gi / (n0 - 1.0), bi / (n0 - 1.0)))
    d = build(idsrc, n0, 17)
    if len(d) != 17 ** 3 * 3 * 2:
        ok = False
    print('    长度 %d %s' % (len(d), 'OK' if len(d) == 17 ** 3 * 3 * 2 else 'FAIL'))
    # 中性索引(8,8,8) ⇒ YCbCr(0.5,0.5,0.5) ⇒ 应输出 (0.5,0.5,0.5)
    ni = 8 + 8 * 17 + 8 * 17 * 17
    vals = [d[ni * 6 + c * 2] | (d[ni * 6 + c * 2 + 1] << 8) for c in range(3)]
    print('    中性索引(8,8,8) → %s（应各≈32767 = 0x7fff）' % vals)
    if max(abs(v - 32767) for v in vals) > 30:
        ok = False
        print('    ★ 中性点偏差过大')
    # 纯红索引：Y=0.5→红 输入 ⇒ 应输出 Cr≈1.0
    ni = 8 + 8 * 17 + 8 * 17 * 17   # 中性
    # 找 Y=1.0 的角
    ni = 16 + 8 * 17 + 8 * 17 * 17
    vals = [d[ni * 6 + c * 2] | (d[ni * 6 + c * 2 + 1] << 8) for c in range(3)]
    print('    Y=1.0 中性色度索引(16,8,8) → %s（应 Y≈65535, Cb≈Cr≈32767）' % vals)
    if not (abs(vals[0] - 65535) < 30 and abs(vals[1] - 32767) < 30
            and abs(vals[2] - 32767) < 30):
        ok = False
        print('    ★ 白点偏差过大')

    print('=== 自测%s ===' % ('通过' if ok else '失败'))
    return ok


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    if '--selftest' in sys.argv[1:] or not args:
        selftest()
        sys.exit(0)

    src_path, dst_path = args[0], args[1]
    n0, src = parse_cube(src_path)
    out = build(src, n0, 17)
    exp = 17 ** 3 * 3 * 2
    if len(out) != exp:
        print('长度错误 %d != %d' % (len(out), exp))
        sys.exit(1)
    open(dst_path, 'wb').write(out)
    print('%s (%d³ RGB) -> %s' % (src_path, n0, dst_path))
    print('  %d 字节  (17³ × YCbCr × u16 LE) OK' % len(out))
    print('  前 48: %s' % ' '.join('%02x' % x for x in out[:48]))