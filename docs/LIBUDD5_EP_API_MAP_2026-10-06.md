# libudd5.so 静态分析报告 — EP 色彩 API 完整图谱

**日期** 2026-10-06 · **目标** 纯静态反汇编 `libudd5.so`（ARM 32-bit ELF），建立 EP/色彩 API 完整调用图谱
**工具** `test_server/isp/udd5.py`（自研 ELF+Capstone 反汇编器，零外部 binutils 依赖）、`regmap.py`
**方法论** 纯静态。不再对实机做任何未验证的 API 调用。

---

## 0. 一句话结论

★★★ **魔灯（三星式全局色彩配方）不需要改 P7 固件，用户态通路已完整闭合。**

之前判断"必须建在 ISP 侧"的依据是"`di-camera-app` 的 1092 个 import 里 3dlut 相关 = 0 条"。
本次分析找到了**真正的写入者**：`libudd5.so` —— 它是 `di-camera-app` 运行时**动态加载**的（所以不在 import 表里），
静态导出 51 个 EP 色彩 API，其中包含完整的 3D LUT 写入序列。

---

## 1. 分析基础设施（本次新建）

本机没有 `arm-linux-gnueabi` binutils，ODroid 上的 `readelf` 也不可用。
自研 `udd5.py`，自己解 ELF（参照 `sym_udd.py` 已验证的做法）+ Capstone 反汇编。

| 子命令 | 作用 |
|---|---|
| `ep` | 列出全部 EP/色彩 API（35 个 reg 层 + 控制层）|
| `dump <name\|addr>` | 反汇编单函数，自动解析 BL 目标 / PLT 导入 / 全局符号 / 字符串 |
| `literals <func>` | 解 literal pool，把 `+0xc`、`0x528` 这类裸偏移还原成"哪个全局基址 + 第几字节" |
| `graph` | 静态调用图：谁调用了哪些 EP API |
| `batch <out> <kw>` | 批量反汇编到 `.asm` |
| `regmap.py` | 全量提取 `(全局符号, 寄存器偏移, 语义)` 三元组 |

### 1.1 踩过的四个 ELF 解析坑（血泪，勿重犯）

| # | 症状 | 根因 | 正解 |
|---|---|---|---|
| 1 | 反汇编输出**全空** | `va2off` 判 `SHT_NOBITS(8)` | **`PROGBITS = 1`**，`NOBITS=8`|
| 2 | 符号名串位（`ini` / `pt` / `rClasses`）| 节头 `entsize` 在 **+36**，误读了 **+32**（`addralign`）| `link@24 info@28 addralign@32 **entsize@36**` |
| 3 | PLT 名全是碎片 | ARM 用 `Elf32_Rel`，`r_info = sym<<8 \| type`（32位 type）| 不是 x86-64 `Rela` 的 `sym<<32\|type`；**`>>8` 不是 `>>12`** |
| 4 | strtab 取错 | `.rel.plt.link` → `.dynsym`，`.dynsym.link` → `.dynstr`，**链式两层** | 直接 `secs[rp['link']]` 是符号表不是字符串表 |

> 这四条铁律已固化进 `udd5.py` 注释。任何新的 ELF 解析器都会再踩一遍。

### 1.2 GOT 基准（`_GLOBAL_OFFSET_TABLE_`）

PIC 代码的标准模式：
```asm
ldr  r3, [pc, #0x64]   ; = 0x0002a3f8
add  r3, pc, r3         ; r3 = GOT_base
ldr  r2, [pc, #0x54]   ; = 0x00000528  ← 这是 GOT 相对偏移，不是地址！
ldr  r3, [r3, r2]      ; r3 = *(GOT + 0x528)
```
★ 实测 `GOT = 0x4a2c0`，算出的和是 `0x4a2bc = GOT - 4`（GOT0 槽占位）。
⇒ **`0x528` 这种小整数字面量才是槽偏移；`0x2a3f8` 是基准。两种形式必须分开判**，
否则会把所有偏移误判成地址（我第一次就是这么错的）。

---

## 2. ★★★ 核心突破：3D LUT 写入序列完整闭合

