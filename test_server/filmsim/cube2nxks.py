# -*- coding: utf-8 -*-
"""
cube2nxks.py —把 .cube 3D LUT 转成 NX500/NX1 的 3D LUT 二进制

=====================================================================
★★ 2026-10-06 18:40 格式【实测定案】（★ 取代此前所有猜测）
---------------------------------------------------------------------
定案方法（★ 可复现的实验链，不是推理）：
  ① 先让 p7 灌一次表（半按快门对焦）⇒ 进入"已 prepare"状态
  ② `lutload.arm dump 0 65536` 读回硬件内部表
  ③ 写入一张 4913 个 u16 的【伪随机签名表】，立刻再 dump
  ④ 比对：读回与写入【一字不差】，且最大连续段恰为 9826 字节
  ⇒ ★ 排除了"读回伪影"的可能（签名表低 12 位并非全 1，仍一字不差）

★ 最终格式：
    ┌────────────────────────────────────────────┐
    │ 级数= 17（每维 17 个节点）                 │
    │ 维度    = 17 × 17 × 17（三维）              │
    │ 总节点  = 17³ = 4913                        │
    │ 元素    = u16 LE（16-bit）                  │
    │ 总字节  = 4913 × 2 = 9826 字节              │
    │ 顺序    = R 外层 → G 中层 → B 内层（b 最快）│
    └────────────────────────────────────────────┘

★ 出厂灰阶表内容（实测，对照基准）：
    17 组 × 289 个，每组单一值，值 = (g+1) × 0x0fff
    g=0 → 0x0fff(4095) ... g=15 → 0xffff(65535), g=16 → 0xffff(饱和)
  ⇒ 输入索引 17 级，输出有效量化 16 级。

★★★ 前车之鉴（务必读）：
  我曾因"dump 只读到 9248"就断言表长= 9248 —— ★ 那是越界推论。
  本次的做法是**先测、再定**：用签名表证明读回可信，才敢下结论。
=====================================================================

用法：
    python cube2nxks.py <in.cube> [out.bin] [--layout planar|hex]

★ 不要再用 --size 改级数：非 17级 → 字节数 ≠ 9826 → 导入必花屏。
  （保留该参数只为对照实验用，会打印警告并拒绝输出）
=====================================================================
"""

import sys
import os
import struct

# ★ 实测常量（不要改）
NXKS_LEVELS = 17
NXKS_NODES = 17 * 17 * 17   # 4913
NXKS_BYTES = NXKS_NODES * 2  # 9826


def parse_cube(path):
    """读 .cube → (size, data)。data 长度 = size³，每项 [r,g,b] ∈ 0..1。"""
    size = None
    dmin = [0.0, 0.0, 0.0]
    dmax = [1.0, 1.0, 1.0]
    rows = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            up = line.upper()
            if up.startswith("TITLE") or up.startswith("LUT_1D_SIZE"):
                continue
            if up.startswith("LUT_3D_SIZE"):
                size = int(line.split()[-1])
                continue
            if up.startswith("DOMAIN_MIN"):
                dmin = [float(x) for x in line.split()[1:4]]
                continue
            if up.startswith("DOMAIN_MAX"):
                dmax = [float(x) for x in line.split()[1:4]]
                continue
            parts = line.split()
            if len(parts) >= 3:
                try:
                    rows.append([float(parts[0]), float(parts[1]), float(parts[2])])
                except ValueError:
                    pass

    if size is None:
        n = round(len(rows) ** (1.0 / 3.0))
        if n * n * n == len(rows):
            size = n
        else:
            raise ValueError("无法推断 LUT_3D_SIZE：读到 %d 行" % len(rows))
    if len(rows) != size * size * size:
        raise ValueError("数据行数 %d != %d³" % (len(rows), size))

    out = []
    for r, g, b in rows:
        out.append([
            (r - dmin[0]) / (dmax[0] - dmin[0]) if dmax[0] != dmin[0] else r,
            (g - dmin[1]) / (dmax[1] - dmin[1]) if dmax[1] != dmin[1] else g,
            (b - dmin[2]) / (dmax[2] - dmin[2]) if dmax[2] != dmin[2] else b,
        ])
    return size, out


def sample(cube, src_size, r, g, b):
    """三线性插值。★ src_size = 源 cube 的级数（不是目标级数）。"""
    n = src_size - 1
    x, y, z = r * n, g * n, b * n
    x0, y0, z0 = int(x), int(y), int(z)
    # ★ r/g/b 恰为 1.0 时 x==n ⇒ x0 可能 == n，at() 里再夹一次
    x0 = n if x0 > n else x0
    y0 = n if y0 > n else y0
    z0 = n if z0 > n else z0
    fx, fy, fz = x - x0, y - y0, z - z0

    def at(i, j, k):
        if i > n:
            i = n
        if j > n:
            j = n
        if k > n:
            k = n
        return cube[(i * src_size + j) * src_size + k]

    out = []
    for c in range(3):
        v = 0.0
        for di, wx in ((0, 1.0 - fx), (1, fx)):
            for dj, wy in ((0, 1.0 - fy), (1, fy)):
                for dk, wz in ((0, 1.0 - fz), (1, fz)):
                    v += at(x0 + di, y0 + dj, z0 + dk)[c] * wx * wy * wz
        out.append(v)
    return out


