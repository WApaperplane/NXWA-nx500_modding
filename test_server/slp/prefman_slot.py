#!/usr/bin/env python3
"""prefman 单槽位读写工具（NX500 / NX1 相机，已实机验证2026-10-06）

用途
----
不改二进制、不算 CRC、不 dump 整个分区，直接读写 pref 结构里的单个字段。
适合「改某个机身设置 → 让 ISP 下次开机读到」这类持久化参数修改。

★ 官方命名表 = 唯一权威的偏移来源
------------------------------------------------
    prefman info <ID> > /tmp/info.txt     # 672 条命名偏移，先查这个
    prefman get  <ID> <offset> l         # l=long(4B) s=short(2B) b=byte
★ 不要靠 diff 猜语义 —— 本项目曾因不查命名表把 3 个字段命名错
  （ISO_PAS 当成"档位"、ISO_PAS_1_3 当成"索引"、WB_TYPE 当成"WB 索引"）。

★★ 三个必踩的坑
------------------------------------------------
1. `prefman save` **不带 ID 是静默空操作**（不报错、不生效）。必须 `prefman save 0`。
2. `prefman fetch` **忽略路径参数**，固定写 `/opt/pref/pref_app.bin`。
   要指定路径用 `prefman save_file <ID> <路径>`（备份走这条）。
3. `type` 是类型名不是字节数：`l`=long / `s`=short / `b`=byte。
   传 `4` 会报 `unrecoginized option = 4`。
   且 `get/set` 的第一个参数是 ID，漏掉会把 offset 当 ID 解析。

NVD 容器结构
------------------------------------------------
    uint32 magic = 0x00330033
    uint32 crc           # 自定义算法，相机自维护，不要自己算
    uint32 size          # ★ 块总长【含 12 字节头】，不是载荷长！
    uint8payload[size-12]
★ 由此：容器偏移 = 载荷偏移 + 12（prefman info 给的是容器口径）。

用法
------------------------------------------------
    # 只读：查命名 + 读当前值
    python prefman_slot.py info0 --grep WB
    python prefman_slot.py get 0 0x0000a394

    # 写入（带备份 + 回读自证 + 落盘）
    python prefman_slot.py set 0 0x0000a394 5500 --save
"""
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOST = "192.168.0.105"          # ★ 实机固定 .105，.104 是 PC 本机
SD = "/opt/storage/sdcard"
WORK = SD + "/prefslot"

TYPES = {"l": "long(4B)", "s": "short(2B)", "b": "byte"}


def _sysarch():
    for p in (HERE / "sysarch", HERE.parent / "sysarch"):
        if (p / "fwprobe.py").exists():
            return p
    raise SystemExit("找不到 sysarch/fwprobe.py")


def _run(cmds, timeout=25):
    """一次 telnet 会话串行跑多条命令（★铁律：telnet 必串行）"""
    sys.path.insert(0, str(_sysarch()))
    from fwprobe import T
    t = T(HOST, timeout=timeout)
    out = []
    try:
        t.login()
        for c, to in cmds:
            out.append((c, t.send(c, to)))
    finally:
        try:
            t.send("exit", 1.0)
            t.close()
        except Exception:
            pass
    return out


def _get_text(cmds, remote, timeout=180):
    """跑完命令后把远端文件 FTP 拉回并返回文本
    ★ FTP 根 = SD 卡，路径必须相对 `/opt/storage/sdcard`（去掉前缀）"""
    sys.path.insert(0, str(_sysarch()))
    from ftpx import ftp_get
    _run(cmds)
    time.sleep(1)
    rel = remote[len(SD):].lstrip("/") if remote.startswith(SD) else remote
    local = HERE / ("_pull_" + rel.replace("/", "_"))
    n = ftp_get(HOST, rel, str(local), timeout=timeout)
    if not n:
        return None
    return local.read_text(encoding="latin1")


