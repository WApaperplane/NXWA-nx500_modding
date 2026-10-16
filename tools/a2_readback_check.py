#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
a2_readback_check.py — A2 p7 回读件校验（NXWA 工具，2026-10-16）

用途：上机日 A2 健康检查（ONDEVICE_SOP_2026-10-16 §7.1「回读不符」精查路径）
      与历史裁决复验。吃相机回读件（telnet dd + nx-fetch 拉回），比对 p7_a2.bin。

判据（与 A2_READBACK_VERDICT_2026-10-15 一致）：
  [1] 前 12,075,648 B（= p7_a2.bin 全长）逐字节一致
  [2] 其后区段（至 min(文件尾, 12MiB) 与可选 --tail-size）应全零（未被运行期写）

用法：
  python tools/a2_readback_check.py <readback.bin>
  python tools/a2_readback_check.py <readback.bin> --ref <p7_a2.bin> --json out.json
  python tools/a2_readback_check.py <readback.bin> --tail-size 19381120   # 检查 30MB 全分区件

退出码：0 = PASS；2 = 差异；1 = 输入错误。
"""
import argparse
import hashlib
import json
import os
import sys

DEFAULT_REF = "E:/NXWA/fw/v1.12/a2/p7_a2.bin"
IMG_SIZE = 12075648          # p7_a2.bin 全长
READ_SIZE_12M = 12 * 1024 * 1024   # dd bs=1M count=12 的读出量


def diff_regions(a, b, limit=10):
    """返回 [(start, end, ...)] 连续差异区（≤limit 个）与总差异字节数"""
    regions = []
    total = 0
    n = min(len(a), len(b))
    i = 0
    while i < n:
        if a[i] != b[i]:
            j = i
            while j < n and a[j] != b[j]:
                j += 1
            total += j - i
            if len(regions) < limit:
                regions.append((i, j))
            i = j
        else:
            i += 1
    return regions, total


def nonzero_regions(buf, limit=10):
    """返回非零字节的连续区段"""
    regions = []
    n = len(buf)
    i = 0
    while i < n:
        if buf[i] != 0:
            j = i
            while j < n and buf[j] != 0:
                j += 1
            if len(regions) < limit:
                regions.append((i, j))
            i = j
        else:
            i += 1
    return regions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("readback")
    ap.add_argument("--ref", default=DEFAULT_REF)
    ap.add_argument("--tail-size", type=int, default=None,
                    help="尾部检查字节数（缺省 = min(文件尾, 12MiB) - 12,075,648）")
    ap.add_argument("--json", dest="json_out", default=None)
    args = ap.parse_args()

    if not os.path.isfile(args.ref):
        print(f"!! ref 不存在: {args.ref}（用 --ref 指定 p7_a2.bin）")
        return 1
    ref = open(args.ref, "rb").read()
    rb = open(args.readback, "rb").read()
    print("== A2 readback check ==")
    print(f"  ref : {args.ref}  ({len(ref)}B, md5 {hashlib.md5(ref).hexdigest()})")
    print(f"  rb  : {args.readback}  ({len(rb)}B, md5 {hashlib.md5(rb).hexdigest()})")
    if len(ref) != IMG_SIZE:
        print(f"  (note: ref size != {IMG_SIZE} —— 非常规镜像，按实际长度比对)")

    result = {"ref": args.ref, "readback": args.readback,
              "ref_size": len(ref), "rb_size": len(rb)}

    # [1] 前 len(ref) 字节
    head_ok = len(rb) >= len(ref) and rb[:len(ref)] == ref
    result["head_identical"] = bool(head_ok)
    if head_ok:
        print(f"  [1] first {len(ref)}B : IDENTICAL with image  ✓")
    else:
        if len(rb) < len(ref):
            print(f"  [1] first {len(ref)}B : readback shorter than image !!")
        else:
            regions, total = diff_regions(rb[:len(ref)], ref)
            print(f"  [1] first {len(ref)}B : DIFF — {total} bytes in {len(regions)}+ region(s); first 5:")
            for s, e in regions[:5]:
                print(f"        {s:#x}..{e:#x} ({e-s}B) rb={rb[s:min(e,s+16)].hex()} ref={ref[s:min(e,s+16)].hex()}")
        result["diff_regions"] = [list(r) for r in regions[:10]] if not head_ok and len(rb) >= len(ref) else []

    # [2] 尾部零区
    tail_start = len(ref)
    tail_end = len(rb)
    if args.tail_size is not None:
        tail_end = min(len(rb), tail_start + args.tail_size)
    if tail_end > tail_start:
        tail = rb[tail_start:tail_end]
        nz = nonzero_regions(tail)
        result["tail_checked"] = tail_end - tail_start
        result["tail_nonzero_regions"] = len(nz)
        if not nz:
            print(f"  [2] tail [{tail_start:#x}..{tail_end:#x}) ({tail_end-tail_start}B) : all zero  ✓")
        else:
            print(f"  [2] tail ({tail_end-tail_start}B) : {len(nz)}+ nonzero region(s); first 5:")
            for s, e in nz[:5]:
                print(f"        +{tail_start+s:#x}..+{tail_start+e:#x} ({e-s}B)")
    else:
        print("  [2] tail : (无尾部区段可比)")

    ok = head_ok and (not result.get("tail_nonzero_regions"))
    result["verdict"] = "PASS: A2 fully present (byte-identical head + clean tail)" if ok else "check required"
    print(f"  => {result['verdict']}")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"  json -> {args.json_out}")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
