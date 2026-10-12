#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C-2 补丁生成器（di-camera-app / NX500 v1.12）

补丁内容（见 docs/current/DICAM_MOD_DESIGN_2026-10-11.md §5-C2）：
  P1: "uscom" 命令名 → "film"        @ file 0x3656dc（全镜像唯一引用）
  P2: FUN_000ca3a8 头部 16B → 桩     @ file 0xc23a8
      桩（ARM）:
        cmp  r0, #2         ; argc >= 2 ?
        bxlo lr             ; 否则直接返回（无参数时不动）
        ldr  r0, [r1, #4]   ; r0 = argv[1]（命令串）
        b    system@plt     ; 尾调用 system()（0xadd08）

输出：di-camera-app.c2 + c2_bytepatch.json（含逐项 old/new 字节，供回滚）
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

BIN = Path(r"E:/NXWA/fw/v1.12/extract/di-camera-app/com.samsung.di-camera-app/bin/di-camera-app")
_args = [a for a in sys.argv[1:] if not a.startswith("--")]
OUT = Path(_args[0] if _args else r"E:/tmp/dicam_strings/c2")
# --stub=v2 ⇒ 用 stub_v2.bin（拼接版，由 build_stub_v2.sh 在 WSL 产出）；默认 v1
STUB_VER = "v2" if any(a in ("--stub=v2", "--v2") for a in sys.argv) else "v1"
MD5_EXPECT = "ae44293e969101d1cf0a93cbe9b99f75"

STUB_VADDR = 0xCA3A8        # FUN_000ca3a8
SYS_PLT = 0xADD08           # system@plt
STR_VADDR = 0x36D6DC        # "uscom"
STR_FILE = 0x3656DC


def arm_b(from_vaddr: int, target_vaddr: int) -> int:
    """编码 ARM 'b target'。from_vaddr = b 指令自身地址。"""
    pc = from_vaddr + 8
    delta = target_vaddr - pc
    assert delta % 4 == 0, "branch delta not word aligned: %#x" % delta
    imm24 = (delta >> 2) & 0xFFFFFF
    return 0xEA000000 | imm24


def main() -> int:
    data = bytearray(BIN.read_bytes())
    md5 = hashlib.md5(bytes(data)).hexdigest()
    if md5 != MD5_EXPECT:
        print("!! 源文件 md5 不符：%s" % md5)
        return 2

    patches = []

    # P1: uscom -> film
    old1 = bytes(data[STR_FILE:STR_FILE + 6])
    assert old1 == b"uscom\x00", old1
    new1 = b"film\x00\x00"
    data[STR_FILE:STR_FILE + 6] = new1
    patches.append(dict(name='P1 "uscom"->"film"', file_off=STR_FILE, vaddr=STR_VADDR,
                        old=old1.hex(), new=new1.hex()))

    # P2: stub @ FUN_000ca3a8
    off2 = STUB_VADDR - 0x8000
    if STUB_VER == "v2":
        binp = Path(__file__).with_name("stub_v2.bin")
        if not binp.exists():
            print("!! 缺 stub_v2.bin —— 先跑 build_stub_v2.sh（WSL）再生成 v2 补丁")
            return 3
        stub = binp.read_bytes()
        words = []
    else:
        words = [0xE3500002, 0x312FFF1E, 0xE5910004, arm_b(STUB_VADDR + 12, SYS_PLT)]
        stub = b"".join(struct.pack("<I", w) for w in words)
    if len(stub) > 656:
        print("!! 桩长 %d B > 656 B（会越入 uscap handler @0xca638）" % len(stub))
        return 4
    old2 = bytes(data[off2:off2 + len(stub)])
    nz = sum(1 for b in old2 if b)
    data[off2:off2 + len(stub)] = stub
    patches.append(dict(name="P2 stub(%s)@FUN_000ca3a8" % STUB_VER, file_off=off2,
                        vaddr=STUB_VADDR, length=len(stub),
                        old=old2.hex(), new=stub.hex(), stub_words=[hex(w) for w in words]))
    print("   覆盖区间: file 0x%x..0x%x (%d B)，其中原非零字节 %d 个"
          % (off2, off2 + len(stub), len(stub), nz))

    OUT.mkdir(parents=True, exist_ok=True)
    out_bin = OUT / ("di-camera-app.c2" if STUB_VER == "v1" else "di-camera-app.c2.v2")
    out_bin.write_bytes(bytes(data))
    meta = dict(src=str(BIN), src_md5=md5,
                out=str(out_bin), out_md5=hashlib.md5(bytes(data)).hexdigest(),
                patches=patches)
    (OUT / ("c2_bytepatch.json" if STUB_VER == "v1" else "c2_bytepatch.v2.json")
     ).write_text(json.dumps(meta, indent=1))

    print("== C-2 补丁已生成 ==")
    print("  输出: %s" % out_bin)
    print("  md5 : %s (src %s)" % (meta["out_md5"], md5))
    for p in patches:
        print("  %s @file 0x%x (vaddr 0x%x)" % (p["name"], p["file_off"], p["vaddr"]))
        print("     old: %s" % p["old"])
        print("     new: %s" % p["new"])
        if "stub_words" in p:
            for w in p["stub_words"]:
                print("     word: %s" % w)
    print("  json: %s" % (OUT / ("c2_bytepatch.json" if STUB_VER == "v1" else "c2_bytepatch.v2.json")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
