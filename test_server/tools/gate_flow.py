#!/usr/bin/env python3
"""NX-KS2 门控引擎 (gate_flow.py)

把 `docs/current/WORKFLOW_PLAN_2026-10-08.md` §4（门控表 G0-G5）与 §5（preflight）
从**散文表格**变成**可执行门控**：一条命令回答三个问题——

  1. 现在允许做什么？（能力放行矩阵）
  2. 被哪道门卡住？（哪一项 FAIL / BLOCKED）
  3. 下一步动作是什么？（每项的"不过怎么办"回流路径）

设计纪律（都是本项目踩过的坑换来的）
------------------------------------
* **门只看证据，不看叙述**。每道门的判定必须落到"某个文件存在且内容可校验"或
  "某个网络/命令返回可复现"，不接受"文档里写了"。
* **三态而非二元**：`BLOCKED`（还没到能判的时候，比如需要上机产物）与 `FAIL`
  （现在就能判且不满足）必须分开——否则一上机前就满屏红，门控会被下意识忽略。
* **MANUAL 单列**：`铁律 104：进程活着 != 系统没被拖垮`。这类判定**只能由人在机身给出**，
  工具不许替人签字，只负责把它挂出来提醒。
* **自证而不是自述**：U1 脚本包里的纪律（单段 <=768 regs / 只读 / setsid / 段间等待）
  不是"生成时保证一次"，而是**每次跑门控时从脚本文本重新解析**（`@gate` 头注释），
  这样脚本被手改坏也会被抓住。
* 只读。**本工具不做任何写相机/写固件的动作**，只探测、只读文件、只跑本地 lint。

用法
----
  python test_server/tools/gate_flow.py                  # 全部门 + 状态板
  python test_server/tools/gate_flow.py --only G0,G1     # 只看某几道门
  python test_server/tools/gate_flow.py --no-probe       # 不碰网络（纯离机判定）
  python test_server/tools/gate_flow.py --u1             # 附打印 U1 上机 runbook
  python test_server/tools/gate_flow.py --json           # 落盘 raw8/gates/gate_status.json

退出码：0 = 没有 FAIL；1 = 至少一道门 FAIL（BLOCKED 不算失败）
"""
from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import re
import socket
import struct
import subprocess
import sys
import time

# ----------------------------------------------------------------------------
# 常量：全部来自本仓已确认的硬事实（不许在这里"顺手推测"）
# ----------------------------------------------------------------------------

CAM_HOST_DEFAULT = "192.168.0.105"

# 铁律 90：21 端口是 FTP（部署通道），23 是 telnet（会话通道）。G0 判 21。
G0_PORT = 21
G0_PORT_HINTS = (21, 23, 8080)

# preflight §5-2：EV_MOBILE.sh 的三个哈希。危险版会被 install.sh 原样装上机。
EV_MOBILE_PATH_CANDIDATES = (
    "scripts/EV_MOBILE.sh",
    "scripts/nx-rc/EV_MOBILE.sh",
    "deploy/filmlab/EV_MOBILE.sh",
)
EV_MOBILE_SAFE = {
    "2657352ebcadd6271f5c4e4332d3b1e6": "deploy/filmlab 版（安全）",
    "54a308b8c55d8e3a313f63c33e06d0a5": "scripts/nx-rc 版（重写版）",
}
EV_MOBILE_DANGER = "55c47b8924342c422559b2181fa07c9f"

# 铁律 88：单次连续段 <=768 regs(3KB)。危险量是"单次运行的循环总量"。
SEG_MAX_REGS = 768

# 相机端 mod 落点（唯一安全可写分区），U1 输出写这里，再由 PC 侧 FTP 拉
CAM_MOD_DIR = "/opt/usr/nx-ks"
CAM_SD_OUT = "/mnt/mmc/u1/out"

# U1 脚本包（由 gate_pack_u1.py 生成；本工具只读它并做 lint）
U1_DIR = os.path.join("test_server", "u1")
U1_RUNBOOK = os.path.join(U1_DIR, "runbook.txt")

# U6 脚本包（3D LUT 上机包；手写资产，同样做 lint）
U6_DIR = os.path.join("test_server", "u6")
U6_RUNBOOK = os.path.join(U6_DIR, "runbook.txt")

# PW 直推包（pwsend/pwcalib；上机跑，受同款 lint）
PWSEND_DIR = os.path.join("test_server", "pwsend")
PWSEND_RUNBOOK = os.path.join(PWSEND_DIR, "runbook.txt")

# LUT 链路包（lutpick 产品工具；无 runbook —— 上机路径由 U6 runbook 覆盖）
LUTPIPE_DIR = os.path.join("test_server", "lutpipe")

# 证据落点（raw8/ 已在 .gitignore，属"本机证据"不入库）
EV_ROOT = os.path.join("raw8", "gates")
EV_U1 = os.path.join(EV_ROOT, "u1")
EV_U1_MEM = os.path.join(EV_U1, "mem_compare.json")
EV_U1_IQR = os.path.join(EV_U1, "iqr_dump.txt")
EV_U1_MAP = os.path.join(EV_U1, "iqr_epmc_map.tsv")
EV_U4 = os.path.join(EV_ROOT, "u4", "acceptance.json")
EV_U5 = os.path.join(EV_ROOT, "u5", "rollback_drill.json")

