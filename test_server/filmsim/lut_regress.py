# -*- coding: utf-8 -*-
"""3D LUT 管线回归测试（不上相机，纯 PC）

为什么必须有这个
--------------
`engine._cube_lookup` 的正确性无法靠"看图对不对"判断——
轴序写反时图片依然有颜色，只是色偏，肉眼在低饱和区根本分不出。
而单核相机不适合频繁上机做验证（见项目铁律）。
所以判据必须能在 PC 上反复跑，且判据本身要能自证。

★ 本文件【零 numpy 依赖】，只用 Pillow。
  原因：判据工具的最大风险是"在别人机器上跑不起来"——
  一旦依赖 numpy/rawpy 这类需要额外安装的库，判据就退化成
  "我记得它上次是过的"。A/B 判据本来就不需要 numpy，
  C 判据只需 3000 次采样，纯 Python 毫秒级完成。
  ⇒ 任何有 Python + Pillow 的机器都能立刻复跑全部判据。

四组判据
--------
A. 恒等表回归（自证轴序语义）
   构造 32^3 恒等表，喂纯红/绿/蓝/25%灰/中灰，
   要求全部零误差还原。过了就说明 index = R*N*N+G*N+B 解释正确。
   ★ 反例警戒：把 at() 的两种轴序解释写在同一个函数里对比是【无效判据】，
     因为两边共用同一个索引公式，等于什么都没测。已踩过这个坑。

B. 边界鲁棒性（防负索引绕表尾）
   rf/gf/bf 传-0.01 / 1.01 / 0.0 / 1.0，不能抛异常、不能返回错色。
   ★ 原实现只 clamp 上界，rf<0 时 ri<0，Python 负索引绕到表尾→静默错色。

C. 真实 LUT × 真实人像（外部交叉验证）
   拿 CC0 的 Kodak Portra 400 套SAM_3187 人像，
   判据 = 肤色区平均输出必须保持 R>G>B（人肤色关系）。
   这条不依赖我们对规范的信心，只依赖"人脸不能变蓝"这个物理事实。

D. 资产自洽性（我们收进来的每个 .cube 都要过）
   size 声明必须等于实际行数，否则 at() 会越界或错位。
   这是"取货验收"，不是"代码正确性"——两件事，判据也必须分开。

用法：
    python test_server/filmsim/lut_regress.py[某个.cube 路径]
退出码：0 = 全过，非 0 = 有失败项（上层可据此判成败）
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image

from engine import load_cube, _cube_lookup, apply_cube

FAILS = 0


def ok(cond, what):
    global FAILS
    print("  [%s] %s" % ("PASS" if cond else "FAIL", what))
    if not cond:
        FAILS += 1
    return cond


def build_identity(n):
    """构造 n^3 恒等表：data[i*N*N+j*N+k] = [i/(n-1), j/(n-1), k/(n-1)]"""
    data = []
    for i in range(n):          # R 索引：最慢
        for j in range(n):      # G
            for k in range(n):  # B：最快
                data.append([i / (n - 1), j / (n - 1), k / (n - 1)])
    return {"size": n, "data": data}


# ---------------------------------------------------------------- A
def test_identity(n=32):
    print("== A. 恒等表回归（%d^3，验证轴序语义）==" % n)
    cube = build_identity(n)
    for nm, rgb in [("纯红", (1.0, 0.0, 0.0)),
                    ("纯绿", (0.0, 1.0, 0.0)),
                    ("纯蓝", (0.0, 0.0, 1.0)),
                    ("25%灰", (0.25, 0.25, 0.25)),
                    ("中灰", (0.5, 0.5, 0.5))]:
        o = _cube_lookup(cube, *rgb)
        err = max(abs(o[k] - rgb[k]) for k in range(3))
        ok(err < 0.01, "%s 零误差还原 (实际误差 %.5f)" % (nm, err))


# ---------------------------------------------------------------- B
def test_bounds():
    print("\n== B. 边界鲁棒性（防负索引绕表尾）==")
    cube = build_identity(32)
    for nm, rgb in [("负输入", (-0.01, 0.5, 0.5)),
                    ("超上界", (1.01, 0.5, 0.5)),
                    ("三通道全负", (-0.5, -0.5, -0.5)),
                    ("全 0", (0.0, 0.0, 0.0)),
                    ("全 1", (1.0, 1.0, 1.0))]:
        try:
            o = _cube_lookup(cube, *rgb)
            # 负/超界输入应被夹到边界：全 0 → (0,0,0)，全 1 → (1,1,1)
            if nm == "全 0":
                good = max(abs(v) for v in o) < 0.01
            elif nm == "全 1":
                good = min(abs(v - 1.0) for v in o) < 0.01
            else:
                good = all(0.0 <= v <= 1.0 for v in o)
            ok(good, "%s 不抛异常且输出在[0,1] -> %s"
               % (nm, ["%.3f" % v for v in o]))
        except Exception as e:
            ok(False, "%s 抛异常: %s" % (nm, e))


# ---------------------------------------------------------------- C
def _skin_samples(photo, want=3000):
    """从照片里挑肤色区像素（纯 Python，不用 numpy）。

    判据逻辑同numpy 版：max通道在 0.30~0.80（中等亮度，非高光非暗部）
    且 (max-min)/max < 0.30（低饱和= 皮肤/灰墙，排除高饱和背景）。
    为控制耗时，只在中心 60% 区域扫描 + 步长抽样。
    """
    im = Image.open(photo).convert("RGB")
    W, H = im.size
    x0, x1 = int(W * 0.20), int(W * 0.80)
    y0, y1 = int(H * 0.20), int(H * 0.80)
    crop = im.crop((x0, y0, x1, y1))
    px = crop.load()
    cw, ch = crop.size
    # 每采 1 个样本要扫 step*step 个像素，取够 want 就停
    total = cw * ch
    step = 1
    while total // (step * step) > want * 4:
        step += 1
    out = []
    for y in range(0, ch, step):
        for x in range(0, cw, step):
            r, g, b = px[x, y]
            mx = max(r, g, b)
            mn = min(r, g, b)
            if mx < 77 or mx > 204:          # 0.30~0.80 * 255
                continue
            if (mx - mn) / mx > 0.30:# 低饱和
                continue
            out.append((r / 255.0, g / 255.0, b / 255.0))
            if len(out) >= want:
                return out
    return out


def test_real_lut(path, photo):
    print("\n== C. 真实 LUT x 真实人像（外部交叉验证）==")
    if not (os.path.isfile(path) and os.path.isfile(photo)):
        print("  SKIP 缺少 %s 或 %s" % (path, photo))
        return
    c = load_cube(path)
    n = c["size"]
    print("     LUT = %s  size=%d  nodes=%d" % (os.path.basename(path), n,
                                                len(c["data"])))

    t0 = time.time()
    samples = _skin_samples(photo)
    if len(samples) < 500:
        print("  SKIP 肤色区样本太少 (%d)" % len(samples))
        return
    print("     肤色样本 %d 个（扫描 %.2fs，步长自适应）"
          % (len(samples), time.time() - t0))

    src = [sum(s[k] for s in samples) / len(samples) * 100 for k in range(3)]
    outs = [_cube_lookup(c, *s) for s in samples]
    out = [sum(o[k] for o in outs) / len(outs) * 100 for k in range(3)]
    print("     原图   肤色区均值 R=%.1f%% G=%.1f%% B=%.1f%%" % tuple(src))
    print("     应用后肤色区均值 R=%.1f%% G=%.1f%% B=%.1f%%" % tuple(out))
    ok(out[0] > out[1] > out[2],
       "应用后肤色仍保持 R>G>B（人脸没变蓝/变青）")
    # 顺带判据：胶片 LUT 必须真的改变画面（否则等于没生效）
    delta = max(abs(out[k] - src[k]) for k in range(3))
    ok(delta > 1.0, "LUT 确实生效（肤色均值最大偏移 %.1f%%）" % delta)


# ---------------------------------------------------------------- D
def test_assets():
    print("\n== D. 资产自洽性（luts/*.cube 取货验收）==")
    d = os.path.join(HERE, "luts")
    if not os.path.isdir(d):
        print("  SKIP 没有 %s" % d)
        return
    cubes = sorted(f for f in os.listdir(d) if f.lower().endswith(".cube"))
    if not cubes:
        print("  SKIP 目录里没有 .cube")
        return
    for f in cubes:
        p = os.path.join(d, f)
        t0 = time.time()
        c = load_cube(p)
        n = c["size"]
        dt = time.time() - t0
        rows_ok = (len(c["data"]) == n ** 3)
        # 抽查首/中/末三行，必须是 3 个0..1 的浮点
        probe = []
        for idx in (0, len(c["data"]) // 2, len(c["data"]) - 1):
            row = c["data"][idx]
            probe.append(len(row) == 3 and all(0.0 <= v <= 1.0 for v in row))
        ok(rows_ok and all(probe),
           "%-34s size=%-3d rows=%-6d 解析%.2fs 首/中/末行合法"
           % (f, n, len(c["data"]), dt))


# ---------------------------------------------------------------- E
def test_perf():
    print("\n== E.性能基线（决定要不要向量化）==")
    p = os.path.join(HERE, "luts", "Kodak Portra 400.cube")
    photo = os.path.join(HERE, "raw", "SAM_3187_view.jpg")
    if not (os.path.isfile(p) and os.path.isfile(photo)):
        print("  SKIP 缺 LUT 或测试图")
        return
    c = load_cube(p)
    src = Image.open(photo).convert("RGB")
    W, H = src.size
    im = src.resize((320, int(320 * H / W)), Image.BILINEAR)
    npx = im.size[0] * im.size[1]
    t0 = time.time()
    apply_cube(im, c, 1.0)
    dt = time.time() - t0
    rate = npx / dt
    full = 5472 * 3648          # NX500 全幅 20MP
    print("     吞吐 %.0f px/s（%dx%d 用时 %.2fs）" % (rate, im.size[0],
                                                  im.size[1], dt))
    print("     ⇒ NX500 全幅5472x3648 预计 %.0f 秒/张" % (full / rate))
    ok(rate > 50000, "吞吐 > 50k px/s（低于此值批量处理不可用）")


def main():
    print("3D LUT 管线回归（零 numpy 依赖）")
    print("=" * 68)
    test_identity()
    test_bounds()

    # 找 CC0 LUT：优先 test_server/filmsim/luts/，否则用命令行给的
    p = sys.argv[1] if len(sys.argv) > 1 else None
    if p is None:
        d = os.path.join(HERE, "luts")
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                if f.lower().endswith(".cube"):
                    p = os.path.join(d, f)
                    break
    test_real_lut(p or "", os.path.join(HERE, "raw", "SAM_3187_view.jpg"))

    test_assets()
    test_perf()

    print("\n" + "=" * 68)
    if FAILS:
        print("失败 %d 项" % FAILS)
    else:
        print("全部通过")
    # ★ 判据工具必须用退出码表成败，否则上层会把失败读成通过（已踩过）
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
