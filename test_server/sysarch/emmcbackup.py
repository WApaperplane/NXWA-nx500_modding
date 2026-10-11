#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NX500 eMMC 关键分区备份 v2（整块 dd 版，只读）。

★ 动机（社区给不了兜底，退路必须自己造）：p7=rtos=ISP 固件本体，变砖无官方救援。

v1 教训（2026-10-11 实测）：分块逻辑存在单位换算 bug（chunk_mb*1024 得 KB，
与字节 total 混用 → 实际每块 4KB）+ 长 telnet 会话被相机 RST，从未跑通。
v2 改为：相机侧单条 setsid 命令（整块 dd + md5sum 落盘）→ PC 轮询 →
FTP 拉回 → 逐一 md5 校验 → MANIFEST。实测读取 24MB/s+，194MB 全程 <1 分钟。

纪律：**只读**（dd if=，永不 of=/dev/mmcblk0*）。

用法: python emmcbackup.py <ip> [outdir=raw8/emmcbak]
"""
import hashlib
import sys
import time
from pathlib import Path

sys.path.insert(0, "test_server/sysarch")
from fwprobe import T  # noqa: E402
from ftpx import ftp_get  # noqa: E402

# 关键分区（pN）——boot0/boot1 用独立设备名，见 README/台账（手动 dd 或用 --boot）
PARTS = [7, 8, 6, 13, 12, 1, 2, 3, 5]
SD = "/opt/storage/sdcard"
REMOTE_DIR = SD + "/emmcbak"


def md5_file(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    host = sys.argv[1]
    outdir = Path(sys.argv[2] if len(sys.argv) > 2 else "raw8/emmcbak")
    outdir.mkdir(parents=True, exist_ok=True)
    print(f"# host={host} outdir={outdir}")
    t = T(host, timeout=25)
    t.login()
    print(t.send("cat /etc/version.info | head -1", 6.0).strip()[:60])

    # 阶段 1：相机侧一条 setsid 命令（整块 dd + md5sum），后台执行
    cmds = ["mkdir -p " + REMOTE_DIR, "cd " + REMOTE_DIR]
    for p in PARTS:
        cmds.append("dd if=/dev/mmcblk0p%d of=p%d.bin 2>/dev/null" % (p, p))
    cmds.append("md5sum *.bin > md5s.txt")
    cmds.append("echo DONE >> md5s.txt")
    one = " && ".join(cmds)
    t.send("/usr/bin/setsid /bin/sh -c '%s'" % one, 6.0)
    print("  [fired] 相机侧整块 dd + md5sum（后台跑）")

    # 阶段 2：轮询 md5s.txt（最多 300s）
    remote_md5 = {}
    for _ in range(30):
        time.sleep(10)
        r = t.send("cat " + REMOTE_DIR + "/md5s.txt 2>/dev/null", 6.0)
        if "DONE" in r:
            for ln in r.splitlines():
                f = ln.split()
                if len(f) >= 2 and len(f[0]) == 32:
                    remote_md5[f[1].replace("\r", "")] = f[0]
            break
    if not remote_md5:
        print("  !! md5s.txt 未就绪（网络/相机问题）——稍后重跑即可（幂等）")
        return

    # 阶段 3：FTP 拉回 + 逐一校验（幂等：已存在且 md5 一致则跳过）
    print("########## FTP 拉回 + 校验 ##########")
    all_ok = True
    for name in sorted(remote_md5):
        local = outdir / name
        if local.exists() and md5_file(local) == remote_md5[name]:
            print(f"  OK(cached)   {name}")
            continue
        ftp_get(host, "/emmcbak/" + name, str(local), timeout=600)
        lm = md5_file(local) if local.exists() else "?"
        ok = lm == remote_md5[name]
        all_ok = all_ok and ok
        print("  %-11s %-12s remote=%s local=%s"
              % ("OK" if ok else "MISMATCH!", name,
                 remote_md5[name][:12], (lm or "?")[:12]))
        time.sleep(0.5)

    # 阶段 4：MANIFEST
    mf = outdir / "MANIFEST.txt"
    with mf.open("w", encoding="utf-8") as f:
        f.write("===== NX500 eMMC 关键分区备份清单（v2）=====\n")
        f.write("时间: %s\n主机: %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), host))
        f.write("方式: 相机侧整块 dd → SD/emmcbak → FTP 拉回（逐一 md5 校验）\n")
        f.write("总校验: %s\n\n" % ("ALL-OK" if all_ok else "HAS-FAILURES"))
        for name in sorted(remote_md5):
            f.write("%-12s md5=%s\n" % (name, remote_md5[name]))
    print("清单:", mf, "总校验:", "ALL-OK" if all_ok else "HAS-FAILURES")
    t.send("exit", 1.0)
    t.close()


if __name__ == "__main__":
    main()
