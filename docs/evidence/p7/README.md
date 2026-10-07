# p7 证据片段 / P7 Evidence Extracts

**日期** 2026-10-06 · **用途** 为 GitHub 读者保留可核对的原始依据

完整 Ghidra 导出（16466 个函数、20MB）体积过大，不入库。
这里只放**支撑文档结论的关键片段**，可与文档逐条比对。

---

## 文件说明

| 文件 | 内容 | 出处 |
|---|---|---|
| `3dlut_registers_from_p7.c` | ★ **3D LUT 全部寄存器定义**（150 行，12 处命中）| `53_all_pseudocode.c:641680+` |
| `50_page_table.txt` | p7 的 MMU 页表（16 个 PTE，1:1 映射）| Ghidra `SmaP7` |
| `50_virt2file.txt` | 虚拟地址 → 文件偏移换算 | Ghidra |
| `50_capdtm.txt` | capdtm 通道分析 | Ghidra `FindCapdtm` |
| `Ghidra_notes.md` | Ghidra 分析全程笔记（含定性速查表）| 当日工作笔记 |

---

## ★ 核心证据：3D LUT 的 5 个寄存器

`3dlut_registers_from_p7.c` 里是全部 12 处 `2082b0xx` 访问，对应**穷举确认的 5 个寄存器**：

```bash
grep -oE "2082b[0-9a-f]{3}" 53_all_pseudocode.c | sort -u
⇒ 2082b000  2082b004  2082b008  2082b00c  2082b010
```

| 寄存器 | 函数 | 语义 |
|---|---|---|
| `_DAT_2082b000` | `FUN_004cf3d4` | OnOff 总开关（bit0）|
| `_DAT_2082b004` | `FUN_004cf3fc/0414/042c/0444` | 通道选择与数据源（bits[1:0] / [5:4] / 8 / 12）|
| `_DAT_2082b008` | `FUN_004cf45c` / `FUN_004cf484` | 写启动脉冲（bit0）/ 读侧清理（bit8, bit4）|
| `_DAT_2082b00c` | `FUN_004cf4b4` | LUT0 数据地址 |
| `_DAT_2082b010` | `FUN_004cf4b4` | LUT1 数据地址 |

★ **没有 bypass/process 寄存器**（穷举确认）—— 这排除了"3DLUT 需要额外模式配置"的假设。

---

## ★ 关键函数索引

| 函数 | 地址 | 行数 | 作用 |
|---|---|---|---|
| `FUN_004cf3d4` | `0x4cf3d4` | 40 | OnOff |
| `FUN_004cf3fc` | `0x4cf3fc` | 24 | SelCbCr（bits[1:0]）|
| `FUN_004cf414` | `0x4cf414` | 24 | SelLUT（bits[5:4]）|
| `FUN_004cf42c` | `0x4cf42c` | 24 | LUT0 数据源（bit8）|
| `FUN_004cf444` | `0x4cf444` | 24 | LUT1 数据源（bit12）|
| `FUN_004cf45c` | `0x4cf45c` | 40 | ★ 写启动脉冲（bit0）|
| `FUN_004cf484` | `0x4cf484` | 48 | ★ 读侧清理 |
| `FUN_004cf4b4` | `0x4cf4b4` | 40 | SetAddress |
| `FUN_004a5c44` | `0x4a5c44` | 164 | **对外 API**：`(lut_phys, chan<3, mode<2)` |
| `FUN_004a5e30` | `0x4a5e30` | 448 | ★ **完整 6 步写入序列** |
| `FUN_0009a3e8` | `0x9a3e8` | 160 | ★ 从 4 个预置常量选一个返回 |

---

## ★ 4 个预置 LUT 缓冲（p7 `.data` 常量）

```c
DAT_003837f0 = 0x810fd100
DAT_003837f4 = 0x81106b00
DAT_003837f8 = 0x81115200    ★ 与实机实测 3DLUT +0x0c 的值完全一致
DAT_003837fc = 0x81101e00
```

★ 这 4 个地址超出 Linux `mem=512M`（上限 `0x20000000`），
也超出 p7 静态页表范围（`0x80000000..0x80ffffff`，见 `50_page_table.txt`）
⇒ **Linux 用户态无法读写它们。**

---

## ★ 256 字节对齐约束（双向交叉验证）

p7侧（`FUN_00179384`）：
```c
if ((param_1 & 0xff) == 0) { ... }   /* LUT 物理地址必须 256 对齐 */
```

用户态（libudd5 `d5_ep_3dl_save_lut`）：
```c
if ((phys & 0xff) != 0) return -301;
```

⇒ **两条独立证据完全对应**（内核态反编译 + 用户态反汇编）。

---

## 如何复核

完整伪代码可用 Ghidra 重新生成：

```
# p7_full.bin 来自 eMMC 分区 p7（rtos），13MB
# Ghidra: ARM:LE:32:v7，基址 0x80000000
# 或直接：objdump -D | grep 2082b0
```

对照文档：`docs/EP_3DLUT_WRITE_EXPERIMENTS_2026-10-06.md` §2。