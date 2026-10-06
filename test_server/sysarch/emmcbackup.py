# -*- coding: utf-8 -*-
"""NX500 eMMC 关键分区备份（只读）。

★ 动机（记忆：社区给不了兜底，退路必须自己造）
  - 官方分区表确认 p7 = `rtos` / `rom.bin` = 我们逆向的 ISP 固件
  - iLauncher 已失效、版本单调性卡死、变砖无官方救援（issue #121 无解）
  - 社区 132 条 issues 零命中"有人备份过 eMMC"
  ⇒ 本工具就是那个"自己造的退路"。

纪律（铁律）：
  - **只读**：`dd if=/dev/mmcblk0pN`，永不 `of=/dev/mmcblk0pN`
  - 单核相机：分块 dd + 块间 sleep，绝不连续重活
  - 校验：每块算 md5 记入清单，回滚时逐块核对
  - 失败不中断：记录并继续，最后汇总

用法：
    python emmcbackup.py <ip> <outdir> [块大小MB]
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, "test_server/sysarch")
from fwprobe import T  # noqa: E402
from ftpx import ftp_get  # noqa: E402

# 关键分区：先保 p7（rtos/rom.bin，ISP 固件本体），再保内核与配置
PARTS = [
    (7, "rtos_rom.bin", "ISP 固件本体 ★最重要"),
    (8, "rtos_data", "rtos 数据区"),
    (6, "uImage", "主内核"),
    (13, "rImage", "恢复内核"),
    (12, "pcache", "预缓存表"),
    (1, "adj", "调整区"),
    (2, "pref", "偏好区"),
    (3, "pref_default", "默认偏好 ★回滚用"),
    (5, "pref_recovery", "恢复偏好 ★回滚用"),
]
SD = "/opt/storage/sdcard"
REMOTE_DIR = SD + "/emmcbak"


def human(n):
    return "%.1fMB" % (n / 1048576.0)


def main():
    host = sys.argv[1]
    outdir = Path(sys.argv[2] if len(sys.argv) > 2 else "raw8/emmcbak")
    chunk_mb = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    outdir.mkdir(parents=True, exist_ok=True)

    print("# host=%s outdir=%s chunk=%dMB" % (host, outdir, chunk_mb))
    t = T(host, timeout=25)
    t.login()
    print(t.send("cat /etc/version.info | head -1", 6.0).strip()[:60])

    t.send("mkdir -p " + REMOTE_DIR, 4.0)

    manifest = []
    for pno, name, note in PARTS:
        print("\n===== p%d  %s  (%s) =====" % (pno, name, note))
        # 分区大小（KB）
        r = t.send("cat /proc/partitions | grep 'mmcblk0p%d$' | awk '{print $3}'"
                   % pno, 6.0)
        kb = 0
        for ln in r.split("\n"):
            f = ln.split()
            if f and f[0].isdigit() and len(f) >= 3:
                kb = int(f[2])
                break
        if not kb:
            print("  !! 分区大小获取失败，跳过")
            manifest.append((pno, name, -1, "SIZE_FAIL", ""))
            continue
        total = kb * 1024
        print("  分区 %d KB = %s" % (kb, human(total)))

        # 远端总文件先截断为 0
        t.send("rm -f %s/%s" % (REMOTE_DIR, name), 3.0)

        step = chunk_mb * 1024
        done = 0
        md5s = []
        while done < total:
            n = min(step, total - done)
            skip_kb = done // 1024
            cnt_kb = (n + 1023) // 1024
            cmd = ("dd if=/dev/mmcblk0p%d bs=1024 skip=%d count=%d "
                   "of=%s/%s bs=1024 seek=%d 2>/dev/null"
                   % (pno, skip_kb, cnt_kb, REMOTE_DIR, name, skip_kb))
            t.send(cmd, 40.0)
            # 每块算一次局部 md5（增量累积，用于最终校验）
            r = t.send("dd if=%s/%s bs=1024 skip=%d count=%d 2>/dev/null | md5sum"
                       % (REMOTE_DIR, name, skip_kb, cnt_kb), 30.0)
            blk = ""
            for tok in r.split():
                if len(tok) == 32 and all(c in "0123456789abcdef" for c in tok):
                    blk = tok
            md5s.append(blk or "?")
            done += n
            print("    %s / %s  (%.0f%%)  md5=%s"
                  % (human(done), human(total), done * 100.0 / total, blk[:12]))
            time.sleep(2.0)          # ★ 让单核喘息

        # 远端总校验
        r = t.send("md5sum %s/%s | awk '{print $1}'" % (REMOTE_DIR, name), 40.0)
        full = ""
        for tok in r.split():
            if len(tok) == 32 and all(c in "0123456789abcdef" for c in tok):
                full = tok
        sz_r = t.send("wc -c < %s/%s" % (REMOTE_DIR, name), 10.0)
        got = 0
        for ln in sz_r.split("\n"):
            f = ln.split()
            if f and f[0].isdigit():
                got = int(f[0])
                break
        print("  远端: %s  md5=%s  块数=%d"
              % (human(got) if got else "?", full[:12] if full else "?", len(md5s)))
        manifest.append((pno, name, got, full, ";".join(md5s)))

    # FTP 拉回
    print("\n########## FTP 拉回 PC ##########")
    for pno, name, got, full, blk in manifest:
        if got <= 0:
            continue
        local = outdir / name
        got2 = ftp_get(host, "/emmcbak/" + name, str(local), timeout=600)
        ok = "OK" if got2 == got else "SIZE-MISMATCH"
        print("  p%-3d %-18s %10s  %s" % (pno, name, human(got2 or 0), ok))
        time.sleep(0.8)

    t.send("exit", 1.0)
    t.close()

    # 清单落盘
    mf = outdir / "MANIFEST.txt"
    with mf.open("w", encoding="utf-8") as f:
        f.write("===== NX500 eMMC 关键分区备份清单 =====\n")
        f.write("时间: %s\n主机: %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), host))
        f.write("官方分区表: /etc/parttab (卷名 rtos=p7=rom.bin)\n\n")
        for pno, name, got, full, blk in manifest:
            f.write("p%-3d %-18s %12d  md5=%s\n"
                    % (pno, name, got, full if full else "?"))
            if blk and blk != "?":
                chunks = blk.split(";")
                for i, c in enumerate(chunks):
                    f.write("     blk%02d %s\n" % (i, c))
    print("\n清单: %s" % mf)


if __name__ == "__main__":
    main()
