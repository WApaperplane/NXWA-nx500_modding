#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""libudd5.so 静态分析工具集（零外部依赖：自己解 ELF + Capstone 反汇编）

为什么不用 readelf/objdump：本机没有 arm-linux-gnueabi binutils，
而 ELF 节头/符号表结构极简，30 行就能自己解出来（参照 sym_udd.py 已验证的做法）。

子命令:
  syms  <kw>            列出 FUNC / OBJECT 符号（kw 可省略）
  dump  <name|addr>     反汇编单个函数（含调用目标、常量、字符串）
  ep                   列出全部 EP/色彩相关 API（51 条那批）
  graph                生成 API 调用图（谁调谁）
  ioctl                扫描所有 ioctl 调用点，提取立即数 ioctl 号
"""
import struct
import re
import sys
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_ARM
from capstone.arm import CS_OP_MEM, CS_OP_IMM, CS_OP_REG

LIB = Path(__file__).resolve().parent / "libudd5.so"


# ---------------------------------------------------------------- ELF
class Elf:
    def __init__(self, path):
        self.d = d = Path(path).read_bytes()
        if d[:4] != b"\x7fELF":
            raise SystemExit("not ELF")
        (self.e_shoff,) = struct.unpack_from("<I", d, 32)
        self.e_shentsize, self.e_shnum, self.e_shstrndx = struct.unpack_from("<HHH", d, 46)
        self.secs = []
        for i in range(self.e_shnum):
            o = self.e_shoff + i * self.e_shentsize
            nm, ty, fl, ad, of, sz = struct.unpack_from("<IIIIII", d, o)
            # Elf32_Shdr 尾部: link@24 info@28 addralign@32 entsize@36
            # ★ entsize 在 +36。误读 +32(addralign) 会让符号表步长全错、名字串位。
            link, inf, _al, ent = struct.unpack_from("<IIII", d, o + 24)
            self.secs.append(dict(nm=nm, ty=ty, ad=ad, of=of, sz=sz, link=link, ent=ent))
        self._load_sections()
        self._load_syms()
        self._load_plt()
        self._load_reldyn()

    def _load_reldyn(self):
        """★ 解析 .rel.dyn：GOT/数据槽偏移 -> 符号名。

        这是把literal pool 里那些"裸偏移"（如 0x528、0x2a3f8）
        还原成"ep_3dlut_reg_base + 0xc"这类真实语义的唯一手段。

        ★★ 两个必须知道的坑：
        (1) ARM 用 REL（r_info = sym<<8|type，32 位 type），不是 x86-64 Rela。
        (2) ★★ 399/436 条是 R_ARM_RELATIVE(type=23, **symidx=0**)，
            它们指向本库内部对象，**符号索引为 0 会被"无名"过滤掉**。
            这些才是 fd_ep / g_d5_dev_ctx 这类本地全局的真实槽位。
            ⇒ 所以必须同时读 .dynsym 里的 OBJECT 符号（st_value = 槽地址）。
        """
        self.relsym = {}    # r_offset -> sym name
        self.reltypes = {}  # r_offset -> reloc type
        rd = self.sec_by_name(".rel.dyn")
        if rd:
            symtab = self.secs[rd["link"]]
            strsec = self.secs[symtab["link"]]
            tab = self.d[strsec["of"]:strsec["of"] + strsec["sz"]]
            ent = symtab["ent"] or 16
            for k in range(rd["sz"] // 8):
                r_off, r_info = struct.unpack_from("<II", self.d, rd["of"] + k * 8)
                symidx = r_info >> 8
                rtype = r_info & 0xFF
                self.reltypes[r_off] = rtype
                if symidx == 0 or symidx * ent + 4 > symtab["sz"]:
                    continue
                n = struct.unpack_from("<I", self.d, symtab["of"] + symidx * ent)[0]
                if n == 0 or n >= len(tab):
                    continue
                end = tab.find(b"\x00", n)
                self.relsym[r_off] = tab[n:end].decode("ascii", "replace")

        # ★ 直接从 .dynsym 的 OBJECT 符号建"符号 -> 槽地址"映射。
        #    这是唯一能拿到 fd_ep / g_d5_dev_ctx 正确地址的办法。
        self.slot_of = {}   # sym name -> slot addr
        self.addr_of = {}   # sym name -> obj addr（同一个值，语义不同）
        for i, s in enumerate(self.secs):
            if s["ty"] not in (2, 11):
                continue
            st = self.secs[s["link"]]
            tab = self.d[st["of"]:st["of"] + st["sz"]]
            ent = s["ent"] or 16
            for k in range(s["sz"] // ent):
                p = s["of"] + k * ent
                n, val, sz, info, oth, sh = struct.unpack_from("<IIIBBH", self.d, p)
                if n == 0 or val == 0:
                    continue
                end = tab.find(b"\x00", n)
                nm = tab[n:end].decode("ascii", "replace")
                if (info & 0xF) == 1:      # STT_OBJECT
                    self.slot_of.setdefault(nm, val)
                    self.addr_of.setdefault(nm, val)
        self.data_start = self.sec_by_name(".data")
        self.got_start = self.sec_by_name(".got")

    def sym_for_off(self, off):
        """任意 .data/.got 槽地址 -> 符号名（先查重定位，再查 dynsym OBJECT）"""
        return self.relsym.get(off)

    def sym_for_slot(self, off):
        """GOT/数据槽偏移 -> 符号名"""
        n = self.relsym.get(off)
        if n:
            return n
        return None

    def got_base(self):
        """_GLOBAL_OFFSET_TABLE_ 基准。

        PIC 代码里`ldr r3,[pc,#N]; add r3,pc,r3` 的和恒等于 GOT base
        （实测 GOT=0x4a2c0，而算出的 0x4a2bc = GOT-4，即 GOT0 槽占位）。
        用它把「代码里的裸偏移」还原成「GOT+off -> 符号」。
        """
        return self.sec_by_name(".got")["ad"] if self.sec_by_name(".got") else None

    def resolve_got_off(self, off):
        """GOT 相对偏移 -> (符号名, 符号绝对地址)"""
        g = self.got_base()
        if g is None:
            return None, None
        a = g + off
        nm = self.relsym.get(a)
        return nm, a

    def _load_plt(self):
        """★ 解析 .rel.plt -> PLT 桩地址 -> 导入符号名。

        ARM PLT 布局（常见形态）：
          .plt[0..19] = PLT0（调 .got.plt[0] 做一次惰性绑定）
          第 i 条桩起始 = plt_addr + 20 + i*12
        .rel.plt 第 i 项的 r_offset 指向该桩用的 GOT 槽，两者顺序一致
        ⇒ 可把 GOT 槽反查成桩地址，再映射到符号名。

        这是打通『libudd5 用户态 API -> 真实驱动/库调用』的唯一静态线索：
        有了它，BL 0x84e0 就能读成 BL memcpy 而不是裸地址。
        """
        self.plt = {}       # plt_stub_addr -> name
        self.got_sym = {}   # got_addr -> name
        rp = self.sec_by_name(".rel.plt")
        plt = self.sec_by_name(".plt")
        if not rp or not plt:
            return
        symtab = self.secs[rp["link"]]
        if symtab["ty"] not in (2, 11):
            return
        strsec = self.secs[symtab["link"]]
        tab = self.d[strsec["of"]:strsec["of"] + strsec["sz"]]
        ent = symtab["ent"] or 16
        STUB = 12
        base = plt["ad"] + 20
        for k in range(rp["sz"] // 8):
            r_off, r_info = struct.unpack_from("<II", self.d, rp["of"] + k * 8)
            # ★ ARM 用 Elf32_Rel: r_info = (sym << 8) | type（32 位 type）
            #   不是 x86-64 Elf64_Rela 的 (sym<<32)|type。写错成 >>12 会全解错。
            symidx = r_info >> 8
            if symidx * ent + 4 > symtab["sz"]:
                continue
            n = struct.unpack_from("<I", self.d, symtab["of"] + symidx * ent)[0]
            if n == 0 or n >= len(tab):
                continue
            end = tab.find(b"\x00", n)
            name = tab[n:end].decode("ascii", "replace")
            stub = base + k * STUB
            self.plt[stub] = name
            self.got_sym[r_off] = name
        self._plt_base = base

    def sym_for_plt(self, addr):
        return self.plt.get(addr) or self.plt.get(addr & ~1)

    def _load_sections(self):
        d = self.d
        s = self.secs[self.e_shstrndx]
        self.shstrtab = d[s["of"]:s["of"] + s["sz"]]
        for s in self.secs:
            off = s["nm"]
            end = self.shstrtab.find(b"\x00", off)
            s["name"] = self.shstrtab[off:end].decode("ascii", "replace")

    def sec_by_name(self, name):
        return next((s for s in self.secs if s["name"] == name), None)

    PROGBITS = 1   # ★ ELF 常量：SHT_PROGBITS=1, SHT_NOBITS=8。别写成 8（那是 NOBITS）

    def va2off(self, va):
        for s in self.secs:
            if s["ty"] != self.PROGBITS:
                continue
            if s["ad"] and s["ad"] <= va < s["ad"] + s["sz"]:
                return s["of"] + (va - s["ad"])
        return None

    def off2va(self, off):
        for s in self.secs:
            if s["ty"] != self.PROGBITS:
                continue
            if s["of"] <= off < s["of"] + s["sz"]:
                return s["ad"] + (off - s["of"])
        return None

    def _load_syms(self):
        d = self.d
        self.funcs = []   # (va, name, size)
        self.objs = []    # (va, name, size, secname)
        self._sym_by_va = {}
        for i, s in enumerate(self.secs):
            if s["ty"] not in (2, 11):  # SYMTAB / DYNSYM
                continue
            st = self.secs[s["link"]]
            tab = d[st["of"]:st["of"] + st["sz"]]
            ent = s["ent"] or 16
            for k in range(s["sz"] // ent):
                p = s["of"] + k * ent
                n, val, sz, info, oth, sh = struct.unpack_from("<IIIBBH", d, p)
                if n == 0 or val == 0:
                    continue
                end = tab.find(b"\x00", n)
                name = tab[n:end].decode("ascii", "replace")
                t = info & 0xF
                if t == 2:
                    self.funcs.append((val, name, sz))
                    self._sym_by_va.setdefault(val, name)
                elif t == 1:
                    self.objs.append((val, name, sz, self.secs[i]["name"] if sh < len(self.secs) else "?"))
        self.funcs.sort()
        self.objs.sort()

    def func_size(self, va):
        fz = [(v, n, s) for v, n, s in self.funcs if v == va]
        if fz and fz[0][2]:
            return fz[0][2]
        # 落到下一个符号
        nxt = [v for v, _, _ in self.funcs if v > va]
        return (nxt[0] - va) if nxt else 0x100

    def get_cstr(self, va, maxlen=200):
        off = self.va2off(va)
        if off is None:
            return None
        end = self.d.find(b"\x00", off, off + maxlen)
        if end < 0:
            return None
        b = self.d[off:end]
        if not b or any(c < 9 or (13 < c < 32) for c in b):
            return None
        try:
            return b.decode("ascii")
        except UnicodeDecodeError:
            return None

    def read_u32(self, va):
        off = self.va2off(va)
        if off is None or off + 4 > len(self.d):
            return None
        return struct.unpack_from("<I", self.d, off)[0]


# ---------------------------------------------------------------- disasm
class Dis:
    """ARM / Thumb 自动识别反汇编器。

    ★ 坑：libudd5.so 的符号 st_value 的 bit0 = 1 表示 Thumb。
      所以 (v & ~1) 是真实地址，bit0 是模式位。
    """

    def __init__(self, elf):
        self.e = elf
        self.cs_arm = Cs(CS_ARCH_ARM, CS_MODE_ARM)
        self.cs_th = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
        for cs in (self.cs_arm, self.cs_th):
            cs.detail = True
            cs.skipdata = True

    def decode(self, va, size, thumb=None):
        off = self.e.va2off(va)
        if off is None:
            return []
        code = self.e.d[off:off + size]
        if thumb is None:
            thumb = self.is_thumb(va)
        cs = self.cs_th if thumb else self.cs_arm
        return list(cs.disasm(code, va))

    def is_thumb(self, va):
        """判定函数模式：符号表 bit0，或扫描函数序言（Thumb 常见 push {r4..}）"""
        for v, n, _ in self.e.funcs:
            if v & ~1 == va & ~1:
                return bool(v & 1)
        off = self.e.va2off(va)
        if off is None:
            return False
        # 序言启发：ARM 是 "stmdb sp!,{...}" 或 "push"; Thumb 常见 tbb/tst
        b = self.e.d[off:off + 8]
        if not b:
            return False
        w = struct.unpack_from("<H", self.e.d, off)[0]
        if (w & 0xFF00) == 0xB500:  # push {lr,...}
            return True
        if (w & 0xFE2F) == 0xe82d or (w & 0x0F00) == 0x0A00:
            return False
        return False

    def annotate(self, ins):
        """给指令加注释：符号名 / 字符串 / 全局常量指针"""
        notes = []
        mn = ins.mnemonic
        # SKIPDATA 模式下 capstone 会造出没有 operands 的伪指令
        try:
            _ops = ins.operands
        except Exception:
            return notes

        # (1) 分支/调用：解析 BL/B 目标符号
        if mn in ("bl", "blx", "b", "b.w", "bx", "blne", "bleq", "bne", "bgt", "blt", "bge", "ble", "bhi", "bls", "bcc", "bcs"):
            for op in ins.operands:
                if op.type != CS_OP_IMM:
                    continue
                tgt = op.imm & 0xFFFFFFFF
                for key in (tgt, tgt & ~1, tgt | 1):
                    s = self.e._sym_by_va.get(key)
                    if s:
                        notes.append("->" + s)
                        break
                else:
                    # PLT 桩 = 外部导入函数（memcpy/ioctl/open ...）
                    p = self.e.sym_for_plt(tgt)
                    if p:
                        notes.append("->@plt %s" % p)
            return notes

        # (2) 常量：直接符号 / 字符串 / 指向全局的 literal
        for op in ins.operands:
            if op.type != CS_OP_IMM:
                continue
            v = op.imm & 0xFFFFFFFF
            s = self.e._sym_by_va.get(v) or self.e._sym_by_va.get(v & ~1)
            if s:
                notes.append(s)
                continue
            st = self.e.get_cstr(v) if 0x8000 < v < 0x20000 else None
            if st and len(st) > 2:
                notes.append('"%s"' % st)
                continue
            # ldr rN, =0xADDR  => 0xADDR 处可能存着全局符号指针
            val = self.e.read_u32(v)
            if val is not None:
                s2 = self.e._sym_by_va.get(val)
                if s2:
                    notes.append("[%s]=%s" % (s2, hex(val)))
        return notes

    def func_text(self, va, maxins=400):
        size = self.e.func_size(va & ~1)
        ins = self.decode(va & ~1, size)
        name = self.e._sym_by_va.get(va) or self.e._sym_by_va.get(va & ~1) or "sub_%x" % (va & ~1)
        lines = ["/* ===== %s @ 0x%08x  size=%d  %s ===== */" % (
            name, va & ~1, size, "THUMB" if self.is_thumb(va) else "ARM")]
        for i, x in enumerate(ins[:maxins]):
            note = self.annotate(x)
            txt = "  %08x:  %-10s %s" % (x.address, x.mnemonic, x.op_str)
            if note:
                txt += "   // " + ", ".join(dict.fromkeys(note))
            lines.append(txt)
        return "\n".join(lines)


# ---------------------------------------------------------------- 子命令
EP_KW = re.compile(
    r"(?i)(3dl|nog|_mc_|ycc|drc|histeq|ccm|_csc|gamma|tone.?curve|ep_|lvr|bblt|ldc|rsz|jpeg|fd_|wbm|awb)")


def cmd_syms(elf, dis, args):
    kw = re.compile(args[0], re.I) if args else None
    print("=== FUNC 符号 %d / OBJECT %d ===" % (len(elf.funcs), len(elf.objs)))
    if kw:
        print("\n--- FUNC 匹配 %r ---" % kw.pattern)
        for v, n, s in elf.funcs:
            if kw.search(n):
                print("  0x%06x %-6s %s" % (v, "T" if v & 1 else "A", n))
        print("\n--- OBJECT 匹配 ---")
        for v, n, s, sn in elf.objs:
            if kw.search(n):
                print("  0x%06x %-5d %-10s %s" % (v, s, sn, n))
    else:
        for v, n, s in elf.funcs:
            print("  0x%06x %s" % (v, n))


def cmd_ep(elf, dis, args):
    print("=== EP / 色彩 API 全表（libudd5.so 静态导出）===")
    rows = [(v, n) for v, n, s in elf.funcs if EP_KW.search(n)]
    for v, n in rows:
        print("  0x%06x %-4s %s" % (v, "TH" if v & 1 else "ARM", n))
    print("\n共 %d 条 FUNC" % len(rows))
    print("\n--- EP 全局数据（寄存器基址/表基址）---")
    for v, n, s, sn in elf.objs:
        if EP_KW.search(n):
            print("  0x%06x %-6d %-10s %s" % (v, s, sn, n))
    print("\n--- 非 EP 但关键的基础设施 ---")
    for v, n, s, sn in elf.objs:
        if re.search(r"(?i)(handle|fd|ioctl|dev_?path|drv)", n):
            print("  0x%06x %-6d %-10s %s" % (v, s, sn, n))


def _resolve(elf, arg):
    if arg.startswith("0x"):
        a = int(arg, 16)
        return elf._sym_by_va.get(a) or elf._sym_by_va.get(a & ~1) or None
    for v, n, s in elf.funcs:
        if n == arg or n.endswith("_" + arg) or n.endswith("." + arg):
            return n
    return None


def _lookup(elf, arg):
    """名字或地址 -> 符号表项的 st_value"""
    if arg.startswith("0x"):
        return int(arg, 16)
    for v, n, s in elf.funcs:
        if n == arg:
            return v
    return None


def cmd_dump(elf, dis, args):
    if not args:
        raise SystemExit("用法: dump <name|addr>")
    va = _lookup(elf, args[0])
    if va is None:
        cands = [(v, n) for v, n, s in elf.funcs if tgt.lower() in n.lower()]
        if len(cands) == 1:
            va = cands[0][0]
        elif len(cands) > 1:
            print("多个匹配:")
            for v, n in cands:
                print("  0x%06x %s" % (v, n))
            return
        else:
            raise SystemExit("找不到符号 %s" % tgt)
    print(dis.func_text(va))


def cmd_graph(elf, dis, args):
    """静态调用图：谁调用了 EP/色彩 API"""
    targets = {n: v for v, n, s in elf.funcs if EP_KW.search(n)}
    tvas = set()
    for v, n, s in elf.funcs:
        if n in targets:
            tvas.add(v & ~1)
    print("=== EP API 调用图（静态 PLT/直接 call 扫描）===")
    callers = {t: [] for t in tvas}
    for v, n, s in elf.funcs:
        size = elf.func_size(v & ~1)
        for x in dis.decode(v & ~1, min(size, 0x2000)):
            if x.mnemonic not in ("bl", "blx", "b", "b.w"):
                continue
            for op in x.operands:
                if op.type == CS_OP_IMM and (op.imm & ~1) in tvas:
                    callers[op.imm & ~1].append((v & ~1, elf._sym_by_va.get(v, "?"), x.mnemonic))
    for t in sorted(tvas):
        nm = elf._sym_by_va.get(t) or elf._sym_by_va.get(t | 1) or hex(t)
        cs = callers[t]
        print("\n%s @ 0x%06x   被 %d 处调用" % (nm, t, len(cs)))
        for a, an, mn in cs[:12]:
            print("    %-8s %s @0x%06x" % (mn, an, a))


IOCTL_KW = re.compile(r"(?i)(ioctl|_IO|_IOR|_IW|_IOWR)")


def cmd_ioctl(elf, dis, args):
    """★ 全库扫描 ioctl() 调用点，提取立即数 ioctl 号 + 参数个数。
    这是打通『用户态 API -> 内核 EP 驱动』的唯一静态线索。"""
    print("=== ioctl 调用点全扫 ===")
    hits = 0
    for v, n, s in elf.funcs:
        size = elf.func_size(v & ~1)
        if size > 0x4000:
            size = 0x4000
        prev = None
        for x in dis.decode(v & ~1, size):
            # 找 blx/bl 到 ioctl
            if x.mnemonic in ("bl", "blx") and prev is not None:
                tgt = None
                for op in x.operands:
                    if op.type == CS_OP_IMM:
                        tgt = op.imm & ~1
                nm = elf._sym_by_va.get(tgt) or elf._sym_by_va.get(tgt | 1) if tgt else None
                if nm and "ioctl" in nm:
                    hits += 1
                    # 往前 8 条找 ldr rN,#imm（ioctl 号）
                    print("\n[%s @ 0x%06x] -> %s" % (n, v & ~1, nm))
                    for op in x.operands:
                        if op.type == CS_OP_IMM:
                            print("    target 0x%08x" % (op.imm & 0xFFFFFFFF))
            prev = x
    print("\n共 %d 个 ioctl 调用函数" % hits)


def cmd_literals(elf, dis, args):
    """解析函数里的 literal pool（ldr rN,[pc,#N]），
    把 PC 相对常量还原成"这个全局符号表项指向哪个基址"。

    这是把『_udd_ep_3dl_reg_* 里的 +0xc / +0x10』还原成
    ★ 真实 EP 寄存器地址（如 0x2082b000 + 偏移）的唯一手段。
    """
    if not args:
        raise SystemExit("用法: literals <func|addr>")
    va = _lookup(elf, args[0])
    size = elf.func_size(va & ~1)
    ins = dis.decode(va & ~1, size)
    base_va = va & ~1
    print("/* ===== literal pool of %s @ 0x%08x ===== */" % (
        elf._sym_by_va.get(base_va) or elf._sym_by_va.get(va) or "?", base_va))
    gotb = elf.got_base()
    for x in ins:
        if x.mnemonic == "ldr" and len(x.operands) == 2:
            mem = x.operands[1]
            if mem.type == CS_OP_MEM and mem.mem.base and x.reg_name(mem.mem.base) == "pc":
                pool = x.address + 8 + mem.mem.disp
                val = elf.read_u32(pool)
                note = ""
                if val is not None:
                    # ★ 两种形式必须分开判：
                    #  (a) val 本身就是 GOT 内绝对地址 => 符号地址
                    #  (b) val 很小（几百字节）=>「GOT+off」的 off
                    #      下一条 add rX,pc,rX 才是加 GOT 基准
                    nm = elf.relsym.get(val)
                    if nm:
                        note = "  -> [abs] %s @0x%08x" % (nm, val)
                    elif gotb is not None and 0 < val < 0x2000:
                        nm2, addr2 = elf.resolve_got_off(val)
                        note = "  -> GOT+0x%03x = %s @0x%08x" % (
                            val, nm2 or "?", addr2 or 0)
                    else:
                        s = elf._sym_by_va.get(val)
                        if s:
                            note = "  -> %s" % s
                        else:
                            inner = elf.read_u32(val)
                            s2 = elf._sym_by_va.get(inner) if inner else None
                            note = "  -> [0x%08x]%s" % (
                                val, (" = " + s2) if s2 else "")
                print("  %08x  %-8s %-22s ; pool@%08x = 0x%08x%s"
                      % (x.address, x.mnemonic, x.op_str, pool, val or 0, note))
    # 直接 dump 函数尾部 64 字节的字面量
    print("\n  --- 尾部 literal 区 ---")
    for a in range(base_va + size - 48, base_va + size, 4):
        v = elf.read_u32(a)
        if v is None:
            continue
        s = elf._sym_by_va.get(v)
        extra = ""
        inner = elf.read_u32(v)
        if inner is not None:
            s2 = elf._sym_by_va.get(inner)
            if s2:
                extra = "  (= %s)" % s2
        print("  %08x: 0x%08x  %s%s" % (a, v, s or "", extra))


def cmd_batch(elf, dis, args):
    """批量导出：udd5.py batch <outfile> <kw>  —— 反汇编所有匹配函数到文件"""
    out = Path(args[0])
    kw = re.compile(args[1], re.I) if len(args) > 1 else EP_KW
    sel = [(v, n) for v, n, s in elf.funcs if kw.search(n)]
    with out.open("w", encoding="utf-8") as f:
        for v, n in sel:
            f.write(dis.func_text(v) + "\n\n")
    print("wrote %d funcs -> %s" % (len(sel), out))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    elf = Elf(LIB)
    dis = Dis(elf)
    {"syms": cmd_syms, "dump": cmd_dump, "ep": cmd_ep,
     "graph": cmd_graph, "ioctl": cmd_ioctl,
     "literals": cmd_literals, "batch": cmd_batch}.get(cmd, cmd_syms)(elf, dis, sys.argv[2:])


if __name__ == "__main__":
    main()