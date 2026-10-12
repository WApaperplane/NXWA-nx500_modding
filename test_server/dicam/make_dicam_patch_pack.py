#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打包 di-camera-app 补丁的 GitHub Release 资产（NX-WA-DICAM-PATCH-<ver>.zip）。

设计原则（见 docs/current/DICAM_PATCH_INSTALL_PATHS_2026-10-12.md）：
  · app 补丁是【可选 / 高风险 / 一次性】动作 ⇒ 独立包，不进日常增量同步链
  · 包内 = 补丁器 + 补丁二进制 + bytepatch + 说明 + md5 清单
  · 相机端落点固定为 /opt/usr/nx-ks/dicam/（p14，刷固件不覆盖）

用法:
  python make_dicam_patch_pack.py [--ver 1.0] [--stub v2] [--out E:/NXWA/release] [--write]
默认 dry-run，只报告；加 --write 才落盘。
"""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FWDIR = Path(r"E:/NXWA/fw/v1.12/dicam")
TMPC2 = Path(r"E:/tmp/dicam_strings/c2")

STUB_MD5 = {
    "v1": "0e1da8b326f49728e9394f98a53ffd35",
    "v2": "48d94bd63e4479fc931ae1a1fee4e94b",   # 2026-10-12 修订：含参数净化（原 697c5739…）
}


def md5f(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def pick(stub, name):
    """优先 fw 工作区，其次 tmp 产物目录。"""
    cands = {
        "v1": [FWDIR / "di-camera-app_c2_v116.patched", TMPC2 / "di-camera-app.c2"],
        "v2": [FWDIR / "di-camera-app.c2.v2", TMPC2 / "di-camera-app.c2.v2"],
    }[stub]
    bp = {"v1": [FWDIR / "c2_bytepatch.json", TMPC2 / "c2_bytepatch.json"],
          "v2": [FWDIR / "c2_bytepatch.v2.json", TMPC2 / "c2_bytepatch.v2.json"]}[stub]
    binp = next((p for p in cands if p.exists()), None)
    jsonp = next((p for p in bp if p.exists()), None)
    return binp, jsonp


README = """# NX-WA · di-camera-app 补丁包（{ver} / 桩 {stub}）

给 `di-camera-app` 加一条官方风格命令 `film`，让 mod 脚本可经 App 命令通道触发：
    st app film <短命令>          # 桩 v1：单参数（≤19 字符）
    st app film <命令> <参数...>   # 桩 v2：自动拼成 `sh /opt/usr/nx-ks/f.sh <命令> <参数...>`

## 安装（相机端，二选一）

> ★ 本包**不含** `info.tg` / `nx_cs.adj` / `install.sh` —— 那是主包的 SD 引导三件套，
> 放同名文件会覆盖主包引导器。请按下面两条路之一投递。

### 路 A：SD 增量同步（配合主包）
1. 把本包内的 `dicam_patch_*.sh`、`di-camera-app.c2.*`、`c2_bytepatch.*.json`
   放进【主包】的 `scripts/dicam/` 目录（仓库里已在该位置 ⇒ 主包天然带上）
2. 按主包流程插卡同步 → 文件落到相机 `/opt/usr/nx-ks/dicam/`
3. 相机上执行：`sh /opt/usr/nx-ks/dicam/dicam_patch_install.sh`
   （★ 同步不会自动装补丁 —— app 补丁必须显式触发）

### 路 B：FTP + telnet（已装机推荐，最直接）
```
# PC:
ftp> put di-camera-app.c2.{stub} /_xfer/dicam/di-camera-app.c2
# 相机（telnet）:
cp -r /mnt/mmc/_xfer/dicam /opt/usr/nx-ks/
sh /opt/usr/nx-ks/dicam/dicam_patch_install.sh
```

## 判据（装完自检）
```
st app help                     # 应回显用法表
st app film "touch /tmp/c2ok"   # 应生成 /tmp/c2ok（v2 会经 f.sh 转发）
st app uscom                    # 应【不再】输出 UserSpec dump 表（= 改名生效）
sh /opt/usr/nx-ks/dicam/dicam_patch_status.sh
```

