"""app-selector 二进制字符串提取 + app 发现机制分析。

目标：搞清楚 NX500 的 com.samsung.app-selector 是怎么发现 /usr/apps/* 里那些 app 的，
以及新 app 要满足什么条件才会被列出来。

只做静态字符串分析，不反汇编（18KB 的量级，字符串通常够定性）。
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent


def strings(data: bytes, minlen: int = 4) -> list:
    """提取 ASCII + 宽字符串（UTF-16LE，Tizen/EFL 常见）。"""
    out = []
    for m in re.finditer(rb"[\x20-\x7e]{%d,}" % minlen, data):
        out.append(("ascii", m.start(), m.group().decode("ascii")))
    for m in re.finditer(rb"(?:[\x20-\x7e]\x00){%d,}" % minlen, data):
        out.append(("utf16", m.start(), m.group().decode("utf-16-le")))
    return out


KEYS = [
    ("目录/路径", r"(^/|/usr|/opt|/app|/home|/mnt|/media|/data|sdcard|storage)"),
    ("app 标识", r"(com\.samsung|org\.tizen|\.tpk|\.app$|apps/)"),
    ("DBus", r"(dbus|DBus|DBUS|org\.freedesktop|method_call|session_bus|system_bus)"),
    ("签名/包管理", r"(signature|Signature|author-sign|\.xml|package|packagekit|cli_app|tizen_app|app_manager|install)"),
    ("UI/edje", r"(edje|EFL|evas|ecore|efl|elm|widget|canvas)"),
]


def main() -> int:
    target = HERE / (sys.argv[1] if len(sys.argv) > 1 else "app-selector")
    if not target.is_file():
        print("no such file:", target)
        return 2
    data = target.read_bytes()
    print("=" * 72)
    print("file: %s  (%d bytes)" % (target.name, len(data)))
    print("=" * 72)

    # ELF 头信息，判断架构与是否 stripped
    if data[:4] == b"\x7fELF":
        cls = {1: "32-bit", 2: "64-bit"}.get(data[4], "?")
        machine = int.from_bytes(data[18:20], "little")
        print("ELF: %s  machine=0x%x%s" % (cls, machine, "  (ARM)" if machine == 40 else ""))
        sec_off = int.from_bytes(data[32:40], "little")
        sh_size = int.from_bytes(data[46:48], "little")
        sh_num = int.from_bytes(data[48:50], "little")
        sh_strndx = int.from_bytes(data[50:52], "little")
        print("section headers: off=%d size=%d num=%d strndx=%d" % (sec_off, sh_size, sh_num, sh_strndx))
        if sec_off and sh_num and 0 < sec_off < len(data) - 64:
            names = []
            st_off = int.from_bytes(data[sh_off + sh_strndx * sh_size + 16 : sh_off + sh_strndx * sh_size + 20], "little")
            for i in range(sh_num):
                b = sh_off + i * sh_size
                nm = int.from_bytes(data[b : b + 4], "little")
                end = data.index(b"\x00", st_off + nm)
                names.append(data[st_off + nm : end].decode("ascii", "replace"))
            print("sections: %s" % ", ".join(n for n in names if n))
            print("  → debug sections present: %s" % any(n.startswith(".debug") for n in names))
    print()

    strs = strings(data)
    print("total strings: %d (ascii + utf16)" % len(strs))
    print()

    for label, pat in KEYS:
        rx = re.compile(pat, re.I)
        hits = sorted({s for _, _, s in strs if rx.search(s)})
        print("--- %s (%d) ---" % (label, len(hits)))
        for h in hits[:40]:
            print("   %s" % h[:160])
        print()

    # 动态链接的库，看它依赖什么框架
    libs = sorted({s for _, _, s in strs if s.endswith(".so") or ".so." in s})
    print("--- linked libraries (%d) ---" % len(libs))
    for l in libs:
        print("   %s" % l[:120])
    print()
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
