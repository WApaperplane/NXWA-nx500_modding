#!/usr/bin/env python3
"""NVD (Non-Volatile Data) 文件格式分析

背景
----
从 DRIMe5 bootloader (SLP[1]) 的字符串表挖到完整的 NVD 分区表：
    nvd_app / nvd_app_restore / nvd_line / nvd_sysrw / nvd_sys /
    nvd_cap / nvd_iq / nvd_vfpn / nvd_cs / nvd_dpc / nvd_dpc2
每类都是「主分区 + 备份分区」结构，并有三级降级日志：
    recovery pref. data loaded / default pref. data loaded / pref. data broken

实机（/opt/pref/default/）的对应文件：
    pref.bin 7971840   pref_app.bin 67340   pref_app_restore.bin 43876
    pref_adj_iq.bin 3584   pref_adj_cs.bin 64000   pref_adj_cap.bin 3584
    pref_adj_dpc.bin 5246976   pref_adj_dpc2.bin 1049600
    pref_adj_sys.bin 3584   pref_adj_vfpn.bin 24064
    pref_line.bin 2560   pref_sysrw.bin 1616

本工具解出文件头格式并验证 crc 算法 —— 这决定了我们能否安全地
构造/修改 IQ 数据（FilmLab 的潜在新入口）。
"""
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "raw8" / "pref"

# bootloader 字符串表里的 NVD 名→ 实机文件名 对应关系
NVD_MAP = [
    ("nvd_app",         "pref_app.bin"),
    ("nvd_app_restore", "pref_app_restore.bin"),
    ("nvd_line",        "pref_line.bin"),
    ("nvd_sysrw",       "pref_sysrw.bin"),
    ("nvd_cap",         "pref_adj_cap.bin"),
    ("nvd_iq",          "pref_adj_iq.bin"),
    ("nvd_cs",          "pref_adj_cs.bin"),
    ("nvd_dpc",         "pref_adj_dpc.bin"),
    ("nvd_dpc2",        "pref_adj_dpc2.bin"),
    ("nvd_sys",         "pref_adj_sys.bin"),
    ("nvd_vfpn",        "pref_adj_vfpn.bin"),
    ("(主pref)",        "pref.bin"),
]


def crc_candidates(d):
    """各种 crc 算法候选"""
    body = d[12:]
    body_nosize = d[12:]
    # crc 字段置零后再算
    d0 = bytearray(d)
    d0[4:8] = b"\0\0\0\0"
    return {
        "zlib(body)":       zlib.crc32(body) & 0xFFFFFFFF,
        "zlib(all)":        zlib.crc32(d) & 0xFFFFFFFF,
        "zlib(crc字段置零)": zlib.crc32(bytes(d0)) & 0xFFFFFFFF,
        "JAMCRC(body)":     (zlib.crc32(body) ^ 0xFFFFFFFF) & 0xFFFFFFFF,
        "JAMCRC(all)":      (zlib.crc32(d) ^ 0xFFFFFFFF) & 0xFFFFFFFF,
        "JAMCRC(置零)":     (zlib.crc32(bytes(d0)) ^ 0xFFFFFFFF) & 0xFFFFFFFF,
        "adler32(body)":    zlib.adler32(body) & 0xFFFFFFFF,
        "sum32(body)":      sum(struct.unpack_from("<%dI" % (len(body) // 4), body)) & 0xFFFFFFFF,
    }


def main():
    print("=" * 76)
    print("NVD 文件格式分析 (pref / IQ 数据)")
    print("=" * 76)
    print()
    hits = {}          # 算法名 -> 命中次数
    total = 0
    magics = {}
    for nvd, fn in NVD_MAP:
        p = ROOT / fn
        if not p.exists():
            continue
        d = p.read_bytes()
        total += 1
        if len(d) < 12:
            print("%-22s ★ 太短 (%d 字节)" % (fn, len(d)))
            continue
        mg, crc, size = struct.unpack_from("<III", d, 0)
        magics.setdefault(mg, []).append(fn)
        nz = sum(1 for b in d if b)
        print("--- %-22s (NVD: %s) ---" % (fn, nvd))
        print("  size=%-9d  magic=0x%08x  crc_field=0x%08x  size_field=%-9d %s"
              % (len(d), mg, crc, size, "OK" if size == len(d) else "★MISMATCH"))
        print("  非零字节 %d / %d  (%.1f%%)" % (nz, len(d), nz * 100.0 / len(d)))
        c = crc_candidates(d)
        hit = [k for k, v in c.items() if v == crc]
        for k in hit:
            hits[k] = hits.get(k, 0) + 1
        if hit:
            print("  ★★ crc 命中: %s" % ", ".join(hit))
        else:
            print("  (crc 字段 0x%08x 未命中常见算法)" % crc)
            for k, v in c.items():
                print("      %-18s = 0x%08x" % (k, v))
        # 前 8 个 u32
        row = [struct.unpack_from("<I", d, i * 4)[0] for i in range(min(8, len(d) // 4))]
        print("  前 8 u32: %s" % " ".join("%d" % v for v in row))
        print()

    print("=" * 76)
    print("汇总")
    print("=" * 76)
    print("文件数: %d" % total)
    print()
    print("magic 分布:")
    for mg, fns in magics.items():
        print("  0x%08x  %d 个文件  %s" % (mg, len(fns), fns[:3]))
    print()
    if hits:
        print("★★★ crc 算法已确定: %s" % max(hits, key=hits.get))
        for k, v in hits.items():
            print("    %-18s 命中 %d/%d" % (k, v, total))
        print()
        print("⇒ NVD 文件格式 = { u32 magic; u32 crc; u32 size; payload[size-12] }")
        print("⇒ ★ 可以安全构造/修改：改 payload 后按此算法重算 crc 即可")
    else:
        print("★ crc 算法未确定 —— 需继续试（可能是自定义 CRC32 变体）")
        print("  ★ 但 magic 与 size 字段已确定，文件结构清楚。")
    return 0


if __name__ == "__main__":
    sys.exit(main())