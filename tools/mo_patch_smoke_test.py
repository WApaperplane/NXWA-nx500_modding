#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mo_patch_smoke_test.py — mo_patch.py 端到端冒烟测试（离线、自包含）

流程：构造规范 .mo（带 header、charset=UTF-8、含中文）
      → mo_patch.py set 替换
      → Python gettext（标准库解析器）加载 + 查询验证
      → 断言：目标条目=新值；其余条目不变

用途：回归测试「mo_patch 产出物 = 标准解析器可加载的合法 MO」。
（真机 di-camera-app.mo 无 header 元数据，Python gettext 对本机文件不可用——
  该限制为原文件固有，与本工具无关；真机文件的验证走 mo_patch verify --glibc-sim。）

运行：python tools/mo_patch_smoke_test.py
"""

import gettext
import io
import os
import struct
import subprocess
import sys
import tempfile


def build_mo(pairs):
    """最小规范 .mo 生成器（无 hash 表；字符串区平铺）"""
    pairs = sorted(pairs, key=lambda x: x[0])
    n = len(pairs)
    orig_off = 28
    trans_off = orig_off + 8 * n
    str_base = trans_off + 8 * n
    blob = bytearray()

    def add(b):
        off = str_base + len(blob)
        blob.extend(b)
        blob.append(0)
        return len(b), off

    orig_desc = [add(k) for k, _ in pairs]
    trans_desc = [add(v) for _, v in pairs]
    out = bytearray()
    out += struct.pack("<7I", 0x950412DE, 0, n, orig_off, trans_off, 0, 0)
    for l, o in orig_desc:
        out += struct.pack("<2I", l, o)
    for l, o in trans_desc:
        out += struct.pack("<2I", l, o)
    out += blob
    return bytes(out)


def main():
    pairs = [
        (b"", b"Project-Id-Version: smoke\n"
              b"Content-Type: text/plain; charset=UTF-8\n"),
        (b"CAP_FN_PW", "图片向导".encode("utf-8")),
        (b"CAP_MENU_CUSTOM_MODE_1", "自定义 1".encode("utf-8")),
        (b"CAP_MENU_CUSTOM_MODE_2", "自定义 2".encode("utf-8")),
        (b"OTHER_KEY", b"unchanged value"),
    ]
    d = tempfile.mkdtemp(prefix="mopatch_smoke_")
    src = os.path.join(d, "test.mo")
    out = os.path.join(d, "out.mo")
    with open(src, "wb") as f:
        f.write(build_mo(pairs))

    # 0) 基线：Python gettext 能加载原文件
    with open(src, "rb") as f:
        tr0 = gettext.GNUTranslations(io.BytesIO(f.read()))
    assert tr0.gettext("CAP_MENU_CUSTOM_MODE_1") == "自定义 1"
    print("[0] baseline: python-gettext loads hand-built MO, query OK")

    # 1) mo_patch set
    tool = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mo_patch.py")
    r = subprocess.run(
        [sys.executable, tool, "set", src, out,
         "--kv", "CAP_MENU_CUSTOM_MODE_1=Portra 400"],
        capture_output=True, text=True, encoding="utf-8")
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr)
        print("SMOKE TEST FAIL: mo_patch set rc != 0")
        return 2

    # 2) Python gettext 加载新文件并验证
    with open(out, "rb") as f:
        tr1 = gettext.GNUTranslations(io.BytesIO(f.read()))
    checks = [
        ("CAP_MENU_CUSTOM_MODE_1", "Portra 400"),   # 已替换
        ("CAP_MENU_CUSTOM_MODE_2", "自定义 2"),      # 不变
        ("CAP_FN_PW", "图片向导"),                   # 不变
        ("OTHER_KEY", "unchanged value"),            # 不变（ASCII）
    ]
    for k, want in checks:
        got = tr1.gettext(k)
        status = "OK " if got == want else "FAIL"
        print(f"    {status} {k}: {got!r} (want {want!r})")
        if got != want:
            print("SMOKE TEST FAIL")
            return 2
    print("SMOKE TEST PASS: build -> patch -> python-gettext load -> query OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
