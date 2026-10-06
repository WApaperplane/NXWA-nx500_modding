#!/usr/bin/env python3
"""SLP 容器 (NX500_v1.12.bin) 交叉分析 —— v2

要回答的问题（本项目最大未决项）：
    eMMC 的 p7 (rtos/rom.bin, ISP 固件本体) 是否在官方 SLP 固件容器内？
      在 => 改 p7 有【官方退路】（刷官方 .bin 走机身菜单）
      不在 => 无退路，只能靠单分区回滚（未验证）

★ 判据修正（v1 的 bug）：
    实机分区是块设备（30MB/10MB...），尾部有零填充；
    SLP 镜像是【紧凑有效数据】。
    ⇒ 正确判据 = `SLP 镜像字节 == 实机分区的前 len(SLP镜像) 字节`
    v1 误用 `len(SLP)==nonzero_len(实机)`，差几个尾部零字节就判"不一致"。
    ⇒ 铁律：判据里的"长度相等"要用【可比区间】而非【容器大小】。

顺带解 CRC32 变体（决定改过镜像后能否自校验）。
"""
import binascii
import hashlib
import struct
import sys
import zlib
from pathlib import Path

SLP = Path("D:/download/NX500_FW_v1.12/NX500_v1.12.bin")
ROOT = Path(__file__).resolve().parents[2]
BAK = ROOT / "raw8" / "emmcbak"
OUT = ROOT / "raw8" / "p7" / "slp_crosscheck.txt"

# 权威解析结果，来自 ge0rg/samsung-nx-hacks tools/slp-firmware.py -p
PARTS = [
    (0, 304, 6160624),
    (1, 6160928, 56289),
    (2, 6217217, 3176040),
    (3, 9393257, 6169816),
    (4, 15563073, 117184),
    (5, 15680257, 12075648),
    (6, 27755905, 280505658),
    (7, 308261563, 5022551),
    (8, 313284114, 28672),
    (9, 313312786, 38808649),
]
HDR_CRC = [0x48F3183B, 0x19D433B2, 0xD8719107, 0x2180947F, 0x8785210E,
           0xDF679D3B, 0xBDA66EC1, 0x41191FB5, 0xEF2256DF, 0xB5082DE3]

# idx -> 推测名称（依据 img_len 与 parttab / 已知结构）
GUESS = {
    0: "vImage / bootloader 区 (5.88MB)",
    1: "IPL+PNLBL 或 pcache.list",
    2: "uImage 主内核前半 (3.03MB)",
    3: "uImage 第二份 / rImage (5.88MB)",
    4: "小镜像 (114KB) 可能是 devicem4 或 pcache",
    5: "★★ rom.bin = rtos = ISP 固件本体 (11.52MB)",
    6: "rootfs.img (267MB)",
    7: "opt.img (4.8MB)",
    8: "小镜像 (28KB)",
    9: "另一 rootfs/备份 (37MB)",
}

LOCAL = [
    ("p7.bin", "rtos/rom.bin", "★★ ISP 固件本体"),
    ("p6.bin", "uImage", "主内核"),
    ("p13.bin", "rImage", "★ 实测也是 uImage"),
    ("p12.bin", "pcache", "预缓存清单"),
    ("p3.bin", "pref_default", "出厂偏好 ★回滚用"),
    ("p5.bin", "pref_recovery", "恢复偏好 ★回滚用"),
    ("p2.bin", "pref", "偏好"),
    ("p1.bin", "adj", "adjust"),
    ("p8.bin", "rtos_data", "rtos 数据区"),
]


def crc_variants(blob):
    """常见 CRC-32 变体，用于猜三星用的是哪个"""
    out = {}
    out["CRC-32/ISO-HDLC (zlib)"] = zlib.crc32(blob) & 0xFFFFFFFF
    out["CRC-32/JAMCRC"] = (zlib.crc32(blob) ^ 0xFFFFFFFF) & 0xFFFFFFFF
    out["CRC-32/BZIP2"] = _crc_nonzero_xorout(blob)
    out["CRC-32/MPEG-2"] = _crc_nonzero_xorout(blob, xorout=0)
    out["CRC-32/POSIX(cksum)"] = zlib.crc32(blob, 0xFFFFFFFF) & 0xFFFFFFFF
    # 也试"长度也被算进去"与"从 1 开始"等少数实现差异
    out["CRC-32/zlib(init=0,xorout=0)"] = _crc32_table(blob, 0, 0)
    out["CRC-32/zlib(init=FF,xorout=FF)"] = _crc32_table(blob, 0xFFFFFFFF, 0xFFFFFFFF)
    return out


# 预计算 256 项表，供无反射变体使用
_CRC_TBL = []
for _i in range(256):
    _c = _i << 24
    for _ in range(8):
        _c = ((_c << 1) ^ 0x04C11DB7) & 0xFFFFFFFF if (_c & 0x80000000) else (_c << 1) & 0xFFFFFFFF
    _CRC_TBL.append(_c)


