#!/usr/bin/env python3
"""WB K值验证实验：prefman save -> prefman fetch（内存态）-> 对比

用法
----
    python nvd_ab.py wb    # fetch 当前 app 块 -> 与 raw8/pref/cur_app.bin 对比
    python nvd_ab.py --save # 先 prefman save 0，再 fetch

★ 铁律（2026-10-06 实测）
------------------------
1. `prefman save` **不带 ID 是静默空操作**。必须 `prefman save 0`（0=app）。
2. `prefman fetch -a 0` 导出的是**内存副本**（/opt/pref/pref_app.bin，67340 字节），
   不是分区内容 —— 比 dd /dev/mmcblk0p2（10MB）快 40 倍，单次实验 15 秒。
3. NVD 的 `size` 字段 = **块总长（含 12 字节头）**，载荷 = size-12。
   取错会让载荷整体错位 4 个字。
4. 改机身设置只改运行时内存，**不 save 不落 NVD**。⇒「改了设置 NVD 没变」
   不能证明该字段不是那个参数（假阴性）。
"""
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PREF = ROOT / "raw8" / "pref"
HOST = "192.168.0.105"
SD = "/opt/storage/sdcard"
OUT = PREF / "cur_app.bin"
CUR = PREF / "cur_app.bin"

sys.path.insert(0, str(ROOT / "test_server" / "sysarch"))
from fwprobe import T          # noqa: E402
from ftpx import ftp_get# noqa: E402

NVD_HDR = 12


def save_and_fetch(do_save=True):
    t = T(HOST, timeout=25)
    t.login()
    if do_save:
        t.send("prefman save 0", 18.0)      # ★ 必须带 ID
        t.send("sync", 4.0)
    t.send("prefman fetch -a 0", 12.0)      # ★ 内存副本
    t.send("cp /opt/pref/pref_app.bin %s/nvdab/cur.bin" % SD, 5.0)
    t.send("wc -c < %s/nvdab/cur.bin" % SD, 8.0)
    t.send("rm -f %s/nvdab/p2.now" % SD, 2.0)
    t.send("exit", 1.0)
    t.close()
    time.sleep(1)
    return ftp_get(HOST, "/nvdab/cur.bin", str(OUT), timeout=180)


def load(path):
    """返回 (容器字节, 载荷字节) —— 已按 size-12 正确切载荷"""
    d = Path(path).read_bytes()
    magic, crc, size = struct.unpack_from("<III", d, 0)
    assert magic == 0x00330033, "magic 错误 0x%08x" % magic
    return d, d[NVD_HDR:size]


def main():
    do_save = "--save" in sys.argv
    if OUT.exists() and not do_save and "--redump" not in sys.argv:
        print("已存在 %s，跳过 fetch（--save 强制重取并先save）" % OUT.name)
    else:
        print("拉回: %s" % save_and_fetch(do_save))

    ca, cb = load(CUR), load(OUT)
    print("=" * 78)
    print("app 块对比: %s(%d字节)  vs  %s(%d字节)"
          % (CUR.name, len(ca[1]), OUT.name, len(cb[1])))
    print("=" * 78)

    for tag, (cd, pd) in (("前", ca), ("后", cb)):
        magic, crc, size = struct.unpack_from("<III", cd, 0)
        print("  %s: crc=0x%08x size=%d载荷=%d" % (tag, crc, size, len(pd)))

    n = min(len(ca[1]), len(cb[1])) // 4
    ch = [(i, struct.unpack_from("<I", ca[1], i * 4)[0],
           struct.unpack_from("<I", cb[1], i * 4)[0])
          for i in range(n)
          if struct.unpack_from("<I", ca[1], i * 4)[0]
          != struct.unpack_from("<I", cb[1], i * 4)[0]]
    print()
    print("差异 %d 个字 / %d" % (len(ch), n))
    for i, a, b in ch[:64]:
        print("  载荷 0x%06x (容器 0x%06x): 0x%08x(%-8d) -> 0x%08x(%-8d)"
              % (i * 4, i * 4 + NVD_HDR, a, a, b, b))
    if len(ch) > 64:
        print("  ... 还有 %d 个" % (len(ch) - 64))

    print()
    print("★ 已知关键槽位速查（载荷偏移 / 容器偏移 = 载荷+12）")
    for off, name in ((0xA37C, "ISO 档位"), (0xA380, "ISO 索引"),
                      (0xA384, "WB 索引"), (0xA388, "★ WB K 值")):
        va = struct.unpack_from("<I", ca[1], off)[0]
        vb = struct.unpack_from("<I", cb[1], off)[0]
        print("  0x%06x/0x%06x %-10s: %-8d -> %-8d %s"
              % (off, off + NVD_HDR, name, va, vb, "★变了" if va != vb else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())