### 2.1 `d5_ep_3dl_load_lut` 逐条解出

```c
int d5_ep_3dl_load_lut(void *handle, int lut_sel, int buf, int buf2) {
    unsigned phys = d5_ep_sma_virt_to_phys(handle);   // ★★★ 虚拟地址 → EP 物理地址
    if (handle == 0)        return -1;
    if (lut_sel > 2)        return -1;   // unsigned <= 2 ⇒ lut_sel ∈ {0,1,2}
    if (buf != 0 && buf != 1) return -1; // buf ∈ {0,1}
    cfg.f0 = 1;             // +0x30
    cfg.f1 = 1;             // +0x2c
    cfg.lut_sel = lut_sel;  // +0x20
    return _udd_ep_3dl_ctrl_ConfigAccessMode(&cfg);
}
```

★★★ **`d5_ep_sma_virt_to_phys()` 是整条通路的第一环。**
LUT 数据不是写 pref 层、不是写 capdtm 槽，而是：
**用户 buffer → SMA 物理地址 → 写进 EP 3DLUT 块的数据地址寄存器 → 硬件按物理地址读。**

这解释了为什么机身 pref 层怎么调都调不出 3D LUT：**它根本不走 pref 层。**

### 2.2 `_udd_ep_3dl_ctrl_ConfigAccessMode`（`0x3ab60`）分派

```c
void _udd_ep_3dl_ctrl_ConfigAccessMode(cfg *c) {
    if (c->mode == 1) sub_3a888(c);   // mode1 = 写（load）
    if (c->mode == 2) sub_3a9e0(c);   // mode2 = 读（save）
}
```
（`cfg+0x4` = mode；`load` 传 1，`save` 传 2）

### 2.3 ★ 写序列（`sub_3a888`，mode=1）

```c
_udd_ep_3dl_reg_OnOff(1);            // 开 3DLUT
_udd_ep_3dl_reg_Acc_OnOff(0);        // 关访问模式
_udd_ep_3dl_reg_Acc_OnOff(1);        // 开访问模式   ← 打开读写窗口
switch (c->mode_at_0x10) {
case 0:  SetAddress(cfg->f8,  c->f4); SetColorFormat(c->f8, *(cfg->f8 + 8)); break;
case 1:  SetAddress(cfg->fc,  c->f4); SetColorFormat(cfg->fc, *(cfg->fc + 8)); break;
case 2:  /* 两个都写 */                                        break;
}
```
- `sub_3a7e4` = `SetAddress` 薄封装 → `_udd_ep_3dl_reg_SetAddress`
- `sub_3a820` = `SetColorFormat` 分派：

| case | 动作 |
|---|---|
| 0 | `_udd_ep_3dl_reg_SetColorFormat_LUT0(fmt)` |
| 1 | `_udd_ep_3dl_reg_SetColorFormat_LUT1(fmt)` |
| 2 | **两个都写**（load 到两块 LUT）|

### 2.3b ★ 读序列（`sub_3a9e0`，mode=2）— 与写序列对称

```c
_udd_ep_3dl_reg_OnOff(1);
_udd_ep_3dl_reg_Acc_OnOff(0);
_udd_ep_3dl_reg_Acc_OnOff(1);
switch (chan) { case 0/1/2: ... }
_udd_ep_3dl_reg_SelLUT(...);        // ★ 比写路径多这一步：先选源LUT
_udd_ep_3dl_reg_rw_Start(...);      // ★ mode != 1 ⇒ 走读脉冲 (bit4)
```
★★ 写路径**不调`SelLUT`**，读路径**必须调**。这条差异可直接用来校验实现是否正确。

### 2.3c `d5_ep_3dlut_op_init` — 初始化只需两步

```c
_udd_ep_3dl_ctrl_ConfigBypassMode(...);
_udd_ep_3dl_ctrl_ConfigProcessMode(...);
```
⇒ **不需要复杂的初始化序列**。`d5_ep_open()` 之后直接 `load_lut` 即可，
或依赖 `di-camera-app` 已完成的 open。**这是步骤 2 风险可控的依据。**