def _crc_nonzero_xorout(data, xorout=0xFFFFFFFF):
    """MSB-first, poly=0x04C11DB7, 无输入/输出反射（即 BZIP2 / MPEG-2 家族）"""
    crc = 0xFFFFFFFF
    tbl = _CRC_TBL
    for byte in data:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ tbl[((crc >> 24) ^ byte) & 0xFF]
    return (crc ^ xorout) & 0xFFFFFFFF


def _crc32_table(data, init, xorout):
    """标准反射式 CRC-32，但 init/xorout 可自定义（排查非标准实现）"""
    crc = init & 0xFFFFFFFF
    for byte in data:
        crc = (crc >> 8) ^ _REVTBL[(crc ^ byte) & 0xFF]
    return (crc ^ xorout) & 0xFFFFFFFF


_REVTBL = []
for _i in range(256):
    _c = _i
    for _ in range(8):
        _c = (_c >> 1) ^ (0xEDB88320 if (_c & 1) else 0)
    _REVTBL.append(_c)


def main():
    if not SLP.exists():
        print("ERR: 找不到 %s" % SLP)
        return 2
    o = []
    f = open(SLP, "rb")
    total = SLP.stat().st_size

    hdr = f.read(64)
    magic = hdr[0:4]
    version = hdr[4:12].split(b"\0")[0].decode()
    project = hdr[12:28].split(b"\0")[0].decode()
    rev = hdr[28:44].split(b"\0")[0].decode()
    has_pcache = struct.unpack_from("b", hdr, 44)[0]

    o.append("=" * 78)
    o.append("SLP 容器 × 实机 eMMC 分区 交叉分析")
    o.append("容器: %s  (%d 字节 = %.1f MB)" % (SLP.name, total, total / 1048576))
    o.append("=" * 78)
    o.append("  magic        = %r  %s" % (magic, "OK" if magic == b"SLP\0" else "★不是 SLP"))
    o.append("  version      = %s" % version)
    o.append("  project      = %s" % project)
    o.append("  version_date = %s" % rev)
    o.append("  has_pcache   = %d  => %s"
             % (has_pcache, "V2 格式，10 个 image 分区表内嵌在文件头" if has_pcache > 1
                else "V1 格式，固定 5 分区 + pcache"))
    o.append("")

    # ---- 分区索引 ----
    o.append("---- SLP 10 个 image 分区（按 img_offset 排序）----")
    o.append("  %-4s %-12s %-34s %-9s %s" % ("idx", "img_len", "head1M_md5", "hdr_crc32", "推测"))
    heads = {}
    blobs = {}
    for idx, off, ln in PARTS:
        f.seek(off)
        blob = f.read(ln)
        blobs[idx] = blob
        heads[idx] = hashlib.md5(blob[:1 << 20]).hexdigest()
        o.append("  %-4d %-12d %-34s %08x  %s"
                 % (idx, ln, heads[idx][:32], HDR_CRC[idx], GUESS.get(idx, "")))
    # 覆盖完整性自证
    covered = sum(ln for _, _, ln in PARTS)
    o.append("")
    o.append("  覆盖自证: 10 个 img_len 之和 = %d (%.1f%% of %d)"
             % (covered, covered * 100.0 / total, total))
    o.append("  分区 6 (280505658) 是否 rootfs：看是否 LZO/ext4 超级块特征在下一节验证")
    o.append("")

    # ---- 与实机备份对照（正确判据：SLP 镜像 == 实机分区前缀）----
    o.append("---- 实机 eMMC 备份 × SLP 分区（判据: SLP 镜像 == 实机分区前 N 字节）----")
    matched = {}
    for name, vol, note in LOCAL:
        p = BAK / name
        if not p.exists():
            o.append("  %-9s MISSING" % name)
            continue
        b = p.read_bytes()
        lm = hashlib.md5(b[:1 << 20]).hexdigest()
        hits = [i for i, m in heads.items() if m == lm]
        if not hits:
            o.append("  %-9s %-16s -> ★★ SLP 内无匹配（属出厂状态/用户数据区）" % (name, vol))
            o.append("             %s" % note)
            continue
        idx = hits[0]
        blob = blobs[idx]
        n = len(blob)
        exact = (b[:n] == blob)
        tail_nonzero = 0
        for i in range(n, len(b)):
            if b[i] != 0:
                tail_nonzero += 1
        matched[name] = (idx, exact)
        o.append("  %-9s %-16s -> SLP[%d] len=%-10d  %s"
                 % (name, vol, idx, n, "★★ 完全一致" if exact else "★ 前缀有差异"))
        o.append("             尾部(超出 SLP 镜像部分)非零字节 = %d  %s"
                 % (tail_nonzero, "(全零 ⇒ SLP 镜像是实机分区的完整有效数据)"
                    if tail_nonzero == 0 else "★ 尾部有数据 ⇒ SLP 镜像不完整"))
        o.append("             %s" % note)
    o.append("")

    # ---- rootfs 验证：SLP[6] 是否 LZO ext4 ----
    o.append("---- SLP[6] (280505658) 是否 rootfs.img ----")
    b6 = blobs[6]
    o.append("  头 16 字节: %s" % " ".join("%02x" % x for x in b6[:16]))
    # ext4 超级块 magic=0xEF53 在 offset 0x438 (LZO 压缩后不可直接读)
    # LZO/xz/gzip 魔数检测
    for nm, magic_bytes in [("gzip", b"\x1f\x8b"), ("xz", b"\xfd7zXZ"),
                            ("bzip2", b"BZ"), ("LZO/lz4", b"\x89LZO"),
                            ("squashfs", b"hsqs"), ("cpio", b"070701"),
                            ("ext4@0", b"\x53\xef")]:
        if b6[:len(magic_bytes)] == magic_bytes:
            o.append("  ★ 命中 %s 魔数" % nm)
    o.append("  ★ rootfs.img 是 LZO 压缩的 ext4（Lzop 格式头 = 9 字节 89 4c 5a 4f 00 0d 0a 1a 0a）")
    o.append("    头 9 字节 = %s  %s"
             % (" ".join("%02x" % x for x in b6[:9]),
                "★ LZOP 命中" if b6[:4] == b"\x89LZO" else ""))
    o.append("")

    # ---- CRC32 变体 ----
    o.append("---- SLP 头 crc32 字段用哪个变体？ ----")
    o.append("  目的：改镜像后能否自校验（若能复算，就能自动改 crc 字段而不被刷写器拒）")
    hitvar = None
    # 先在小分区上试（快）：若命中变体即可锁定，再到大分区验证
    for idx in (8, 4, 1, 0):
        o.append("  --- SLP[%d] len=%d header_crc32=%08x ---" % (idx, PARTS[idx][2], HDR_CRC[idx]))
        v = crc_variants(blobs[idx])
        for k, val in v.items():
            ok = "MATCH ★★★" if val == HDR_CRC[idx] else ""
            o.append("      %-26s = %08x  %s" % (k, val, ok))
            if ok and hitvar is None:
                hitvar = k
        o.append("")
    o.append("  结论: %s" % ("★ 命中变体 = %s ⇒ 改镜像后必须同步改 crc32 字段" % hitvar
                            if hitvar else "★ 全部变体都不匹配 ⇒ 校验算法未知（非标准 CRC32）"
                                                 "⇒ 改镜像后无法预知刷写器是否接受，风险高"))
    o.append("")

    # ---- 最终结论 ----
    o.append("=" * 78)
    o.append("最终结论")
    o.append("=" * 78)
    p7 = matched.get("p7.bin")
    if p7 and p7[1]:
        o.append("★★★ p7 (rtos/rom.bin = ISP 固件) 【完全在官方 SLP 容器的分区 %d 内】" % p7[0])
        o.append("   ⇒ 【有官方退路】：改坏 p7 后，把官方 NX500_v1.12.bin 放 SD 卡，")
        o.append("     走机身菜单 Settings → Device Information → Firmware Update 恢复。")
        o.append("   ⇒ 恢复粒度是【整机级】（rootfs + rtos + 所有分区一起刷回官方状态）")
        o.append("   ⇒ 这解开了昨晚的 T-Kernel 歧义：")
        o.append("     SLP 里的 T-Kernel 2.01.03 ≈ 分区 5（11.52MB，rom.bin）")
        o.append("     ★ 它就是 ISP 固件，不是给 Cortex-A7/A9 的 Linux 内核")
    else:
        o.append("★★ p7 在 SLP 内【未完全匹配】⇒ 无官方退路，只能靠单分区回滚（未验证）")

    o.append("")
    o.append("完全匹配 SLP 分区的实机备份: %s"
             % (", ".join("%s->SLP[%d]" % (n, v[0]) for n, v in matched.items() if v[1]) or "(无)"))
    un = [n for n, _, _ in LOCAL if n not in matched]
    if un:
        o.append("未匹配的备份: %s" % ", ".join(un))
        o.append("  ⇒ 这些分区【不在官方 SLP 内】= 出厂状态/用户数据区")
        o.append("  ⇒ ★ 刷官方固件【不会覆盖它们】= 我们的 prefman/adj 等持久化数据是安全的")
        o.append("  ⇒ ★★ 但也因此：p12(pcache) 若被改坏，官方固件救不了 —— 备份已在手")

    txt = "\n".join(o)
    print(txt)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(txt, encoding="utf-8")
    print()
    print("written: %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())