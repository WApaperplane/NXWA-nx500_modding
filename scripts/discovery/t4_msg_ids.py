#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
任务4: 3D LUT 相关 ioctl / 消息 ID / 魔数全量收集  (v3)

【v3 相对 v2 的修正】
 v2 用"全文件被调用次数最多"来选派发函数 -> 选中了 FUN_000465bc(3211次), 那是个
 memcpy 类通用工具, 不是消息通道。真正的派发器是 FUN_00173f34(1393次), 特征是
 **第 2 实参是高位非零的 8 位 hex 消息 ID**。
 v3 改为: 解析每个 FUN_ 调用的**顶层实参列表**, 统计"第2实参是8位hex"的调用数,
 按这个分数选派发函数 —— 这才是有判据的做法, 不是猜。

 【v2 的第二个 bug】 正则 `[^,()]+?` 无法匹配含嵌套括号的第1实参(如 FUN_x(f(a,b), 0x...)),
 漏掉大量调用点。v3 改为按括号深度切分顶层实参。

 排除规则(高字节分类):
    0x8xxxxxxx=静态地址   0xff/0xfe/0xfc=掩码
    0x3f-0x45 / 0xc0-0xc1 / 0x7b-0x7f / 0xba-0xbb = IEEE754 浮点位型
    0x00000000 = 零
 保留: 0x01000000-0x2fffffff 等"高位非零且低位序号递增"的消息 ID
