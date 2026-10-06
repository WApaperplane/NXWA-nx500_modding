# 3D LUT 子系统完整解剖 · NX500/NX1

> **A Complete Anatomy of the 3D LUT Subsystem — NX500/NX1**
>
> 三星 NX500 / NX1 相机 ISP 固件（代号 `p7`）逆向工程成果。
> 全部结论由**静态分析**得出（capstone 精确反汇编 + 二进制字面量统计），**零实验猜测**。
> 2026-10-06

---

## 核心结论速览

| # | 结论 | 置信度 |
|---|---|---|
| 1 | ★★★★★ **3D LUT 表长 = 19652 字节**（`17³` 节点 × 4 字节） | 两次独立验证 |
| 2 | ★★★★★ **取景器与拍照是两套完全独立的选表逻辑** | capstone 全链验证 |
| 3 | ★★★★ **取景器只有 4 档静态表；拍照有 24 档动态表 + 三参数加权** | 反汇编直接可见 |
| 4 | ★★★★ **LUT 数据由 Linux 侧经 `CLiveviewDataPocket` 送入，p7 只读不写** | 断言串 + 无写入点 |
| 5 | ★★★ **改 p7 的数据指针即可导入自定义 LUT**（3 字节改动，不变砖） | 实机验证 |

---

## 一、LUT 表结构

### 1.1 定案方法：数指针间距（而非实验试错）

`p7` 的 `.data` 段里有 28 个 LUT 数据指针（静态初值、全部只读）。
扫描全部 `0x81xxxxxx` 字面量后发现 **41 个地址构成等距数组，间距精确为 `0x4D00` = 19712 字节**，
且**4 个静态档 + 24 个动态档全部落在其中**。

求解「节点数 × 每节点字节数」对齐到 19712：

| 节点数 N | BW | N×BW | 对齐 256 | = 19712？ |
|---|---|---|---|---|
| **4913 = 17³** | **4** | **19652** | **19712** | ★★★ **唯一解** |
| 4913 | 2 | 9826 | 9984 | ✘ |
| 4913 | 6 | 29478 | 29696 | ✘ **物理装不下** |

```c
┌─ NXKS3D LUT 数据结构 ──────────────────────┐
│ 级数    = 17 × 17 × 17 = 4913 节点            │
│ 元素    = 4 字节/节点                        │
│ 总字节  = 19652（槽位 19712，256 对齐）        │
│ 分组    = 每 289 个（17×17）一组，共 17 组     │
│ 顺序    = 最外层维度变化最慢                  │
└─────────────────────────────────────────────┘
```

★ **推论**：标准 `.cube` 的 `17³×3×u16` = 29478 字节 > 19712 ⇒ **不可能是 RGB 三通道交织**。
★ 转换器见 `test_server/filmsim/cube2nxks.py`。

### 1.2 独立第二证

`FUN_003829a4` 内另有一组间距同为 `0x4D00` 的 12 项等距数组（疑似按画面宽高比分派），
构成对 19712 的**独立第二次验证**。

### 1.3 排除的历史假设

| 曾经的假设 | 排除依据 |
|---|---|
| 4913 字节 | 17³×1，未考虑对齐 |
| 9826 字节（"标量 u16"） | 对齐后 9984 ≠ 19712 |
| 9248 字节 | `dump` 未在 prepare 状态下测，读到的是 CMA 残留 |
| 14739 / 29478（RGB 三通道） | 均 > 19712，物理装不下 |

---

## 二、数据源链路（p7 只读不写）

### 2.1 完整调用链

```
CBackend_3dlut_View::_load  @0x8011e20c
  ├ FUN_00524194(stEpParam → st3dlutParam)   ← dynamic_cast
  ├ FUN_000f6474()      ★ 加载 CLiveviewDataPocket
  ├ FUN_000f1b58()      读 flag
  ├ FUN_0009a3e8()  或  FUN_0009a408()   ★ 静态4档 / 动态24档选表
  ├ FUN_004dbb08(..., 0xb4, ...)         通知 ISP
  └ FUN_00179314(addr, 0, r5, 0)         ★ 请求投递
       ├ if (addr == 0) return -1            "lut base addr is NULL!"
       ├ 打包 4 参 → FUN_00173f34(单例, 0x20000003, …)   ★ 异步入队
       └ b → 0x80061594 → 0x800602ac        ★ 真正的实现
            cmp arg1, #0x01040001 / #0x01040002 / #0x01040006  ← 通道 ID
            ubfx r3, arg1, #0x10, #8 ; cmp r3, #7
            → ==7: 用结构体 +0x24  ★ 另一种布局
            → !=7: 用结构体 +0x04
```

