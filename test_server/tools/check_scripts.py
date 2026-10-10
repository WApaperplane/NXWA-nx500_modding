#!/usr/bin/env python3
"""scripts/ 母本体检 CI  (NX-KS2 / 铁律 99 的自动化)

背景
----
铁律 99：**Windows 上写的 .sh 部署前必须 assert `b'\\r\\n' not in data`**。
本项目历史上因 CRLF 导致 `/bin/bash^M: bad interpreter` RC=126，是排查最久的一次事故。
本脚本把它变成可复跑的检查，供拆仓后直接接入 CI。

检查项
------
1. CRLF 断言（铁律 99）        —— 命中即 FAIL
2. `bash -n` 语法检查          —— 仅对 .sh；★ `.tp` 是 mod_gui 菜单模板（`button|标签|命令`），
                                  不是 shell，误报需排除
3. 可执行位                    —— .sh 应有 +x（mod_gui 用 system() 调它）
4. shebang 缺失提示            —— 无 shebang 的 .sh 由调用方决定解释器，记 WARN

检查范围
--------
`scripts/**`、`install.sh`、`uninstall_pkg/*.sh`，以及 **`test_server/u1/`**（U1 只读上机
脚本包——它同样要在相机上跑，所以同样受铁律 99 约束；把它纳入这里，门控 G1 的第 8 项
才有意义）。

用法
  python check_scripts.py <repo_root> [--quiet]
退出码：0 = 全通过；1 = 有 FAIL
"""
from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys

SHELL_EXT = (".sh",)


def git_modes(root):
    """★ 在 Windows 上 `core.filemode=false` ⇒ 文件系统位不可靠，
    必须用 `git ls-files -s` 记录的 mode 判断"部署出去会不会丢执行位"。
    返回 {path: mode_str}；非 git 仓库返回 None。"""
    try:
        r = subprocess.run(["git", "ls-files", "-s"], cwd=root, capture_output=True)
        if r.returncode != 0:
            return None
        out = {}
        for ln in r.stdout.decode("utf-8", "replace").splitlines():
            p = ln.split(None, 3)
            if len(p) == 4:
                out[p[3]] = p[0]          # "100644" / "100755"
        return out or None
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    os.chdir(root)

    files = sorted(set(
        glob.glob("scripts/**/*.sh", recursive=True)
        + glob.glob("scripts/**/*.tp", recursive=True)
        + glob.glob("install.sh") + glob.glob("uninstall_pkg/*.sh")
        # U1 只读上机脚本包（生成物，但同样要在相机上跑 ⇒ 同样受铁律 99 约束）
        + glob.glob("test_server/u1/*.sh")
        + glob.glob("test_server/u1/*.py")
        # U6 3D LUT 上机包（含写类子命令 u6_lut.sh；相机端资产一视同仁）
        + glob.glob("test_server/u6/*.sh")
        + glob.glob("test_server/u6/*.py")
        # PW 直推包（pwsend/pwcalib；上机跑，受铁律 99 约束）
        + glob.glob("test_server/pwsend/*.sh")
        + glob.glob("test_server/pwsend/*.py")
        # LUT 链路包（lutpick.sh / deploy_luts.py）
        + glob.glob("test_server/lutpipe/*.sh")
        + glob.glob("test_server/lutpipe/*.py")
        # FilmLab 包（flab.py 配方工具 / flab_sim.sh 离线回归 / nxfilmui 构建脚本）
        + glob.glob("test_server/filmlab/*.sh")
        + glob.glob("test_server/filmlab/*.py")
    ))
    files = [f for f in files if os.path.isfile(f)]

    fails, warns = [], []
    crlf_files, syntax_files, noexec, noshebang = [], [], [], []

    for p in files:
        data = open(p, "rb").read()
        is_shell = p.endswith(SHELL_EXT)

        if b"\r\n" in data:
            crlf_files.append((p, data.count(b"\r\n")))

        if is_shell:
            r = subprocess.run(["bash", "-n", p], capture_output=True)
            if r.returncode != 0:
                msg = r.stderr.decode("utf-8", "replace").strip().splitlines()
                syntax_files.append((p, msg[0][:100] if msg else "?"))
            if not data.startswith(b"#!"):
                noshebang.append(p)

    # 执行位：优先用 git 记录的模式（Windows 上文件系统位不可信）
    modes = git_modes(root)
    for p in files:
        if not p.endswith(SHELL_EXT):
            continue
        if modes is not None:
            key = p.replace(os.sep, "/")
            m = modes.get(key)
            if m == "100644":
                noexec.append(f"{p}  [git mode 100644 —— 在 Linux 上 clone 出来没有执行位]")
        elif not (os.stat(p).st_mode & 0o111):
            noexec.append(f"{p}  [工作区无可执行位]")

    for p, c in crlf_files:
        fails.append(f"CRLF  [铁律99] {p}  ({c} 处) —— 部署会得到 /bin/bash^M")
    for p, e in syntax_files:
        fails.append(f"SYNTAX        {p}  {e}")
    for p in noexec:
        warns.append(f"NOEXEC        {p}")
    for p in noshebang:
        warns.append(f"NOSHEBANG     {p}")

    if not a.quiet:
        print(f"检查 {len(files)} 个文件（{len([f for f in files if f.endswith('.sh')])} 个 .sh）")
        print(f"  CRLF 违规     : {len(crlf_files)}")
        print(f"  语法错误      : {len(syntax_files)}")
        print(f"  无可执行位    : {len(noexec)}")
        print(f"  无 shebang    : {len(noshebang)}")
        print()
        for f in fails:
            print("  FAIL " + f)
        for w in warns:
            print("  warn " + w)
        print()
    print(f"RESULT: {'FAIL' if fails else 'PASS'}  ({len(fails)} fail / {len(warns)} warn)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
