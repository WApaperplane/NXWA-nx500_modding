#!/usr/bin/env python
"""gen33.py — 生成 33³ identity LUT（215622 字节）用于验证表尺寸假设

★ 为什么做这个（2026-10-07）
  昨晚的自我否证：`save_lut` 读不出硬件表 ⇒ "表长 29478" 是自证循环的产物。
  ⇒ ★★ 最大的疑点：如果硬件表其实是 33³ = 215622 字节，
     那么我写的 29478 字节【只覆盖 1/8 的输入域】，其余是未初始化垃圾
     ⇒ ★★★ 这就能解释"所有表都偏色，连identity 都不中性"

★ 三张表一起生成，便于对比
  id33_u16.bin   33³ × 3 通道 × u16 LE = 215622   ★ 主候选
  id17_u16.bin   17³ × 3 通道 × u16 LE =  29478   （对照组，已知偏色）

★ 自带自测（铁律 69：PC 端先验证，再上机）
"""
import sys

N = 33
BYTES = N * N * N * 3 * 2


def gen_identity(n, stride=2):
    """标准 identity：第 i 个节点的第 c 通道 = 该通道网格坐标
    遍历顺序 r 最快→ g → b（与 .cube 规范一致）
    ★ 注意：identity 表与"哪个通道变快"无关——三通道数值全同，
       所以它同时是 interleaved/planar 通用的 identity。
    """
    out = bytearray()
    for b in range(n):
        for g in range(n):
            for r in range(n):
                for idx in (r, g, b):
                    q = int(idx / (n - 1.0) * 65535.0 + 0.5)
                    if stride == 2:
                        out.append(q & 0xff)
                        out.append((q >> 8) & 0xff)
                    else:
                        out.append(int(idx / (n - 1.0) * 255.0 + 0.5))
    return bytes(out)


def selftest():
    print('=== gen33 自测 ===')
    ok = True

    n = 33
    d = gen_identity(n)
    exp = n * n * n * 3 * 2
    print('  长度 %d（期望 %d）%s' % (len(d), exp,
          'OK' if len(d) == exp else 'FAIL'))
    if len(d) != exp:
        ok = False

    # 逐节点核对：第 i 节点的三通道应等于 (r,g,b) 网格坐标
    bad = 0
    for i in range(n ** 3):
        r = i % n
        g = (i // n) % n
        b = i // (n * n)
        for c, idx in enumerate((r, g, b)):
            q = d[i * 6 + c * 2] | (d[i * 6 + c * 2 + 1] << 8)
            expq = int(idx / (n - 1.0) * 65535.0 + 0.5)
            if q != expq:
                bad += 1
                if bad <= 3:
                    print('    节点%d 通道%d: 期望 %d 实得 %d' % (i, c, expq, q))
    print('  逐节点核对: 不符 %d / %d %s' % (bad, n ** 3 * 3,
          'OK' if bad == 0 else 'FAIL'))
    if bad:
        ok = False

    # 关键抽查
    print('  首节点(全0)   : %s' % ' '.join('%02x' % x for x in d[:6]))
    print('  末节点(全ff)  : %s' % ' '.join('%02x' % x for x in d[-6:]))
    if d[:6] != b'\x00' * 6:
        ok = False
        print('    ★ 首节点应为全0')
    if d[-6:] != b'\xff' * 6:
        ok = False
        print('    ★ 末节点应为全 FF')
    # 节点1 = (r=1,g=0,b=0) ⇒ R = 65535/(n-1) 四舍五入
    # ★ 2026-10-07 修正判据：n=33 时 65535/32 = 2047.97 ⇒ +0.5 后进位为 2048
    #   原判据写死 2047 是错的（把"截断"当成了"四舍五入"）
    exp1 = int(65535.0 / (n - 1.0) + 0.5)
    q = d[6] | (d[7] << 8)
    print('  节点1 R       : %d (0x%04x) 期望 %d (0x%04x) %s'
          % (q, q, exp1, exp1, 'OK' if q == exp1 else 'FAIL'))
    if q != exp1:
        ok = False
    # 全级量化误差必须 ≤ 0.5 LSB（四舍五入的理论上限）
    mx = max(abs(int(idx / (n - 1.0) * 65535.0 + 0.5) - idx / (n - 1.0) * 65535.0)
             for idx in range(n))
    print('  最大量化误差 : %.4f LSB（上限 0.5）%s' % (mx, 'OK' if mx <= 0.5 else 'FAIL'))
    if mx > 0.5:
        ok = False

    print('=== 自测%s ===' % ('通过' if ok else '失败'))
    return ok


if __name__ == '__main__':
    if '--selftest' in sys.argv[1:] or len(sys.argv) < 2:
        selftest()
        sys.exit(0)

    outdir = sys.argv[1] if len(sys.argv) > 1 else '.'
    for n in (33, 17):
        d = gen_identity(n)
        p = '%s/id%d_u16.bin' % (outdir, n)
        open(p, 'wb').write(d)
        print('已写 %s  %d 字节  (%d³ × 3 × u16 LE)' % (p, len(d), n))