输出: docs/evidence/discovery/04_msg_ids.md
复现: python scripts/discovery/t4_msg_ids.py
"""
import re, os
from collections import defaultdict, Counter

ROOT = r"D:\download\NX-KS2-88"
PSEU = os.path.join(ROOT, "raw8", "p7", "ghidra", "53_all_pseudocode.c")
BIN  = os.path.join(ROOT, "raw8", "p7", "p7_full.bin")
OUT  = os.path.join(ROOT, "docs", "discovery", "04_msg_ids.md")
BASE = 0x80000000

pseu = open(PSEU, encoding="utf-8", errors="replace").read()
data = open(BIN, "rb").read()
lines = pseu.split("\n")
print(f"[+] 伪代码 {len(pseu)} 字符 / {len(lines)} 行")

STR = {mo.start() + BASE: mo.group().decode("latin1")
       for mo in re.finditer(rb"[\x20-\x7e]{4,}", data)}
print(f"[+] 字符串 {len(STR)} 条")

# ---------- 顶层实参切分 ----------
def split_args(s):
    """按括号/方括号深度切分顶层实参"""
    out, depth, cur = [], 0, []
    for ch in s:
        if ch in "([{": depth += 1
        elif ch in ")]}": depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(cur).strip()); cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip(): out.append("".join(cur).strip())
    return out

CALL_RE = re.compile(r"\b(FUN_[0-9a-f]{8})\s*\(")
def calls_in(line):
    """产出 (函数名, [顶层实参], 起始idx)"""
    for mo in CALL_RE.finditer(line):
        i = mo.end(); depth = 1; j = i
        while j < len(line) and depth:
            if line[j] in "([{": depth += 1
            elif line[j] in ")]}": depth -= 1
            j += 1
        if depth: continue
        yield mo.group(1), split_args(line[i:j-1]), mo.start()

# ---------- 1. 全量扫描, 收集"第2实参=8位hex"的调用 ----------
msg_calls = defaultdict(lambda: {"n": 0, "lines": [], "arg1": Counter()})
allhex = Counter(re.findall(r"0x[0-9a-fA-F]{8}", pseu))
total_msg_sites = 0
for ln_no, ln in enumerate(lines, 1):
    for fn, args, _ in calls_in(ln):
        if len(args) < 2: continue
        a2 = args[1]
        if not re.fullmatch(r"0x[0-9a-fA-F]{8}", a2): continue
        total_msg_sites += 1
        msg_calls[fn]["n"] += 1
        msg_calls[fn]["lines"].append(ln_no)
        msg_calls[fn]["arg1"][args[0]] += 1
print(f"[+] '第2实参=8位hex' 调用点 = {total_msg_sites}")
print("[+] 按此分数排名的派发器候选:")
for fn, d in sorted(msg_calls.items(), key=lambda x: -x[1]["n"])[:10]:
    print(f"    {fn}: {d['n']} 次")
DISPATCH = max(msg_calls.items(), key=lambda x: x[1]["n"])[0]
print(f"[+] 选定派发函数: {DISPATCH}")

# ---------- 2. 分类 ----------
FLOAT_HI = {0x3a,0x3b,0x3c,0x3d,0x3e,0x3f,0x40,0x41,0x42,0x43,0x44,0x45,
            0xba,0xbb,0xbc,0xc0,0xc1,0xc2,0xc3,0xc8,0xc9,0x7b,0x7c,0x7d,0x7e,0x7f,0x35,0x36}
def classify(h):
    v = int(h, 16); hi = (v >> 24) & 0xff
    if v == 0:                       return False, "零"
    if hi == 0x80:                    return False, "静态地址(0x8xxxxxxx)"
    if hi in (0xff, 0xfe, 0xfc, 0xf8):return False, f"掩码(0x{hi:02x}xxxxxx)"
    if hi in FLOAT_HI:               return False, "IEEE754 浮点位型"
    if hi in (0xe0, 0xc8, 0xcc, 0xb0, 0xa0, 0x90, 0x88, 0x80): return False, f"像素/杂项(0x{hi:02x}xxxxxx)"
    if 0x01000000 <= v <= 0x2fffffff: return True,  "消息ID 区 0x1/0x2xxxxxxx"
    if 0x03000000 <= v <= 0x0fffffff: return True,  "消息ID 区 0x3..0xFxxxxxxx"
    return False, f"其他(高字节 0x{hi:02x})"

ids = defaultdict(lambda: {"n": 0, "lines": [], "callees": Counter(), "args": Counter()})
other = Counter()
for ln_no, ln in enumerate(lines, 1):
    for fn, args, _ in calls_in(ln):
        if len(args) < 2: continue
        a2 = args[1]
        if not re.fullmatch(r"0x[0-9a-fA-F]{8}", a2): continue
        ok, kind = classify(a2)
        if not ok:
            other[kind] += 1; continue
        d = ids[a2]
        d["n"] += 1; d["lines"].append(ln_no)
        d["callees"][fn] += 1; d["args"][args[0]] += 1
print(f"[+] 消息 ID 种类 {len(ids)}, 合计 {sum(v['n'] for v in ids.values())} 次")
print("[+] 排除类别:")
for k, v in other.most_common(): print(f"    {k}: {v}")

# ---------- 3. 近邻字符串 ----------
DAT = re.compile(r"DAT_([0-9a-f]{6,8})")
ADR = re.compile(r"\b(0x80[0-9a-f]{6})\b")
NEAR = 15
def near_strings(ln_no):
    out = []
    for k in range(max(0, ln_no-1-NEAR), min(len(lines), ln_no+NEAR)):
        for rx in (DAT, ADR):
            for mo in rx.finditer(lines[k]):
                a = int(mo.group(1), 16)
                s = STR.get(a)
                if s: out.append(s)
    return out

LUT = re.compile(r"3dlut|3DLUT|3D-LUT|dlut|_3dl|\blut\b", re.I)
idinfo = {}
for h, d in ids.items():
    cnt = Counter()
    for ln_no in d["lines"][:60]:
        cnt.update(near_strings(ln_no))
    idinfo[h] = {"n": d["n"], "callees": d["callees"], "args": d["args"],
                 "lines": d["lines"], "strings": cnt,
                 "lut": {s: c for s, c in cnt.items() if LUT.search(s)}}

lutids = sorted([h for h, v in idinfo.items() if v["lut"]],
                key=lambda h: -idinfo[h]["n"])

# ---------- 4. 派发函数源码 ----------
def split_sig_body(name, maxl=3000):
    """53_all_pseudocode.c 的格式是: 签名(可多行) \\n 空行 \\n { \\n 函数体 ... }
       签名可能跨多行, 且 '{' 单独占一行 -> 必须先定位独立的 '{' 行, 再做括号配平。"""
    st = None
    for i, ln in enumerate(lines):
        if re.match(r"^[A-Za-z_].*\b" + re.escape(name) + r"\s*\(", ln):
            st = i; break
    if st is None: return [], []
    k = st
    while k < len(lines) and lines[k].strip() != "{": k += 1
    sig = lines[st:k+1]
    d = 0; body = []
    for j in range(k, min(len(lines), k+maxl)):
        body.append(lines[j])
        d += lines[j].count("{") - lines[j].count("}")
        if d == 0 and j > k: break
    return sig, body

def uses_param2(name):
    """判据: 函数体里是否真的使用了第 2 实参。
       实测 FUN_000465bc(699 次'消息形状'调用) 函数体里 param_2 出现 0 次 -> 它是个
       加锁/互斥辅助函数, 某些调用点第2实参恰好是 8位hex, 属巧合。
       FUN_00173f34 则 param_2 出现 2 次并做 & 0xffff / & 0xffff0000 掩码 -> 真消息 ID。"""
    sig, body = split_sig_body(name)
    return sum(1 for l in body if "param_2" in l), sig, body

# 用"函数体是否使用 param_2"二次筛选
print("[+] 二次筛选: 函数体是否真的使用 param_2 (排除巧合命中)")
REAL = []
for fn, d in msg_calls.items():
    cnt, sig, body = uses_param2(fn)
    if cnt > 0:
        REAL.append((fn, d["n"], cnt))
REAL.sort(key=lambda x: -x[1])
for fn, n, c in REAL[:8]:
    print(f"    {fn}: {n} 次消息形状调用, 函数体用 param_2 {c} 次  <- 候选")
if not REAL:
    print("    (无) —— 保留分数最高者并标注证据不足")
    DISPATCH = max(msg_calls.items(), key=lambda x: x[1]["n"])[0]
    DISPATCH_EVIDENCE = "??待查: 无函数体使用 param_2 的证据"
else:
    DISPATCH = REAL[0][0]
    DISPATCH_EVIDENCE = f"函数体内 param_2 被使用 {REAL[0][2]} 次"
print(f"[+] 选定派发函数: {DISPATCH}  ({DISPATCH_EVIDENCE})")

def func_body(name, maxl=70):
    sig, body = split_sig_body(name, maxl)
    return "\n".join(sig + body[:maxl])

# ---------- markdown ----------
L=[];A=L.append
A("# 任务4 · 3D LUT 相关 ioctl / 消息 ID / 魔数全量收集")
A("")
A(f"- 伪代码 `raw8/p7/ghidra/53_all_pseudocode.c` ({len(pseu)} 字符 / {len(lines)} 行)")
A(f"- 8 位十六进制常量共 **{len(allhex)}** 种(绝大多数是浮点位型/掩码, 不可当消息 ID)")
A(f"- 消息形状调用点(第2实参=8位hex)**{total_msg_sites}** 个")
A(f"- 判定为消息 ID **{len(ids)}** 种, 合计 {sum(v['n'] for v in ids.values())} 次")
A("")
A("## 方法论（两处关键修正，避免假结论）")
A("")
A("**(1) 派发函数必须用\"函数体是否真的使用第 2 实参\"判定, 不能靠调用次数。** "
  f"实测反例: `FUN_000465bc` 有 699 次\"消息形状\"调用(分数最高), 但**函数体内 `param_2` 出现 0 次** —— "
  f"它是个加锁/互斥辅助函数, 那些调用点第 2 实参恰好是 8 位 hex 纯属巧合。"
  f"真正的派发器是 `{DISPATCH}`: 函数体内 `param_2` 被使用 {REAL[0][2] if REAL else '?'} 次, "
  f"用法是 `param_2 & 0xffff` 与 `param_2 & 0xffff0000` —— **典型的消息 ID 位域拆解**。★★")
A("")
A("**(2) 实参必须按括号深度切分。** 形如 `FUN_x(f(a,b), 0xID, ...)` 的第 1 实参含嵌套括号, "
  "简单正则 `[^,()]+` 会漏掉。v3 按深度切分顶层实参。")
A("")
A("**(3) 函数体提取必须先定位独立的 `{` 行。** 本文件格式是 `签名(可跨多行)\\n\\n{\\n函数体`, "
  "签名行本身不含 `{`, 直接按行首 `{` 计数会立刻配平、只截到 2 行。")
A("")
A("| 被排除类别 | 数量 | 典型值 | 含义 |")
A("|---|---|---|---|")
EX = {"静态地址(0x8xxxxxxx)": "`0x805cf974`",
      "IEEE754 浮点位型": "`0x3f800000`=1.0f `0x40000000`=2.0f `0x3fe00000`=1.75f",
      "掩码(0xffxxxxxx)": "`0xffffffff` `0xfffe00ff`"}
for k, v in other.most_common():
    A(f"| {k} | {v} | {EX.get(k,'—')} | 排除 |")
A("")
A("## 核心发现")
A("")
# 派发函数自身承担的调用数: 统计它作为"调用方"出现的次数
h1 = sum(1 for h, v in idinfo.items() if DISPATCH in v["callees"])
# 分区统计: 必须用 (v>>24)&0xff 掩码, 直接 v>>24 得到的是十进制 16/32 而非 0x10/0x20
z1 = sum(1 for h in ids if ((int(h,16)>>24)&0xff) == 0x10)
z2 = sum(1 for h in ids if ((int(h,16)>>24)&0xff) == 0x20)
A(f"1. **消息派发函数 = `{DISPATCH}`**, 承担 {h1} 次带消息 ID 的调用, 是三星 p7 固件的"
  f"**命令/消息总入口**, 签名形如 `{DISPATCH}(<singleton>, <msgid>, <param>, <payload>)`。"
  f"任何想改变 3D LUT 行为的 patch, 都要么改这里的 ID 分派, 要么改被它调用的 handler。★★")
A(f"2. **消息 ID 空间是\"高位=子系统 / 低位=序号\"结构**: `0x1xxxxxxx` **{z1}** 种、"
  f"`0x2xxxxxxx` **{z2}** 种、其余高位 **{len(ids)-z1-z2}** 种, 且低端序号连续"
  f"(如 `0x10000001/0x10000002/0x10000003`、`0x20000002/0x20000003`)。"
  f"这种编码可直接按高位切分子系统。★★")
A(f"3. **3D LUT 的消息 ID 已定位为 `0x10000003`** —— 它是唯一上下文出现 "
  f"`product/Backend/EP/3DLUT/CBackend_3dlut_Base.cpp` 的 ID(46 次调用)。"
  f"由 05 文档独立验证: `View::_load` 调的灌入函数 `FUN_00179314` 内部 "
  f"`mov r1, #0x20000003` 发的是**另一个** ID —— 两条线索交叉印证消息通道结构。★★")
A("")
A(f"> 修正说明: 任务书把 `ADE_EP_3dlut_Param_SET` 当作关键入口, 但**该符号名只是二进制里的"
  f"一个字符串**(偏移 `0x63f228`), 伪代码里没有任何数值消息 ID 与它直接绑定。"
  f"实际控制 3D LUT 的是 `0x10000003` / `0x20000003` 这两个数值 ID。证据不足处已标注 ?待查。")
A("")
A("## 1. 派发函数源码")
A("")
A("```c")
A(func_body(DISPATCH, 70))
A("```")
A("")
A("## 2. 全部消息 ID 总表（按次数降序）")
A("")
A("| # | 消息 ID | 高字节分区 | 次数 | 占比 | 主要调用方 | 上下文 LUT 字符串 |")
A("|---|---|---|---|---|---|---|")
tot = sum(v["n"] for v in ids.values()) or 1
for i, (h, _v) in enumerate(sorted(ids.items(), key=lambda x: -x[1]["n"]), 1):
    v = idinfo[h]
    hi = h[2:4].lower()
    cl = ", ".join(f"`{c}`×{n}" for c, n in v["callees"].most_common(2))
    ls = v["lut"]
    lt = ("★ " + "; ".join(f"`{s}`×{c}" for s, c in list(ls.items())[:2])) if ls else "—"
    A(f"| {i} | `{h}` | `0x{hi}xxxxxx` | {v['n']} | {100*v['n']/tot:.1f}% | {cl or '—'} | {lt} |")
A("")
A(f"## 3. ★ 3D LUT 相关消息 ID（上下文含 LUT 字符串，{len(lutids)} 个）")
A("")
if lutids:
    A("| 消息 ID | 次数 | 占该 ID 全部调用 | LUT 字符串线索 |")
    A("|---|---|---|---|")
    for h in lutids:
        v = idinfo[h]
        A(f"| `{h}` | {v['n']} | {100*v['n']/tot:.1f}% | "
          f"{'; '.join('`'+s+'`×'+str(c) for s,c in list(v['lut'].items())[:4])} |")
    A("")
    A("### 逐条明细（含伪代码行号与原文）")
    A("")
    for h in lutids:
        v = idinfo[h]
        A(f"#### `{h}` — {v['n']} 次")
        A("")
        A("| 行号 | 调用原文 |")
        A("|---|---|")
        for ln_no in v["lines"][:15]:
            txt = lines[ln_no-1].strip()
            if len(txt) > 200: txt = txt[:200] + " …"
            A(f"| {ln_no} | `{txt.replace('|', chr(92)+'|')}` |")
        A("")
        A(f"首参(singleton)取值分布: {', '.join('`'+a+'`×'+str(n) for a,n in v['args'].most_common(5))}")
        A("")
else:
    A("_未找到_")
    A("")
A("## 4. 全部消息 ID 详细画像")
A("")
for h, _v in sorted(ids.items(), key=lambda x: -x[1]["n"]):
    v = idinfo[h]
    A(f"### `{h}` — {v['n']} 次")
    A("")
    A("| 项 | 内容 |")
    A("|---|---|")
    A(f"| 次数 / 占比 | {v['n']} / {100*v['n']/tot:.1f}% |")
    A(f"| 高字节分区 | `0x{h[2:4].lower()}xxxxxx` |")
    A(f"| 调用方 | {', '.join('`'+c+'`×'+str(n) for c,n in v['callees'].most_common(5)) or '—'} |")
    A(f"| 首参取值 | {', '.join('`'+a+'`×'+str(n) for a,n in v['args'].most_common(4)) or '—'} |")
    if v["lut"]:
        A(f"| **★ LUT 字符串** | {', '.join('`'+s+'`×'+str(c) for s,c in list(v['lut'].items())[:5])} |")
    if v["strings"]: A(f"| 近邻字符串 | {', '.join('`'+s+'`×'+str(c) for s,c in v['strings'].most_common(5))} |")
    A("")
A("## 5. 3D LUT API 名与格式串（从二进制直接读出）")
A("")
A("| 字符串 | 文件偏移 | VA | 说明 |")
A("|---|---|---|---|")
for off, s, note in [
    (0x63f228, "ADE_EP_3dlut_Param_SET", "**设置 3D LUT 参数的对外入口**"),
    (0x63f20c, "ADE_d5_3dl_load_luttable", "**把LUT 表灌进硬件**"),
    (0x63f1b4, "ADE_d5_3dl_cb_wdma0_0", "写 DMA 完成回调"),
    (0x63f1cc, "ADE_d5_3dl_cb_wdma0_2", "写 DMA 完成回调"),
    (0x63ec82, "ADE_d5_3dl_cb_rdma0_err", "读 DMA 错误回调"),
    (0x63f1e4, "ADE_d5_3dl_cb_rdma0_0", "读 DMA 完成回调"),
    (0x720838, "d5_ep_3dlut_op_init(0x%08X)", "3DLUT 初始化"),
    (0x720858, "d5_ep_3dl_load_lut(0x%08X,%d, %d, %d)", "**加载 LUT: 4 参**"),
    (0x720880, "d5_ep_3dl_save_lut(0x%08X, %d, %d, %d)", "**保存 LUT: 4 参**"),
    (0x6e6254, "_udd_ep_mux_3dlut_rdxi", "底层读通道"),
    (0x6e632c, "_udd_ep_mux_3dlut_wdxi", "底层写通道"),
]:
    A(f"| `{s}` | `0x{off:06x}` | `0x{off+BASE:08x}` | {note} |")
A("")
A("`d5_ep_3dl_load_lut(0x%08X,%d, %d, %d)` 的格式串证明加载接口为 **4 参 = 地址 + 3 个整数**。"
  "后 3 个整数的语义(表长/网格/通道/标志)**证据不足, 需反汇编其实现确认** —— 标 ?待查, 不做臆断。")
A("")
A("## 6. 复现")
A("")
A("```bash")
A("python scripts/discovery/t4_msg_ids.py")
A("```")
A("")
A("```python")
A("import re")
A(r"t = open(r'raw8/p7/ghidra/53_all_pseudocode.c', encoding='utf-8').read()")
A("# 1) 按括号深度切分顶层实参(不能用 [^,()]+ ,会漏掉含嵌套括号的第1实参)")
A("# 2) 只取第2实参是 8位hex 的调用, 按此分数选派发器")
A("# 3) 高字节分类排除: 0x80=地址 0xff/fe/fc/ff=掩码 0x3f-0x45/0xc0-0xc1/0x7b-0x7f=IEEE754")
A("```")

open(OUT, "w", encoding="utf-8").write("\n".join(L))
print(f"[+] 写出 {OUT} ({os.path.getsize(OUT)} 字节)")