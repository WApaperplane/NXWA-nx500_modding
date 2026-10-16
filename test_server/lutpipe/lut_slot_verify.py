#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lut_slot_verify.py — p7 静态 3D LUT 表池「严格语义校验」（T1 证据收口 · 2026-10-16）

口径（依 FILMLAB_LUT_NATIVE_UI_GOALS_2026-10-16 §2 修正项 + U6_ONMACHINE_RESULT §3）：
  * 「黑点为 0」不等于 identity；**严格 identity = 4913/4913 项输出 == 对应输入格点**。
  * 输入格点 = 17 档 [0,16,32,…,240,255]（step 16，末档 255）。
  * 索引 = ((B*17+G)*17+R)*4（R 最快）；项 = {R_out,G_out,B_out,pad}。

输出（42 槽）：
  1) 严格 identity 计数（预期：**0**——验证 GOALS 的结论）
  2) 恒等项计数 / 最大分量偏差（近恒等度量）
  3) 轴序矩阵：沿 R/G/B 索引轴扫描 → 各输出通道的响应幅度（验证「索引轴 ↔ 通道」对应）
  4) 槽边界/长度：尾部指纹（末项×3 + 48×0）+ 表长可读性
  5) 末项/白点/黑点数值（诊断）

用法: python lut_slot_verify.py <p7_image.bin> [--json out.json]
"""
import argparse
import json

SLOT = 0x4D00
TABLE = 4913 * 4
BLOCKS = [("A", 0x808592C0, 20), ("B", 0x808B9AC0, 22)]


def level(i):
    """第 i 档输入电平（i=0..16）"""
    return 255 if i == 16 else i * 16


def idx(r, g, b):
    return ((b * 17 + g) * 17 + r) * 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--json", dest="json_out", default=None)
    a = ap.parse_args()
    d = open(a.image, "rb").read()
    print(f"图像: {a.image} ({len(d)}B)")
    print(f"判据: 严格 identity = 4913/4913 项 (R,G,B)out == (level(r),level(g),level(b))；"
          f"格点=17 档 step16 末档255")
    print()

    hdr = f"{'块':<3}{'#':<4}{'E0':<14}{'白点':<14}{'严格id':<8}{'恒等项':<8}{'最大偏差':<9}{'指纹':<6}{'轴序(R/G/B→响应)':<22}"
    print(hdr)
    print("-" * 108)

    rows = []
    for name, base_va, n in BLOCKS:
        for i in range(n):
            va = base_va + i * SLOT
            off = va - 0x80000000
            blk = d[off:off + TABLE]
            if len(blk) < TABLE:
                continue
            # 严格恒等 + 偏差
            nid = 0
            maxdev = 0
            for r in range(17):
                for g in range(17):
                    for b in range(17):
                        o = idx(r, g, b)
                        want = (level(r), level(g), level(b))
                        got = (blk[o], blk[o + 1], blk[o + 2])
                        dev = max(abs(got[0] - want[0]), abs(got[1] - want[1]), abs(got[2] - want[2]))
                        maxdev = max(maxdev, dev)
                        if dev == 0:
                            nid += 1
            strict_id = (nid == 4913)
            # 轴序：沿各索引轴扫（另一端固定 8），看每输出通道的响应幅度
            resp = {}
            for axis in range(3):          # 0=R轴 1=G轴 2=B轴
                ch_min = [255, 255, 255]
                ch_max = [0, 0, 0]
                for k in range(17):
                    r, g, b = 8, 8, 8
                    if axis == 0:
                        r = k
                    elif axis == 1:
                        g = k
                    else:
                        b = k
                    o = idx(r, g, b)
                    for c in range(3):
                        ch_min[c] = min(ch_min[c], blk[o + c])
                        ch_max[c] = max(ch_max[c], blk[o + c])
                resp[axis] = [ch_max[c] - ch_min[c] for c in range(3)]
            # 指纹
            eL4 = blk[4912 * 4:4912 * 4 + 4]
            tail = d[off + TABLE:off + TABLE + 60]
            fp = (tail[:12] == bytes(eL4) * 3 and tail[12:] == b"\x00" * 48)
            # 白点 = idx(16,16,16)，黑点 = idx(0,0,0)
            wp = tuple(blk[idx(16, 16, 16):idx(16, 16, 16) + 3])
            e0 = tuple(blk[idx(0, 0, 0):idx(0, 0, 0) + 3])
            # 轴序要点：主轴（R轴→R通道等）响应应显著
            axis_note = "/".join(
                f"轴{'RGB'[ax]}→({resp[ax][0]},{resp[ax][1]},{resp[ax][2]})" for ax in range(3))
            print(f"{name:<3}{i:<4}{str(e0):<14}{str(wp):<14}"
                  f"{'YES' if strict_id else '-':<8}{nid:<8}{maxdev:<9}"
                  f"{'OK' if fp else 'BAD':<6}{axis_note}")
            rows.append(dict(block=name, idx=i, va=hex(va), e0=e0, white=wp,
                             strict_identity=strict_id, n_identical=nid,
                             max_deviation=maxdev, fingerprint_ok=fp,
                             axis_response={f"axis{'RGB'[k]}": resp[k] for k in range(3)}))

    n_strict = sum(1 for r in rows if r["strict_identity"])
    n_near = sum(1 for r in rows if r["n_identical"] > 4000)
    print("-" * 108)
    print(f"合计 {len(rows)} 槽：**严格 identity = {n_strict}**（GOALS 预期 0）；"
          f"恒等项>4000 的“近恒等” {n_near} 个；指纹异常 {sum(1 for r in rows if not r['fingerprint_ok'])}")
    if rows:
        best = max(rows, key=lambda r: r["n_identical"])
        print(f"最接近恒等者: {best['block']}{best['idx']} ({best['va']}) "
              f"恒等 {best['n_identical']}/4913，最大偏差 {best['max_deviation']}")

    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as f:
            json.dump(dict(image=a.image, slot=hex(SLOT), table_bytes=TABLE,
                           criterion="strict identity = 4913/4913 items equal",
                           summary=dict(n_slots=len(rows), n_strict_identity=n_strict,
                                        n_near_identity=n_near),
                           slots=rows), f, ensure_ascii=False, indent=1)
        print(f"json -> {a.json_out}")


if __name__ == "__main__":
    main()
