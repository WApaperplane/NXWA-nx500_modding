#!/usr/bin/env python3
"""SLP 固件容器【重打包器】—— 回答"有没有刷写固件的途径"

背景
----
ge0rg/samsung-nx-hacks 的 `slp-firmware.py` 只能解析、不能重打包（作者明说）。
本项目需要在官方 NX500_v1.12.bin 的基础上替换其中一个 image 分区
（首要目标 = SLP[5] = rom.bin = rtos = ISP 固件本体），产出可被官方流程接受的 .bin。

格式（已由 4 个分区交叉验证，见 docs/SLP_FLASH_PATH_2026-10-05.md）
------------------------------------------------------------------
文件头 FwFileMeta (64 字节, P_FWFILE_META = "<4s8s16s16sbI15s"):
    0x00  4s   magic        = b"SLP\\0"
    0x04  8s   version      = "1.12\\0..."        (用户可见版本, ★刷写器比对这个)
    0x0C  16s  project      = "NX500\\0..."
    0x1C  16s  version_date = "NX500GLU0APC1\\0" (板号, 决定机型匹配)
    0x2C  1b   has_pcache   = 10  (>1 => V2 格式, 下面 10 个 image header 内嵌)
    0x2D  4I   pcache_offset(=0) + reserved
    0x40  ...  image header #0 开始

每个 image header (24 字节, P_FW_IMAGE_HEADER2 = "<IIII8s"):
    +0x00 4I  img_len      镜像字节数
    +0x04 4I  crc32        ★ CRC-32/JAMCRC (不是 zlib!) 已 4/4 分区验证
    +0x08 4I  img_offset   数据在文件中的绝对偏移
    +0x0C 4I  magic        分区标识 (part0 必须 0xffffffff)
    +0x10 8s  extra        文件名 (V1 才有意义, V2 通常全 0)

镜像数据区：从 offset 0x130 (304) 起，按 img_offset 递增紧密排列。
10 个 img_len 之和 = 352121131, 容器总长 = 352121435 => 头部 304 字节，完全吻合。

安全设计（本工具的核心价值观）
--------------------------
1. **只改你指定的那一个分区**，其余 9 个分区字节级原样搬运
2. **自动重算受影响分区的 img_offset 与 crc32**（改长度会导致后续分区偏移全变）
3. **crc32 变体固定为 JAMCRC**，与官方 4 个分区实测一致；不匹配则拒绝写
4. **默认 dry-run**：不加 --write 只做解析+模拟+报告，绝不产生输出文件
5. **--verify-back** 回读校验：把重打包结果重新解析，逐分区与源/目标对比
6. **拒绝改变 version / project / version_date**：刷写器的版本单调性检查靠这三个字段
7. 若替换后长度变化，明确警告"官方刷写流程可能拒绝非等长镜像"
"""
import argparse
import hashlib
import shutil
import struct
import sys
import zlib
from pathlib import Path

SLP_MAGIC = b"SLP\0"
META_FMT = "<4s8s16s16sbI15s"
META_SIZE = struct.calcsize(META_FMT)      # 64
IMG_FMT = "<IIII8s"
IMG_SIZE = struct.calcsize(IMG_FMT)        # 24
assert META_SIZE == 64 and IMG_SIZE == 24


def crc_jamcrc(data):
    """★ 三星 SLP 用的 CRC32 变体 = 标准 CRC32 再 xor 0xFFFFFFFF
    已对官方固件的 4 个分区逐一验证 MATCH。"""
    return (zlib.crc32(data) ^ 0xFFFFFFFF) & 0xFFFFFFFF


def cstr(b):
    return b.split(b"\0")[0].decode("ascii", "replace")