## 回滚
```
sh /opt/usr/nx-ks/dicam/dicam_patch_rollback.sh
```

## ★ 安装路径（相机端权威）
| 路径 | 内容 |
|---|---|
| `/opt/usr/nx-ks/dicam/` | 补丁体 + 官方件备份 + bytepatch（p14，**刷固件不覆盖**） |
| `/opt/usr/nx-ks/init.sh` | 开机复挂钩子（追加 `# [dicam-T2]` 块） |
| `/usr/apps/com.samsung.di-camera-app/bin/di-camera-app` | bind-mount 挂载点（**rootfs 字节不变**） |

## 风险与已知边界
- 本包**不修改 rootfs 任何字节**；方式为 bind-mount（T2）。
- `di-camera-app.service` 的 `Restart=always` 被注释 ⇒ App 崩了不自愈，需手动
  `systemctl restart di-camera-app`；失败先跑 rollback。
- 补丁针对 **NX500 v1.12** 的 `di-camera-app`（md5 `ae44293e969101d1cf0a93cbe9b99f75`）；
  其它版本请勿安装。
- 补丁体 md5：`{binmd5}`

---
生成：{stamp} · 分支 nxwa · 详见 `docs/current/DICAM_MOD_DESIGN_2026-10-11.md`
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ver", default="1.0")
    ap.add_argument("--stub", default="v2", choices=["v1", "v2"])
    ap.add_argument("--out", default=r"E:/NXWA/release")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    binp, jsonp = pick(args.stub, None)
    if not binp:
        print("!! 找不到 %s 补丁二进制（先跑 mk_c2_patch.py --stub=%s）" % (args.stub, args.stub))
        return 1
    if not jsonp:
        print("!! 找不到 bytepatch json")
        return 2

    got = md5f(binp)
    exp = STUB_MD5[args.stub]
    print("补丁      : %s" % binp)
    print("md5       : %s" % got)
    if got != exp:
        print("   ⚠ 与台账不符（台账 %s）—— 请更新台账或核对文件" % exp)
    print("bytepatch : %s" % jsonp)

    stamp = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M")
    zname = "NX-WA-DICAM-PATCH-%s-%s.zip" % (args.ver, args.stub)
    zpath = Path(args.out) / zname

    # ★ 补丁包【不含】info.tg / nx_cs.adj / install.sh ——
    #   那两个是主包的 SD 引导三件套，本包若带同名 install.sh 会【覆盖主包引导器】。
    members = [
        ("README.md", README.format(ver=args.ver, stub=args.stub, binmd5=got, stamp=stamp).encode("utf-8")),
        ("dicam_patch_install.sh", (REPO / "scripts/dicam/dicam_patch_install.sh").read_bytes()),
        ("dicam_patch_rollback.sh", (REPO / "scripts/dicam/dicam_patch_rollback.sh").read_bytes()),
        ("dicam_patch_status.sh", (REPO / "scripts/dicam/dicam_patch_status.sh").read_bytes()),
        ("di-camera-app.c2.%s" % args.stub, binp.read_bytes()),
        ("c2_bytepatch.%s.json" % args.stub, jsonp.read_bytes()),
    ]
    md5lines = "\n".join("%s  %s" % (hashlib.md5(d).hexdigest(), n) for n, d in members) + "\n"

    print()
    print("将打包 %d 个成员：" % (len(members) + 1))
    for n, d in members:
        print("  %10d  %s" % (len(d), n))
    print("  %10d  md5.txt" % len(md5lines))
    print()
    print("输出      : %s" % zpath)

    if not args.write:
        print("（dry-run；加 --write 落盘）")
        return 0

    zpath.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in members:
            z.writestr(n, d)
        z.writestr("md5.txt", md5lines)
    print("已写出：%s（%d B，md5 %s）" % (zpath, zpath.stat().st_size, md5f(zpath)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
