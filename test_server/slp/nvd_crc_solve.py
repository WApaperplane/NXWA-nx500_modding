#!/usr/bin/env python3
"""NVD crc 算法反解 —— 用真实数据穷举变体

背景
----
NVD 文件头（12 字节）：
    +0x00 u32 magic = 0x00330033
    +0x04 u32 crc
    +0x08 u32 size  = 载荷字节数
    +0x0C u8[] payload

之前用 default 节点的 12 个文件试了 8 种常见算法全部未命中 ——
但那些文件 **payload 几乎全零**（非零字节仅 7-14 个），
⇒★ **用全零数据反解 crc 是无效的**（很多变体在全零输入上输出相同，无法区分）。

本工具用**有真实数据的 p2 分区**重试：
  0x000000 app    size=67340  （用户数据，与 default 节点同尺寸但内容不同）
  0x060000 app_restore size=43876
  0x080000 line   size=2560
  0x100000 sysrwsize=1616    ← 非零字节 33 个，default 节点只有 8个 ⇒★ 有真实数据
"""
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P2 = ROOT / "raw8" / "pref" / "p2_live.raw"
DEF = ROOT / "raw8" / "pref"

# p2 分区的 4 个 NVD 块（已用官方 --merge seek 公式验证）
P2_BLOCKS = [
    (0x000000, "app"),
    (0x060000, "app_restore"),
    (0x080000, "line"),
    (0x100000, "sysrw"),
]

# 三星常用 CRC32 poly
POLYS = {
    "0x04C11DB7(reflect out)": 0xEDB88320,
    "0x04C11DB7(no reflect)": 0x04C11DB7,
}


def build_crc_tables(poly):
    """预计算反射/非反射表"""
    refl = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ (poly if (c & 1) else 0)
        refl.append(c & 0xFFFFFFFF)
    nrefl = []
    for i in range(256):
        c = (i << 24) & 0xFFFFFFFF
        for _ in range(8):
            c = ((c << 1) ^ poly) & 0xFFFFFFFF if (c & 0x80000000) else (c << 1) & 0xFFFFFFFF
        nrefl.append(c & 0xFFFFFFFF)
    return refl, nrefl


def crc_generic(data, poly, init, xorout, reflected, width=32):
    """通用 CRC32：reflected + 任意 init/xorout"""
    if reflected:
        tbl = []
        for i in range(256):
            c = i
            for _ in range(8):
                c = (c >> 1) ^ (poly if (c & 1) else 0)
            tbl.append(c & 0xFFFFFFFF)
        crc = init & 0xFFFFFFFF
        for b in data:
            crc = (crc >> 8) ^ tbl[(crc ^ b) & 0xFF]
        return (crc ^ xorout) & 0xFFFFFFFF
    else:
        tbl = []
        for i in range(256):
            c = (i << 24) & 0xFFFFFFFF
            for _ in range(8):
                c = ((c << 1) ^ poly) & 0xFFFFFFFF if (c & 0x80000000) else (c << 1) & 0xFFFFFFFF
            tbl.append(c & 0xFFFFFFFF)
        crc = init & 0xFFFFFFFF
        for b in data:
            crc = ((crc << 8) & 0xFFFFFFFF) ^ tbl[((crc >> 24) ^ b) & 0xFF]
        return (crc ^ xorout) & 0xFFFFFFFF


def candidates(data, crc_field_off=4):
    """穷举常见 (poly, init, xorout, reflected, range) 组合"""
    out = {}
    body = data
    zeroed = bytearray(data)
    zeroed[crc_field_off:crc_field_off + 4] = b"\0\0\0\0"
    zeroed = bytes(zeroed)
    after = data[crc_field_off + 4:]

    ranges = {
        "body": body,
        "crc字段置零": zeroed,
        "crc字段之后": after,
    }
    inits = {
        "0x00000000": 0x00000000,
        "0xFFFFFFFF": 0xFFFFFFFF,
    }
    xorouts = {
        "0x00000000": 0x00000000,
        "0xFFFFFFFF": 0xFFFFFFFF,
    }
    for rname, rdata in ranges.items():
        for pname, poly in POLYS.items():
            refl = "no reflect" not in pname
            for iname, iv in inits.items():
                for xname, xv in xorouts.items():
                    key = "%s | %s | init=%s | xor=%s" % (rname, pname, iname, xname)
                    try:
                        out[key] = crc_generic(rdata, poly, iv, xv, refl)
                    except Exception:
                        pass
    # 内置快速算法
    out["zlib(body)"] = zlib.crc32(body) & 0xFFFFFFFF
    out["JAMCRC(body)"] = (zlib.crc32(body) ^ 0xFFFFFFFF) & 0xFFFFFFFF
    out["adler32(body)"] = zlib.adler32(body) & 0xFFFFFFFF
    return out


def main():
    d = P2.read_bytes()
    print("=" * 78)
    print("NVD crc 算法反解（用 p2 分区的真实数据）")
    print("=" * 78)
    print("数据源: %s (%d 字节)" % (P2.name, len(d)))
    print()
    print("★ 上一轮失败的原因: default 节点 12 个文件的 payload 几乎全零")
    print("  (非零字节仅 7-14) ⇒ 用全零数据无法区分 crc 变体")
    print()

    hits = {}
    total = 0
    for off, name in P2_BLOCKS:
        mg, crc, size = struct.unpack_from("<III", d, off)
        payload = d[off + 12:off + 12 + size]
        nz = sum(1 for b in payload if b)
        total += 1
        print("---- 块 %-14s offset=0x%06x size=%-8d 载荷非零=%-7d(%.2f%%) crc字段=0x%08x ----"
              % (name, off, size, nz, nz * 100.0 / max(1, len(payload)), crc))
        c = candidates(payload)
        hit = [k for k, v in c.items() if v == crc]
        for k in hit:
            hits[k] = hits.get(k, 0) + 1
        if hit:
            print("   ★★ 命中: %s" % " | ".join(hit[:4]))
        else:
            print("   (%d 种组合均未命中)" % len(c))
            # 打印最接近的几个
            near = sorted(c.items(), key=lambda kv: -bin(kv[1] ^ crc).count("1"))[:3]
            for k, v in near:
                print("       %-64s = 0x%08x  (差 %d bit)" % (k, v, bin(v ^ crc).count("1")))
        print()

    print("=" * 78)
    if hits:
        best = max(hits, key=hits.get)
        print("★★★ crc 算法确定: %s" % best)
        print("   命中 %d / %d 个块" % (hits[best], total))
    else:
        print("★ 仍未确定 —— 需要更大范围的穷举（如 byte-order/bit-reversal/非32 位 crc）")
    return 0


if __name__ == "__main__":
    sys.exit(main())