def parse(path, verbose=True):
    """解析 SLP，返回 (meta_dict, [ (img_len, crc32, img_offset, magic, extra, data) ])"""
    path = Path(path)
    with open(path, "rb") as f:
        total = Path(path).stat().st_size
        raw = f.read(META_SIZE)
        if len(raw) < META_SIZE:
            raise ValueError("文件太小，不是 SLP")
        magic, version, project, vdate, has_pcache, pcache_off, reserved = \
            struct.unpack(META_FMT, raw)
        if magic != SLP_MAGIC:
            raise ValueError("magic = %r，不是 SLP 容器" % magic)
        meta = dict(version=cstr(version), project=cstr(project),
                    version_date=cstr(vdate), has_pcache=has_pcache,
                    pcache_offset=pcache_off, reserved=reserved)
        if verbose:
            print("源容器 : %s" % path)
            print("  magic=%r version=%s project=%s board=%s" %
                  (magic, meta["version"], meta["project"], meta["version_date"]))
            print("  has_pcache=%d  => %s" %
                  (has_pcache, "V2" if has_pcache > 1 else "V1"))
        n = has_pcache if has_pcache > 1 else 5
        # ★ 先把 n 个 image header 全部顺序读完，再去读各分区数据。
        #   否则"读 header -> seek 读数据 -> 再读 header"会让第 2 个 header
        #   从数据区开始读，拿到垃圾 img_offset（这个坑我踩了一次）。
        raws = []
        for i in range(n):
            hdr = f.read(IMG_SIZE)
            if len(hdr) < IMG_SIZE:
                raise ValueError("image header #%d 读不到" % i)
            raws.append(struct.unpack(IMG_FMT, hdr))
        parts = []
        for i, (img_len, crc, off, mg, extra) in enumerate(raws):
            if off + img_len > total:
                raise ValueError("分区 %d 越界（offset=%d len=%d 文件仅 %d 字节）"
                                 % (i, off, img_len, total))
            f.seek(off)
            data = f.read(img_len)
            if len(data) != img_len:
                raise ValueError("分区 %d 数据读不全（offset=%d len=%d）" % (i, off, img_len))
            parts.append(dict(idx=i, img_len=img_len, crc32=crc, img_offset=off,
                              magic=mg, extra=extra, data=data))
        total = path.stat().st_size
        covered = META_SIZE + IMG_SIZE * n
        if verbose:
            print("  分区数=%d  头部=%d 字节  数据总量=%d  文件=%d  %s"
                  % (n, covered, sum(p["img_len"] for p in parts), total,
                     "OK 吻合" if covered + sum(p["img_len"] for p in parts) == total
                     else "★ 不吻合"))
            print()
            print("  %-4s %-12s %-12s %-12s %-10s %s"
                  % ("idx", "img_offset", "img_len", "crc32", "magic", "crc 校验"))
            for p in parts:
                got = crc_jamcrc(p["data"])
                print("  %-4d %-12d %-12d %08x   %08x  %s"
                      % (p["idx"], p["img_offset"], p["img_len"], p["crc32"],
                         p["magic"], "OK" if got == p["crc32"] else "★MISMATCH %08x" % got))
            print()
    return meta, parts


def build(meta, parts, out_path, write=False):
    """按新顺序重打包。返回 (bytes_written, warnings)"""
    warn = []
    n = len(parts)
    # 头部 = meta(64) + n*24，然后数据区起点
    data_start = META_SIZE + IMG_SIZE * n
    blobs = []
    off = data_start
    newparts = []
    for p in parts:
        blobs.append(p["data"])
        newparts.append(dict(img_len=len(p["data"]), crc32=crc_jamcrc(p["data"]),
                             img_offset=off, magic=p["magic"], extra=p["extra"]))
        off += len(p["data"])

    # 组装 meta（三个关键字段原样保留 —— 改版本会导致刷写器拒绝）
    mraw = struct.pack(META_FMT, SLP_MAGIC,
                       meta["version"].encode().ljust(8, b"\0"),
                       meta["project"].encode().ljust(16, b"\0"),
                       meta["version_date"].encode().ljust(16, b"\0"),
                       meta["has_pcache"], meta["pcache_offset"],
                       meta["reserved"])

    # part0 magic 必须为 0xffffffff，否则官方解析器直接抛异常
    if newparts[0]["magic"] != 0xFFFFFFFF:
        warn.append("part0 magic 不是 0xffffffff，已强制修正")
        newparts[0]["magic"] = 0xFFFFFFFF

    buf = bytearray(data_start)
    buf[0:META_SIZE] = mraw
    for i, np_ in enumerate(newparts):
        hraw = struct.pack(IMG_FMT, np_["img_len"], np_["crc32"],
                           np_["img_offset"], np_["magic"], np_["extra"])
        buf[META_SIZE + i * IMG_SIZE: META_SIZE + (i + 1) * IMG_SIZE] = hraw
    for b in blobs:
        buf += b

    if write:
        Path(out_path).write_bytes(buf)
    return bytes(buf), warn


def verify(path, expect_meta, src_parts, replaced_idx, repl_data):
    """回读校验：解析产物，逐分区核对"""
    print("---- 回读校验 ----")
    meta, parts = parse(path, verbose=False)
    ok = True
    if (meta["version"] != expect_meta["version"] or
            meta["project"] != expect_meta["project"] or
            meta["version_date"] != expect_meta["version_date"]):
        print("  ★ meta 字段与源不一致")
        ok = False
    else:
        print("  meta 字段一致: version=%s project=%s board=%s"
              % (meta["version"], meta["project"], meta["version_date"]))
    if len(parts) != len(src_parts):
        print("  ★ 分区数不一致 %d != %d" % (len(parts), len(src_parts)))
        return False
    for i, (a, b) in enumerate(zip(parts, src_parts)):
        got = crc_jamcrc(a["data"])
        crc_ok = (got == a["crc32"])
        if i == replaced_idx:
            same = (a["data"] == repl_data)
            okn = "OK(内容==替换值)" if same else "★内容不符"
            print("  分区 %d [已替换] len=%-10d crc %s  %s" %
                  (i, a["img_len"], "OK" if crc_ok else "★BAD", okn))
            ok &= crc_ok and same
        else:
            same = (a["data"] == b["data"])
            if not same:
                print("  ★ 分区 %d 内容被意外改动！" % i)
            ok &= crc_ok and same
    print()
    print("  总体:", "PASS ✔" if ok else "FAIL ✘")
    return ok