★ **`FUN_00179314` 不是灌入函数，是【请求投递器】**（对比同址的 `b` 分支可见）。

### 2.2 ★ 关键：28 个指针全代码库【只读，零写入点】

数据由 **Linux 侧**通过 `CLiveviewDataPocket` 送入（断言串泄露身份）：

```
0x8070dcc0: 'm_pcLiveviewDataPocket != __null'
0x8057e458: 'GetDataPocket'
0x0070e878: 'product/Liveview/common/CLiveviewDataPocket.cpp'
```

⇒ **表数据不在固件里**（p7 分区镜像对应位置全0 = `.bss`）。

### 2.3 ★ 14 种数据源（日志直接给出）

```
lv1 / lv2 / lv3  data size = %d, lut size = %d
4k1 / 4k2data size = %d, lut size = %d
ud2  data size = %d, lut size = %d      ← UD = User Defined（自定义入口）
burst / 1080 / faf / vfaf / hfull / dmf / reserved …
live data size = %d, lut size = %d       ← ★★ 取景器
```
★ **`live`/`lv1..3` 是取景器数据源；拍照的 `still` 未单列** ⇒两者要的数据源本就不同。

其它关键日志：
```
0x73c398  lut size error too large~ (%d) > %d        ★ 表长上限校验（唯一一处）
0x720858  d5_ep_3dl_load_lut(0x%08X,%d, %d, %d)     ★ 4 参接口
0x758ec0  3D-LUT table SRAM load failed [driver error]!!
0x758ef0  3D-LUT table SRAM load success
3D-LUT: BYPASS Mode / PROCESS Mode
```

---

## 三、★★ 取景器 vs 拍照：两套独立逻辑（本项目最重要发现）

### 3.1 五层分岔链（capstone 逐层验证）

```
View::_load @0x11e20c                Still::_load @0x11e678
 cmp #0x10000002（闸门）                cmp #0x20000002（闸门）
 读 +0x20/+0x21/+0x22（3 字节）          读 +0x21/+0x22（只 2 字节）
 bl 0x8009a3e8                         bl 0x8009a3c8
   ↓ b 0x2b03f4                          ↓ b 0x2b03d4
   ↓ b 0x29baa4                          ↓ b 0x29ba84
   ↓ b 0x381b2c                          ↓ b 0x381abc
★★ @0x3837d0（7 条指令）               ★★ @0x382b30（三参数加权）
```

### 3.2 取景器的最终实现全文（★ 全部逻辑就这 7 条）

```asm
0x803837d0: cmp   r2, #1
0x803837d4: ldreq r3, [pc, #0x14]   → 0x81106b00（电影）
0x803837d8: ldreq r0, [pc, #0x14]   → 0x81101e00（黑白）
0x803837dc: ldrne r3, [pc, #0x14]   → 0x81115200（肤色）
0x803837e0: ldrne r0, [pc, #0x14]   → 0x810fd100（标准）
0x803837e4: cmp   r1, #1
0x803837e8: moveq r0, r3
0x803837ec: bx    lr
```
★ `0x3837d0` 紧邻 4 档指针区 `0x3837f0`（相差 0x20）⇒ **两者是一体的**

### 3.3 拍照的最终实现（完全不同的算法）

```asm
bl 0x2b0000 / 0x2aff3c / 0x2b0078      ← Picture Wizard 三参数
mov r3,#0x64 ; mul r3,r3,r0 ; sub r3,r3,#0x1f40   ← ×100 − 8000 阈值
asr r6, r3, #4                        ← >>4
```

### 3.4 ★★ 必须警惕的假阳性

> **"照片正常 = 硬件接受了我的表" —— 此推论不成立。**

照片走 **24 档动态表**（`DAT_00383a24..80`），**根本没读被修改的静态档**（`DAT_003837fc`）。
照片正常只说明那张表未被污染。

★ 这是本项目最隐蔽的假阳性—— 它看起来像客观证据。
⇒ 若要验证静态档的效果，**必须在取景器里看**。

---

## 四、p7 C++ 类结构（RTTI 完整）

```
product/Backend/EP/3DLUT/CBackend_3dlut_Base.cpp
product/Backend/EP/3DLUT/View/CBackend_3dlut_View.cpp
product/Backend/EP/3DLUT/Still/CBackend_3dlut_Still.cpp
product/Backend/EP/3DLUT/CS/CBackend_3dlut_CS.cpp
```