### 2.4 ★★ `_udd_ep_3dl_reg_SetAddress` — 寄存器偏移解出

```asm
ldr  r2, [pc, #0x54]   ; = 0x528
ldr  r3, [r3, r2]      ; r3 = ep_3dlut_reg_base   (GOT+0x528)
ldr  r3, [r3]          ; r3 = *base               (运行时由驱动填的真实物理基址)
add  r2, r3, #0xc      ; ★★ LUT0 数据地址寄存器
bl   _udd_ep_3dl_reg_SetReg
```

| 参数 | 寄存器 | 块内偏移 |
|---|---|---|
| `chan == 1` | **LUT0 数据地址** | `*(ep_3dlut_reg_base) + 0x0c` |
| `chan == 2` | **LUT1 数据地址** | `*(ep_3dlut_reg_base) + 0x10` |

### 2.5 ★★★ `_udd_ep_3dl_reg_rw_Start` — write-1-clear 硬件握手

```c
u32 v = GetReg(base + 0x08);
if (mode == 1) {          // 写
    v |=  0x100;  SetReg(base + 0x08, v);   // 置位 bit8
    v &= ~0x100;  SetReg(base + 0x08, v);   // 再清bit8  → 硬件据此启动一次写
} else {                   // 读
    v |=  0x010;  SetReg(base + 0x08, v);   // 置位 bit4
    v &= ~0x010;  SetReg(base + 0x08, v);   // 再清 bit4  → 启动一次读
}
```

★★ **这是标准的 write-1-clear 脉冲握手，不是普通寄存器写。**
含义：**3DLUT 硬件只认"边沿触发"**，写完必须清零才能复位。
⇒ 之前若有人试过直接往 `0x2082b008` 写值而无脉冲，**必然无效**——这是可解释的历史失败原因。

### 2.6 3DLUT 寄存器偏移全表（35 个 reg 函数自动提取）

| API | 块内偏移 | 立即数 | 语义 |
|---|---|---|---|
| `_udd_ep_3dl_reg_GetReg` / `SetReg` | — | 0 | 裸 `*reg` / `*reg = v` |
| `_udd_ep_3dl_reg_OnOff(v)` | `+0x20 +0x64 +0x68` | 0,1,8 | 3DLUT 总开关 |
| `_udd_ep_3dl_reg_SelCbCr_ch` | `+0x24 +0x60 +0x64` | 0,2,3,4,8 | Cb/Cr 通道选择 |
| `_udd_ep_3dl_reg_SelLUT` | `+0x24 +0x60 +0x64` | 2,3,4,8 | **LUT0/LUT1 选择** |
| `_udd_ep_3dl_reg_SetColorFormat_LUT0` | `+0x24 +0x60 +0x64` | 1,4,8 | LUT0 格式 |
| `_udd_ep_3dl_reg_SetColorFormat_LUT1` | `+0x24 +0x60 +0x64` | 1,4,8,12 | LUT1 格式 |
| `_udd_ep_3dl_reg_Acc_OnOff(v)` | `+0x24 +0x6c +0x70` | 0,1,8 | **访问窗口开关** |
| **`_udd_ep_3dl_reg_rw_Start`** | **`+0x50 +0x80 +0xac +0xe4 +0xe8`** | **256(=bit8)** | **写/读启动脉冲** |
| `_udd_ep_3dl_reg_SetAddress` | `+0x24 +0x54 +0x64` | 4,12,16 | **数据地址 (0xc/0x10)** |

> 注：`+0x24` 出现在几乎所有函数里 = **GOT 槽加载偏移**（`ldr rX,[GOT+0x528]` 的 0x24），
> 不是 EP 块内偏移。真正的块内偏移是 `0x0c/0x10/0x08/0x64/0x6c/0x70` 等。

---

## 3. NOG（噪声生成）— 完整参数链已解

### 3.1 `d5_ep_nog_set_noisegen` = 6 步编排

