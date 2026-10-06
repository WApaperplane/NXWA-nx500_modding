#!/usr/bin/env python3
"""app 块 0xa300-0xa600 区段的常量/数组结构分析

目的
----
已定位 UserData 索引槽（0xa388 ISO档位 / 0xa38c ISO索引 / 0xa390 WB索引），
但周边还有一批"一直存在"的常量（0x157c / 0x70007×10 / 0x64×N），
需要判断哪些是参数、哪些是固定表 —— 这决定它们能不能改。

判据
----
若某值在"基线"和"改过设置"两份 dump 里【都相同且非零】⇒ 它是常量或默认值，
   不是本次被改的参数。
若在某次实验中【只有它变了】⇒ 那就是被改的参数。
"""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "raw8" / "pref"
BASE = ROOT / "p2_live.raw"        # 基线：未改任何设置
CUR = ROOT / "p2_wb1600.raw"       # ISO1600 + WB5500K

APP = 0x00000000
APP_R = 0x00060000


def rd(path, off):
    return struct.unpack_from("<I", Path(path).read_bytes(), off)[0]


def main():
    print("=" * 76)
    print("app 块 0xa300-0xa600 区段结构分析")
    print("=" * 76)
    print()
    print("判据: 基线与当前都相同且非零 = 常量/默认值（不可改）")
    print("只变= 被改的参数")
    print()

    print("---- 1. 扫描 0x64(=100) 连续区 ----")
    for label, f in (("基线", BASE), ("当前", CUR)):
        d = Path(f).read_bytes()
        run = 0
        runs = []
        for off in range(0xA300, 0xA600, 4):
            if struct.unpack_from("<I", d, off)[0] == 0x64:
                run += 1
            else:
                if run >= 3:
                    runs.append((off - run * 4, run))
                run = 0
        if run >= 3:
            runs.append((0xA600 - run * 4, run))
        print("  %s: %s" % (label, ["0x%06x起 %d个" % (s, n) for s, n in runs] or "无"))

    print()
    print("---- 2. 0x157c 是否随 WB 变化（关键判据）----")
    v_base = rd(BASE, APP + 0xA394)
    v_cur = rd(CUR, APP + 0xA394)
    print("  0xa394  基线=0x%08x (%d)   当前=0x%08x (%d)   %s"
          % (v_base, v_base, v_cur, v_cur, "变了★" if v_base != v_cur else "★未变 ⇒ 是常量/默认值"))
    print("  用户设的 WB = 5500K；0x157c = %d" % v_base)
    print("  ⇒差 %d" % (5500 - v_base))
    print("  ⇒ 结论: %s"
          % ("该值不随 WB 改而变，**不是当前 K 值的存储**（可能是默认 WB 或别的常量）"
             if v_base == v_cur else "★随 WB 变 ⇒ 可能是 K 值存储"))

    print()
    print("---- 3. 0xa300-0xa360 的 2的幂/常量特征 ----")
    d = Path(BASE).read_bytes()
    for off in range(0xA300, 0xA364, 4):
        v = struct.unpack_from("<I", d, off)[0]
        tag = ""
        if v and (v & (v - 1)) == 0:
            tag = "<< 2的幂 = %d" % v
        print("  0x%06x: 0x%08x %10d  %s" % (off, v, v, tag))

    print()
    print("---- 4. 全区段：区分【常量区】【索引槽区】【数据区】----")
    changed = set()
    db, dc = Path(BASE).read_bytes(), Path(CUR).read_bytes()
    for off in range(0xA300, 0xA600, 4):
        if struct.unpack_from("<I", db, off)[0] != struct.unpack_from("<I", dc, off)[0]:
            changed.add(off)
    # 分段统计
    print("  变化点:", ["0x%06x" % o for o in sorted(changed)])
    print()
    # 0x70007 重复区
    print("---- 5. 0x70007 重复区（10 次）是什么 ----")
    cnt = 0
    for off in range(0xA300, 0xA600, 4):
        if struct.unpack_from("<I", db, off)[0] == 0x70007:
            cnt += 1
    print("  0x70007 出现 %d 次" % cnt)
    print("  0x70007 = 0x0007<<16 | 0x0007 ⇒ 16.16 定点数 = 0x0007.0007 ≈ 7.0004")
    print("  ★ 若解释为 16.16 定点: 7.0004")
    print("  ★ 若是两个 16 位段: 高=0x0007=7, 低=0x0007=7")
    print("  ⇒ 重复 10 次⇒ 很可能是【10 个通道/档位的固定系数表】")
    print("    (10 = 3 个RGB 通道 ×? 或 ISO 档位表/ 镜头补偿表)")

    print()
    print("---- 6. 0x0a×4 与 0x64×N 的可能含义 ----")
    for v, cnt in ((0x0A, 0), (0x64, 0)):
        c = sum(1 for off in range(0xA300, 0xA600, 4)
                if struct.unpack_from("<I", db, off)[0] == v)
        print("  0x%02x (%d) 出现 %d 次" % (v, v, c))
    print("  ★ 0x0a(10) ×4  ⇒ 可能是 4 个通道/档位的固定值")
    print("  ★ 0x64(100) ×N ⇒ ★★ 很可能是【百分比增益表】(100 = 100% 基准)")
    return 0


if __name__ == "__main__":
    sys.exit(main())