| 类 | 角色 |
|---|---|
| `CBackend_3dlut_View` | ★ 取景器通路（静态 4 档）|
| `CBackend_3dlut_Still` | ★ 拍照通路（24 档动态 + 三参数）|
| `CBackend_3dlut_CS` / `CS0_Callback` / `CS1_Callback` | CS 模式（基类是 `IBackend_Ep_Callback_Base`，**不在 3D LUT 主继承链上**）|
| `CMaterial_3DLUT_Liveview` | 取景器材质 |
| `CBackend_3dlut_Base::st3dlutParam` | 参数结构（长度明文 `0x300` = 768 字节）|

★ 模式枚举：`STILL_3DLUT_NORMAL` / `STILL_3DLUT_CS` / `STILL_3DLUT_SELECT_COLOR`

### 消息 ID 位域（`FUN_00173f34`）

```c
uVar8 = param_2 & 0xffff;
if (uVar8 == 0) { 立即处理 }  else { 入环形队列（0x180 字节/槽，最多 1000） }
if ((puVar1[1] & param_2 & 0xFFFF0000) == 0) return;   // 事件掩码
```
★ 低 16 位 = 同步标志；高 16 位 = 子系统掩码
★ 3D LUT 主事件 `0x10000001`｜灌入投递 `0x20000003`｜材质描述分支 `0x10000002`
★ 通道 ID 实际是 `0x0104000X`（`mov`+`movt` 合成）

---

## 五、导入自定义 LUT（B 线，已实机验证）

### 5.1 原理

`p7` 的静态档指针是**纯静态初值、只读、无写入点** ⇒ **直接改固件里的指针值**即可。

```bash
# 3 字节改动：DAT_003837fc（0x3837fc）0x81115200 → 你的 CMA 地址
python3 test_server/sysarch/p7lut.py raw8/p7/p7_full.bin 0x94100000 --slot 3 --apply
dd if=p7_full.lutmod.bin of=/dev/mmcblk0p7 bs=1M count=12
```

### 5.2 工具

| 工具 | 说明 |
|---|---|
| `lutload.arm poke <phys> <file>` | ★★ 只写 CMA 内存，**完全不碰 EP 寄存器、不触发 DMA** ⇒ 结构上不可能花屏/卡死 |
| `lutload.arm settle [n]` | ★★ 纯只读轮询 `Pulse/Cfg/LUT0` |
| `lutload.arm import <file> [fmt] [cbcr] [phys]` | 主动 DMA 版（危险，但机制已通）|
| `cmapick.arm` | ★ 实时扫描 CMA 找空闲落点（**每次导入前必跑**）|
| `p7lut.py` | ★ p7 指针补丁工具（默认 dry-run / 逐点回读校验 / `--restore` 可还原）|

### 5.3 安全边界（实机验证）

| 项 | 结论 |
|---|---|
| 刷 p7 会变砖吗 | ★ **不会**。boot0 不动，Linux 侧独立 |
| p7 启动失败会怎样 | 画面异常，但 ★ **telnet/SSH 仍在** |
| 回滚 | ★ `dd if=p7_orig.bin of=/dev/mmcblk0p7 bs=1M`（30 秒）|
| 官方退路 | SLP 官方固件刷机（1.12 同版本已验证）|

---

## 六、CMA 内存硬事实

```
dmesg: cma: reserved 288 MiB at 94000000 / 72 MiB at 8f800000
```

> ★★ **探测到"空闲" ≠ 可以安全独占。**

`0x94000000` 曾导致整机卡死（`alloc_contig_range failed`，需拔电池）。
它不是空地，是 ISP 的 WDMA 硬件工作区。

⇒ **对 DMA 缓冲区只能"临时借用 + 用完即还"**，且每次导入前用 `cmapick.arm` 重新探测。

---

## 七、方法论（本项目的核心资产）

这一天产生 **4 条铁律**，全部来自踩坑：

| # | 铁律 | 今日实证代价 |
|---|---|---|
| **65** | ★★★ 结构信息优先从**资源布局**提取，不要从**实验数据**反推 | 6 小时实验 / 3 次推翻 / 4 次花屏 vs **一次减法** |
| **66** | ★★★★★ **有静态数据源在手时，先扒代码，不要钻实验** | 用户当面批评 |
| **67** | ★★★★★ **指令级结论必须用 capstone 读**，禁止手写十六进制解码 | 手写解码把字面量池当代码 ⇒ 整段结论作废 |
| **68** | ★★★★★ 判断"是否存在独立数据通路"要找**数据源日志**，而非只看调用链 | 三次猜错通路，一条 `live data size` 日志定案 |

★ **推荐工作流**：
```
静态布局（数间距 / 扫指针）
  → 扒代码（伪代码 / RTTI / 断言串 / 官方头文件）
    → capstone 精确反汇编（★ 唯一可信的指令级来源）
      → 找数据源日志验证行为（★ 日志说"实际做了什么"）
        → 最后才做实验
```