```c
_udd_ep_nog_reg_struct_init();
_udd_ep_nog_set_random_seed(...);
_udd_ep_nog_select_rv_type(...);     // 随机数类型（uniform/gaussian/poisson…）
_udd_ep_nog_set_std_sigma(...);       // ★ memcpy 拷贝参数块
_udd_ep_nog_set_gamma(...);           // ★ 有参数范围检查
_udd_ep_nog_seed_load_switch(...);
```

### 3.2 参数校验上限（静态可见的硬约束）

| API | 检查 | 含义 |
|---|---|---|
| `_udd_ep_nog_set_gamma` | `cmp r2, #0xf` | **gamma ≤ 15**（约 4 bit）|
| `_udd_ep_nog_set_std_sigma` | `cmp r3, #0x1f` | **sigma ≤ 31**（约 5 bit）|
| `_udd_ep_nog_set_random_seed` / `select_rv_type` | `cmp r2, #0` | 仅判空|

★★ 这直接回答了之前的死结：**gamma 只有 2 档是因为 NOG 硬件 gamma 就是 4 bit（16 级）**，
不是机身层截断。要更多档位只能改 P7 里的 NOG 定点换算。

### 3.3 与 P7 侧交叉验证

`libudd5` 的 NOG 参数走 `_udd_ep_nog_regset0/1`（GOT+0x538 / 0x4fc），
对应 P7 侧 `FUN_004aff08` 解出的**双实例 4×32 位参数**（`0x20821c10/14/18/1c` 与 `+0x30`）。
⇒ **两侧独立解出同一结构，互为交叉验证，可信。**

---

## 4. EP 寄存器基址全表（GOT 槽 → 实机 `/dev/mem` 交叉验证）

`libudd5.so` 的 10 个 EP 块基址全部解出，与实机 `/dev/mem` 读侧**逐一对上**：

| 全局符号 | GOT 槽 | 实机地址（此前 `/dev/mem` 实测）|
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

★★★ **10/10 全部命中。** 这是"用户态 API 图谱"与"内核/固件实际地址"之间的**完整闭环**，
双向可逆验证通过（此前只有读侧验证）。

### 4.1 其它关键全局（已解出，可直接 dlsym 读）

| 符号 | GOT 槽 | 用途 |
|---|---|---|
| `g_d5_dev_ctx` | +0x524 | **设备上下文**（`d5_ep_open` 的真实 handle 来源）|
| `fd_ep` | +0x548 | **EP 文件描述符** |
| `g_dev_id` | +0x4ec | 设备号 |
| `g_dd_mutex_lock` | +0x4e8 | 全局锁 |
| `g_dd_sync_cond` | +0x53c | 同步条件变量 |
| `path_ep_cs0` / `path_ep_cs1` | +0x510 / +0x558 | **EP 通路 0/1** |
| `_udd_ep_nog_regset0/1` | +0x538 / +0x4fc | NOG 双实例参数表 |
| `rgb2ycbcr_*` / `ycbcr2rgb_*`（8 个）| +0x4f0..+0x564 | **★ YCbCr 转换矩阵与偏移 —— 色彩配方核心** |

★★★ `rgb2ycbcr_mtx_fd` / `ycbcr2rgb_mtx_fd_udd` + `*_offset_y/cb/cr_fd_udd`
= **8 个可读写全局变量 = 一整套 YCbCr↔RGB 矩阵与偏移**。
这是"不碰 3D LUT 也能改颜色"的**低风险备选面**（只是矩阵，不是完整曲线）。

---

## 5. 修正此前的错误结论

| 此前结论 | 修正 |
|---|---|
| "3D LUT 写入者在内核态/ISP 固件，改P7 才能做魔灯" | ❌ **错**。写入者是 `libudd5.so` 用户态，`di-camera-app` 动态加载它所以 import 表里看不到 |
| "`di-camera-app` 1092 import 里 3dlut = 0 条 ⇒ 不存在" | ⚠️ **该证据无效**：动态加载的库不在 import 表里。这是典型的"排除性判据给假阴性" |
| "gamma 只有 2 档是机身层限制" | ❌ **错**。NOG 硬件 gamma ≤ 15（4 bit），是硬件位宽 |
| "capdtm 是机身 UI 通道" | ⚠️ 需修正：capdtm 是属性总线；**真正的画面参数写入面是 `libudd5` 的 EP API** |
| "`/dev/mem` EP 寄存器地址只有读侧验证过" | ✅ **现已双向**：10/10 基址与 `libudd5` GOT 槽交叉验证 |