# G5 的静态判据 ID 全表（184 个 eIQ_ID_*，从 p7 字符串面提取）
EIQLIST = os.path.join("raw8", "p7", "tuning_keys.txt")
EIQ_MIN_IDS = 184

# G3 的离线预渲染产物（.gitignore 排除 *.png，属本机证据）
UI_PAGES = [os.path.join("raw8", "repro", f"ui_page_p{i}.png") for i in range(1, 6)]
UI_LOG = os.path.join("raw8", "repro", "ui_pages.log")
UI_W, UI_H = 720, 480
D7_REPORT = os.path.join("docs", "current", "D7_NXFILMUI_CJK_REBROADCAST_2026-10-08.md")

# G4 的不可再生资产（硬前置：没有备份就不许碰 p7）
ASSET_SLP = os.path.join(".uploads", "fw", "nx500_v1.13.bin")
ASSET_EMMCBAK = os.path.join("raw8", "emmcbak")
QUARANTINED = (
    (os.path.join("raw8", "p7", "quarantine", "p7_patched.bin.DO-NOT-FLASH"),
     "危险补丁（复位期 DACR 被改坏）"),
    (os.path.join("raw8", "fw", "quarantine", "NX500_FW_v1.12.zip.TRUNCATED-DO-NOT-USE"),
     "截断固件包"),
)
MUST_BE_ABSENT = (
    os.path.join("raw8", "p7", "p7_patched.bin"),
    os.path.join(".uploads", "fw", "p7_patched.bin"),
)

# 门状态。★ INFO 是"诊断信息，不参与判定"——没有它的话，
# 一个 Timeout 的旁证端口会被渲染成 [ OK ]，读起来像"它没事"，属于误导性输出。
PASS, FAIL, BLOCKED, MANUAL, INFO = "PASS", "FAIL", "BLOCKED", "MANUAL", "INFO"
MARK = {PASS: "[ OK ]", FAIL: "[FAIL]", BLOCKED: "[BLOCK]", MANUAL: "[MAN]", INFO: "[INFO]"}


# ----------------------------------------------------------------------------
# 基础设施
# ----------------------------------------------------------------------------

