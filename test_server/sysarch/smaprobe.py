# -*- coding: utf-8 -*-
"""SMA 共享区 (0x94000000) 只读活动性探针 —— 判据工具。

★ 目的：判定"ISP 固件与 EP 是否真的通过这块共享内存交换帧数据"。
  静态分析已确认 0x94000000 存在于两侧（ISP 固件 0x9FC0 内存段表 +
  Linux dmesg `cma: reserved 288 MiB at 94000000`），
  但**共享内存存在 ≠ 数据在流动**。本工具用只读方式采样多轮，
  用 md5 差异做客观判据。

纪律（铁律）：
  - **只读**：`dd if=/dev/mem` 永不写；不 mmap 写、不碰 EP 寄存器。
  - 单核相机：每条命令独立超时，轮次之间留呼吸。
  - 判据不成立必须**返回非零退出码**（记忆铁律 10）。

用法：
    python smaprobe.py <ip> [轮次] [每轮字节数]
"""
import hashlib
import sys
import time

sys.path.insert(0, "test_server/sysarch")
from fwprobe import T  # noqa: E402

BASE = 0x94000000
DEFAULT_ROUNDS = 4
DEFAULT_LEN = 4096


def sample(t, off, length, label):
    """只读采一块物理内存，返回 (md5, 十六进制前若干字节)。"""
    cmd = ("dd if=/dev/mem bs=1 skip=$((%d)) count=%d 2>/dev/null | md5sum"
           % (off, length))
    out = t.send(cmd, 25.0)
    digest = ""
    for tok in out.split():
        if len(tok) == 32 and all(c in "0123456789abcdef" for c in tok):
            digest = tok
    # 再取头部 64 字节的十六进制，人工核对是否全零
    cmd2 = ("dd if=/dev/mem bs=1 skip=$((%d)) count=64 2>/dev/null"
            " | od -A n -t x1 | tr -d ' \\n' | cut -c1-64" % off)
    hexs = t.send(cmd2, 20.0)
    line = ""
    for ln in hexs.split("\n"):
        ln = ln.strip()
        if len(ln) >= 32 and all(c in "0123456789abcdef" for c in ln[:32]):
            line = ln
    print("  [%s] off=0x%08x len=%d md5=%s" % (label, off, length,
                                                 digest or "<none>"))
    print("       head=%s" % (line or "<parse failed>"))
    return digest, line


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "192.168.0.105"
    rounds = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_ROUNDS
    length = int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_LEN

    print("# host=%s  rounds=%d  len=%d  base=0x%08x" %
          (host, rounds, length, BASE))
    print("# 只读：dd if=/dev/mem，无任何写操作\n")

    t = T(host)
    t.login()
    print("### 基线：dmesg CMA 记录 ###")
    print(t.send("dmesg | grep -i cma | head -3", 8.0)[:400])

    results = {}
    print("\n### 采样 %d 轮（每轮间隔 2.5s）###" % rounds)
    for r in range(rounds):
        # 每轮同时采 SMA 头 + 一个已知活跃区作对照
        d1, h1 = sample(t, BASE, length, "SMA  r%d" % r)
        time.sleep(2.5)
        d2, h2 = sample(t, BASE, length, "SMA  r%d(recheck)" % r)
        results[r] = (d1, h2, h1)
        time.sleep(1.5)

    t.send("exit", 1.0)
    t.close()

    # ── 判据 ──
    print("\n#### 判据 ####")
    digests = {r: v[0] for r, v in results.items()}
    uniq = set(d for d in digests.values() if d)
    all_zero = all(
        h == "0" * 64
        for v in results.values() for h in (v[1], v[2]) if h)

    print("  不同 md5 个数: %d  %s" % (len(uniq), digests))
    if len(uniq) > 1:
        print("  => 内存内容在变 ⇒ 有活动")
        rc = 0
    else:
        if not uniq:
            print("  => 采样全失败（md5 未解析）")
            rc = 2
        elif all_zero:
            print("  => 内容恒定且全零 ⇒ 本时段无活动")
            rc = 3
        else:
            print("  => 内容恒定但非零 ⇒ 本时段无活动（存在静态数据）")
            rc = 3
    print("  全零判定: %s" % ("是" if all_zero else "否"))

    print("\n退出码 %d （0=有活动 / 3=无活动 / 2=采样失败）" % rc)
    sys.exit(rc)


if __name__ == "__main__":
    main()
