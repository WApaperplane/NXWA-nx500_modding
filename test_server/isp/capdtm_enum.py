#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
capdtm_enum.py —— capdtm 槽位黑盒枚举器（★ p7 静态不可见，只能实机试）

原理
----
`varlist` 的 45 个变量名在 p7 里是纯字符串流，id 分派是运行时动态注册的
（静态分析确认 refs=0，见 memory 2026-06 15:55）。
⇒ 唯一办法：逐槽位写一个可辨识的值，看 `varlist` 里哪个变量变了 ⇒ 反推映射。

用法
----
python capdtm_enum.py [IP]              # 扫槽位 0..63
python capdtm_enum.py [IP] --one 5      # 只看槽位 5
"""
import socket, sys, time, re

HOST = "192.168.0.105"
PORT = 23


class Tel:
    def __init__(self, host, port=23, timeout=8):
        self.s = socket.create_connection((host, port), timeout=timeout)
        self.s.settimeout(2)
        self.buf = b""

    def drain(self, t=1.2):
        end = time.time() + t
        while time.time() < end:
            try:
                c = self.s.recv(4096)
                if not c:
                    break
                self.buf += c
            except socket.timeout:
                pass
        return self.take()

    def take(self):
        o = self.buf
        self.buf = b""
        # 过滤 telnet IAC
        o = re.sub(rb"\xff[\xfb-\xfe].|\xff.", b"", o)
        return o.decode("utf-8", errors="replace")

    def send(self, cmd, wait=1.2):
        self.s.sendall((cmd + "\n").encode())
        time.sleep(0.15)
        return self.drain(wait)


VL = re.compile(r"\[\s*(\d+)\]\s*\|?\s*(VARIABLE_\w+)\s*\|\s*(\d+)\s*\|\s*([-0-9A-Fa-fx]+)\s*\|\s*([-0-9A-Fa-fx]+)")


GV = re.compile(r"Variable Data is (0x[0-9a-fA-F_]+)")


def getvar1(t, slot):
    """单槽 getvar（★ 必须单独发：`;` 串联会与prompt 混排导致解析错位）"""
    out = t.send("st cap capdtm getvar %d 2>&1" % slot, wait=1.2)
    m = re.search(r"Variable Data is (0x[0-9a-fA-F_]+)", out)
    return m.group(1) if m else "?"


def getvars(t, slots):
    """逐槽 getvar -> {slot: hexstr}（逐条发，保证顺序对应）"""
    d = {}
    for i in slots:
        d[i] = getvar1(t, i)
    return d


def varlist(t):
    """返回 {索引: (name, length, hexval, decval)}
    ★ 注意：不用 `| grep` 管道 —— 非交互 shell 下管道输出可能不刷新（实测踩到）"""
    out = t.send("st cap capdtm varlist 2>&1", wait=8.0)
    d = {}
    for line in out.splitlines():
        m = VL.search(line)
        if m:
            d[int(m.group(1))] = (m.group(2), int(m.group(3)), m.group(4), m.group(5))
    if not d:
        # 退化：把原始输出存盘供人工看
        with open("_varlist_raw.txt", "w", encoding="utf-8", errors="replace") as fh:
            fh.write(out)
    return d


def main():
    host = HOST
    args = sys.argv[1:]
    only = None
    if args and re.match(r"^\d+\.\d+\.\d+\.\d+$", args[0]):
        host = args.pop(0)
    if args and args[0] == "--one":
        only = int(args[1])

    t = Tel(host)
    # 登录：先等 banner，若看到 login/password 就发 root
    o = t.drain(2.5)
    for _ in range(4):
        low = o.lower()
        if "login" in low or "password" in low or "drime5 login" in low:
            t.s.sendall(b"root\n")
            time.sleep(0.5)
            o = t.drain(1.5)
        elif "#" in o:
            break
        else:
            t.s.sendall(b"\n")
            time.sleep(0.3)
            o = t.drain(1.0)
    print("=== connected %s ===" % host)
    # 验证 shell 可用
    probe = t.send("echo READY_$?", wait=1.5)
    if "READY_0" not in probe:
        print("!! shell 未就绪，最后输出：")
        print(probe[:500])
        return 1

    base = varlist(t)
    if not base:
        print("!! varlist 解析失败，telnet 输出前 400 字：")
        print(t.drain(1.0)[:400])
        return 1
    print("baseline: %d 个变量" % len(base))

    if only is not None:
        slots = [only]
    elif "--quick" in sys.argv:
        slots = [0, 1, 4, 5, 6, 7]
    else:
        slots = list(range(0, 64))
    hits = []
    gbase = getvars(t, slots)
    print("getvar baseline 采样完成")

    for i in slots:
        # 写入可辨识值：0x0000_i001（槽位在高16位，低16位=1）
        key = 0x00000001 | (i << 16)
        o = t.send("st cap capdtm setvar %d 0x%08X 4 2>&1 | head -1" % (i, key), wait=1.0)
        wrote = "is set" in o
        now = getvar1(t, i)
        if now != gbase.get(i, "?") and now != "0x00000000_00000000":
            print("slot %-3d wrote=%-5s getvar: %s -> %s  ★命中" % (i, wrote, gbase.get(i), now))
            hits.append((i, gbase.get(i), now))
        else:
            print("slot %-3d wrote=%-5s getvar: %s (未变)" % (i, wrote, now))
        gbase[i] = now
        # 恢复
        t.send("st cap capdtm setvar %d 0x%08X 4" % (i, key), wait=0.6)

    print("\n=== 命中汇总 ===")
    for i, a, b in hits:
        print("slot %-3d : %s -> %s" % (i, a, b))
    t.s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
