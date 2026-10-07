# libudd5.so EP 色彩 API 静态分析

**导出** 2026-10-06 · **详情** `docs/archive/LIBUDD5_EP_API_MAP_2026-10-06.md`
**工具** `test_server/isp/udd5.py`（自研 ELF+Capstone，零 binutils 依赖）、`regmap.py`

---

## TL;DR

**魔灯（三星式全局色彩配方）不需要改 P7 固件。**

旧结论"3D LUT 写入者在内核态/ISP 固件"**作废**。
写入者是 **`libudd5.so` 用户态**，`di-camera-app` 动态加载它
⇒ 不在 import 表里 ⇒ 旧的"1092 imports 里 0 条 3dlut"是**假阴性**。

---

## 3D LUT 写入序列（静态闭合）

```c
d5_ep_3dl_load_lut(handle, lut_sel, buf, buf2):
    phys = d5_ep_sma_virt_to_phys(handle);      // ← 虚拟地址 → EP 物理地址
    assert(handle != 0);
    assert(lut_sel <= 2);          // {0,1,2}
    assert(buf == 0 || buf == 1);  // {0,1}
    return _udd_ep_3dl_ctrl_ConfigAccessMode({f0=1, f1=1, lut_sel, mode=1});
```

| mode | 路径 | 序列 |
|---|---|---|
| 1 (write) | `sub_3a888` | `OnOff(1)` → `Acc_OnOff(0)` → `Acc_OnOff(1)` → `SetAddress` → `SetColorFormat` |
| 2 (read) | `sub_3a9e0` | 同前 3 步 → **`SelLUT`** → `rw_Start` |

★ **写不调 `SelLUT`，读必须调** — 实现正确性的自检判据。

---

## 3DLUT 寄存器（块内偏移）

| 项 | 偏移 |
|---|---|
| **LUT0 数据地址** | `*(ep_3dlut_reg_base) + 0x0c` |
| **LUT1 数据地址** | `+0x10` |
| **握手/启动** | `+0x08` |
| 总开关 `OnOff` | `+0x64` / `+0x68` |
| 访问窗口 `Acc_OnOff` | `+0x6c` / `+0x70` |

### write-1-clear 脉冲握手

```c
v = GetReg(base + 0x08);
if (mode == 1) { v |=  0x100; SetReg(v); v &= ~0x100; SetReg(v); }  // write, bit8
else           { v |=  0x010; SetReg(v); v &= ~0x010; SetReg(v); }  // read,  bit4
```

★★ **3DLUT hardware only responds to an edge trigger.**
Writing a plain value to `+0x08` without the pulse **can never work** —
this explains every historical "wrote it, nothing happened".

---

## NOG gamma 档位根因

| API | 静态检查 | 含义 |
|---|---|---|
| `_udd_ep_nog_set_gamma` | `cmp r2, #0xf` | **γ ≤ 15 (4 bit)** |
| `_udd_ep_nog_set_std_sigma` | `cmp r3, #0x1f` | **σ ≤ 31 (5 bit)** |

⇒ **硬件 bit-width, not a body-side truncation.**
More levels would require patching the P7 fixed-point conversion.

---

## EP 块基址：GOT 槽 ↔ 实机 `/dev/mem`，10/10 双向闭环

| 全局符号 | GOT 槽 | 实机地址 |
|---|---|---|
| `ep_top_reg_base` | +0x4d4 | `0x20820000` ✓ |
| `ep_nog_reg_base` | +0x4e0 | `0x20821c00` ✓ |
| `ep_ldc_reg_base` | +0x50c | `0x20823000` ✓ |
| `ep_mc_reg_base` | +0x560 | `0x20824000` ✓ |
| `ep_rsz_reg_base` | +0x550 | `0x20826000` ✓ |
| `ep_lvr_reg_base` | +0x564 | `0x20827000` ✓ |
| `ep_bblt_reg_base` | +0x51c | `0x20828000` ✓ |
| `ep_fd_reg_base` | +0x530 | `0x20829000` ✓ |
| `ep_jpeg_reg_base` | +0x534 | `0x2082a000` ✓ |
| **`ep_3dlut_reg_base`** | **+0x528** | **`0x2082b000` ✓** |

### Other globals worth `dlsym`

| Symbol | GOT | Purpose |
|---|---|---|
| `g_d5_dev_ctx` | +0x524 | device context (real handle source) |
| `fd_ep` | +0x548 | **EP file descriptor** |
| `g_dev_id` | +0x4ec | device id |
| `path_ep_cs0` / `cs1` | +0x510 / +0x558 | **EP path 0/1** |
| `rgb2ycbcr_mtx_fd` + 7 more | +0x4f0..+0x564 | ★ **YCbCr↔RGB matrices/offsets = low-risk colour面** |

---

## Four ELF parsing traps (will bite again)

| # | Symptom | Root cause | Fix |
|---|---|---|---|
| 1 | disassembly **empty** | `va2off` checked `SHT_NOBITS(8)` | **`PROGBITS = 1`** (`NOBITS = 8`) |
| 2 | symbol names garbled | `entsize` is at **+36**, I read **+32** (`addralign`) | `link@24 info@28 addralign@32 entsize@36` |
| 3 | PLT names are fragments | ARM `Elf32_Rel`: `r_info = sym<<8 \| type` | not x86-64 Rela `sym<<32\|type`; **`>>8` not `>>12`** |
| 4 | wrong strtab | `.rel.plt.link`→`.dynsym`, `.dynsym.link`→`.dynstr` — **two levels** | `secs[rp['link']]` is the symtab, not strtab |

### PLT stub mapping (the key to linking user-space APIs to real calls)

```
stub_addr = plt.addr + 20 + k*12        # PLT0 header = 20 bytes
k = index into .rel.plt
```
⇒ `BL 0x84e0` reads as `BL _udd_ep_3dl_ctrl_ConfigAccessMode`, not a bare address.

### GOT literal pool: two distinct forms (I got this wrong first)

- `ldr rX,[pc,#N]` → **small integer** (e.g. `0x528`) = **GOT-relative slot offset**
- `ldr rX,[pc,#N]` → large value (e.g. `0x2a3f8`) = **`_GLOBAL_OFFSET_TABLE_` base**

Measured `GOT = 0x4a2c0`; `pc + 0x2a3f8 = 0x4a2bc = GOT - 4` (GOT0 slot placeholder).

---

## Next step: safe on-device verification (needs approval)

1. **Read-only** — `dlsym("g_d5_dev_ctx")` / `dlsym("fd_ep")` (zero risk)
2. **Read-only** — `d5_ep_open()` + `d5_ep_3dl_save_lut(h, 0, buf, buf2)` → read current LUT
3. **Single bit** — pulse `+0x08` (`|=0x100; &=~0x100`) only, no address write
   ⇒ should not alter the image

**Rules**: one step at a time · **camera must be in Liveview/capture state**
(EP mappings are built lazily ⇒ SIGBUS otherwise, iron rule 42) ·
never reuse another process's mmap pointers (the v4 crash).

---

## Artifacts

| File | Contents |
|---|---|
| `test_server/isp/udd5.py` | ELF + Capstone disassembler (6 subcommands) |
| `test_server/isp/regmap.py` | EP register offset extractor |
| `test_server/isp/out/ep_api_table.txt` | all EP/colour APIs + globals (434 lines) |
| `test_server/isp/out/regmap.txt` | 35 reg-layer functions (173 lines) |
| `test_server/isp/out/callgraph.txt` | static call graph (739 lines) |
| `test_server/isp/out/{3dlut,nog,mc}.asm` | full disassembly (937/968/924 lines) |