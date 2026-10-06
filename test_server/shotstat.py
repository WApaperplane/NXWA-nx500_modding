#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shotstat.py — 拉取相机 JPG 并做像素统计（客观判据通道）

用途
----
验证「FilmLab 一键切换真的生效」不能靠"用户看一眼取景器"。
本脚本从相机 80 端口拉 JPG，算 R/G/B 均值/饱和度分布，
用【数值差异】证明不同配方真的产生了不同画面。

判据
----
1. 纯黑白配方（trix400 / hp5 / monowarm，SAT=0）→ R≈G≈B
   ★ 这是最干净的判据：饱和度应接近 0，与彩色配方差异极大。
2. 不同彩色配方 → R/G/B 均值应有可测量差异（建议阈值 mean|Δ| > 1.5/255）
3. 同一配方连拍两张 → 差异应很小（证明噪声底，见下方 --noise-floor）

用法
----
  # 单张统计
  python shotstat.py <IP> 575PHOTO/SAM_3200.JPG

  # 对比两张（推荐：一张彩色 + 一张黑白）
  python shotstat.py <IP> --compare 575PHOTO/SAM_3200.JPG 575PHOTO/SAM_3201.JPG

  # 抓最新一张并统计（自动从 8080 dirlist 取最新）
  python shotstat.py <IP> --latest

  # 噪声底：拍同配方两张，量化"同配方也有差异"的幅度
  python shotstat.py <IP> --noise-floor 575PHOTO/A.JPG 575PHOTO/B.JPG

  # ★ 完全离线：直接读本地文件（用于回归验证判据本身，不需相机在线）
  python shotstat.py local --compare demo/dcim_trix/IMG_0001.JPG demo/dcim/IMG_0001.JPG

注意
----
* 抓图走 80 端口（8080 不行，实测）；大文件约 20s/36MB，JPG 小得多。
* ★ 已内置 ProxyHandler({}) 绕过系统代理 —— 无需任何额外参数。
  （curl 才需要 --noproxy；这里用 urllib 的话必须显式建空ProxyHandler，
   否则 Windows 的系统代理会造成 502 假象。）
