#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""3dlut_qemu.py —— 在 QEMU/Unicorn 上复现 p7 的 3D LUT 应用线路

思路：
  p7_full.bin 是 **ARM 用户态 flat image**，base=0x80000000（VA = 文件偏移 + 0x80000000）。
  3D LUT 的「应用线路」尾段是纯用户态代码（无 SVC、无 MMU 依赖）——
  因此可以用 Unicorn 直接执行，并在 MMIO 窗口 0x2082b000 上挂写钩子，
  得到 **真实的寄存器写序列**（这是上机 regdump 之外唯一能拿到"写序"的手段）。

场景（逐个独立执行）：
  S1  FUN_004cf3d4(1) / (0)             —— OnOff 原语
  S2  FUN_004cf484(1) / (2)             —— ★ Load/Save 启动脉冲
  S3  FUN_004cf4b4(addr,len,1|2)        —— LUT0/LUT1 地址
  S4  ★ FUN_004a5c44(table,sel,fmt,0)   —— load_lut 3 参封装（sel 0/1/2 x fmt 0/1）
  S5  ★ FUN_00179384(table,sel,fmt,ptr) —— p7 侧 load/save 完全封装（带参数校验与 -300）
  S6  FUN_0009a3e8(a,b,c)               —— View 路径「静态 4 档」选表（纯查表）
  S7  FUN_004a5b6c(&desc)               —— 描述符解析 -> 配置路径（不搬数据）
  S8  ★ FUN_003f2c60(idx,table,sel)     —— MCB 侧跳转表选表 -> tail-call

产物：raw8/p7/3dlut_qemu.json + 控制台报告

