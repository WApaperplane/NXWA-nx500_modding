#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
capdtm_enum2.py —— capdtm 槽位【安全】黑盒枚举器v2

★ 与 v1 的区别（v1 写挂了 p7 capture 服务）
------------------------------------
v1 对 0..63 全盲扫，撞上 `varlist` 里的运行控制变量（SENSORFRAMERATE /
OBJTRACKRUNSTATE / LENSINIT...）⇒ **p7 capture 服务崩溃**，所有 `st cap *` 失效。

v2 的安全措施：
  ① **只扫 usrlist 报告的槽位**（UI 可改项，值域受控）—— 除非显式 `--all`
  ② **每次写后立刻探活**：`st cap iqr|head -1` 无输出 ⇒ 立即停止，不再写任何槽位
  ③ **白名单模式**（默认）：只写已知的 USERDATA_* 槽位
     `--probe`模式：探活式试探（写→探活→不恢复，靠重启还原），
                     一次只试 1 个槽位，失败即整体中止
  ④ 写后**不恢复**（避免恢复动作再触发一次崩溃），
     由调用方重启相机或手工还原

用法
----
python capdtm_enum2.py<IP>                 # 列出所有 usrlist 槽位
python capdtm_enum2.py <IP> --probe         # 逐槽探活式试探（每槽一次 telnet 会话）
python capdtm_enum2.py <IP> --slot 5        # 只处理槽位 5
"""
import socket, sys, time, re, json

HOST_DEFAULT = "192.168.0.105"
VL = re.compile(r"\[\s*(\d+)\]\s*\|?\s*(VARIABLE_\w+)\s*\|\s*(\d+)\s*\|\s*([-0-9A-Fa-fx]+)\s*\|\s*([-0-9A-Fa-fx]+)")
UL = re.compile(r"\[\s*(\d+)\]\s*\|\s*(USERDATA_\w+)\s*\|\s*([A-Z0-9_]+)\s*\|\s*([-0-9A-Fa-fx]+)")
VAR = re.compile(r"Variable Data is (0x[0-9a-fA-F_]+)")


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
        o, self.buf = self.buf, b""
        o = re.sub(rb"\xff[\xfb-\xfe].|\xff.", b"", o)
        return o.decode("utf-8", errors="replace")

    def send(self, cmd, wait=1.2):
        self.s.sendall((cmd + "\n").encode())
        time.sleep(0.15)
        return self.drain(wait)

    def login(self):
        o = self.drain(2.5)
        for _ in range(4):
            low = o.lower()
            if "login" in low or "password" in low or "#" not in o:
                self.s.sendall(b"root\n")
                time.sleep(0.5)
                o = self.drain(1.5)
            else:
                break
        probe = self.send("echo RDY_$?", wait=1.5)
        return "RDY_0" in probe

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass


def alive(t):
    """★ 探活：iqr 必须有输出。返回 True/False"""
    o = t.send("st cap iqr 2>&1 | head -8", wait=2.5)
    if "CFrame" in o or "MCB" in o or "Cann" in o:
        return False
    return "eIQ_ID_" in o


def getvar1(t, slot):
    o = t.send("st cap capdtm getvar %d 2>&1" % slot, wait=1.2)
    m = VAR.search(o)
    return m.group(1) if m else "?"


def cmd_list(ip):
    t = Tel(ip)
    if not t.login():
        print("!! 登录失败")
        return 1
    print("=== usrlist（安全槽位 = UI 可改项）===")
    o = t.send("st cap capdtm usrlist 2>&1", wait=6.0)
    n = 0
    for line in o.splitlines():
        m = UL.search(line)
        if m:
            n += 1
            print("  [%3s] %-28s %-26s %s" % m.groups())
    print("--- 共 %d 项 ---" % n)
    t.close()
    return 0


def cmd_probe(ip, only=None):
    """探活式：一次一个槽位，写后立刻探活；不恢复"""
    t = Tel(ip)
    if not t.login():
        print("!! 登录失败")
        return 1
    if not alive(t):
        print("!! 服务当前无响应，先重启相机")
        t.close()
        return 1
    print("服务存活，开始探活式试探（每槽写 1，不恢复）")

    # 取 usrlist 槽位
    o = t.send("st cap capdtm usrlist 2>&1", wait=6.0)
    slots = []
    for line in o.splitlines():
        m = UL.search(line)
        if m:
            slots.append((int(m.group(1)), m.group(2), m.group(3)))
    if not slots:
        print("!! usrlist 解析失败")
        t.close()
        return 1
    print("usrlist %d 槽" % len(slots))

    if only is not None:
        slots = [s for s in slots if s[0] == only]

    results = []
    for slot, name, param in slots:
        if not alive(t):
            print("!! 服务在槽位 %d 前已死，中止" % slot)
            break
        before = getvar1(t, slot)
        # 写当前 usr 值+1（保持在 UI 允许的枚举范围内）
        try:
            v = int(param, 16) & 0xFFFF
        except Exception:
            v = 0
        v2 = (v + 1) & 0xFFFF
        key = (slot << 16) | v2
        o = t.send("st cap capdtm setvar %d 0x%08X 4 2>&1 | head -1" % (slot, key), wait=1.2)
        ok = "is set" in o
        a = alive(t)
        after = getvar1(t, slot) if a else "DEAD"
        flag = "OK" if a else "★★ 弄死了服务，停止 ★★"
        print("  slot %-3d %-26s wrote=%-5s alive=%-5s %s -> %s  %s"
              % (slot, name, ok, a, before, after, flag))
        results.append((slot, name, ok, a))
        if not a:
            break
    t.close()
    print("\n=== 汇总 ===")
    print("已试%d 槽，服务存活: %s" % (len(results), all(r[3] for r in results)))
    return 0



def iqr_snap(t):
    """iqr 全段快照 -> {字段名: 值字符串}（快，2s）"""
    o = t.send("st cap iqr 2>&1", wait=3.5)
    d = {}
    # ★ telnet 里的形态: '\x00[ 97]| \x1b[33meIQ_ID_XXX   \x1b[m| 名称 | 值 | hex|'
    #   ⇒ 先剥 ANSI，再按 "| " 切，最后用正则取字段名与数值列
    o = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", o).replace("\x00", " ")
    for line in o.splitlines():
        if "eIQ_ID_" not in line:
            continue
        m = re.search(r"eIQ_ID_([A-Z0-9_]+)", line)
        if not m:
            continue
        name = "eIQ_ID_" + m.group(1)
        # 数值列: 最后一个 "| <digits> | 0xHEX |" 里的十进制
        nums = re.findall(r"\|\s*(-?\d+)\s*\|\s*0x[0-9a-fA-F]+\s*\|", line)
        d[name] = nums[0] if nums else "?"
    # ★ 服务无响应时 iqr 无输出 => 返回空 dict（而不是全 "?"）
    if len(d) < 5:
        return {}
    return d


WBKEYS = ["eIQ_ID_WB_COLORTEMP", "eIQ_ID_WB_KELVIN", "eIQ_ID_WB_MODE",
          "eIQ_ID_WB_ADJUST_AB", "eIQ_ID_WB_ADJUST_MG",
          "eIQ_ID_WB_BA_X", "eIQ_ID_WB_GM_Y", "eIQ_ID_WB_TYPE",
          "eIQ_ID_WB_BRACKET_AB", "eIQ_ID_WB_BRACKET_MG",
          "eIQ_ID_CWB_R_GAIN", "eIQ_ID_CWB_B_GAIN", "eIQ_ID_CWB_G_GAIN",
          "eIQ_ID_PW_COLOR", "eIQ_ID_PW_COLOR_R", "eIQ_ID_PW_COLOR_G",
          "eIQ_ID_PW_COLOR_B", "eIQ_ID_PW_HUE", "eIQ_ID_PW_SATURATION",
          "eIQ_ID_COLOR_SPACE", "eIQ_ID_SRA_WB_UPDATE",
          "eIQ_ID_SMARTART_COLORTEMP_STATE", "eIQ_ID_SMARTART_COLORTEMP_LEVEL",
          "eIQ_ID_MOVIE_GAMMA_MODE", "eIQ_ID_OLED_COLOR"]


def iqr_wb(t):
    """iqr 里 WB 相关字段"""
    d = iqr_snap(t)
    return {k: d.get(k, "?") for k in WBKEYS}


def vl_wbc(temp):
    """返回 varlist 里 WBCOLORTEMP 的 hex 值"""
    o = temp.send("st cap capdtm varlist 2>&1", wait=7.0)
    for line in o.splitlines():
        m = VL.search(line)
        if m and m.group(2) == "VARIABLE_WBCOLORTEMP":
            return m.group(4)
    return "?"


def cmd_find(temp_ip, slots):
    """★ 只针对 WBCOLORTEMP：写小值到候选槽位，看varlist 里 WBCOLORTEMP 是否变化
    ★ 每次写后立刻探活"""
    t = Tel(temp_ip)
    if not t.login():
        print("!! 登录失败")
        return 1
    if not alive(t):
        print("!! 服务无响应")
        t.close()
        return 1
    b0 = iqr_wb(t)
    print("baseline iqr WB:")
    for k, v in b0.items():
        print("   %-24s %s" % (k, v))
    found = []
    for s in slots:
        if not alive(t):
            print("!! 服务在槽 %d 前已死，停止" % s)
            break
        o = t.send("st cap capdtm setvar %d 0x%08X 4 2>&1|head -1" % (s, (s << 16) | 1), wait=1.0)
        ok = "is set" in o
        a = alive(t)
        nw = iqr_wb(t) if a else {}
        # ★★ 关键修正：iqr 无输出时 iqr_wb 返回 {}，此时不能算"全部变化"（那是假阳性）
        #    slot 62 教训：全字段变 "?" 实际是服务已死
        if a and len(nw) < 5:
            print("  slot %-3d wrote=%-5s ★ iqr 无输出（服务已死），停止" % s)
            a = False
            nw = {}
        chg = [(k, b0.get(k), nw[k]) for k in WBKEYS
               if k in nw and nw[k] != b0.get(k) and nw[k] != "?"] if a else []
        if not a:
            print("  slot %-3d wrote=%-5s ★ 弄死服务，停止" % (s, ok))
            break
        if chg:
            print("  slot %-3d wrote=%-5s ★★ 命中:" % (s, ok))
            for k, x, y in chg:
                print("        %-24s %s -> %s" % (k, x, y))
            found.append((s, chg))
            b0 = nw
        else:
            print("  slot %-3d wrote=%-5s 无变化" % (s, ok))
    t.close()
    print("\n=== 命中汇总 ===")
    for s, chg in found:
        print("  slot %d: %s" % (s, ", ".join("%s %s->%s" % c for c in chg)))
    return 0


def main():
    args = sys.argv[1:]
    ip = HOST_DEFAULT
    if args and re.match(r"^\d+\.\d+\.\d+\.\d+$", args[0]):
        ip = args.pop(0)
    if args and args[0] == "--find":
        #只试安全区：usrlist 已验证的 USERDATA 槽位 + varlist 前若干
        s = [int(x) for x in args[1:]] if len(args) > 1 else list(range(0, 30))
        return cmd_find(ip, s)
    if args and args[0] == "--probe":
        return cmd_probe(ip)
    if args and args[0] == "--slot":
        return cmd_probe(ip, int(args[1]))
    return cmd_list(ip)


if __name__ == "__main__":
    sys.exit(main())