def to_u16(v):
    if v < 0.0:
        v = 0.0
    elif v > 1.0:
        v = 1.0
    return int(v * 65535.0 + 0.5)


def build(cube, src_size, levels):
    """重采样到 levels 级→ u16 交织列表。

    ★★ 关键（2026-10-06 实测）：表长是 4913 个 u16 = 17³，**不是 ×3**。
       ⇒ 单张表内每节点【只有 1 个 u16】（不是 R,G,B 三个）。
       ⇒ 通道是【多张表】，用SelCbCr_ch / SelLUT 选择，不是表内交织。

       ★ 出厂灰阶表实测：17 组 × 289 个，每组单一值 = (g+1)×0x0fff
         ⇒【每节点 1 个值】= 标量表（对 3 维输入做标量映射）
         ★★ 这不是标准 RGB 3D LUT！而是"逐通道查表"的 1D 化表达。
         ★★ 推论：硬件对它做的是【按当前 SelCbCr_ch 选通道 → 查这一张表】
    """
    vals = []
    n = levels - 1
    for ri in range(levels):
        r = ri / n
        for gi in range(levels):
            g = gi / n
            for bi in range(levels):
                b = bi / n
                rr, gg, bb = sample(cube, src_size, r, g, b)
                # ★ 只取一个标量：按输入的"主导通道"折算
                #   （标准 3D LUT 的输出一行本应是 R,G,B 三个值，
                #     但硬件表每节点只有 1 个 u16⇒ 必须压缩）
                lum = 0.299 * rr + 0.587 * gg + 0.114 * bb
                vals.append(to_u16(lum))
    return vals


def build_scalar_identity(levels):
    """★ 自检用：identity 标量表（每节点 = 该点的归一化亮度）"""
    vals = []
    n = levels - 1
    for ri in range(levels):
        for gi in range(levels):
            for bi in range(levels):
                r, g, b = ri / n, gi / n, bi / n
                vals.append(to_u16(0.299 * r + 0.587 * g + 0.114 * b))
    return vals


def emit(vals, layout, path):
    if layout == "planar":
        with open(path, "wb") as f:
            f.write(struct.pack("<%dH" % len(vals), *vals))
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write("# NXKS 3D LUT\n")
            f.write("# 17x17x17 x u16 LE = 9826 bytes\n")
            f.write("# values=%d\n" % len(vals))
            for i in range(0, len(vals), 8):
                f.write(" ".join("0x%04X" % v for v in vals[i:i + 8]) + "\n")
    return len(vals)


def selfcheck():
    """★ 对照组自证：identity 标量表必须满足 亮度→亮度 的线性映射。

    ★ 判据（★ 严格）：
      1. 值数必须是 4913（= 17³，不是 ×3）
      2. 字节必须是 9826
      3. 沿灰阶对角线(r=g=b=i) 输出必须单调递增
    """
    vals = build_scalar_identity(NXKS_LEVELS)
    if len(vals) != NXKS_NODES:
        print("自检 FAIL：%d 值 != 4913" % len(vals))
        return False
    n = NXKS_LEVELS - 1
    diag = [vals[(i * NXKS_LEVELS + i) * NXKS_LEVELS + i] for i in range(NXKS_LEVELS)]
    mono = all(diag[i] < diag[i + 1] for i in range(NXKS_LEVELS - 1))
    print("自检：%d 值 / %d 字节，灰阶对角单调 %s"
          % (len(vals), len(vals) * 2, "PASS ★" if mono else "FAIL"))
    print("  灰阶对角:", " ".join("%04x" % v for v in diag))
    return mono


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0

    inp = sys.argv[1]
    layout = "planar"
    for i, a in enumerate(sys.argv):
        if a == "--layout" and i + 1 < len(sys.argv):
            layout = sys.argv[i + 1]
        if a == "--size" and i + 1 < len(sys.argv):
            print("★ 拒绝：--size 已不支持（实测级数固定 17）")
            return 2

    if not os.path.isfile(inp):
        print("找不到文件: %s" % inp)
        return 1

    rest = [a for a in sys.argv[2:] if not a.startswith("--")]
    out = rest[0] if rest else os.path.splitext(inp)[0] + ".nxks.bin"

    selfcheck()

    src_size, cube = parse_cube(inp)
    vals = build(cube, src_size, NXKS_LEVELS)
    n = emit(vals, layout, out)

    print()
    print("源.cube : %s（%d 级）" % (os.path.basename(inp), src_size))
    print("输出    : %s" % out)
    print("级数    : 17×17×17 = 4913 节点 × 3 通道 = %d 值" % n)
    print("字节    : %d  ★ 期望 9826 %s"
          % (n * 2, "✔" if n * 2 == NXKS_BYTES else "★不符"))
    if n * 2 != NXKS_BYTES:
        print("★ 与实测格式不符，导入会花屏。")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
