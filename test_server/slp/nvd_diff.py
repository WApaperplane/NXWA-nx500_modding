#!/usr/bin/env python3
"""NVD A/B 对比工具 —— 定位"哪个偏移 = 哪个参数"

用法
----
    python nvd_diff.py base          # 以 p2_live.raw 为基线，dump 当前 p2 并diff
    python nvd_diff.py <file>        # 与基线 diff 指定的 dump
    python nvd_diff.py --save-base   # 把当前 p2 存为新基线

原理
----
NVD 载荷是 4 字节对齐的稀疏数组（已由 line 块的结构确认：
16 个非零区段全在 0x1F4-0x23B 的 72 字节内，值全是 0x02）。
所以对比的基本单位是 **4 字节字**，而不是字节 ——
单字节 diff 会把"同一条记录的相邻字段"混在一起，看不出语义。

输出
----
- 每个 NVD 块里变化的 4 字节字：偏移 / 旧值 / 新值 / 位翻转模式
- 变化的字节总数
- 对"只变一个字段"的字额外标注（最可能是被改的那个参数）
"""
import struct
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "raw8" / "pref" / "p2_live.raw"
HOST = "192.168.0.105"
SD = "/opt/storage/sdcard"

# p2 分区的 4 个 NVD 块（已用官方 --merge seek 公式 4/4 验证）
BLOCKS = [
    (0x000000, "app"),
    (0x060000, "app_restore"),
    (0x080000, "line"),
    (0x100000, "sysrw"),
]
NVD_HDR = 12


def dump_from_camera(out_local, host=HOST):
    """只读 dd 相机 p2 分区 -> FTP 拉回本地"""
    import sys as _s
    _s.path.insert(0, str(ROOT / "test_server" / "sysarch"))
    from fwprobe import T
    from ftpx import ftp_get
    t = T(host, timeout=25)
    t.login()
    t.send("mkdir -p %s/nvdab" % SD, 3.0)
    t.send("dd if=/dev/mmcblk0p2 of=%s/nvdab/p2.now bs=1024 2>/dev/null" % SD, 40.0)
    sz = t.send("wc -c < %s/nvdab/p2.now" % SD, 10.0)
    t.send("exit", 1.0)
    t.close()
    time.sleep(1)
    n = ftp_get(host, "/nvdab/p2.now", str(out_local), timeout=600)
    return n


def load_blocks(path):
    d = path.read_bytes()
    out = {}
    for off, name in BLOCKS:
        mg, crc, size = struct.unpack_from("<III", d, off)
        payload = d[off + NVD_HDR:off + NVD_HDR + size]
        out[name] = dict(off=off, magic=mg, crc=crc, size=size, payload=payload)
    return out


def bitdiff(a, b):
    """两值的位翻转模式描述"""
    x = a ^ b
    if x == 0:
        return ""
    bits = []
    for i in range(32):
        if x & (1 << i):
            bits.append("b%d" % i)
    s = ",".join(bits)
    return s if len(s) <= 12 else s[:9] + "..."


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]

    if cmd == "--save-base":
        n = dump_from_camera(BASE)
        print("新基线已存: %s (%s bytes)" % (BASE, n))
        return 0

    if cmd == "base":
        cur = ROOT / "raw8" / "pref" / "p2_now.raw"
        n = dump_from_camera(cur)
        if not n:
            print("ERR: dump 失败")
            return 1
        print("当前 p2 已拉回: %s bytes" % n)
        target = cur
    else:
        target = Path(sys.argv[1])

    if not BASE.exists():
        print("ERR: 基线不存在 %s" % BASE)
        return 1
    if not target.exists():
        print("ERR: 对比目标不存在 %s" % target)
        return 1

    A = load_blocks(BASE)
    B = load_blocks(target)
    print("=" * 78)
    print("NVD A/B 对比: %s  vs  %s" % (BASE.name, target.name))
    print("=" * 78)

    total_words = 0
    total_bytes = 0
    for off, name in BLOCKS:
        a, b = A[name], B[name]
        print()
        print("---- 块 %-14s (容器偏移 0x%06x, size=%d) ----" % (name, off, a["size"]))
        if a["crc"] != b["crc"]:
            print("  ★ crc 变了: 0x%08x -> 0x%08x" % (a["crc"], b["crc"]))
        if a["magic"] != b["magic"]:
            print("  ★★★ magic 变了(通常意味着块损坏!): 0x%08x -> 0x%08x" % (a["magic"], b["magic"]))
        pa, pb = a["payload"], b["payload"]
        n = min(len(pa), len(pb))
        if len(pa) != len(pb):
            print("  ★ size 变了: %d -> %d" % (len(pa), len(pb)))
        # 4 字节字对比
        nw = n // 4
        changed = []
        for i in range(nw):
            wa = struct.unpack_from("<I", pa, i * 4)[0]
            wb = struct.unpack_from("<I", pb, i * 4)[0]
            if wa != wb:
                changed.append((i, wa, wb))
        if not changed:
            print("  无变化(4 字节粒度)")
            continue
        # 字节级差异
        nbytes = sum(1 for i in range(n) if pa[i] != pb[i])
        total_words += len(changed)
        total_bytes += nbytes
        print("  变化: %d 个字 / %d 字节 (载荷 %d 字节)" % (len(changed), nbytes, n))
        print("  %-10s %-12s %-12s %s" % ("字偏移", "旧值", "新值", "翻转位"))
        for i, wa, wb in changed[:64]:
            print("  0x%08x  0x%08x  0x%08x  %s" % (i * 4, wa, wb, bitdiff(wa, wb)))
        if len(changed) > 64:
            print("  ... 还有 %d 个字未显示" % (len(changed) - 64))
        # 只变了一个字的 = 高置信度的目标参数
        if len(changed) == 1:
            i, wa, wb = changed[0]
            print()
            print("  ★★★ 只变了一个字 => 高置信度目标参数")
            print("       字偏移 0x%08x : 0x%08x -> 0x%08x (翻转 %s)"
                  % (i * 4, wa, wb, bitdiff(wa, wb)))
            print("       块内偏移 = 0x%08x (含 12 字节头)" % (i * 4 + NVD_HDR))

    print()
    print("=" * 78)
    print("总计: %d 个字变化 / %d 字节变化" % (total_words, total_bytes))
    return 0


if __name__ == "__main__":
    sys.exit(main())