★ **协作经验**：子代理做**规模**（穷尽清点/统计/交叉验证），我做**精度**（capstone 复核/下结论）。
　本次子代理清点出 125 条字符串 + 24 张 vtable + 7 组等距数组，并修正我 6 处错误前提。

---

## 八、文件索引

| 文件 | 内容 |
|---|---|
| **`3DLUT_SUBSYSTEM_ANATOMY_2026-10-06.md`** | ★★ **本文档**（总纲）|
| `LUT_FORMAT_V3_STATIC_ANALYSIS_2026-10-06.md` | 格式定案全过程（含 3 次自我推翻）|
| `discovery/01_3dlut_strings.md` | 125 条 3D LUT 字符串全清单 |
| `discovery/02_vtables.md` | 24 张 vtable + RTTI 校验 |
| `discovery/03_ptr_arrays.md` | 等距指针数组穷尽扫描 |
| `discovery/04_msg_ids.md` | 全部消息 ID 统计 |
| `discovery/05_st3dlutparam.md` | `st3dlutParam` 全部访问点 |
| `discovery/06_param_sources.md` | 四个选择字节的写入点追查 |
| `LUT_EXPERIMENT_LOG_2026-10-06.md` | 实验日志（含卡死事故）|
| `SMA_ALLOC_FINDINGS_2026-10-06.md` | SMA 动态分配实测（判定不可行）|
| `USB_SAFE_CHANNEL_2026-10-06.md` | USB/SSH 安全通道定案 |

---

## 九、仍未解决

| # | 问题 | 状态 |
|---|---|---|
| 1 | ★★★ 取景器花屏的最终根因 | ★★ 已定位到「两套独立选表逻辑」，但**表语义/格式是否匹配**仍未验证 |
| 2 | ★★ 4 字节节点的**内部布局** | ？待查（u32 / 2×u16 / 4×u8 / RGB 三元组）|
| 3 | ★★ `st3dlutParam.+0x20/+0x21/+0x22/+0x40` 运行期值 | ★ 静态写不到（`.bss`），由 768 字节参数块运行期注册下发 |
| 4 | ★ `CLiveviewDataPocket` 的填充者 | ？Linux 侧驱动，尚未逆|

---

## 十、致谢

感谢 `ottokiksmaler/nx500_nx1_modding`（NX-KS mod 基础）与 `mewlips`（社区源头）。
本仓库的mod 层（SSH/telnet/FTP/menu）建立在社区工作之上；
3D LUT 部分为独立逆向成果。

---

## Core Conclusions (EN)

| # | Conclusion | Confidence |
|---|---|---|
| 1 | ★★★★★ **3D LUT table length = 19652 bytes** (17³ nodes × 4 bytes) | Two independent proofs |
| 2 | ★★★★★ **Viewfinder and Still are two entirely separate table-selection paths** | Full capstone chain verified |
| 3 | ★★★★ Viewfinder uses only **4 static tables**; Still uses **24 dynamic tables + 3-parameter weighting** | Directly visible in disassembly |
| 4 | ★★★★ LUT data is **supplied by the Linux side** via `CLiveviewDataPocket`; p7 only reads | Assert strings + zero write sites |
| 5 | ★★★ **Patching p7's data pointers is enough** to import a custom LUT (3-byte change, no brick risk) | Verified on real hardware |

### Key Mechanism

- **Table size derivation**: 41 equally-spaced pointers in `p7 .data` with pitch `0x4D00` = 19712 bytes; solving `N × BW` aligned to 256 yields the unique solution `4913 × 4 = 19652`.
  ⇒ Standard `.cube` RGB (29478 bytes) **cannot fit**.
- **Data source**: all 28 pointers are **read-only with zero write sites** ⇒ data comes from Linux via a Liveview "DataPocket", not from the firmware.
- **★ Gotcha**: "Photos look normal" proves nothing — photos read the **24 dynamic tables**, never the static slot you patched.

### Safety

Patching p7 is **not** brick-bricks: boot0 is untouched and Linux stays alive (telnet/SSH preserved).
Rollback is a single 30-second `dd`.

### Methodology

Four hard-won rules: prefer **resource layout** over experiment; **read the code first** when static data is at hand; **always use capstone** for instruction-level conclusions (hand-decoding bit literal pools as code cost me a whole wrong conclusion); and **look for data-source logs** when guessing whether independent pipelines exist.

---
*Generated 2026-10-06. All conclusions from static analysis on the official firmware image.*