#!/usr/bin/env python3
"""apply_ci_fixes.py —— 落实 check_scripts.py 抓到的缺陷（铁律 99 CI 的第一次修复）

修四件事：
  1. scripts/fstack.sh         —— 去掉 CRLF，并补 shebang（它由 mod_gui 直接执行）
  2. scripts/gui_br_NX1.tp     —— 去掉 CRLF（菜单模板，CRLF 会让 mod_gui 解析失败）
  3. scripts/rem_set.sh        —— while 读文件那行 do/done 之间缺 ';'
  4. git 索引执行位            —— 136 个脚本在 git 里是 100644；改为 100755

★ 纪律：Windows 上写的 .sh 必须 assert b'\r\n' not in data（铁律 99）。
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # test_server/tools/ -> repo root


def strip_crlf(p: Path) -> int:
    d = p.read_bytes()
    n = d.count(b"\r\n")
    if n:
        p.write_bytes(d.replace(b"\r\n", b"\n"))
    assert b"\r\n" not in p.read_bytes(), f"CRLF 仍在: {p}"
    return n


def main() -> int:
    rc = 0

    # 1. fstack.sh
    f = ROOT / "scripts" / "fstack.sh"
    n = strip_crlf(f)
    d = f.read_bytes()
    if not d.startswith(b"#!"):
        f.write_bytes(b"#!/bin/sh\n" + d)
        print(f"  fstack.sh: 补 shebang #!/bin/sh")
    print(f"  fstack.sh: 去掉 CRLF {n} 处 -> {f.stat().st_size} 字节")

    # 2. gui_br_NX1.tp
    t = ROOT / "scripts" / "gui_br_NX1.tp"
    n = strip_crlf(t)
    print(f"  gui_br_NX1.tp: 去掉 CRLF {n} 处")

    # 3. rem_set.sh 缺分号
    r = ROOT / "scripts" / "rem_set.sh"
    txt = r.read_text(encoding="utf-8")
    bad = 'do echo "Text read from file: $line"  done < "$filename"'
    good = 'do echo "Text read from file: $line"; done < "$filename"'
    if bad in txt:
        r.write_bytes(txt.replace(bad, good).encode("utf-8"))
        print("  rem_set.sh: 补上 do/done 之间的 ';'")
    elif good in txt:
        print("  rem_set.sh: 已是修好的形式")
    else:
        print("  rem_set.sh: ★ 未找到预期行，请人工确认")
        rc = 1
    assert b"\r\n" not in r.read_bytes(), "rem_set.sh 有 CRLF"

    # 4. git 执行位
    out = subprocess.run(["git", "ls-files", "-s"], cwd=ROOT,
                         capture_output=True, text=True).stdout
    targets = []
    for line in out.splitlines():
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        mode, _sha, _stage, path = parts
        if mode == "100644" and (path.endswith(".sh")):
            targets.append(path)
    if targets:
        subprocess.run(["git", "update-index", "--chmod=+x", "--"] + targets,
                       cwd=ROOT, check=True)
    print(f"  git 执行位: 已为 {len(targets)} 个 .sh 记录 100755")

    print("DONE")
    return rc


if __name__ == "__main__":
    sys.exit(main())