def cmd_info(seg=0, grep=None):
    cmds = [("mkdir -p %s" % WORK, 3.0),
            ("prefman info %d > %s/info%d.txt 2>&1" % (seg, WORK, seg), 25.0)]
    txt = _get_text(cmds, WORK + "/info%d.txt" % seg)
    if txt is None:
        print("拉取失败")
        return 1
    lines = [l for l in txt.splitlines() if l.strip()]
    if grep:
        pat = re.compile(grep, re.I)
        hits = [l for l in lines if pat.search(l)]
        print("匹配 %d 条（%s）" % (len(hits), grep))
        for l in hits:
            print("  " + l.strip())
    else:
        print("\n".join(l.strip() for l in lines[:60]))
        print("... 共 %d 行，完整文件在本地" % len(lines))
    return 0


_VAL = re.compile(r"value\s*=\s*(-?\d+)\s*\(0x([0-9a-fA-F]+)\)")


def cmd_get(seg, off):
    off = _norm(off)
    r = _run([("prefman get %d %s l 2>&1" % (seg, off), 8.0)])
    m = _VAL.search(r[0][1])
    if m:
        print("0x%s = %s (0x%s)" % (off, m.group(1), m.group(2)))
    else:
        print(r[0][1].strip()[-300:])
        return 1
    return 0


def cmd_set(seg, off, value, save=False, backup=True):
    """写单槽位。默认先备份 + 写后回读自证。"""
    off = _norm(off)
    cmds = [("mkdir -p %s" % WORK, 3.0)]
    if backup:
        cmds.append(("prefman save_file %d %s/bak_seg%d.bin 2>&1 | tail -2"
                     % (seg, WORK, seg), 18.0))
    cmds += [
        ("prefman get %d %s l 2>&1 | tail -3" % (seg, off), 8.0),
        ("prefman set %d %s l %s 2>&1 | tail -3" % (seg, off, value), 8.0),
        ("prefman get %d %s l 2>&1 | tail -3" % (seg, off), 8.0),
    ]
    if save:
        cmds.append(("prefman save %d" % seg, 20.0))   # ★ 必须带 ID
        cmds.append(("sync", 4.0))
        cmds.append(("prefman get %d %s l 2>&1 | tail -3" % (seg, off), 8.0))
    out = _run(cmds)

    print("=" * 66)
    print("写入 0x%s = %s%s" % (off, value, "（含落盘）" if save else "（仅内存，未落盘）"))
    print("=" * 66)
    for c, r in out:
        tail = [x for x in r.replace("\r", "").splitlines() if x.strip()]
        keep = [x for x in tail if "value =" in x or "nvd_save" in x
                or "Error" in x or "error" in x or "Usage" in x]
        print("  %-58s %s" % (c[:58], (keep[-1].strip() if keep else "")))

    # 自证：写后读数必须等于目标值
    if save:
        last = [x for x in out[-1][1].replace("\r", "").splitlines() if "value =" in x]
        got = _VAL.search(last[-1]) if last else None
        if got and int(got.group(1)) == int(value):
            print("\n✔ 自证通过：读回 %s == 目标 %s" % (got.group(1), value))
            return 0
        print("\n✘ 自证失败 —— 读回不等于目标值，检查上面的输出")
        return 1
    print("\n提示：加 --save 才会写入 eMMC 持久层（否则重启即丢）")
    return 0


def _norm(off):
    off = str(off).lower()
    return off if off.startswith("0x") else "0x%08x" % int(off, 0)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    #兼容 `info0` / `info 0` / `info0 ISO` 三种写法
    head = sys.argv[1].lower()
    rest = sys.argv[2:]
    if head.startswith("info"):
        tail = head[4:]
        seg = int(tail, 0) if tail else (int(rest[0], 0) if rest else 0)
        grep = None
        if tail:
            grep = rest[0] if rest else None
        elif rest:
            grep = rest[1] if len(rest) > 1 else None
        return cmd_info(seg, grep)

    a = [head] + rest

    if a[0] == "get":
        if len(a) < 3:
            print(__doc__)
            return 2
        return cmd_get(int(a[1], 0), a[2])

    if a[0] == "set":
        if len(a) < 4:
            print(__doc__)
            return 2
        seg = int(a[1], 0)
        return cmd_set(seg, a[2], a[3], "--save" in a, "--nobackup" not in a)

    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())