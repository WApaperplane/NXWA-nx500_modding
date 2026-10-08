#!/usr/bin/env python3
"""p7 · 调用图 + 标签传播  (NX-KS2 / U01 扩展 II)

由来
----
U01（模块地图）给 3786 个函数打上硬证据标签（函数引用的字符串落在哪个 __FILE__ 段）；
RTTI 三跳（p7_class_map.py）再补 1198 个（其中 757 个是新的）⇒ 硬证据合计 4543/16466 = 27.6%。
剩下 1.2 万个函数"不引用任何 B 区日志串、也不在任何 vtable 里"。

本工具用**调用图传播**给它们估计归属。★★ 纪律：**这是推断，不是硬证据**，
必须与硬证据分开统计、分开呈现（铁律 94：截断/不完整的数据不得支撑结论；
铁律 118：对照失败即不得出结论）。

方法
----
① 从 53_all_pseudocode.c 的函数头 `// ==== NAME @ 0xADDR size=N ====` 切函数体
② 正则取体内所有 `FUN_xxxxxxxx(` ⇒ 调用边（有向）
③ 标签来源：p7_code_map.tsv（模块）/ p7_class_map.txt（类）
④ 迭代传播：节点的标签 = 其**已标注邻居**的加权多数（入边权重 1、出边权重 0.5），
   仅当(胜出占比 ≥ 0.6 且 支持邻居数 ≥ 2) 才采纳
⑤ 输出三种口径，绝不混为一谈：
      hard   = U01 ∪ RTTI
      inferred = 传播新增（附支持度）
      unknown  = 仍无标签

用法  python p7_callgraph.py
"""
from __future__ import annotations

import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
P7 = os.path.join(REPO, "raw8", "p7")
PS = os.path.join(P7, "ghidra", "53_all_pseudocode.c")
TSV = os.path.join(P7, "p7_code_map.tsv")
CLS = os.path.join(P7, "p7_class_map.txt")
OUT = os.path.join(P7, "p7_callgraph.txt")

HDR = re.compile(r"^// ==== (\S+) @ (0x[0-9a-f]+) size=(\d+) ====")
CALL = re.compile(r"\bFUN_[0-9a-f]{8}\s*\(")
NAME = re.compile(r"\bFUN_[0-9a-f]{8}\b")


