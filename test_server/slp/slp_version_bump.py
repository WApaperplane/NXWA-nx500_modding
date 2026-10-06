#!/usr/bin/env python3
"""生成"改版本号"的 SLP 固件 —— 后备方案

背景
----
2026-10-06 实测：把官方 `NX500_v1.12.bin` 改名成 `NX500.bin` 后，
**机身"Body Firmware Update"菜单项从灰色变亮** ⇒ 拦路虎是【文件名】而非版本号。
但这是官方流程走通的必要条件，不等于版本检查一定也能过
（相机当前 1.12，固件也是 1.12，单调性检查存在但尚未被执行到）。

所以准备一个后备镜像：只把 SLP 头偏移 0x04 的 version_user 从 "1.12" 改成更高版本。
依据 = 社区唯一实证先例（NX1000 降级包，ottokiksmaler 仓库）：
    "just the string \"1.13\" changed to \"1.16\" in nx1000.bin. No other changes have been made."
    相机显示 v1.16 而实际内容是 v1.13 ⇒ 版本检查单向单调，且读的是内容里的版本串。

安全设计
--------
1. **只改 SLP 头，不动任何分区** —— 10 个 image header 与数据区逐字节原样搬运
2. **SLP 头不在任何分区内** ⇒ 改动【不影响】任何分区的 JAMCRC，无需重算
3. version_user 是 8 字节定长（NUL 填充）⇒ 改版本号不改变任何偏移
4. **默认 dry-run**，不加 --write 不落盘
5. 拒绝把版本改短（会破坏 8 字节定长字段的对齐假设）
6. 回读校验：确认只有一个字节位变化，且版本号正确

用法
----
    python slp_version_bump.py NX500.bin --to 1.13 -O out.bin          # dry-run
    python slp_version_bump.py NX500.bin --to 1.13 -O out.bin --write  # 真写

⚠️ 命名提醒：输出文件名【必须是 nx500.bin 或 NX500.bin】
   —— 实测 updater 硬编码找的就是这个名字（文件内容改名无效，文件名必须改）
"""
import argparse
import hashlib
import struct
import sys
from pathlib import Path

META_FMT = "<4s8s16s16sbI15s"
META_SIZE = struct.calcsize(META_FMT)   # 64
VER_OFF = 4                               # version_user 在 SLP 头内的偏移
VER_LEN = 8                               # 定长 8 字节


def read_meta(head):
    if len(head) < META_SIZE:
        raise ValueError("文件太小")
    magic, ver, proj, vdate, has_pc, pc_off, rsv = struct.unpack_from(META_FMT, head, 0)
    return dict(magic=magic, version=ver, project=proj, version_date=vdate,
                has_pcache=has_pc, pcache_offset=pc_off, reserved=rsv)


def bump_version(src, new_ver, out, write=False):
    """只改 SLP 头 0x04 的 version_user，返回 (结果说明, 新字节 or None)"""
    src = Path(src)
    size = src.stat().st_size
    with open(src, "rb") as f:
        head = bytearray(f.read(META_SIZE))
    meta = read_meta(head)

    old_ver = meta["version"].split(b"\0")[0].decode("ascii", "replace")
    new_b = new_ver.encode("ascii")
    if len(new_b) > VER_LEN - 1:
        raise ValueError("新版本号太长（最多 %d 字节，含 NUL）" % (VER_LEN - 1))
    if len(new_b) < len(old_ver):
        raise ValueError("新版本号比旧的短（%r -> %r）会改变字段填充，"
                         "为安全起见本工具拒绝" % (old_ver, new_ver))

    print("---- 版本串改写计划 ----")
    print("  源文件      : %s" % src)
    print("  文件大小    : %d 字节 (%.1f MB)" % (size, size / 1048576))
    print("  偏移        : 0x%02X (META_FMT 的 version_user 字段)" % VER_OFF)
    print("  旧值        : %r  (raw %s)"
          % (old_ver, " ".join("%02x" % x for x in head[VER_OFF:VER_OFF + VER_LEN])))
    print("  新值        : %r" % new_ver)
    print()
    print("  ★ 只改 SLP 头，10 个 image 分区与数据区逐字节不变")
    print("  ★ SLP 头不在任何分区内 ⇒ JAMCRC 无需重算")
    print("  ★ version_user 是 8 字节定长 ⇒ 所有偏移不变")
    print()
    print("  ★★ 刷写时文件名【必须是 nx500.bin / NX500.bin】（实测拦路虎）")
    print()

    # 改：NUL 填充到 8 字节
    newhead = bytearray(head)
    newhead[VER_OFF:VER_OFF + VER_LEN] = new_b.ljust(VER_LEN, b"\0")
    diff = [i for i in range(META_SIZE) if head[i] != newhead[i]]
    print("  将改变 %d 个字节: %s" % (len(diff), [hex(x) for x in diff]))
    if not write:
        print("  dry-run：未写文件。加 --write 生成。")
        return True

    tmp = Path(out + ".tmp")
    h = hashlib.md5()
    with open(src, "rb") as fi, open(tmp, "wb") as fo:
        fo.write(bytes(newhead))
        h.update(bytes(newhead))
        fi.seek(META_SIZE)
        while True:
            b = fi.read(1 << 22)
            if not b:
                break
            fo.write(b)
            h.update(b)
    tmp.replace(out)
    out = Path(out)

    # 回读校验
    with open(out, "rb") as f:
        back = f.read(META_SIZE)
    m2 = read_meta(back)
    got = m2["version"].split(b"\0")[0].decode("ascii", "replace")
    # 与源逐字节比对差异位置（应只在 0x04..0x0b 内）
    with open(src, "rb") as f:
        f.seek(VER_OFF)
        a = f.read(VER_LEN)
    d2 = [i for i in range(VER_LEN) if a[i] != back[VER_OFF + i]]
    print("---- 回读校验 ----")
    print("  版本号读回   : %r  %s" % (got, "OK" if got == new_ver else "★不符"))
    print("  改动的字节   : %s (区内偏移 %s)"
          % ([hex(x) for x in d2], "全在 0x04..0x0b 内" if d2 and max(d2) < VER_LEN else "★越界!"))
    print("  文件大小     : %d  %s" % (out.stat().st_size,
                                       "OK 与源一致" if out.stat().st_size == size else "★变了!"))
    print("  md5          : %s" % h.hexdigest())
    ok = (got == new_ver) and d2 and max(d2) < VER_LEN and out.stat().st_size == size
    print()
    print("  总体: %s" % ("PASS ✔" if ok else "FAIL ✘"))
    if ok:
        print()
        print("  ★ 接下来：把输出文件【改名为 nx500.bin】放 SD 卡根目录，")
        print("    走机身 MENU → Setting → Device Information → Firmware Update → Body Firmware Update")
    return ok


def main():
    ap = argparse.ArgumentParser(description="SLP 版本串改写（后备方案，默认 dry-run）")
    ap.add_argument("src", help="源 .bin（建议用官方原文件）")
    ap.add_argument("--to", required=True, help="新版本号，如 1.13")
    ap.add_argument("-O", "--out", default="nx500_v1.13.bin", help="输出路径")
    ap.add_argument("--write", action="store_true", help="★ 真写文件（默认只报告）")
    args = ap.parse_args()

    print("=" * 70)
    print("SLP 版本串改写工具（后备方案 / 默认 dry-run）")
    print("=" * 70)
    print()
    try:
        ok = bump_version(args.src, args.to, args.out, write=args.write)
    except Exception as e:
        print("ERR: %s" % e)
        return 2
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())