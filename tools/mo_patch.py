#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mo_patch.py — GNU MO 文件解析 / 追加式替换 / 离线验证（NXWA 项目工具）

用途：安全替换 .mo（gettext 编译目录）中的 msgstr，并给出可复核的证据链。
场景：NXWA 相机端 di-camera-app.mo 文案替换（M2 配方名显示，2026-10-16 起）。

工艺：追加式替换（append-only rewrite）——比"等长替换"更保守：
  1) 新 msgstr 写入文件尾「追加区」（UTF-8，NUL 结尾）；
  2) 仅改写 translations 表对应条目的 (length, offset) 8 字节；
  3) msgid 表 / hash 表 / 字符串排序 / 原字符串存储区 / 其余全部字节
     —— 100% 原样保留（旧 msgstr 字节留作不引用数据，不覆盖、不删除）。
  ⇒ 变长安全；差异面可证明 = 「8B×N 表项 + 尾部追加区」，零附带差异。

子命令：
  info    <mo> [--grep PAT]           列文件结构 + 词条（可过滤）
  get     <mo> <msgid>                查一条 msgstr
  set     <src.mo> <out.mo> (--kv ID=VAL ... | --map map.json)
                                      [--expect-src-md5 MD5] [--manifest out.json]
  verify  <orig.mo> <new.mo> [--expect map.json] [--pygettext]
                                      自写解析器逐条对比 + 可选 Python gettext 交叉验证
  diff    <orig.mo> <new.mo>          字节级差异概览（应仅见表项 + 追尾）

