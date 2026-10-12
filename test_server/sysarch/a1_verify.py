#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A1（方案 G）刷后验证（只读）—— p7 分区回读比对 + 零区存活探针。

判据（TASKFLOW_2026-10-12 W-2 序 3/4、W-5 序 2）：
  1) /dev/mmcblk0p7 前 12,075,648 B 是否与【待刷包内的 p7 镜像】逐字节一致
  2) 0x510b0 四字节是否为重定向 b 0x80011504（= 13 01 ff ea）
  3) ★ 0x11502..0x115ff 零区内容是否仍是"我们写进去的东西"
       —— 这是 Step1 的唯一未知（区域被运行期覆盖 ⇒ p7 异常）

用法:
  python a1_verify.py <相机IP> --pack step1          # 上机
  python a1_verify.py --pack step1 --selftest        # 离线自测（不连相机）
  python a1_verify.py <相机IP> --pack "E:/…/官方.bin"
产出:
  raw8/gates/a1/<variant>_readback.bin + <variant>_readback.json
"""
import argparse
import hashlib
import json
import struct
import sys
import time
from pathlib import Path

SD_DIR = "/opt/storage/sdcard"
REMOTE = SD_DIR + "/a1verify"

PACKS = {
    "step1": (r"E:/NXWA/fw/v1.12/a1/slp_a1_p7_g_step1_v116.bin", "1e0be7df0ed54c4b71cd6a6a0ea3b243"),
    "full":  (r"E:/NXWA/fw/v1.12/a1/slp_a1_p7_g_v116.bin",       "2ee98811a60059353a82c46ee2d836bc"),
}
OFFICIAL_P7_MD5 = "5fc4824f5b6a6a3caca1f9104238b8ac"

B_OFF = 0x510B0          # 重定向点（应为 13 01 ff ea）
BLK_OFF = 0x11504        # 特判块落点
ZONE_LO = 0x11502        # 零区起点
ZONE_HI = 0x11600        # 零区终点（不含）

REDIRECT = bytes.fromhex("1301ffea")
BLOCK_STEP1 = bytes.fromhex("a2ff00ea")     # b 0x80051394，行为等价原路径
BLOCK_FULL = bytes.fromhex(
    "133e40e2" "030053e3" "a0ff008a" "000081e5" "0000a0e3" "17ff00ea")   # 24B 恒等特判块


def md5b(b):
    return hashlib.md5(b).hexdigest()


def slp_extract(path, idx=5):
    """从 SLP 容器取第 idx 个镜像（header 从 0x40 起，24B/项）。"""
    data = Path(path).read_bytes()
    if data[:4] != b"SLP\0":
        raise SystemExit("!! 不是 SLP 容器：%s" % path)
    hdr = data[0x40 + idx * 24: 0x40 + idx * 24 + 24]
    img_len, crc, img_off, magic, _extra = struct.unpack("<IIII8s", hdr)
    return data[img_off:img_off + img_len], img_len


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("host", nargs="?", default="selftest",
                    help="相机 IP（--selftest 时可省略）")
    ap.add_argument("--pack", default="step1", help="step1 | full | <SLP 路径>")
    ap.add_argument("--bytes", type=int, default=12075648)
    ap.add_argument("--selftest", action="store_true",
                    help="离线自测：不连相机，用包内镜像自比对，验证判定逻辑")
    args = ap.parse_args()

    if args.pack in PACKS:
        pack_path, exp_p7_md5 = PACKS[args.pack]
        variant = args.pack
    else:
        pack_path, exp_p7_md5 = args.pack, None
        variant = "custom"

    ref, ref_len = slp_extract(pack_path)
    print("参考包     : %s" % pack_path)
    print("包内 p7    : %d B  md5 %s" % (ref_len, md5b(ref)))
    if exp_p7_md5 and md5b(ref) != exp_p7_md5:
        print("!! 包内 p7 md5 与台账不符（期望 %s）—— 请核对包" % exp_p7_md5)

    outdir = Path("raw8/gates/a1")
    outdir.mkdir(parents=True, exist_ok=True)
    local = outdir / ("%s_readback.bin" % variant)

    if args.selftest:
        print("== selftest：以包内 p7 镜像冒充读回，只验证判定逻辑 ==")
        up = "selftest"
        cur = ref
    else:
        sys.path.insert(0, "test_server/sysarch")
        from fwprobe import T          # noqa: E402
        from ftpx import ftp_get       # noqa: E402
        t = T(args.host, timeout=25)
        t.login()
        up = t.send("cat /proc/uptime", 4.0).strip()[:40]
        print("uptime     :", up)
        t.send("mkdir -p %s" % REMOTE, 3.0)
        rd = "dd if=/dev/mmcblk0p7 of=%s/p7.bin bs=4096 count=%d 2>/dev/null" % (
            REMOTE, (args.bytes + 4095) // 4096)
        t.send(rd, 40.0)
        print("remote md5 :", t.send(
            "/opt/usr/nx-ks/busybox md5sum %s/p7.bin 2>/dev/null | head -1" % REMOTE,
            25.0).strip()[:90])
        t.close()
        print("FTP 拉回 ...")
        for a in range(3):
            if ftp_get(args.host, "/a1verify/p7.bin", str(local), timeout=600):
                break
            print("  重试", a + 1)
            time.sleep(3)
        cur = local.read_bytes()

    n = min(len(cur), len(ref))
    diffs = [i for i in range(n) if cur[i] != ref[i]]
    print("读回       : %d B  md5 %s" % (len(cur), md5b(cur[:len(ref)])))

    # ---- 判据 1/2/3 ----
    identical = (len(cur) >= len(ref)) and not diffs
    redir = cur[B_OFF:B_OFF + 4]
    zone = cur[ZONE_LO:ZONE_HI]
    blk_expect = BLOCK_STEP1 if variant == "step1" else BLOCK_FULL
    blk_ok = zone[BLK_OFF - ZONE_LO: BLK_OFF - ZONE_LO + len(blk_expect)] == blk_expect
    zone_tail = zone[BLK_OFF - ZONE_LO + len(blk_expect):]
    tail_clean = all(b == 0 for b in zone_tail)
    zone_intact = blk_ok and tail_clean

    cur_full_md5 = md5b(cur[:len(ref)])
    if cur_full_md5 == OFFICIAL_P7_MD5:
        verdict = "未刷（读回 = 官方 p7）"
    elif identical:
        verdict = "已刷且完整一致 ✓"
    else:
        verdict = "读回与待刷镜像不一致（差异 %d 字节）" % len(diffs)

    print()
    print("---- 结论 ----")
    print("  判据1 逐字节一致 : %s（差异 %d 处）" % ("PASS" if identical else "FAIL", len(diffs)))
    print("  判据2 0x510b0    : %s  %s" % (redir.hex(), "PASS" if redir == REDIRECT else "FAIL"))
    print("  判据3 零区存活   : %s（块 %s / 尾部清零 %s）"
          % ("PASS" if zone_intact else "FAIL", blk_ok, tail_clean))
    print("  → %s" % verdict)
    if not zone_intact and variant == "step1" and not args.selftest:
        print("  ★★ 零区被运行期覆盖 ⇒ 停止，改选址候选 B（0x11010），见 A1 设计 §4")

    rec = dict(
        host=args.host, variant=variant, pack=pack_path, uptime=up, selftest=bool(args.selftest),
        expect_p7_md5=md5b(ref), readback_md5=cur_full_md5,
        readback_bytes=len(cur), diff_count=len(diffs),
        diff_first=[hex(i) for i in diffs[:16]],
        redirect_at_0x510b0=redir.hex(), redirect_ok=(redir == REDIRECT),
        zone_block_ok=blk_ok, zone_tail_clean=tail_clean, zone_intact=zone_intact,
        identical=identical, verdict=verdict,
        note="readback 仅含前 %d B（改动点全部 < 0x60000）" % args.bytes,
    )
    if not args.selftest:
        jf = outdir / ("%s_readback.json" % variant)
        jf.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
        print("  证据: %s" % jf)
    else:
        print("  (selftest 不落证据文件)")


if __name__ == "__main__":
    main()