依赖：unicorn（E:\\nxks2-re venv）
用法：python test_server/isp/3dlut_qemu.py
"""
import json
import os
import struct
import sys

try:
    from unicorn import (Uc, UcError, UC_ARCH_ARM, UC_MODE_ARM,
                         UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_HOOK_MEM_READ,
                         UC_HOOK_INTR)
    from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                                   UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR,
                                   UC_ARM_REG_PC, UC_ARM_REG_CPSR)
except ImportError:
    print("需要 unicorn：E:/nxks2-re/Scripts/python.exe")
    sys.exit(1)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
P7 = os.path.join(ROOT, "raw8", "p7", "p7_full.bin")
OUT_JSON = os.path.join(ROOT, "raw8", "p7", "3dlut_qemu.json")

BASE = 0x80000000
REG_BLOCK = 0x2082B000
REG_END = REG_BLOCK + 0x40

# 需要 stub 的外部函数（日志 / MCB / 内存操作）—— 执行到入口即"返回 0"
STUBS = {
    0x4D9724: "log", 0x4DCBB8: "log", 0x000465BC: "log", 0x00046484: "log",
    0x00173C88: "log", 0x00173F34: "log",
    0x004B7A38: "mcb", 0x004B78CC: "mcb", 0x004B7958: "mcb", 0x004B71DC: "mcb",
    0x004B7284: "mcb", 0x004B77EC: "mcb", 0x004B7680: "mcb", 0x004B7464: "mcb",
    0x004B7A40: "mcb", 0x004BA6A8: "mcb", 0x004B7EC0: "mcb", 0x004B64CC: "mcb",
    0x004B6698: "mcb", 0x004B6FA8: "mcb",
    0x0017B570: "lock", 0x0017B5C8: "unlock",
    0x00509EEC: "memcpy", 0x00524194: "lookup", 0x00176884: "material",
    0x0017ABD4: "x", 0x0017B2C4: "x", 0x0017AB88: "x", 0x00179BD4: "x",
    0x00179C20: "x", 0x004DB408: "x", 0x004D9C3C: "x", 0x004042DC: "x",
    0x004047FC: "x", 0x001796D4: "x", 0x004D9EE8: "x", 0x004D9A8C: "x",
}

# 观察点：记录这些"3D LUT 关键函数"被调用时的 r0-r3（= 真实传参）
WATCH = {
    0x4A5C44: "load_lut(table,sel,fmt,0)",
    0x4A5E30: "load/save 主体(&desc)",
    0x4A5B6C: "描述符解析(&desc)",
    0x4A5FF0: "配置(&desc)",
    0x4CF3D4: "reg OnOff",
    0x4CF4B4: "reg LUT 地址",
    0x4CF484: "reg 启动脉冲",
    0x179314: "API load(table,a2,a3,a4)",
    0x179384: "API save/load(table,sel,fmt,ptr)",
    0x3FB3B8: "MCB 装载封装(addr,sel,fmt)",
    0x3FB4AC: "参数胶水",
}


class P7Emu:
    """一次性的 p7 用户态小环境。"""

    def __init__(self, verbose=False):
        img = open(P7, "rb").read()
        self.img = img
        self.mu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        # 镜像 + BSS（0x80000000..0x82000000）
        self.mu.mem_map(BASE, 0x2000000)
        self.mu.mem_write(BASE, img)
        # MMIO / EP / IPC 区（0x20000000..0x22000000）
        self.mu.mem_map(0x20000000, 0x2000000)
        # 栈（0x7E000000..0x80000000，紧邻镜像基址）
        self.mu.mem_map(0x7E000000, 0x2000000)
        self.SP = 0x7F800000
        self.verbose = verbose
        self.writes = []       # (addr, size, value)
        self.trace = []        # (kind, detail)
        self.calls = []        # (off, name, [r0..r3])
        self.mu.hook_add(UC_HOOK_MEM_WRITE, self._on_write)
        self.mu.hook_add(UC_HOOK_CODE, self._on_code)

    # ---- hooks ----
    def _on_write(self, uc, access, address, size, value, user):
        self.writes.append((address, size, value))
        if self.verbose:
            print("      WR 0x%08x size=%d <- 0x%x" % (address, size, value))

    def _on_code(self, uc, address, size, user):
        off = address - BASE
        if off in STUBS:
            self.trace.append(("stub", "0x%x %s" % (off, STUBS[off])))
            lr = uc.reg_read(UC_ARM_REG_LR)
            uc.reg_write(UC_ARM_REG_R0, 0)
            uc.reg_write(UC_ARM_REG_PC, lr)
            return
        if off in WATCH:
            self.calls.append((off, WATCH[off],
                               [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1,
                                                         UC_ARM_REG_R2, UC_ARM_REG_R3)]))

    # ---- runner ----
    def call(self, off, args, max_ins=200000, name=""):
        """执行 off 处函数，args 依次放 r0..r3；返回 (rc, writes)"""
        mu = self.mu
        self.writes = []
        self.trace = []
        self.calls = []
        ret_magic = 0x7EFFFFFF & ~3
        mu.reg_write(UC_ARM_REG_SP, self.SP)
        mu.reg_write(UC_ARM_REG_LR, ret_magic)
        regs = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3]
        for i, a in enumerate(args[:4]):
            mu.reg_write(regs[i], a & 0xFFFFFFFF)
        for i in range(len(args), 4):
            mu.reg_write(regs[i], 0)
        try:
            mu.emu_start(BASE + off, ret_magic, timeout=10 * 1000000,
                         count=max_ins)
            rc = mu.reg_read(UC_ARM_REG_R0)
        except UcError as e:
            rc = "UCERROR: %s (pc=0x%x)" % (e, mu.reg_read(UC_ARM_REG_PC))
        # 只保留 3D LUT 寄存器块内的写
        reg_w = [(a, s, v) for (a, s, v) in self.writes
                 if REG_BLOCK <= a < REG_END]
        other_w = [(a, s, v) for (a, s, v) in self.writes
                   if not (0x20000000 <= a < 0x22000000) and not (
                       0x7E000000 <= a < 0x7F000000)]
        return rc, reg_w, other_w, list(self.trace), list(self.calls)
    def write_struct(self, addr, blob):
        self.mu.mem_write(addr, blob)


def fmt_writes(ws):
    return ["0x%08x <- 0x%08x (%d)" % (a, v, s) for (a, s, v) in ws]


def dump_reg_state(emu, label):
    """读回 0x2082b000 块前 0x20 字节"""
    st = emu.mu.mem_read(REG_BLOCK, 0x20)
    vals = struct.unpack("<8I", st)
    return {"label": label, "regs": {("+0x%03x" % (i * 4)): "0x%08x" % v
                                     for i, v in enumerate(vals)}}


def main():
    emu = P7Emu()
    res = {"image": os.path.basename(P7), "base": hex(BASE),
           "reg_block": hex(REG_BLOCK), "scenarios": []}
    log = []
    def p(s=""):
        log.append(s)
        print(s)

    p("=== p7 3D LUT 应用线路 · QEMU/Unicorn 复现 ===")
    p("镜像 %d B，映射 0x80000000+0x2000000（含 BSS）" % len(emu.img))
    p()

    def scen(name, off, args, note=""):
        # 每个场景前把寄存器块清零（幂等）
        emu.mu.mem_write(REG_BLOCK, b"\x00" * 0x40)
        rc, rw, ow, tr, calls = emu.call(off, args, name=name)
        rec = {"name": name, "func": "0x%x" % off, "args": ["0x%x" % a for a in args],
               "note": note, "rc": (rc if isinstance(rc, str) else "0x%x" % (rc & 0xFFFFFFFF)),
               "reg_writes": [{"off": "0x%x" % (a - REG_BLOCK), "val": "0x%x" % v, "size": s}
                              for (a, s, v) in rw],
               "stubs": tr[:12],
               "key_calls": [{"fn": "0x%x" % o, "name": nm,
                              "args": ["0x%x" % (x & 0xFFFFFFFF) for x in ar]}
                             for (o, nm, ar) in calls[:12]],
               "reg_after": dump_reg_state(emu, name)["regs"]}
        res["scenarios"].append(rec)
        p("── %s  func=0x%x args=%s %s" % (name, off, rec["args"], note))
        p("   rc=%s  寄存器写入 %d 条:" % (rec["rc"], len(rw)))
        for a, s, v in rw:
            p("      [0x2082b%03x] <- 0x%08x  (%d B)" % (a - REG_BLOCK, v, s))
        after = rec["reg_after"]
        nonzero = {k: v for k, v in after.items() if v != "0x00000000"}
        p("   终态: %s" % (nonzero if nonzero else "(全 0)"))
        if calls:
            for o, nm, ar in calls[:6]:
                p("   → 命中 %s(0x%x)   r0=0x%x r1=0x%x r2=0x%x r3=0x%x"
                  % (nm, o, ar[0] & 0xFFFFFFFF, ar[1] & 0xFFFFFFFF,
                     ar[2] & 0xFFFFFFFF, ar[3] & 0xFFFFFFFF))
        p()
        return rec

    # ---- S1..S3 寄存器原语 ----
    p("■ S1-S3 寄存器原语（验证 0x2082b0xx 的位语义）")
    scen("S1a OnOff(1)", 0x4CF3D4, [1], "Pulse/OnOff (+0x000 bit0) 置位")
    scen("S1b OnOff(0)", 0x4CF3D4, [0], "OnOff 清位")
    scen("S2a Pulse_cmd(1)", 0x4CF484, [1], "★ Load 启动脉冲 bit8 先置后清")
    scen("S2b Pulse_cmd(2)", 0x4CF484, [2], "★ Save 启动脉冲 bit4 先置后清")
    scen("S3a SetLUT0(addr,len,1)", 0x4CF4B4, [0x94000000, 0x4D00, 1], "写 +0x00c = LUT0 地址（Load 目标）")
    scen("S3b SetLUT1(addr,len,2)", 0x4CF4B4, [0x94000000, 0x4D00, 2], "+0x010 <- **第 2 参**（Save 目标），非第 1 参")

    # ---- S4 load_lut 3 参封装 ----
    p("■ S4 FUN_004a5c44(table, sel, fmt, 0) —— load_lut 的 3 参封装")
    for sel in (0, 1, 2):
        for fmt in (0, 1):
            scen("S4 sel=%d fmt=%d" % (sel, fmt), 0x4A5C44,
                 [0x94000000, sel, fmt, 0], "table=0x94000000 (Linux CMA，p7 可见)")

    # ---- S5 p7 侧完全封装 ----
    p("■ S5 FUN_00179384(table, sel, fmt, ptr) —— p7 侧 load/save 封装（含校验）")
    for sel, fmt in ((0, 0), (1, 0), (2, 0), (3, 0), (0, 2)):
        scen("S5 sel=%d fmt=%d" % (sel, fmt), 0x179384,
             [0x94000000, sel, fmt, 0], "sel>2 / fmt>1 应返回错误码")

    # ---- S6 View 静态 4 档选表 ----
    p("■ S6 FUN_0009a3e8(fmt, cbcr) —— View 路径静态 4 档选择器（纯查表）")
    for a, b in ((0, 0), (1, 0), (0, 1), (1, 1)):
        scen("S6 a=%d b=%d" % (a, b), 0x9A3E8, [0, a, b, 0],
             "返回 0x810fd100 族中的一档")

    # ---- S7 描述符解析 ----
    p("■ S7 FUN_004a5b6c(&desc) —— 描述符解析 -> 配置路径")
    desc_addr = 0x7E000000
    for mode, ch, fmt_ in ((0, 0, 0), (0, 1, 0), (0, 3, 0), (1, 0, 0)):
        emu.write_struct(desc_addr, bytes([mode, fmt_, ch, 0, 0, 0, 0, 0]))
        scen("S7 desc={mode=%d,fmt=%d,ch=%d}" % (mode, fmt_, ch), 0x4A5B6C,
             [desc_addr, 0, 0, 0], "ch>2 应拒绝")

    # ---- S8 MCB 侧跳转表 ----
    p("■ S8 FUN_003f2c60(r0=?, r1=?, r2=idx) —— MCB 侧跳转表选表 + tail-call")
    p("   ★ 跳转表 @0x3f2c70 倒序: idx1→0x3f2cc4 / 2→0x3f2cb0 / 3→0x3f2c9c / 4→0x3f2c80")
    p("   ★ 对应 4 张表: 0x813D8800 / 0x813DD500 / 0x813E2200 / 0x813E6F00 (等距 0x4D00)")
    for idx in (1, 2, 3, 4, 5):
        scen("S8 idx=%d" % idx, 0x3F2C60, [idx, 0x94000000, idx],
             "r2=idx 才是跳转索引；8=默认分支")

    json.dump(res, open(OUT_JSON, "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    open(os.path.join(ROOT, "raw8", "p7", "3dlut_qemu.txt"), "w",
         encoding="utf-8").write("\n".join(log) + "\n")
    print("写出: " + OUT_JSON)


if __name__ == "__main__":
    main()
