#!/usr/bin/env python3
"""initramfs (SLP[1]) 分析器 —— 找 init.xImage 的 dd 直烧逻辑

背景
----
ge0rg 在 issue #121 反编译 vImage 的 initramfs 时发现**三个** init 模板：
  init.vImage  -> 调 fw_upgrade（正常刷固件，**有版本检查**）
  init.rImage  -> recovery 镜像，调 fw_recovery
  ★ init.xImage -> 从 SD 卡 dd 直烧 devicem4.bin/rootfs.img/opt.img/rImage/pcache.list
                  **完全绕过 SLP 容器与版本检查**  ← 本项目最关心的

本工具做三件事：
  1. 解开 SLP[1]（裸 ARM initramfs，无压缩）
  2. 列出 initramfs 里的文件清单（cpio newc 格式手工解析）
  3. dump 三个 init.* 脚本的全文，重点标出 dd / 刷写相关行

cpio newc 格式（本工具只做读取，不构造）：
  magic     6B  "070701"
  ino/mode/uid/gid/nlink/mtime/filesize/devmaj/devmin/rdevmaj/rdevmin/
  namesize/chksum   各 8B 十六进制
  name      namesize 字节（NUL 结尾）
  pad       到 4 字节边界
  data      filesize 字节
  pad       到 4 字节边界
  ... 直到 name == "TRAILER!!!"
"""
import struct
import sys
from pathlib import Path

SLP = Path("D:/download/NX500_FW_v1.12/NX500.bin")
# SLP[1] = offset 6160928, len 56289（权威值来自 ge0rg slp-firmware.py -p）
PART_OFF, PART_LEN = 6160928, 56289
OUTDIR = Path(__file__).resolve().parent.parent / "raw8" / "initramfs"


def read_slp_part(off, ln):
    with open(SLP, "rb") as f:
        f.seek(off)
        return f.read(ln)


def parse_cpio(blob):
    """手工解析 cpio newc，返回 [(name, mode, filesize, data_offset)]"""
    out = []
    p = 0
    n = len(blob)
    while p + 110 <= n:
        if blob[p:p + 6] not in (b"070701", b"070702"):
            # 允许 padding：跳到下一个 magic
            idx = blob.find(b"070701", p)
            if idx < 0:
                break
            p = idx
            continue
        hdr = blob[p + 6:p + 110]
        f = [int(hdr[i * 8:(i + 1) * 8], 16) for i in range(13)]
        namesize, filesize = f[11], f[6]
        name_off = p + 110
        name = blob[name_off:name_off + namesize - 1].decode("utf-8", "replace")
        data_off = name_off + namesize
        data_off = (data_off + 3) & ~3
        mode = f[1]
        if name == "TRAILER!!!":
            break
        out.append((name, mode, filesize, data_off))
        p = (data_off + filesize + 3) & ~3
    return out


def main():
    blob = read_slp_part(PART_OFF, PART_LEN)
    print("=" * 74)
    print("initramfs (SLP[1]) 分析")
    print("=" * 74)
    print("来源: %s  offset=%d  len=%d" % (SLP.name, PART_OFF, PART_LEN))
    print("容器 : 裸 ARM 镜像（无 uImage 头），头 4 字节 = 06 00 00 ea = ARM 'b .'")
    print()
    entries = parse_cpio(blob)
    if not entries:
        print("!! cpio 解析失败 —— 尝试直接扫可读串定位 init 脚本")
        blob_out = OUTDIR / "initramfs_raw.bin"
        blob_out.parent.mkdir(parents=True, exist_ok=True)
        blob_out.write_bytes(blob)
        print("已存原始镜像: %s" % blob_out)
        # 手工找脚本
        import re
        print()
        print("---- 可读串里的 init/fw_/dd 线索 ----")
        for m in re.finditer(rb"[ -~]{8,}", blob):
            s = m.group().decode("ascii", "replace")
            if re.search(r"(init\.|fw_|dd |/mnt/mmc|xImage|vImage|rImage|parttab)", s):
                print("  0x%06x %s" % (m.start(), s[:110]))
        return 1

    print("cpio 条目数: %d" % len(entries))
    print()
    print("---- 文件清单 ----")
    OUTDIR.mkdir(parents=True, exist_ok=True)
    for name, mode, size, off in entries:
        kind = "d" if (mode & 0o170000) == 0o040000 else (
            "l" if (mode & 0o170000) == 0o120000 else "-")
        perm = oct(mode & 0o7777)
        mark = ""
        if re_match(name, r"init"):
            mark = "  ★★★"
        elif re_match(name, r"fw_|sh$"):
            mark = "  ★"
        print("  %s %-6s %-9d 0x%06x  %s%s" % (kind, perm, size, off, name, mark))

    # dump 关键文件
    print()
    print("---- 关键文件内容 ----")
    keys = [e for e in entries if re_match(e[0], r"(init\.|.*fw_.*)")]
    for name, mode, size, off in keys:
        data = blob[off:off + size]
        safe = name.replace("/", "_")
        (OUTDIR / safe).write_bytes(data)
        print()
        print("=== %s (%d 字节) ===" % (name, size))
        try:
            txt = data.decode("utf-8", "replace")
            print(txt[:4000])
        except Exception:
            print("  (二进制, 已存 %s)" % (OUTDIR / safe))
        # dd / 刷写行高亮
        print("  ---- 刷写相关行 ----")
        for i, ln in enumerate(data.decode("utf-8", "replace").split("\n"), 1):
            if re_match(ln, r"(dd |fw_|/mnt/mmc|parttab|mmcblk|flash)"):
                print("    L%-4d %s" % (i, ln.rstrip()[:110]))
    print()
    print("文件已存: %s" % OUTDIR)
    return 0


def re_match(s, pat):
    import re
    return re.search(pat, s) is not None


if __name__ == "__main__":
    sys.exit(main())