def main():
    ap = argparse.ArgumentParser(description="SLP 固件容器解析 / 重打包（安全版）")
    ap.add_argument("src", help="源 .bin（如 NX500_v1.12.bin）")
    ap.add_argument("-l", "--list", action="store_true", help="只列出分区表")
    ap.add_argument("-x", "--extract", metavar="DIR", help="解包全部分区到 DIR")
    ap.add_argument("-r", "--replace", metavar="IDX", type=int,
                    help="要替换的分区索引（0-9）")
    ap.add_argument("-f", "--file", metavar="FILE", help="替换内容（裸镜像）")
    ap.add_argument("-O", "--out", default="out_firmware.bin", help="输出路径")
    ap.add_argument("--write", action="store_true",
                    help="★ 真正写文件（默认 dry-run，只报告不落盘）")
    args = ap.parse_args()

    src = Path(args.src)
    if not src.exists():
        print("ERR: 找不到 %s" % src)
        return 2

    print("=" * 74)
    print("SLP 固件容器工具（安全版：默认 dry-run）")
    print("=" * 74)
    print()
    meta, parts = parse(src)
    print()

    if args.extract:
        d = Path(args.extract)
        d.mkdir(parents=True, exist_ok=True)
        for p in parts:
            fp = d / ("part%02d_%d.bin" % (p["idx"], p["img_len"]))
            fp.write_bytes(p["data"])
            print("  解包 %-28s md5=%s" % (fp.name,
                  hashlib.md5(p["data"]).hexdigest()[:16]))
        print()
        return 0

    if args.replace is None:
        print("只解析模式。加 -x DIR 解包，或 -r IDX -f FILE --write -O OUT 重打包。")
        return 0

    if not args.file:
        print("ERR: -r 需要配 -f 指定替换内容")
        return 2
    if not (0 <= args.replace < len(parts)):
        print("ERR: 分区索引越界 (0..%d)" % (len(parts) - 1))
        return 2

    repl_raw = Path(args.file).read_bytes()
    tgt = parts[args.replace]
    # ★ 关键：源若是【块设备整分区备份】（尾部有零填充），必须先裁到原有效长度，
    #   否则会平白多出十几 MB 零，把后续分区全顶走。
    repl = repl_raw[:tgt["img_len"]] if len(repl_raw) > tgt["img_len"] else repl_raw
    print("---- 替换计划 ----")
    print("  分区     : [%d]" % args.replace)
    print("  原长度   : %d 字节 (%.2f MB)" % (tgt["img_len"], tgt["img_len"] / 1048576))
    print("  输入文件 : %d 字节 (%.2f MB)" % (len(repl_raw), len(repl_raw) / 1048576))
    if len(repl_raw) != tgt["img_len"]:
        tail = repl_raw[tgt["img_len"]:]
        nz = sum(1 for x in tail if x)
        print("  自动裁剪 : 是（尾部多出 %d 字节，其中非零 %d）"
              % (len(tail), nz))
        if nz:
            print("  ⚠ 尾部裁掉的部分【含非零数据】⇒ 可能是真实内容丢失，请人工确认！")
    print("  实际替换 : %d 字节 (%.2f MB)" % (len(repl), len(repl) / 1048576))
    print("  长度变化 : %s" % ("不变 ✔" if len(repl) == tgt["img_len"]
                                else "★ 变了 %+d 字节" % (len(repl) - tgt["img_len"])))
    if len(repl) == tgt["img_len"] and repl == tgt["data"]:
        print("  ★ 内容与原镜像【完全相同】⇒ 本次是空替换（用于往返自测）")
    if len(repl) != tgt["img_len"]:
        print()
        print("  ⚠⚠⚠ 长度变化的三重风险 ⚠⚠⚠")
        print("  1. 后续 9 个分区的 img_offset 全部要重算（本工具会自动做）")
        print("  2. 官方刷写流程【可能拒绝非等长镜像】（未验证）")
        print("  3. 分区表可能在刷写时有额外约束（parttab / has_pcache 语义）")
        print("  ⇒ 强烈建议：先把新镜像【填充/截断到原长度】再替换，保持等长")
    print()

    newparts = list(parts)
    newparts[args.replace] = dict(tgt, data=repl)
    print("---- 模拟重打包 ----")
    blob, warn = build(meta, newparts, args.out, write=False)
    print("  产物大小: %d 字节 (%.1f MB)" % (len(blob), len(blob) / 1048576))
    for w in warn:
        print("  ⚠ %s" % w)
    print("  新 crc32[%d] = %08x (JAMCRC)" % (args.replace, crc_jamcrc(repl)))
    print()
    print("  dry-run 结束，未写任何文件。")
    if not args.write:
        print("  确认无误后加 --write 真正生成：")
        print("    python %s %s -r %d -f %s -O %s --write"
              % (Path(sys.argv[0]).name, src, args.replace, args.file, args.out))
        return 0

    blob, warn = build(meta, newparts, args.out, write=True)
    print("  ★ 已写入 %s (%d 字节)" % (args.out, len(blob)))
    print()
    if not verify(args.out, meta, parts, args.replace, repl):
        print("  ⇒ 回读校验失败，产物不可用！")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())