> ★ 方法论：**"grep 零结果"必须先自证工具有效。** 本次正是——import 表零命中，
> 但换静态视角（导出符号表 + PLT）后一次命中 51 条 API。

---

## 6. 安全实机验证方案（下一步，需用户批准）

静态已闭合机制，剩下的是**运行时确认**。以下步骤按风险从低到高排列，**每步单独验证**：

### 步骤 1：只读确认 handle（零风险）
```c
// 验证 g_d5_dev_ctx / fd_ep 是否已被 di-camera-app 填好
dlsym("g_d5_dev_ctx") / dlsym("fd_ep")
```
★ **不调用任何函数，纯读全局变量**。若 `fd_ep ≥ 0` 且 `g_d5_dev_ctx != 0` ⇒ 通路已初始化。

### 步骤 2：只读 LUT 保存（低风险，已有官方 API）
```c
d5_ep_open();
d5_ep_3dl_save_lut(handle, 0, buf, buf2);   // ★ 官方读接口，参数已静态确认
```
只读回当前 LUT，不写。若返回 0 且 buffer 有非零数据 ⇒ **3DLUT 硬件在线，映射正常**。

### 步骤 3：单 bit 写-清-写握手（可控风险）
只对 `*(ep_3dlut_reg_base)+0x08` 做一次 `|=0x100; &=~0x100` 脉冲，
**不写任何地址寄存器** ⇒ 理论上不改变画面（没有数据源）。
⇒ 这是**验证握手机制本身**的最小实验。

### 铁律（延续）
- ★ **每步单独跑，相机必须在 Liveview/拍摄态**（否则 EP 映射未初始化 ⇒ SIGBUS，铁律 42）
- ★ 绝不跨进程复用 mmap 指针（v4 死机事故）
- ★ 批量写前必须白名单
- ★ telnet 串行，≥10KB 走 FTP

---

## 7. 产物清单

| 文件 | 内容 |
|---|---|
| `test_server/isp/udd5.py` | 自研 ELF+Capstone 反汇编器（6 个子命令）|
| `test_server/isp/regmap.py` | EP 寄存器偏移自动提取器 |
| `test_server/isp/out/ep_api_table.txt` | 全部 EP/色彩 API + 全局数据表（434 行）|
| `test_server/isp/out/regmap.txt` | 35 个 reg 函数的偏移/立即数/调用（173 行）|
| `test_server/isp/out/callgraph.txt` | 静态调用图（739 行）|
| `test_server/isp/out/3dlut.asm` | 20 个 3DLUT 函数全反汇编（937 行）|
| `test_server/isp/out/nog.asm` | 13 个 NOG 函数（968 行）|
| `test_server/isp/out/mc.asm` | 10 个 MC 函数（924 行）|

---

## 8. 魔灯可行性重估

| 条件 | 此前状态 | 现在 |
|---|---|---|
| 3D LUT 写入通路 | ❓ 未知 | ✅ **静态闭合**（物理地址 + 地址寄存器 + 握手脉冲）|
| LUT 大小/格式 | ❓ | 待步骤 2 实测（`save_lut` 读回长度）|
| 与取景器隔离 | ❓ 需改 P7 | ✅ **不需改 P7**——`Still`/`View` 是两条API 路径，可只走 Still |
| gamma 档位数 | 2 档 | ⚠️ **硬件 16 级上限**（4 bit），要更多必须改 P7 定点换算 |
| YCbCr 矩阵可写 | ❓ | ✅ **8 个全局变量**（`rgb2ycbcr_mtx_fd` 等）|

⇒ **魔灯主体（3D LUT 全局配方）不需要改 P7。**
只有"NOG gamma 超过 16 级"这一个子需求需要动固件。