def parse_graph():
    """-> callees: dict[name] = Counter[name], callers: dict[name] = Counter[name], sizes"""
    callees = collections.defaultdict(collections.Counter)
    callers = collections.defaultdict(collections.Counter)
    sizes = {}
    cur = None
    with open(PS, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            m = HDR.match(ln)
            if m:
                cur = m.group(1)
                sizes[cur] = int(m.group(3))
                callees.setdefault(cur, collections.Counter())
                continue
            if cur and "(" in ln and "FUN_" in ln:
                for tgt in NAME.findall(ln):
                    if tgt != cur:
                        callees[cur][tgt] += 1
                        callers[tgt][cur] += 1
    return callees, callers, sizes


def load_labels():
    labels = {}
    if os.path.exists(TSV):
        with open(TSV, encoding="utf-8", errors="replace") as fh:
            next(fh, None)
            for ln in fh:
                p = ln.rstrip("\r\n").split("\t")
                if len(p) >= 2 and p[0]:
                    labels[p[0]] = ("mod:" + p[1], 1.0)
    hard_mod = len(labels)
    cls = 0
    ctsv = os.path.join(P7, "p7_class_map.tsv")
    if os.path.exists(ctsv):                      # ★ 优先全量 TSV
        with open(ctsv, encoding="utf-8", errors="replace") as fh:
            next(fh, None)
            for ln in fh:
                p = ln.rstrip("\r\n").split("\t")
                if len(p) >= 4 and p[0] and p[3] not in labels:
                    labels[p[3]] = ("cls:" + p[0], 1.0)
                    cls += 1
    elif os.path.exists(CLS):                     # 退化：txt 明细只有 top 60 类
        cur = None
        for ln in open(CLS, encoding="utf-8", errors="replace"):
            m = re.match(r"^### (.+?)\s+\(串 @ ", ln)
            if m:
                cur = m.group(1)
                continue
            m2 = re.match(r"^\s+\[\s*\d+\]\s+(FUN_[0-9a-f]{8})", ln)
            if m2 and cur and m2.group(1) not in labels:
                labels[m2.group(1)] = ("cls:" + cur, 1.0)
                cls += 1
    return labels, hard_mod, cls


def main():
    callees, callers, sizes = parse_graph()
    nodes = set(callees) | set(callers)
    edges = sum(len(v) for v in callees.values())
    print(f"functions(nodes)={len(nodes)}  call-edges={edges}")

    labels, hard_mod, hard_cls = load_labels()
    hard = {k: v for k, v in labels.items() if k in nodes}
    print(f"hard labels: module={hard_mod}  class={hard_cls}  in-graph={len(hard)}")

    inferred = {}
    rounds = 0
    for it in range(15):
        new = {}
        for f in nodes:
            if f in hard or f in inferred:
                continue
            votes = collections.Counter()
            support = collections.Counter()
            for c, w in callers.get(f, {}).items():          # 谁调用我
                src = hard.get(c) or inferred.get(c)
                if src:
                    votes[src[0]] += 1.0 * w
                    support[src[0]] += 1
            for c, w in callees.get(f, {}).items():          # 我调用谁
                src = hard.get(c) or inferred.get(c)
                if src:
                    votes[src[0]] += 0.5 * w
                    support[src[0]] += 1
            tot = sum(votes.values())
            if not tot:
                continue
            best, sc = votes.most_common(1)[0]
            if sc / tot >= 0.6 and support[best] >= 2:
                new[f] = (best, round(sc / tot, 3), support[best])
        if not new:
            break
        inferred.update(new)
        rounds = it + 1
        print(f"  round {rounds}: +{len(new)} inferred  (total inferred {len(inferred)})")

    all_lab = len(set(hard) | set(inferred))
    total = len(nodes)
    print(f"\nhard={len(hard)}  inferred={len(inferred)}  combined={all_lab}/{total} "
          f"({100.0*all_lab/total:.2f}%)  still-unknown={total-all_lab}")

    lines = []
    lines.append("=" * 96)
    lines.append("p7 · 调用图 + 标签传播  (NX-KS2 / U01 扩展 II)")
    lines.append("=" * 96)
    lines.append(f"函数节点            : {total}")
    lines.append(f"调用边              : {edges}")
    lines.append(f"硬证据标签（模块）  : {hard_mod}")
    lines.append(f"硬证据标签（RTTI）  : {hard_cls}")
    lines.append(f"★★ 硬证据合计       : {len(hard)} / {total} ({100.0*len(hard)/total:.2f}%)")
    lines.append(f"→ 传播新增（推断）  : {len(inferred)}   （{rounds} 轮收敛）")
    lines.append(f"★ 硬 + 推断         : {all_lab} / {total} ({100.0*all_lab/total:.2f}%)")
    lines.append(f"仍未知              : {total-all_lab}")
    lines.append("")
    lines.append("★★ 纪律：**上面'硬证据'与'推断'是两种东西，不得混用**。")
    lines.append("   推断项的采纳门槛：加权票占比 ≥ 0.6 且 支持邻居 ≥ 2；每条附支持度与邻居数。")
    lines.append("   硬证据项可用于下结论；推断项只能用于**缩小搜索范围**。")
    lines.append("")
    lines.append("-" * 96)
    lines.append("## 推断新增按标签聚合（top 60）")
    lines.append("-" * 96)
    agg = collections.Counter(v[0] for v in inferred.values())
    lines.append(f"{'函数数':>6}  标签")
    for lab, c in agg.most_common(60):
        lines.append(f"{c:>6}  {lab}")
    lines.append("")
    lines.append("-" * 96)
    lines.append("## 推断明细（全部，函数 / 推断标签 / 胜出占比 / 支持邻居数）")
    lines.append("-" * 96)
    for f in sorted(inferred):
        lab, conf, sup = inferred[f]
        lines.append(f"  {f:<22} {lab:<52} conf={conf:<5} support={sup}")

    lines.append("")
    lines.append("-" * 96)
    lines.append("## 图结构速览")
    lines.append("-" * 96)
    ind = sorted(((len(callers.get(f, {})), f) for f in nodes), reverse=True)[:25]
    lines.append("入度最高（被调用最多，≈ 公共设施）：")
    for d, f in ind:
        lines.append(f"   indeg={d:<5} {f:<22} {hard.get(f, inferred.get(f, ('?',)))[0]}")
    lines.append("")
    outd = sorted(((len(callees.get(f, {})), f) for f in nodes), reverse=True)[:25]
    lines.append("出度最高（调用最多，≈ 调度/分发）：")
    for d, f in outd:
        lines.append(f"   outdeg={d:<5} {f:<22} {hard.get(f, inferred.get(f, ('?',)))[0]}")
    lines.append("")
    lines.append("孤立节点（无入无出，多为 thunk/桩）：")
    iso = [f for f in nodes if not callers.get(f) and not callees.get(f)]
    lines.append(f"   共 {len(iso)} 个（占 {100.0*len(iso)/total:.1f}%）")

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    sys.exit(main())