class Repo:
    def __init__(self, root):
        self.root = os.path.abspath(root)

    def p(self, *parts):
        return os.path.join(self.root, *parts)

    def has(self, rel):
        return os.path.exists(self.p(rel))

    def size(self, rel):
        try:
            return os.path.getsize(self.p(rel))
        except OSError:
            return -1

    def md5(self, rel):
        try:
            h = hashlib.md5()
            with open(self.p(rel), "rb") as fh:
                for blk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(blk)
            return h.hexdigest()
        except OSError:
            return None

    def text(self, rel):
        try:
            with open(self.p(rel), "r", encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except OSError:
            return None

    def json(self, rel):
        raw = self.text(rel)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None


class Check:
    """一项判定。state ∈ {PASS, FAIL, BLOCKED, MANUAL}"""

    def __init__(self, cid, title, state, detail, next_action=""):
        self.cid, self.title, self.state = cid, title, state
        self.detail, self.next_action = detail, next_action


class Gate:
    def __init__(self, gid, name, purpose, on_fail, checks):
        self.gid, self.name, self.purpose = gid, name, purpose
        self.on_fail, self.checks = on_fail, checks

    @property
    def state(self):
        """聚合规则：FAIL 优先，其次 BLOCKED，其次 MANUAL，全 PASS 才 PASS。

        ★ 为什么 BLOCKED 高于 MANUAL：MANUAL 是"上机时请人确认"，
          BLOCKED 是"连上机的机会都还没有"，后者更上游。
        ★ INFO 不参与聚合（纯诊断）。
        """
        states = [c.state for c in self.checks if c.state != INFO]
        for s in (FAIL, BLOCKED, MANUAL, PASS):
            if s in states:
                return s
        return PASS

    @property
    def blockers(self):
        return [c for c in self.checks if c.state == FAIL]


# ----------------------------------------------------------------------------
# 网络探测（唯一会碰外部世界的地方；--no-probe 可整体关闭）
# ----------------------------------------------------------------------------

def probe_tcp(host, port, timeout=3.0):
    """返回 (kind, detail)。kind ∈ OPEN / REFUSED / TIMEOUT / UNREACH / DNS

    ★ 铁律 90 的语义区分必须保住：
      REFUSED = 相机活着但服务没起（还有救）
      TIMEOUT = 整机离线（别重试，先去开机）
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return "OPEN", ""
    except ConnectionRefusedError as e:
        return "REFUSED", str(e) or "connection refused"
    except socket.timeout:
        return "TIMEOUT", f"{timeout:g}s 无响应"
    except socket.gaierror as e:
        return "DNS", str(e)
    except OSError as e:
        # Windows 的 WSAEHOSTUNREACH(10065) / WSAEHOSTDOWN / WSAENETUNREACH 都落这里
        winerr = getattr(e, "winerror", None)
        if e.errno == errno.ETIMEDOUT or winerr == 10060:
            return "TIMEOUT", "timeout"
        tail = f"errno={e.errno}" + (f" winerror={winerr}" if winerr else "")
        return "UNREACH", f"{e.strerror or e} ({tail})"


def g0_probe(host, enabled):
    """G0 的判定体，返回 (state, detail, raw)。raw 供后续门复用，避免重复探测。"""
    if not enabled:
        return BLOCKED, "已用 --no-probe 跳过网络探测", {}
    raw = {str(p): probe_tcp(host, p) for p in G0_PORT_HINTS}
    kind, msg = raw[str(G0_PORT)]
    if kind == "OPEN":
        return PASS, f"{host}:{G0_PORT} 可连", raw
    if kind == "REFUSED":
        return FAIL, f"{host}:{G0_PORT} ConnectionRefused（服务未起，相机本身可能活着）", raw
    if kind == "TIMEOUT":
        return FAIL, f"{host}:{G0_PORT} Timeout（整机离线）", raw
    return FAIL, f"{host}:{G0_PORT} 网络层不可达（{msg}）", raw


# ----------------------------------------------------------------------------
# U1 脚本包 lint —— 让 preflight 第 5/6/7 项变成自动可判
# ----------------------------------------------------------------------------

GATE_HDR = re.compile(r"^#\s*@gate\b(?P<kv>.*)$", re.M)
SEG_LINE = re.compile(r"^#\s*@seg\b(?P<kv>.*)$", re.M)
KV = re.compile(r"(\w+)=([^\s]+)")
RUN_LINE = re.compile(r"^RUN:\s*(?P<cmd>.+)$", re.M)
WAIT_LINE = re.compile(r"^WAIT:\s*(?P<sec>\d+)\s*$", re.M)


def parse_kv(s):
    return {k: v for k, v in KV.findall(s)}


def lint_pack(repo, dirrel, runbook_rel=None, allow_rw=False):
    """通用脚本包 lint（U1/U6/PW/LUT 共用）。
    返回 dict：{'exists', 'scripts', 'segs', 'max_regs', 'readonly', 'one_shot',
                  'lf_only', 'shebang', 'setsid_ok', 'waits', 'problems'}

    allow_rw=False（U1）：所有脚本必须声明 opens=rdonly；
    allow_rw=True （U6/PW/LUT）：接受 opens=rw，但必须标安全闸来源：
        gate=cmasafe|cmapick|both —— 走 CMA 的写类（表写入）
        gate=mcb                —— 走 MCB 白名单的写类（PW 直推）
    runbook_rel=None：产品工具包（无 runbook）；有则严格核对 setsid/WAIT。"""
    out = {"exists": repo.has(dirrel), "scripts": [], "segs": [], "max_regs": 0,
           "readonly": True, "one_shot": True, "lf_only": True, "shebang": True,
           "setsid_ok": True, "waits": [], "problems": []}
    if not out["exists"]:
        return out

    shs = sorted(f for f in os.listdir(repo.p(dirrel)) if f.endswith(".sh"))
    out["scripts"] = shs
    for f in shs:
        rel = os.path.join(dirrel, f)
        path = repo.p(rel)
        data = open(path, "rb").read()
        if b"\r\n" in data:
            out["lf_only"] = False
            out["problems"].append(f"{f}: 含 CRLF（铁律 99）")
        txt = data.decode("utf-8", "replace")
        if not txt.startswith("#!"):
            out["shebang"] = False
            out["problems"].append(f"{f}: 缺 shebang")

        hdr = GATE_HDR.search(txt)
        if not hdr:
            out["problems"].append(f"{f}: 缺 @gate 头注释（无法自证纪律）")
            continue
        meta = parse_kv(hdr.group("kv"))
        opens = meta.get("opens", "").lower()
        if opens in ("rdonly", "read-only", "ro"):
            pass
        elif allow_rw and opens == "rw":
            # U6/PW/LUT：写类脚本放行，但必须打安全闸来源标记
            if meta.get("gate", "").lower() not in ("cmasafe", "cmapick", "both", "mcb"):
                out["problems"].append(
                    f"{f}: opens=rw 但未标 gate=cmasafe|mcb（写类须内嵌安全闸）")
        else:
            out["readonly"] = False
            out["problems"].append(f"{f}: opens={meta.get('opens')} 不是只读")
        if meta.get("one_shot") not in ("1", "true", "yes"):
            out["one_shot"] = False
            out["problems"].append(f"{f}: one_shot != 1（一次只做一件事）")

        for m in SEG_LINE.finditer(txt):
            kv = parse_kv(m.group("kv"))
            try:
                nbytes = int(kv.get("bytes", "0"), 0)
            except ValueError:
                nbytes = -1
            if nbytes < 0:
                out["problems"].append(f"{f}: @seg bytes 解析失败 -> {m.group('kv').strip()}")
                continue
            regs = nbytes // 4
            out["segs"].append({"script": f, "name": kv.get("name", "?"),
                                "addr": kv.get("addr", "?"), "bytes": nbytes, "regs": regs})
            out["max_regs"] = max(out["max_regs"], regs)

    # runbook（可选）：每条 RUN 必须 setsid；除第一条外每条 RUN 前必须有一次 >=60s 的 WAIT
    if runbook_rel is None:
        pass          # 产品工具包（如 lutpipe）：无 runbook 属正常，不检查
    else:
        rb = repo.text(runbook_rel)
        if rb is not None:
            ops = re.findall(r"^(RUN|WAIT):.*$", rb, re.M)
            for ln in rb.splitlines():
                m = RUN_LINE.match(ln)
                if m and "setsid" not in m.group("cmd"):
                    out["setsid_ok"] = False
                    out["problems"].append(f"runbook: RUN 未用 /usr/bin/setsid -> {m.group('cmd')[:70]}")
            for m in WAIT_LINE.finditer(rb):
                out["waits"].append(int(m.group("sec")))
            if out["waits"] and min(out["waits"]) < 60:
                out["problems"].append("runbook: 存在 <60s 的段间等待（铁律 88）")
            if "RUN" in ops and "WAIT" not in ops:
                out["problems"].append("runbook: 有 RUN 但无 WAIT（段间必须让出）")
        else:
            out["setsid_ok"] = False
            out["problems"].append("runbook.txt 缺失（无法核对 setsid / 段间等待）")
    return out


def lint_u1(repo):
    return lint_pack(repo, U1_DIR, U1_RUNBOOK, allow_rw=False)


def lint_u6(repo):
    return lint_pack(repo, U6_DIR, U6_RUNBOOK, allow_rw=True)


def lint_pwsend(repo):
    return lint_pack(repo, PWSEND_DIR, PWSEND_RUNBOOK, allow_rw=True)


def lint_lutpipe(repo):
    # 产品工具包：无 runbook（上机路径由 U6 runbook 覆盖）
    return lint_pack(repo, LUTPIPE_DIR, None, allow_rw=True)


def run_check_scripts(repo):
    """调用既有 CI（铁律 99 的守门人），只看退出码与末行。"""
    tool = repo.p("test_server", "tools", "check_scripts.py")
    if not os.path.exists(tool):
        return None
    try:
        r = subprocess.run([sys.executable, tool, repo.root], capture_output=True, timeout=300)
    except Exception as e:
        return ("ERR", str(e))
    last = [l for l in r.stdout.decode("utf-8", "replace").splitlines() if l.strip()]
    return ("PASS" if r.returncode == 0 else "FAIL", last[-1] if last else "")


# ----------------------------------------------------------------------------
# 图像最小校验（不依赖 PIL：直接读 PNG IHDR）
# ----------------------------------------------------------------------------

def png_size(path):
    try:
        with open(path, "rb") as fh:
            head = fh.read(24)
    except OSError:
        return None
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    w, h = struct.unpack(">II", head[16:24])
    return w, h


# ----------------------------------------------------------------------------
# 门定义
# ----------------------------------------------------------------------------

def gate_g0(repo, ctx):
    state, detail, raw = g0_probe(ctx["host"], ctx["probe"])
    checks = [Check("G0-1", f"探测 {ctx['host']}:{G0_PORT}", state, detail,
                    "相机开机 + 与 PC 同网段；确认 telnetd/ftpd 已起（REFUSED 与 TIMEOUT 含义不同，铁律 90）")]
    if raw:
        for p in G0_PORT_HINTS[1:]:
            kind, msg = raw[str(p)]
            checks.append(Check(f"G0-{p}", f"旁证端口 {ctx['host']}:{p}（不参与判定）", INFO,
                                kind + (f"（{msg}）" if msg else ""), ""))
    ctx["g0_open"] = (state == PASS)
    return checks


def gate_g1(repo, ctx):
    c = []

    # --- 1. 端口（复用 G0 的结论，不重复探测）---
    state, detail, _ = g0_probe(ctx["host"], ctx["probe"])
    c.append(Check("G1-1", "21 端口可达", state, detail, "退，绝不盲发（铁律 90）"))

    # --- 2. EV_MOBILE.sh md5（本地三份 + 机上核对）---
    found, danger_hits, unknown = [], [], []
    for rel in EV_MOBILE_PATH_CANDIDATES:
        if not repo.has(rel):
            continue
        h = repo.md5(rel)
        if h == EV_MOBILE_DANGER:
            danger_hits.append(rel)
            found.append(f"{rel} = {h[:8]} DANGER")
        elif h in EV_MOBILE_SAFE:
            found.append(f"{rel} = {h[:8]} OK({EV_MOBILE_SAFE[h]})")
        else:
            unknown.append(f"{rel}={h[:8]}")
            found.append(f"{rel} = {h[:8]} 未知")
    if danger_hits:
        c.append(Check("G1-2", "EV_MOBILE.sh 非死循环版", FAIL,
                       "；".join(found) + f"  **{danger_hits[0]} 是社区'每 2s ip addr ls'死循环版**，"
                       "install.sh 会原样装上机",
                       f"改用安全版覆盖：cp scripts/nx-rc/EV_MOBILE.sh {danger_hits[0]}"
                       "（或 deploy/filmlab 版）；上机后仍须核对机上 md5 ∈ {2657352e…, 54a308b8…}"))
    elif unknown:
        c.append(Check("G1-2", "EV_MOBILE.sh 非死循环版", BLOCKED,
                       "；".join(found) + "  有未登记哈希，需人工确认", "人工比对后再上机"))
    else:
        c.append(Check("G1-2", "EV_MOBILE.sh 非死循环版", PASS,
                       "；".join(found) or "三份均不存在", "机上仍需核对 md5（铁律 105：别挂缺陷槽位）"))

    # --- 3/4. 必须由人给的判定 ---
    c.append(Check("G1-3", "上机前负载基线", MANUAL,
                   "需机上取心跳/uptime/ps 计数并落 SD 卡", "上机第一件事采集，作为'拖垮'的参照物（铁律 104）"))
    c.append(Check("G1-4", "telnet 一会话只发一条命令", MANUAL,
                   "纪律项，工具无法代签", "结果一律 FTP 拉，不信回显"))

    # --- 5/6/7. 从 U1 脚本包自证（不是生成时保证，是每次重新解析）---
    lint = ctx["lint"]
    if not lint["exists"]:
        c.append(Check("G1-5", "只读（O_RDONLY）", BLOCKED,
                       "U1 脚本包尚未生成", "python test_server/tools/gate_pack_u1.py"))
        c.append(Check("G1-6", f"单段 <={SEG_MAX_REGS} regs", BLOCKED,
                       "U1 脚本包尚未生成", "同上"))
        c.append(Check("G1-7", "telnet 起的进程用 setsid", BLOCKED,
                       "U1 脚本包尚未生成", "同上"))
    else:
        c.append(Check("G1-5", "只读（O_RDONLY）",
                       PASS if lint["readonly"] else FAIL,
                       f"{len(lint['scripts'])} 个脚本，只读声明={'一致' if lint['readonly'] else '不一致'}",
                       "写操作必须单列并写明回滚方法"))
        ok_seg = lint["max_regs"] <= SEG_MAX_REGS
        c.append(Check("G1-6", f"单段 <={SEG_MAX_REGS} regs",
                       PASS if ok_seg else FAIL,
                       f"{len(lint['segs'])} 段，最大 {lint['max_regs']} regs（{lint['max_regs']*4} B）",
                       "压死过相机 5 次；危险的是单次运行的循环总量（铁律 88）"))
        c.append(Check("G1-7", "telnet 起的进程用 setsid",
                       PASS if (lint["setsid_ok"] and lint["one_shot"]) else FAIL,
                       f"runbook RUN 全 setsid={lint['setsid_ok']}，one_shot={lint['one_shot']}",
                       "见 runbook.txt"))
        if lint["problems"]:
            c.append(Check("G1-7b", "U1 包 lint 附加项", FAIL,
                           "；".join(lint["problems"][:6]), "修 gate_pack_u1 后重新生成"))

    # --- 7c. 上机包 lint（U6/PW/LUT；写类子命令须内嵌安全闸）---
    packs = [("U6", ctx.get("lint_u6")), ("PW", ctx.get("lint_pwsend")),
             ("LUT", ctx.get("lint_lutpipe"))]
    parts, probs, all_ok, any_exists = [], [], True, False
    for tag, lp in packs:
        if lp is None:
            continue
        if not lp["exists"]:
            parts.append(tag + "=未生成")
            continue
        any_exists = True
        ok = lp["setsid_ok"] and lp["one_shot"] and not lp["problems"]
        all_ok = all_ok and ok
        parts.append("%s=%d脚本/%s" % (tag, len(lp["scripts"]), "OK" if ok else "FAIL"))
        probs += ["%s: %s" % (tag, x) for x in lp["problems"][:3]]
    if not any_exists:
        c.append(Check("G1-7c", "上机包 lint", MANUAL,
                       "U6/PW/LUT 包均未生成", "资产就绪后重新跑本状态板"))
    else:
        c.append(Check("G1-7c", "上机包 lint（U6/PW/LUT：setsid/CRLF/安全闸标）",
                       PASS if all_ok else FAIL,
                       "；".join(parts),
                       "；".join(probs[:5]) if probs else "写类内嵌安全闸（cmasafe/mcb）"))

    # --- 8. 脚本卫生 CI（铁律 99 的自动化）---
    res = run_check_scripts(repo)
    if res is None:
        c.append(Check("G1-8", "脚本 CRLF/语法/执行位 CI", BLOCKED, "check_scripts.py 不在位", ""))
    else:
        st, last = res
        c.append(Check("G1-8", "脚本 CRLF/语法/执行位 CI",
                       PASS if st == "PASS" else FAIL, last, "python test_server/tools/apply_ci_fixes.py"))
    return c


def gate_g2(repo, ctx):
    d = repo.json(EV_U1_MEM)
    if d is None:
        return [Check("G2-1", "U1 /dev/mem 四点对照结论", BLOCKED,
                      f"缺 {EV_U1_MEM}（需上机产出）",
                      "上机 U1 步骤 1-4；这是 U11 路线判定的唯一输入")]
    addrs = d.get("addresses") or {}
    need = ["0x810fd100", "0x81115200", "0x2082b000", "0x94000000"]
    missing = [a for a in need if a not in addrs]
    if missing:
        return [Check("G2-1", "四点对照完整性", BLOCKED,
                      f"缺 {', '.join(missing)}（铁律 119：'地址面无 X' 须附地址面完整性证明）",
                      "补齐四点再判")]
    c = [Check("G2-1", "四点对照完整性", PASS, "四点均有记录", "")]
    lut_readable = any(addrs[a].get("readable") for a in ("0x810fd100", "0x81115200"))
    if lut_readable:
        c.append(Check("G2a", "LUT 缓冲可读 -> 走读表差分", PASS,
                       "0x810fd100 / 0x81115200 至少一个可读",
                       "D1 降级为交叉验证；lutmod 补丁【永久弃用】"))
    else:
        c.append(Check("G2b", "LUT 缓冲不可读 -> 才评估 lutmod", PASS,
                       "两个 LUT 缓冲均不可读",
                       "评估 p7_full.lutmod.bin 前【必须重推目标地址】（CMA 窗口会变）"))
    return c


def gate_g3(repo, ctx):
    """G3 是"进门条件"：离线五页预渲染出图 + 每处文本都设了字体。
    ★ 注意：G3 判的是**能不能上机**，不是"上机成功了"。"""
    c = []
    seen = {}
    bad = []
    for rel in UI_PAGES:
        sz = png_size(repo.p(rel))
        if sz is None:
            bad.append(f"{os.path.basename(rel)} 缺失/非 PNG")
            continue
        if sz != (UI_W, UI_H):
            bad.append(f"{os.path.basename(rel)} 尺寸 {sz[0]}x{sz[1]} != {UI_W}x{UI_H}")
    for rel in UI_PAGES:
        h = repo.md5(rel)
        if h:
            seen.setdefault(h, []).append(os.path.basename(rel))
    dup = {h: v for h, v in seen.items() if len(v) > 1}
    if bad:
        c.append(Check("G3-1", "五页离线预渲染出图", FAIL, "；".join(bad), "重跑 ui_pages_render"))
    elif len(seen) != 5:
        c.append(Check("G3-1", "五页离线预渲染出图", FAIL,
                       f"只有 {len(seen)} 张互不相同的 PNG：{dup}", "五页必须内容各不相同"))
    else:
        c.append(Check("G3-1", "五页离线预渲染出图", PASS,
                       f"5 张 {UI_W}x{UI_H} PNG，md5 互不相同", ""))

    log = repo.text(UI_LOG)
    if log is None:
        c.append(Check("G3-2", "每处文本都设了字体", BLOCKED, f"缺 {UI_LOG}", "重跑渲染并保留日志"))
    else:
        m = re.search(r"total font_set calls\s*=\s*(\d+)", log)
        pages = re.findall(r"PAGE (\d+) -> .*ink=(\d+)", log)
        n_fs = int(m.group(1)) if m else 0
        zero_ink = [p for p, ink in pages if int(ink) == 0]
        if n_fs <= 0 or len(pages) != 5 or zero_ink:
            c.append(Check("G3-2", "每处文本都设了字体", FAIL,
                           f"font_set={n_fs}, PAGE 行={len(pages)}, 零墨页={zero_ink}",
                           "evas 真约束 = 必须调用一次 font_set（不设则几何 0x0 不画）"))
        else:
            c.append(Check("G3-2", "每处文本都设了字体", PASS,
                           f"font_set 共 {n_fs} 次，5 页 ink 全 >0（{', '.join(i for _, i in pages)}）", ""))

    t = repo.text(D7_REPORT)
    if t is None:
        c.append(Check("G3-3", "nxfilmui 同款序列实测 PASS", BLOCKED, f"缺 {D7_REPORT}", ""))
    else:
        ok = "PASS" in t and "font_set" in t
        c.append(Check("G3-3", "nxfilmui 同款序列实测 PASS",
                       PASS if ok else BLOCKED,
                       "报告含同款调用序列实测 PASS" if ok else "报告中未见到 PASS 记录",
                       "应用 nxfilmui v4 后再上机"))
    return c


def gate_g4(repo, ctx):
    """G4 = 允许改 p7。前置 = U4 通过 且 U5 回滚演练成功。
    ★ 先把'有没有本钱'查清：没有备份就不许开门，这条比 U4/U5 更优先。"""
    c = []
    assets = []
    if repo.has(ASSET_SLP):
        assets.append(f"官方 SLP {repo.size(ASSET_SLP)//(1<<20)}MB")
    if repo.has(ASSET_EMMCBAK):
        assets.append("emmcbak/ 已备份")
    missing_asset = []
    if not repo.has(ASSET_SLP):
        missing_asset.append(ASSET_SLP)
    if not repo.has(ASSET_EMMCBAK):
        missing_asset.append(ASSET_EMMCBAK)
    c.append(Check("G4-0", "不可再生资产在手", FAIL if missing_asset else PASS,
                   "；".join(assets) or "无", f"缺：{missing_asset} -> 没备份不许碰 p7"))

    q_ok, q_absent_ok, qmsg = True, True, []
    for rel, why in QUARANTINED:
        if repo.has(rel):
            qmsg.append(f"已隔离 {os.path.basename(rel)}")
        else:
            q_ok = False
            qmsg.append(f"未隔离 {rel}")
    for rel in MUST_BE_ABSENT:
        if repo.has(rel):
            q_absent_ok = False
            qmsg.append(f"**仍存在可刷形态** {rel}")
    c.append(Check("G4-0b", "危险样本已隔离", PASS if (q_ok and q_absent_ok) else FAIL,
                   "；".join(qmsg) or "无",
                   "改 0x200 破坏复位期 DACR 写入 => 不可刷，必须从可刷路径移走"))

    u4 = repo.json(EV_U4)
    if u4 is None:
        c.append(Check("G4-1", "U4 官方升级路径接受重打包 SLP", BLOCKED,
                       f"缺 {EV_U4}", "先做'等长、只改 1 字节、重算 JAMCRC'的最小实验"))
    else:
        ok = bool(u4.get("accepted")) and bool(u4.get("telnet_alive_after"))
        c.append(Check("G4-1", "U4 官方升级路径接受重打包 SLP", PASS if ok else FAIL,
                       f"accepted={u4.get('accepted')}, telnet_alive_after={u4.get('telnet_alive_after')}",
                       "被拒就去看三个拒点 [IMG-CRC32] / [IMG-MAGIC] / [PROJECT]"))

    u5 = repo.json(EV_U5)
    if u5 is None:
        c.append(Check("G4-2", "U5 单分区回滚演练", BLOCKED, f"缺 {EV_U5}",
                       "演练'改坏 -> 恢复'闭环至少一次"))
    else:
        n = int(u5.get("drills") or 0)
        ok = n >= 1 and bool(u5.get("ok"))
        c.append(Check("G4-2", "U5 单分区回滚演练", PASS if ok else FAIL,
                       f"drills={n}, ok={u5.get('ok')}", "★ boot0/boot1 绝不碰"))
    return c


def gate_g5(repo, ctx):
    """G5 = 固件级改动的生效判据。铁律 86：写不出验收判据不许开工。"""
    c = []
    ids = set()
    t = repo.text(EIQLIST)
    if t:
        ids = set(re.findall(r"eIQ_ID_[A-Za-z0-9_]+", t))
    c.append(Check("G5-1", f"静态判据 ID 全表 >={EIQ_MIN_IDS}", PASS if len(ids) >= EIQ_MIN_IDS else FAIL,
                   f"{EIQLIST} 命中 {len(ids)} 个唯一 eIQ_ID_*",
                   "这是'改了生效没有'的唯一客观判据（st cap iqr）"))

    dump = repo.text(EV_U1_IQR)
    if dump is None:
        c.append(Check("G5-2", "机上 iqr 值 dump", BLOCKED, f"缺 {EV_U1_IQR}",
                       "上机 U1 步骤 5；离线跑 st cap 会因 IPCC UDD 打不开而失败"))
    else:
        n = len(set(re.findall(r"eIQ_ID_[A-Za-z0-9_]+", dump)))
        c.append(Check("G5-2", "机上 iqr 值 dump", PASS if n >= EIQ_MIN_IDS else BLOCKED,
                       f"dump 含 {n} 个唯一 ID", "不足则确认是否被截断（铁律 94）"))

    mp = repo.text(EV_U1_MAP)
    c.append(Check("G5-3", "能区分'值变了'与'参数被消费'", PASS if mp else BLOCKED,
                   f"关联表 {'在位' if mp else '缺失'}：{EV_U1_MAP}",
                   "需要 iqr(184 ID) x epmc(两块 21x10) 的关联（目标矩阵 C14）；"
                   "★ 且必须记录写入瞬间的运行时槽号（U14）"))
    return c


def build_gates(repo, ctx):
    return [
        Gate("G0", "上机可达", "21 端口能连上", "退回离机轨（离机轨已清空，则可休整或做加固）",
             gate_g0(repo, ctx)),
        Gate("G1", "上机安全", "preflight 8 项全绿", "修完再上机；绝不在红门下开机身",
             gate_g1(repo, ctx)),
        Gate("G2", "U11 路线判定", "/dev/mem 四点对照有结论", "无（只读，等 U1 结果）",
             gate_g2(repo, ctx)),
        Gate("G3", "原生 UI 上机", "离线五页出图 + 每处文本设了字体", "回去改 UI",
             gate_g3(repo, ctx)),
        Gate("G4", "允许改 p7", "U4 通过 且 U5 回滚演练成功", "永远停在'用户态 + ISP 参数块'层",
             gate_g4(repo, ctx)),
        Gate("G5", "固件改动生效判据", "存在客观判据且能区分'值变了'与'被消费'", "不许改（铁律 86）",
             gate_g5(repo, ctx)),
    ]


# ----------------------------------------------------------------------------
# 能力放行矩阵 —— 门控的真正用户可见产物
# ----------------------------------------------------------------------------

CAPABILITIES = [
    ("L1  用户态脚本 / 胶片引擎 / 3D LUT 写入", (), "已实机验证，常态允许"),
    ("L2  原生 EFL UI 上机（nxfilmui）", ("G0", "G1", "G3"), "需人在机身判定'没拖垮'（铁律 104）"),
    ("路径 B  ISP 参数块写入（21 槽）", ("G0", "G1", "G5"), "生效判据是硬前置（铁律 86）"),
    ("U4  SLP 重打包无害实验", ("G0", "G1"), "D3 已完成；先做等长只改 1 字节的最小实验"),
    ("L4  改 p7 分区", ("G0", "G1", "G4"), "★ 唯一不可逆的一层"),
]


def capability_board(gates):
    by = {g.gid: g for g in gates}
    rows = []
    for name, need, note in CAPABILITIES:
        if not need:
            rows.append((name, PASS, "无门控", note))
            continue
        states = [by[g].state for g in need if g in by]
        if all(s == PASS for s in states):
            st = PASS
        elif FAIL in states:
            st = FAIL
        elif BLOCKED in states:
            st = BLOCKED
        else:
            st = MANUAL
        blocked_by = ",".join(g for g in need if g in by and by[g].state != PASS) or "-"
        rows.append((name, st, blocked_by, note))
    return rows


# ----------------------------------------------------------------------------
# 输出
# ----------------------------------------------------------------------------

def print_board(repo, host, gates, caps, probe_enabled):
    w = 78
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print("=" * w)
    print(f"NX-KS2 门控状态板   {ts}   相机 {host}"
          + ("" if probe_enabled else "   (--no-probe)"))
    print("=" * w)
    for g in gates:
        print(f"\n{g.gid}  {g.name}   {MARK[g.state]} {g.state}")
        print(f"    目的：{g.purpose}")
        for c in g.checks:
            print(f"      {MARK[c.state]} {c.cid}  {c.title}")
            if c.detail:
                print(f"             依据：{c.detail}")
            if c.next_action and c.state != PASS:
                print(f"             下一步：{c.next_action}")
        if g.state != PASS:
            print(f"    >> 不过怎么办：{g.on_fail}")

    print("\n" + "-" * w)
    print("能力放行矩阵")
    print("-" * w)
    for name, st, blocked_by, note in caps:
        print(f"  {MARK[st]} {name}")
        print(f"          卡在：{blocked_by}    {note}")

    n_fail = sum(1 for g in gates if g.state == FAIL)
    n_blk = sum(1 for g in gates if g.state == BLOCKED)
    print("\n" + "-" * w)
    allowed = [n for n, s, _, _ in caps if s == PASS]
    forbidden = [(n, b) for n, s, b, _ in caps if s != PASS]
    print(f"当前放行：{len(allowed)}/{len(caps)}")
    for n in allowed:
        print(f"   + {n}")
    for n, b in forbidden:
        print(f"   - {n}   （卡 {b}）")
    print(f"\n汇总：FAIL={n_fail}  BLOCKED={n_blk}  退出码={1 if n_fail else 0}")
    print("=" * w)


def print_u1_runbook(repo):
    rb = repo.text(U1_RUNBOOK)
    print("\n" + "=" * 78)
    if rb is None:
        print("U1 runbook 不存在：先 python test_server/tools/gate_pack_u1.py")
        print("=" * 78)
        return
    print(rb.rstrip())
    print("=" * 78)


def main():
    ap = argparse.ArgumentParser(description="NX-KS2 门控引擎（只读，不碰相机写路径）")
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--host", default=CAM_HOST_DEFAULT)
    ap.add_argument("--only", default="", help="只跑某些门，如 G0,G1")
    ap.add_argument("--no-probe", action="store_true", help="跳过网络探测")
    ap.add_argument("--u1", action="store_true", help="附打印 U1 上机 runbook")
    ap.add_argument("--json", nargs="?", const=os.path.join(EV_ROOT, "gate_status.json"),
                    default=None, help="落盘 JSON（默认 raw8/gates/gate_status.json）")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    repo = Repo(a.root)
    ctx = {"host": a.host, "probe": not a.no_probe, "lint": lint_u1(repo),
           "lint_u6": lint_u6(repo), "lint_pwsend": lint_pwsend(repo),
           "lint_lutpipe": lint_lutpipe(repo)}

    gates = build_gates(repo, ctx)
    if a.only:
        want = {s.strip().upper() for s in a.only.split(",") if s.strip()}
        gates = [g for g in gates if g.gid in want] or gates

    caps = capability_board(gates)

    if not a.quiet:
        print_board(repo, a.host, gates, caps, ctx["probe"])
        if a.u1:
            print_u1_runbook(repo)
    else:
        n_fail = sum(1 for g in gates if g.state == FAIL)
        print(f"FAIL={n_fail} " + " ".join(f"{g.gid}={g.state}" for g in gates))

    if a.json:
        out = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "host": a.host,
            "probe_enabled": ctx["probe"],
            "gates": [{"id": g.gid, "name": g.name, "state": g.state,
                       "purpose": g.purpose, "on_fail": g.on_fail,
                       "checks": [{"id": c.cid, "title": c.title, "state": c.state,
                                   "detail": c.detail, "next": c.next_action}
                                  for c in g.checks]} for g in gates],
            "capabilities": [{"name": n, "state": s, "blocked_by": b, "note": nt}
                             for n, s, b, nt in caps],
            "u1_lint": ctx["lint"],
            "u6_lint": ctx.get("lint_u6"),
            "pwsend_lint": ctx.get("lint_pwsend"),
            "lutpipe_lint": ctx.get("lint_lutpipe"),
        }
        p = repo.p(a.json)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)
        if not a.quiet:
            print(f"JSON -> {a.json}")

    return 1 if any(g.state == FAIL for g in gates) else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