* 只读操作，不在相机上跑任何 CPU 密集任务。
"""
import sys
import io
import time
import argparse

try:
    import numpy as np
    from PIL import Image
except ImportError:
    print("缺少依赖：pip install numpy pillow", file=sys.stderr)
    sys.exit(1)


def fetch(ip, relpath, timeout=60):
    """从相机 80 端口拉一张 JPG，返回 bytes。

    ★ ip == "local" 时改为读本地文件（离线回归验证判据用）。
    """
    import os
    if ip == "local":
        p = relpath
        with open(p, "rb") as f:
            data = f.read()
        print(f"  本地 {p}  {len(data)/1024:.0f} KB")
        return data
    import urllib.request
    url = f"http://{ip}/{relpath.lstrip('/')}"
    # ★必须绕过系统代理
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(url, headers={"Connection": "close"})
    t0 = time.time()
    with opener.open(req, timeout=timeout) as r:
        data = r.read()
    dt = time.time() - t0
    print(f"  拉取 {relpath}  {len(data)/1024:.0f} KB  {dt:.1f}s")
    return data


def fetch_latest(ip, port=8080, timeout=10):
    """从 8080 dirlist拿最新一张照片的相对路径。"""
    import urllib.request
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    url = f"http://{ip}:{port}/cgi-bin/dirlist"
    with opener.open(url, timeout=timeout) as r:
        raw = r.read().decode("utf-8", errors="replace")
    import json
    data = json.loads(raw)
    # dirlist 结构：目录列表 → 该目录内文件，按文件名倒序即最新
    best = None
    dirs = data if isinstance(data, list) else data.get("dirs", data)
    if isinstance(dirs, dict):
        dirs = dirs.get("dirs", [])
    for d in dirs:
        files = d.get("files", []) if isinstance(d, dict) else []
        for f in files:
            n = f.get("name", "") if isinstance(f, dict) else str(f)
            if n.upper().endswith((".JPG", ".JPEG")):
                dn = d.get("name", "575PHOTO") if isinstance(d, dict) else "575PHOTO"
                cand = f"{dn}/{n}"
                if best is None or cand > best:
                    best = cand
    if best is None:
        raise SystemExit("dirlist 里没找到 JPG")
    return best


def stats(data):
    """返回一张图的客观统计量。"""
    img = Image.open(io.BytesIO(data))
    w, h = img.size
    a = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    R, G, B = a[..., 0], a[..., 1], a[..., 2]

    lum = 0.2126 * R + 0.7152 * G + 0.0722 * B
    mean = a.reshape(-1, 3).mean(axis=0)
    # 饱和度（HSV 的 S，0..1）。★ 对"纯黑白"配方，这个值应接近 0
    mx = a.max(axis=-1)
    mn = a.min(axis=-1)
    sat = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)

    return {
        "size": (w, h),
        "R": float(mean[0]), "G": float(mean[1]), "B": float(mean[2]),
        "lum": float(lum.mean()),
        "lum_p1": float(np.percentile(lum, 1)),
        "lum_p99": float(np.percentile(lum, 99)),
        "sat_mean": float(sat.mean()),
        "sat_p99": float(np.percentile(sat, 99)),
        "rgb_spread": float(mean.max() - mean.min()),
    }


def fmt(name, s):
    return (f"  {name:<24} {s['size'][0]}x{s['size'][1]}  "
            f"R={s['R']:.4f} G={s['G']:.4f} B={s['B']:.4f}  "
            f"spread={s['rgb_spread']:.4f}  sat={s['sat_mean']:.4f}  "
            f"lum p1={s['lum_p1']:.4f} p99={s['lum_p99']:.4f}")


def judge(a, b, noise_floor=None):
    """给出客观判据结论。"""
    print("\n=== 判据 ===")
    d_rgb = max(abs(a["R"] - b["R"]), abs(a["G"] - b["G"]), abs(a["B"] - b["B"]))
    d_sat = abs(a["sat_mean"] - b["sat_mean"])
    ok = True

    # 判据 1：其中一个是纯黑白（sat 极低）
    for nm, x, y in (("A", a, b), ("B", b, a)):
        if x["sat_mean"] < 0.08 and y["sat_mean"] > 0.15:
            print(f"  ✓ 判据1成立：{nm} 是纯黑白（sat={x['sat_mean']:.4f} < 0.08），"
                  f"另一张 sat={y['sat_mean']:.4f} → 饱和度差异 {d_sat:.4f}")
            print("     ★ 这是最硬的证据：SAT=0 的配方确实把画面拍成了黑白。")
            break
    else:
        print(f"  · 判据1未命中（两张 sat 分别为 {a['sat_mean']:.4f} / {b['sat_mean']:.4f}）")
        print("     → 两张都是彩色或都是黑白，换一对更有区分度的配方再测")

    # 判据 2：通道均值有可测量差异
    thr = 0.0059  # ≈1.5/255
    if noise_floor is not None:
        thr = max(thr, noise_floor * 2.5)
        print(f"· 噪声底 = {noise_floor:.5f} → 阈值提高到 {thr:.5f}（2.5×噪声）")
    if d_rgb > thr:
        print(f"  ✓ 判据2成立：通道均值最大差异 {d_rgb:.4f} > 阈值 {thr:.4f} → 画面确实变了")
    else:
        print(f"  ✗ 判据2不成立：通道均值最大差异 {d_rgb:.4f} ≤ 阈值 {thr:.4f}")
        print("     → 两张图基本一样。可能原因：① ISP 没重读 PW 段（本次修复的 bug）")
        print("       ② 两个配方数值太接近③ 场景/曝光差异掩盖了色彩差异")
        ok = False

    print(f"\n  sat差异 = {d_sat:.4f}   通道 spread 差异 = "
          f"{abs(a['rgb_spread'] - b['rgb_spread']):.4f}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ip", help="相机 IP，或 local 表示读本地文件（离线自测）")
    ap.add_argument("paths", nargs="*", help="照片相对路径，如 575PHOTO/SAM_3200.JPG")
    ap.add_argument("--compare", action="store_true", help="对比两张")
    ap.add_argument("--latest", action="store_true", help="自动取最新一张")
    ap.add_argument("--noise-floor", action="store_true",
                    help="噪声底模式：两张是同配方的连拍")
    args = ap.parse_args()

    if args.latest and args.ip == "local":
        sys.exit("--latest 需要真实相机 IP，local 模式下不可用")

    if args.latest:
        p = fetch_latest(args.ip)
        print(f"  最新照片 = {p}")
        s = stats(fetch(args.ip, p))
        print(fmt("latest", s))
        return

    if not args.paths:
        ap.print_help()
        sys.exit(1)

    if args.compare or args.noise_floor or len(args.paths) == 2:
        if len(args.paths) != 2:
            sys.exit("需要两张照片")
        print("=== 拉取 ===")
        a = stats(fetch(args.ip, args.paths[0]))
        b = stats(fetch(args.ip, args.paths[1]))
        print("\n=== 统计 ===")
        print(fmt(args.paths[0], a))
        print(fmt(args.paths[1], b))
        if args.noise_floor:
            d = max(abs(a["R"] - b["R"]), abs(a["G"] - b["G"]), abs(a["B"] - b["B"]))
            print(f"\n=== 噪声底 = {d:.5f} ===")
            print("  → 判据 2 的阈值应设为该值的 2.5 倍")
        else:
            # ★ 判据不成立必须以非零退出码返回，否则上层自动化会把失败当通过
            if not judge(a, b):
                sys.exit(1)
    else:
        for p in args.paths:
            print("=== 拉取 ===")
            s = stats(fetch(args.ip, p))
            print("\n=== 统计 ===")
            print(fmt(p, s))


if __name__ == "__main__":
    main()