版本：v1 · 2026-10-16 · 离线编写与验证（未见真机加载；见 M2_RECIPE_NAME_DESIGN 文档）
"""

import argparse
import hashlib
import io
import json
import struct
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TOOL_VERSION = "mo_patch.py v1 · 2026-10-16"


class MoError(Exception):
    pass


class MOFile:
    """最小 GNU MO 解析器（LE/BE；不变更内存内容，只读字段 + 切串）"""

    def __init__(self, path_or_data):
        if isinstance(path_or_data, (bytes, bytearray)):
            self.data = bytes(path_or_data)
            self.path = None
        else:
            self.path = path_or_data
            with open(path_or_data, "rb") as f:
                self.data = f.read()
        self._parse()

    def _parse(self):
        d = self.data
        if len(d) < 28:
            raise MoError("file too small to be a MO file")
        m_le = struct.unpack("<I", d[:4])[0]
        if m_le == 0x950412DE:
            self.fmt = "<"
        elif m_le == 0xDE120495:
            self.fmt = ">"
        else:
            raise MoError("bad MO magic: %#x" % m_le)
        (self.rev, self.n, self.orig_off, self.trans_off,
         self.hash_size, self.hash_off) = struct.unpack(self.fmt + "6I", d[4:28])
        end_orig_tab = self.orig_off + 8 * self.n
        end_trans_tab = self.trans_off + 8 * self.n
        if end_orig_tab > len(d) or end_trans_tab > len(d):
            raise MoError("table offset out of range (corrupt file?)")
        self._idx = None

    # ---- entry access ----
    def _desc(self, table_off, i):
        l, o = struct.unpack(self.fmt + "2I", self.data[table_off + 8 * i:
                                                        table_off + 8 * i + 8])
        if o + l > len(self.data):
            raise MoError("string [%d] out of range" % i)
        return l, o

    def msgid(self, i):
        l, o = self._desc(self.orig_off, i)
        return self.data[o:o + l]

    def msgstr(self, i):
        l, o = self._desc(self.trans_off, i)
        return self.data[o:o + l]

    def find(self, msgid):
        if self._idx is None:
            self._idx = {self.msgid(i): i for i in range(self.n)}
        b = msgid.encode("utf-8") if isinstance(msgid, str) else msgid
        return self._idx.get(b)

    @property
    def md5(self):
        return hashlib.md5(self.data).hexdigest()

    def byte_order_warning(self):
        # 追加式替换对 BE 同样有效；仅提示
        return self.fmt == ">"


# ---------------------------------------------------------------- commands

def cmd_info(args):
    mo = MOFile(args.mo)
    print("== MO info ==")
    print(f"  path        : {args.mo}")
    print(f"  size        : {len(mo.data)} bytes  md5={mo.md5}")
    print(f"  byte order  : {'BE' if mo.fmt == '>' else 'LE'}   revision={mo.rev}")
    print(f"  nstrings    : {mo.n}")
    print(f"  orig_tab    : {mo.orig_off:#x} .. {mo.orig_off + 8 * mo.n:#x}")
    print(f"  trans_tab   : {mo.trans_off:#x} .. {mo.trans_off + 8 * mo.n:#x}")
    print(f"  hash        : size={mo.hash_size} off={mo.hash_off:#x}")
    # 字符串区边界（用于确认追尾写入安全）
    max_end = 0
    for i in range(mo.n):
        for tb in (mo.orig_off, mo.trans_off):
            l, o = mo._desc(tb, i)
            max_end = max(max_end, o + l)
    print(f"  string area : max end {max_end:#x}  file {len(mo.data):#x}  tail_pad={len(mo.data) - max_end}B")
    if args.grep:
        pat = args.grep.encode("utf-8")
        hits = 0
        for i in range(mo.n):
            mid = mo.msgid(i)
            if pat in mid:
                st = mo.msgstr(i)
                print(f"  [{i:5d}] {mid.decode('utf-8', 'replace')}")
                print(f"          -> {st.decode('utf-8', 'replace')!r}")
                hits += 1
        print(f"  grep '{args.grep}': {hits} hit(s)")


def cmd_get(args):
    mo = MOFile(args.mo)
    i = mo.find(args.msgid)
    if i is None:
        print("NOT FOUND", file=sys.stderr)
        return 3
    print(mo.msgstr(i).decode("utf-8", "replace"))
    return 0


def _load_mapping(args):
    mapping = {}
    if args.map:
        with open(args.map, "r", encoding="utf-8") as f:
            mapping.update(json.load(f))
    for kv in (args.kv or []):
        k, sep, v = kv.partition("=")
        if not sep:
            raise MoError("bad --kv (need MSGID=VALUE): %r" % kv)
        mapping[k] = v
    if not mapping:
        raise MoError("no replacements given (use --kv or --map)")
    return mapping


def _apply_replacements(src_data, mapping):
    """核心：追加式替换。返回 (new_bytes, changes)"""
    mo = MOFile(src_data)
    new_data = bytearray(mo.data)
    changes = []
    for msgid, value in mapping.items():
        i = mo.find(msgid)
        if i is None:
            raise MoError("msgid not found: %s" % msgid)
        vb = value.encode("utf-8")
        if b"\x00" in vb:
            raise MoError("value must not contain NUL byte: %s" % msgid)
        old_b = mo.msgstr(i)
        old_len, old_off = mo._desc(mo.trans_off, i)
        new_off = len(new_data)          # 追加区起点（写入前取长度）
        new_data += vb + b"\x00"
        struct.pack_into(mo.fmt + "2I", new_data,
                         mo.trans_off + 8 * i, len(vb), new_off)
        changes.append({
            "msgid": msgid,
            "old": old_b.decode("utf-8", "replace"),
            "new": value,
            "old_len": old_len, "old_off": old_off,
            "new_len": len(vb), "new_off": new_off,
            "warn_truncation_risk": len(vb) > 24,
        })
    return bytes(new_data), changes


def cmd_set(args):
    with open(args.src, "rb") as f:
        src_data = f.read()
    src_md5 = hashlib.md5(src_data).hexdigest()
    if args.expect_src_md5 and src_md5 != args.expect_src_md5:
        raise MoError("src md5 mismatch: %s != %s" % (src_md5, args.expect_src_md5))
    mapping = _load_mapping(args)
    new_data, changes = _apply_replacements(src_data, mapping)
    with open(args.out, "wb") as f:
        f.write(new_data)
    new_md5 = hashlib.md5(new_data).hexdigest()
    print("== set done ==")
    print(f"  src : {args.src}  ({len(src_data)}B, md5 {src_md5})")
    print(f"  out : {args.out}  ({len(new_data)}B, md5 {new_md5})")
    for c in changes:
        tag = "  [warn: >24B, may truncate in UI]" if c["warn_truncation_risk"] else ""
        print(f"  * {c['msgid']}: {c['old']!r} -> {c['new']!r}  "
              f"(len {c['old_len']}->{c['new_len']}, off {c['old_off']:#x}->{c['new_off']:#x}){tag}")

    # 立即自动验证（自写解析器）
    issues = _verify(src_data, new_data, {k: v for k, v in mapping.items()})
    if issues:
        print("!! self-verify FAILED:")
        for x in issues:
            print("   -", x)
        return 2
    print("  self-verify: PASS (逐条对比，除目标外全同)")

    if args.manifest:
        man = {
            "tool": TOOL_VERSION,
            "src": {"path": args.src, "size": len(src_data), "md5": src_md5},
            "out": {"path": args.out, "size": len(new_data), "md5": new_md5},
            "changes": changes,
            "verify": {"self_parser": "PASS"},
        }
        with open(args.manifest, "w", encoding="utf-8") as f:
            json.dump(man, f, ensure_ascii=False, indent=2)
        print(f"  manifest -> {args.manifest}")
    return 0


def _verify(src_data, new_data, expect):
    """expect: {msgid: expected_value}（str→str）。返回 issues 列表"""
    issues = []
    a, b = MOFile(src_data), MOFile(new_data)
    if a.n != b.n:
        issues.append("nstrings differ: %d vs %d" % (a.n, b.n))
        return issues
    exp_b = {k.encode("utf-8"): v.encode("utf-8") for k, v in expect.items()}
    seen = set()
    for i in range(a.n):
        mid_a, mid_b = a.msgid(i), b.msgid(i)
        if mid_a != mid_b:
            issues.append("[%d] msgid differs: %r vs %r" % (i, mid_a, mid_b))
            continue
        sa, sb = a.msgstr(i), b.msgstr(i)
        if mid_a in exp_b:
            seen.add(mid_a)
            if sb != exp_b[mid_a]:
                issues.append("[%d] %s: new=%r expected=%r"
                              % (i, mid_a.decode("utf-8", "replace"),
                                 sb.decode("utf-8", "replace"), exp_b[mid_a].decode("utf-8", "replace")))
        else:
            if sa != sb:
                issues.append("[%d] %s: msgstr changed unexpectedly (%r -> %r)"
                              % (i, mid_a.decode("utf-8", "replace"),
                                 sa.decode("utf-8", "replace"), sb.decode("utf-8", "replace")))
    for mid in exp_b:
        if mid not in seen:
            issues.append("expected msgid missing in files: %s" % mid.decode("utf-8", "replace"))
    return issues


def _glibc_hash_string(s: bytes) -> int:
    """GNU hashpjw（intl/hash-string.h 32 位参照实现）"""
    hval = 0
    for c in s:
        hval = (hval << 4) & 0xFFFFFFFF
        hval = (hval + c) & 0xFFFFFFFF
        g = hval & (0xF << 28)
        if g:
            hval ^= (g >> 24) & 0xFFFFFFFF
            hval ^= g
    return hval


def _load_hash_tab(mo):
    if mo.hash_size == 0:
        return None
    return list(struct.unpack(mo.fmt + f"{mo.hash_size}I",
                              mo.data[mo.hash_off:mo.hash_off + 4 * mo.hash_size]))


def _hash_lookup(mo, hash_tab, msgid):
    """glibc _nl_find_msg hash 路径：h%size 起线性探测至空槽。返回 (idx, steps) 或 (None, steps)"""
    hs = mo.hash_size
    h = _glibc_hash_string(msgid) % hs
    j = h
    steps = 0
    while steps <= hs:
        v = hash_tab[j]
        if v == 0:
            return None, steps
        idx = v - 1
        if 0 <= idx < mo.n and mo.msgid(idx) == msgid:
            return idx, steps
        j = (j + 1) % hs
        steps += 1
    return None, steps


def _binary_lookup(mo, msgid):
    """二分路径（orig 表按字节序排序）"""
    lo, hi = 0, mo.n
    while lo < hi:
        mid = (lo + hi) // 2
        m = mo.msgid(mid)
        if m < msgid:
            lo = mid + 1
        elif m > msgid:
            hi = mid
        else:
            return mid
    return None


def _glibc_sim(src_data, new_data, keys):
    """模拟真机（glibc）两条查找路径，验证目标 msgid 在新文件中的可达性与读出值"""
    print("  -- glibc path simulation (hash + binary) --")
    for label, data in (("orig", src_data), ("new ", new_data)):
        mo = MOFile(data)
        htab = _load_hash_tab(mo)
        if htab is None:
            print(f"  [{label}] no hash table (size=0)")
            continue
        # coverage: every index appears exactly once as value-1
        cov = set(v - 1 for v in htab if v != 0)
        dup = len([v for v in htab if v != 0]) - len(cov)
        # hash reachability over full table
        reach = sum(1 for i in range(mo.n)
                    if _hash_lookup(mo, htab, mo.msgid(i))[0] == i)
        print(f"  [{label}] hash: size={mo.hash_size} coverage={len(cov)}/{mo.n} "
              f"dup={dup} hash-reachable={reach}/{mo.n}")
        for k in keys:
            kb = k.encode("utf-8")
            hi_idx, steps = _hash_lookup(mo, htab, kb)
            bi_idx = _binary_lookup(mo, kb)
            hv = mo.msgstr(hi_idx).decode("utf-8", "replace") if hi_idx is not None else "<no hash path>"
            bv = mo.msgstr(bi_idx).decode("utf-8", "replace") if bi_idx is not None else "<no binary path>"
            flag = "OK " if (hi_idx is not None and bi_idx is not None and hv == bv) else "!! "
            print(f"    {flag}{k}: hash_idx={hi_idx}(steps={steps}) bin_idx={bi_idx} -> {hv!r} / {bv!r}")
    print("    note: hash 表字节两文件全同（未被替换触碰）；msgid→index 映射不变，"
          "仅 index→msgstr 的目标条目指向新值。hash 表若因构建环境差异被 glibc 加载期弃用，"
          "则走二分路径——两路径对本替换同样成立。")


def cmd_verify(args):
    with open(args.orig, "rb") as f:
        a = f.read()
    with open(args.new, "rb") as f:
        b = f.read()
    expect = {}
    if args.expect:
        with open(args.expect, "r", encoding="utf-8") as f:
            expect = json.load(f)
    else:
        # 无 expect 时自动推断：差异条目即为预期（并打印）
        ma, mb = MOFile(a), MOFile(b)
        if ma.n == mb.n:
            for i in range(ma.n):
                if ma.msgid(i) == mb.msgid(i) and ma.msgstr(i) != mb.msgstr(i):
                    expect[ma.msgid(i).decode("utf-8", "replace")] = \
                        mb.msgstr(i).decode("utf-8", "replace")
        print("  (no --expect; inferred %d changed entr(ies))" % len(expect))
    issues = _verify(a, b, expect)
    print("== verify ==")
    print(f"  orig: {args.orig}  ({len(a)}B, md5 {hashlib.md5(a).hexdigest()})")
    print(f"  new : {args.new}  ({len(b)}B, md5 {hashlib.md5(b).hexdigest()})")
    print(f"  expected replacements: {len(expect)}")
    for k, v in expect.items():
        print(f"    {k} -> {v!r}")
    if issues:
        print("  RESULT: FAIL")
        for x in issues:
            print("   -", x)
        return 2
    print("  RESULT: PASS (逐条对比：除预期目标外 msgid/msgstr 全同)")

    if args.pygettext:
        print("  -- python gettext cross-check --")
        def _try_load(data):
            import gettext as gt
            return gt.GNUTranslations(io.BytesIO(data))
        try:
            tr = _try_load(b)
        except Exception as e:
            # 原文件是否同样失败？（证明是文件固有属性而非替换引入）
            try:
                _try_load(a)
                print(f"    !! original loads OK but patched file fails: "
                      f"{type(e).__name__}: {e}")
                return 2
            except Exception:
                print(f"    skipped: orig & patched both fail identically "
                      f"({type(e).__name__}) — file-inherent (e.g. no header metadata), "
                      f"NOT introduced by patch; see --glibc-sim for mechanism-level check")
        else:
            ok = 0
            for k, v in expect.items():
                got = tr.gettext(k)
                if got == v:
                    ok += 1
                else:
                    print(f"    [FAIL] {k}: gettext()={got!r} != {v!r}")
            # 抽样不变的条目
            ma = MOFile(a)
            sample_n = 0
            bad = False
            for i in range(0, ma.n, max(1, ma.n // 50)):
                mid = ma.msgid(i)
                if not mid:  # 跳过 header
                    continue
                if mid.decode("utf-8", "replace") in expect:
                    continue
                got = tr.gettext(mid.decode("utf-8", "replace"))
                if got.encode("utf-8") != ma.msgstr(i):
                    print(f"    [FAIL] sample {mid!r}: {got!r} != {ma.msgstr(i)!r}")
                    bad = True
                sample_n += 1
            if bad:
                return 2
            if ok == len(expect):
                print(f"    PASS: {ok}/{len(expect)} expected + {sample_n} samples consistent")
            else:
                print(f"    PARTIAL: {ok}/{len(expect)}")
                return 2

    if args.glibc_sim:
        _glibc_sim(a, b, list(expect.keys()))
    return 0


def cmd_diff(args):
    with open(args.orig, "rb") as f:
        a = f.read()
    with open(args.new, "rb") as f:
        b = f.read()
    print("== byte diff ==")
    print(f"  sizes: {len(a)} -> {len(b)}  (delta {len(b) - len(a):+d})")
    common = min(len(a), len(b))
    regions = []
    i = 0
    while i < common:
        if a[i] != b[i]:
            j = i
            while j < common and a[j] != b[j]:
                j += 1
            regions.append((i, j))
            i = j
        else:
            i += 1
    total = sum(e - s for s, e in regions)
    print(f"  differing regions in common prefix: {len(regions)}  (total {total} bytes)")
    for s, e in regions[:20]:
        print(f"    {s:#08x}..{e:#08x}  ({e - s}B)  "
              f"a={a[s:e].hex()} b={b[s:e].hex()}")
    if len(regions) > 20:
        print(f"    ... ({len(regions) - 20} more)")
    if len(b) > len(a):
        print(f"  appended tail: {len(a):#x}..{len(b):#x}  ({len(b) - len(a)}B)")
        print(f"    hex: {b[len(a):len(a) + 96].hex()} ...")
    elif len(b) < len(a):
        print(f"  !! file shrank by {len(a) - len(b)}B (unexpected for append-only)")
    return 0


def main():
    ap = argparse.ArgumentParser(prog="mo_patch.py",
                                 description="GNU MO 解析/追加式替换/验证（NXWA）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("info", help="列结构 + 词条")
    p.add_argument("mo")
    p.add_argument("--grep", default=None)
    p.set_defaults(fn=cmd_info)

    p = sub.add_parser("get", help="查一条 msgstr")
    p.add_argument("mo")
    p.add_argument("msgid")
    p.set_defaults(fn=cmd_get)

    p = sub.add_parser("set", help="追加式替换生成新文件")
    p.add_argument("src")
    p.add_argument("out")
    p.add_argument("--kv", action="append", help="MSGID=VALUE（可多次）")
    p.add_argument("--map", help="JSON 映射文件 {msgid: value}")
    p.add_argument("--expect-src-md5", default=None)
    p.add_argument("--manifest", default=None)
    p.set_defaults(fn=cmd_set)

    p = sub.add_parser("verify", help="逐条对比验证")
    p.add_argument("orig")
    p.add_argument("new")
    p.add_argument("--expect", default=None, help="JSON 映射（缺省=自动推断差异项）")
    p.add_argument("--pygettext", action="store_true", help="追加 Python gettext 交叉验证")
    p.add_argument("--glibc-sim", action="store_true", help="模拟 glibc hash/二分双路径查询")
    p.set_defaults(fn=cmd_verify)

    p = sub.add_parser("diff", help="字节差异概览")
    p.add_argument("orig")
    p.add_argument("new")
    p.set_defaults(fn=cmd_diff)

    args = ap.parse_args()
    try:
        rc = args.fn(args)
    except MoError as e:
        print("ERROR:", e, file=sys.stderr)
        rc = 1
    sys.exit(rc or 0)


if __name__ == "__main__":
    main()
