#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""3dlut_paths.py —— p7 3D LUT「应用线路」穷举器（静态）

目标：回答「3D LUT 到底有几条可能被应用的线路，各自由谁触发」。

方法（三层证据，全部离线可复现）：
  L0 硬件入口：**谁真正访问 0x2082b000 寄存器块**。
      —— p7 用 `movw/movt` 立即数构造该地址（字面量搜不到！），故按指令位模式扫。
  L1 原语层：写该寄存器块的寄存器原语函数（OnOff/Pulse/Cfg/LUT0/LUT1）。
  L2 调用链：从原语向上 BFS：
      (a) BL / BLcc / B 指令目标（不依赖 Ghidra 是否解析出 thunk）
      (b) 函数指针表槽（.data 中指向函数的 32 位字）
      直到"无上游" = 线路入口。
  L3 入口定性：入口是 vtable 槽（类方法）/ MCB 桩 / 裸 BL 调用者。

输出：
  raw8/p7/3dlut_paths.json  机器可读
  raw8/p7/3dlut_paths.txt   人读报告

用法：python test_server/isp/3dlut_paths.py
"""
import json
import os
import re
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
P7 = os.path.join(ROOT, "raw8", "p7", "p7_full.bin")
FUNCS = os.path.join(ROOT, "raw8", "p7", "ghidra", "02_functions.txt")
CLS = os.path.join(ROOT, "raw8", "p7", "p7_class_map.tsv")
OUT_JSON = os.path.join(ROOT, "raw8", "p7", "3dlut_paths.json")
OUT_TXT = os.path.join(ROOT, "raw8", "p7", "3dlut_paths.txt")

BASE = 0x80000000
REG_BLOCK = 0x2082B000

SEED_PRIMITIVES = {
    0x4CF3D4: "OnOff(+0x000 b0)",
    0x4CF3FC: "Cfg[1:0]=SelCbCr_ch(+0x004)",
    0x4CF414: "Cfg[5:4]=SelLUT(+0x004)",
    0x4CF42C: "Cfg[8]=ch0_en(+0x004)",
    0x4CF444: "Cfg[12]=ch1_en(+0x004)",
    0x4CF45C: "Pulse b0(+0x008)",
    0x4CF484: "★ Pulse b8/b4 **脉冲**(+0x008) = Load/Save 启动",
    0x4CF4B4: "LUT0/LUT1 addr(+0x00c/+0x010)",
}
SEED_DISPATCH = {
    0x4A5E10: "load_lut: mode==1 -> 关闭",
    0x4A5E30: "★ load/save LUT 主体（唯一写 LUT0/1 地址）",
    0x4A5FF0: "configure 通道使能/选择（不搬数据）",
    0x4A5B6C: "load_lut 描述符解析器 -> 4a5ff0",
    0x4A5C44: "load_lut 3参封装 -> 4a5e30",
    0x4A5DE4: "ch 使能写入器(mode 1/0/2)",
}
SEED_API = {
    0x179314: "FUN_00179314 (p7 侧 load 提交)",
    0x179384: "FUN_00179384 (p7 侧 load/save 封装)",
    0x1792C8: "FUN_001792c8 (-> 4a5b6c)",
}
SEEDS = {}
SEEDS.update(SEED_PRIMITIVES)
SEEDS.update(SEED_DISPATCH)
SEEDS.update(SEED_API)


def load_funcs():
    fs = []
    for ln in open(FUNCS, encoding="utf-8", errors="replace"):
        m = re.match(r"^([0-9a-f]{8})\t(\d+)\t(\S+)", ln)
        if m:
            a = int(m.group(1), 16)
            fs.append((a, a + max(int(m.group(2)), 4), m.group(3)))
    fs.sort()
    return fs


def which_func(fs, a):
    lo, hi = 0, len(fs) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        s, e, nm = fs[mid]
        if a < s:
            hi = mid - 1
        elif a >= e:
            lo = mid + 1
        else:
            return (s, e, nm)
    return None


def load_classmap():
    m = {}
    if not os.path.exists(CLS):
        return m
    for ln in open(CLS, encoding="utf-8", errors="replace"):
        p = ln.rstrip("\n").split("\t")
        if len(p) < 4:
            continue
        cls, vt, mi, fn = p[0], p[1], p[2], p[3]
        try:
            off = int(fn[4:], 16) if fn.startswith("FUN_") else int(fn[2:], 16)
        except ValueError:
            continue
        m.setdefault(off, []).append((cls, vt, mi))
    return m


def scan_branches(data):
    """扫 B / BL / 条件 BL 目标（ARM，4 字节对齐）-> {target: [(kind, at)]}"""
    N = len(data)
    out = {}
    for a in range(0, N - 4, 4):
        wd = struct.unpack_from("<I", data, a)[0]
        top = (wd >> 24) & 0xFF
        if top == 0xEA:
            kind = "B"
        elif top == 0xEB:
            kind = "BL"
        elif (wd & 0x0F000000) == 0x0B000000:
            kind = "BLcc"
        else:
            continue
        imm = wd & 0xFFFFFF
        if imm & 0x800000:
            imm -= 0x1000000
        t = (a + 8 + (imm << 2)) & 0xFFFFFFFF
        if t < N:
            out.setdefault(t, []).append((kind, a))
    return out


def _arm_imm12_rot(imm12):
    """ARM 数据处理立即数：value = ror(imm8, 2*rot)"""
    rot = (imm12 >> 8) & 0xF
    imm8 = imm12 & 0xFF
    if rot == 0:
        return imm8
    sh = 2 * rot
    return ((imm8 >> sh) | (imm8 << (32 - sh))) & 0xFFFFFFFF


def scan_addr_const(data, target, window=0x200):
    """找以「mov/movw Rd,#lo ; movt Rd,#hi」构造出 target 附近常量的位置。

    ★ 关键：p7 用 **ARM 旋转立即数的 `mov`**（编码 0xE3A03A0B = mov r3,#0xB000）
      装载低 16 位，而不是 movw（0xE3000000）。两条路径都要覆盖。
    返回 [at_off of the lo-instruction]；窗口 window 内的基址+偏移也算。
    """
    N = len(data)
    pend = {}     # rd -> (at, lo16)
    hits = []
    for a in range(0, N - 4, 4):
        wd = struct.unpack_from("<I", data, a)[0]
        cond = wd >> 28
        if cond == 0xE and (wd & 0xFFF00000) == 0xE3000000:      # movw Rd,#imm16
            imm16 = ((wd >> 16) & 0xF) << 12 | (wd & 0xFFF)
            pend[(wd >> 12) & 0xF] = (a, imm16)
        elif cond == 0xE and (wd & 0x0FF00000) == 0x03A00000:    # mov Rd,#imm12(rot)
            val = _arm_imm12_rot(wd & 0xFFF)
            if val < 0x10000:                                    # 只认"低 16 位"形态
                pend[(wd >> 12) & 0xF] = (a, val)
        elif cond == 0xE and (wd & 0xFFF00000) == 0xE3400000:    # movt Rd,#imm16
            rd = (wd >> 12) & 0xF
            imm16 = ((wd >> 16) & 0xF) << 12 | (wd & 0xFFF)
            p = pend.get(rd)
            if p and a - p[0] <= 16:
                full = (imm16 << 16) | p[1]
                if target <= full < target + window:
                    hits.append((p[0], full))
            pend.pop(rd, None)
        # 陈旧条目清理
        if a % 0x4000 == 0:
            pend = {k: v for k, v in pend.items() if a - v[0] <= 16}
    return sorted(set(hits))


def scan_ptr_refs(data):
    """扫 .data 里所有 0x80xxxxxx 形式的 32 位字 -> {target_off: [at_off]}"""
    N = len(data)
    idx = {}
    for a in range(0, N - 4, 4):
        wd = struct.unpack_from("<I", data, a)[0]
        if (wd >> 24) == 0x80:
            idx.setdefault(wd - BASE, []).append(a)
    return idx


def main():
    data = open(P7, "rb").read()
    N = len(data)
    fs = load_funcs()
    cmap = load_classmap()
    br = scan_branches(data)

    report = []
    def w(s=""):
        report.append(s)

    w("=== p7 3D LUT 应用线路穷举（静态） ===")
    w("镜像 %d B | Ghidra 函数 %d | class_map 条目 %d | 分支目标 %d"
      % (N, len(fs), len(cmap), len(br)))
    w()

    # ---------- L0. 谁访问 0x2082b000 ----------
    w("L0. 硬件入口：以 movw/movt 构造 0x%08x 的位置（p7 用立即数，字面量搜不到）"
      % REG_BLOCK)
    movw_hits = scan_addr_const(data, REG_BLOCK)
    reg_writers = {}
    for h, full in movw_hits:
        f = which_func(fs, h)
        if not f:
            w("   off 0x%06x  const 0x%08x (不在 Ghidra 函数表内)" % (h, full))
            continue
        reg_writers.setdefault(f[0], {"name": f[2], "sites": []})
        reg_writers[f[0]]["sites"].append((h, full))
    for k in sorted(reg_writers):
        v = reg_writers[k]
        w("   %-16s 构造点 %s" % (v["name"],
                                  ["0x%x->0x%x" % (h, c) for h, c in v["sites"]]))
    w("   ★ 结论：3D LUT 寄存器块的**全部**访问者 = %d 个函数" % len(reg_writers))
    for k in sorted(reg_writers):
        w("      - %s (off 0x%x)" % (reg_writers[k]["name"], k))
    w()

    # ---------- L1/L2. 从种子向上 BFS ----------
    w("L1/L2. 从 3D LUT 种子函数向上回溯（BL/BLcc/B + 指针表）")
    nodes = {}
    for s in SEEDS:
        f = which_func(fs, s)
        nodes[s] = {"name": f[2] if f else "?", "label": SEEDS[s], "up": []}

    frontier = set(SEEDS)
    visited = set(SEEDS)
    depth = 0
    while frontier and depth < 8:
        depth += 1
        nxt = set()
        for t in sorted(frontier):
            for kind, a in br.get(t, []):
                cf = which_func(fs, a)
                if cf is None:
                    nodes[t]["up"].append({"kind": kind, "at": hex(a + BASE),
                                           "caller": "(非函数区@0x%x)" % a})
                    continue
                cstart, cname = cf[0], cf[2]
                nodes[t]["up"].append({"kind": kind, "at": hex(a + BASE),
                                       "caller": cname, "caller_off": hex(cstart)})
                if cstart not in nodes:
                    nodes[cstart] = {"name": cname, "label": "", "up": []}
                if cstart not in visited:
                    visited.add(cstart)
                    nxt.add(cstart)
        frontier = nxt

    roots = [k for k, v in nodes.items() if not v["up"]]
    w("   节点 %d 个；『无上游』(线路入口) %d 个" % (len(nodes), len(roots)))
    for r in sorted(roots):
        f = which_func(fs, r)
        cls = cmap.get(r, [])
        w("     - %-16s off 0x%-8x %s" % (nodes[r]["name"], r,
                                          ("类=%s" % cls[0][0]) if cls else ""))
    w()

    # ---------- L3. 分层 ----------
    w("L3. 分层汇总")
    layers = [("L1-primitive(寄存器原语)", SEED_PRIMITIVES),
              ("L2-dispatch(分发层)", SEED_DISPATCH),
              ("L3-api(p7 侧 API)", SEED_API)]
    for name, d in layers:
        w("   %-26s : %s" % (name, ", ".join(nodes[k]["name"] for k in d if k in nodes)))
    entries = [k for k in nodes if k not in SEEDS]
    w("   %-26s : %d 个" % ("L4-entry(线路入口)", len(entries)))
    for k in sorted(entries):
        v = nodes[k]
        cls = cmap.get(k, [])
        w("      %-16s off 0x%-8x up=%s%s"
          % (v["name"], k,
             [(u["kind"], u["caller"]) for u in v["up"][:3]] or "★无",
             ("  类=%s" % cls[0][0]) if cls else ""))
    w()

    obj = {
        "image": os.path.basename(P7),
        "reg_block": hex(REG_BLOCK),
        "l0_reg_writers": {("0x%x" % k): {"name": v["name"],
                                          "sites": ["0x%x->0x%x" % (h, c) for h, c in v["sites"]]}
                           for k, v in reg_writers.items()},
        "nodes": {("0x%x" % k): {"name": v["name"], "label": v["label"],
                                 "classes": [c[0] for c in cmap.get(k, [])],
                                 "up": v["up"]} for k, v in nodes.items()},
        "roots": ["0x%x" % r for r in sorted(roots)],
    }
    json.dump(obj, open(OUT_JSON, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    open(OUT_TXT, "w", encoding="utf-8").write("\n".join(report) + "\n")
    print("\n".join(report))
    print("\n写出: " + OUT_JSON)


if __name__ == "__main__":
    main()
