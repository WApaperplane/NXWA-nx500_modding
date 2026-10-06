#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★★ 对照实验：用成熟工具 pyelftools 交叉验证自研 udd5.py 的解析结果。

方法论铁律：自研解析器必须用现成工具做对照组自证，
否则"能跑出结果"不等于"结果正确"（我已踩过 4 个ELF 坑）。

用法: python crosscheck.py
"""
import sys
from pathlib import Path

from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection
from elftools.elf.sections import SymbolTableSection

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from udd5 import Elf, LIB  # noqa

ARM_ABS = {2, 3, 28}     # R_ARM_ABS32 / COPY / GOTOFF32


def main():
    lib = LIB
    ok = [0]; fail = [0]

    def chk(label, mine, theirs):
        good = mine == theirs
        print("  [%s] %-34s mine=%s  pyelftools=%s"
              % ("OK " if good else "DIFF", label, mine, theirs))
        if good:
            ok[0] += 1
        else:
            fail[0] += 1

    print("=" * 72)
    print("对照验证：udd5.py  vs  pyelftools %s" % LIB.name)
    print("=" * 72)

    mine = Elf(lib)
    # ★ pyelftools 的惰性 section 解析需要文件句柄全程存活
    f = open(lib, "rb")
    try:
        return run(mine, f, chk, ok, fail)
    finally:
        f.close()


def run(mine, f, chk, ok, fail):
    e = ELFFile(f)

# ---- (1) FUNC 符号 ----
    print("\n(1) FUNC 符号表")
    st = e.get_section_by_name(".dynsym")
    # ★ pyelftools 把 libc 导入函数（ioctl/open/memcpy…）也算 FUNC，
    #   它们的 st_value = 0 且 st_shndx = SHN_UNDEF。
    #   我的解析器按"有真实地址"过滤掉了它们 —— 这是口径差异，不是缺陷。
    #   正确判据是 SHN_UNDEF，不是"地址是否落在 .plt 段内"。
    t_all = {s.name for s in st.iter_symbols()
             if s["st_info"]["type"] == "STT_FUNC" and s.name}
    t_def = {s.name for s in st.iter_symbols()
             if s["st_info"]["type"] == "STT_FUNC" and s.name
             and s["st_shndx"] != "SHN_UNDEF"}
    m = {n for v, n, s in mine.funcs}
    print("     pyelftools FUNC %d = 本库定义 %d + libc 导入 %d(SHN_UNDEF)"
          % (len(t_all), len(t_def), len(t_all) - len(t_def)))
    chk("已定义 FUNC 数量", len(m), len(t_def))
    chk("已定义 FUNC 集合一致", m == t_def, True)

    # ---- (2) OBJECT 符号（我踩坑最多的地方）----
    print("\n(2) OBJECT 符号（★ 我曾漏掉 399 条 R_ARM_RELATIVE）")
    to = {s.name: s["st_value"] for s in st.iter_symbols()
          if s["st_info"]["type"] == "STT_OBJECT" and s.name}
    chk("dynsym OBJECT 数量", len(mine.slot_of), len(to))
    for nm in ("fd_ep", "g_d5_dev_ctx", "ep_3dlut_reg_base", "g_dev_id"):
        chk("OBJECT %s" % nm, mine.slot_of.get(nm), to.get(nm))

    # ---- (3) .rel.dyn 重定位总数（RELATIVE也算）----
    print("\n(3) .rel.dyn 重定位")
    rd = e.get_section_by_name(".rel.dyn")
    chk("rel.dyn 条目总数", len(mine.reltypes), rd.num_relocations())

    # ---- (4) PLT 桩 -> 符号映射（最关键的推断）----
    print("\n(4) PLT 桩地址映射（★ 我的推断：base=plt+20, 步长 12）")
    rp = e.get_section_by_name(".rel.plt")
    plt = e.get_section_by_name(".plt")
    symtab = e.get_section(rp["sh_link"])
    # pyelftools 侧的真相：r_offset 是 GOT 槽
    got_of_plt = {}
    for i, rel in enumerate(rp.iter_relocations()):
        sym = symtab.get_symbol(rel["r_info_sym"])
        got_of_plt.setdefault(sym.name, []).append(rel["r_offset"])
    print("  .rel.plt %d 条 / .plt 0x%08x+0x%x (头 20B, 每条 12B -> 可容 %d 条)"
          % (rp.num_relocations(), plt["sh_addr"], plt["sh_size"],
             (plt["sh_size"] - 20) // 12))
    chk(".rel.plt 条数 <= PLT 可容条数",
        rp.num_relocations() <= (plt["sh_size"] - 20) // 12, True)

    # 抽 5 个符号核对：我的 plt[base+k*12] 是否与 rel.plt 第 k 项一致
    dis = mine
    bad = 0
    for k, rel in enumerate(rp.iter_relocations()):
        sym = symtab.get_symbol(rel["r_info_sym"])
        stub = plt["sh_addr"] + 20 + k * 12
        got = dis.plt.get(stub)
        if got != sym.name:
            bad += 1
            if bad <= 3:
                print("     DIFF k=%d stub=0x%08x mine=%r truth=%r"
                      % (k, stub, got, sym.name))
    chk("全部 %d 个 PLT 桩名匹配" % rp.num_relocations(), bad, 0)

    # ---- (5) GOT 基准推断 ----
    print("\n(5) _GLOBAL_OFFSET_TABLE_ 基准推断")
    # 真值 = .rel.plt 第 0 项桩的 GOT 槽；用桩里的 ldr 目标反推
    first_got = got_of_plt and list(got_of_plt.values())[0][0]
    chk(".got 段起始 == 我的 got_base()",
        mine.got_base(), e.get_section_by_name(".got")["sh_addr"])
    print("     首个 .rel.plt 的 GOT 槽 = 0x%08x（比 .got 起始大 %d）"
          % (first_got, first_got - mine.got_base()))

    # ---- (6) ioctl 号解码复核（★ 手工独立推一遍，不调 decode_ioc）----
    print("\n(6) ioctl 0xc0047302 独立解码（★ 不调自己的 decode_ioc，避免自证）")
    IOC = 0xc0047302
    # ★ Linux asm-generic/ioctl.h（ARM 与通用一致）：
    #   nr:bits0-7  type:bits8-15  size:bits16-29  dir:bits30-31
    #   ⚠️ 我第一次写成 nr&0xFFF / size&0x3FFF 都错，会解出 nr=770 size=0。
    #   对照反汇编 movw r1,#0x7302 / movt r1,#0xc004 可自证。
    DIR = {0: "NONE", 1: "WRITE", 2: "READ", 3: "READ|WRITE"}
    exp = dict(dir=DIR[(IOC >> 30) & 0x3],
               size=(IOC >> 16) & 0x3FFF,
               type=chr((IOC >> 8) & 0xFF),
               nr=IOC & 0xFF)
    print("     手算: %s nr=%d type='%s' size=%d"
          % (exp["dir"], exp["nr"], exp["type"], exp["size"]))
    print("     =>  _IOWR('%s', %d, u%d)  == 0x%08x"
          % (exp["type"], exp["nr"], exp["size"] * 8, IOC))
    chk("方向", exp["dir"], "READ|WRITE")
    chk("type ('s'=Samsung SMA)", exp["type"], "s")
    chk("nr", exp["nr"], 2)
    chk("size", exp["size"], 4)
    # 再用解码器复核一遍（两个独立实现应一致）
    n, t_, sz, d = decode_ioc(IOC)
    chk("decode_ioc 与手算一致", (n, chr(t_), sz, d),
        (exp["nr"], exp["type"], exp["size"], exp["dir"]))

    print("\n" + "=" * 72)
    print("结果：%d 项一致，%d 项不一致" % (ok[0], fail[0]))
    print("=" * 72)
    return 0 if fail[0] == 0 else 1


def decode_ioc(v):
    """Linux ARM 的 _IOC/_IOWR 编码。★ 宏在 C 里是 32 位，务必用 Python 算。"""
    nr = v & 0xFF          # ★ bits 0-7，不是 0x3FFF
    size = (v >> 16) & 0x3FFF
    t_ = (v >> 8) & 0xFF
    d = (v >> 30) & 0x3
    parts = {0: "", 1: "WRITE", 2: "READ", 3: "READ|WRITE"}
    return nr, t_, size, parts[d]


if __name__ == "__main__":
    sys.exit(main())