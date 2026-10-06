# Ghidra headless 输出（2026-10-06）

Ghidra 12.1.4 分析 `p7_full.bin`（ARM:LE:32:v7，base 0x0）的导出结果。

## 重新生成

```bash
export JAVA_HOME="E:/Android SDK/jdk21"
GH="E:/ghidra_12.1.4_PUBLIC_20260921/ghidra_12.1.4_PUBLIC"

# 首次导入 + 自动分析（779 秒）
"$GH/support/analyzeHeadless.bat" /e/ghidra_proj NXKS2 -import p7_full.bin \
  -processor "ARM:LE:32:v7" -loader BinaryLoader -loader-baseAddr 0x0 -cspec default -overwrite

# 跑导出脚本（7-25 秒）
"$GH/support/analyzeHeadless.bat" /e/ghidra_proj NXKS2 -process p7_full.bin -noanalysis \
  -scriptPath "<repo>/test_server/isp/ghidra" -postScript <Script>.java "E:/ghidra_out"
```

脚本：`DumpP7.java`（基础导出）｜`ProbeP7.java`（对照实验）｜
`DeepP7.java`（MMU/vtable/名字搜索）｜`SmaP7.java`（SMA/EP/浮点表）｜`SmaDeepP7.java`（消费者反编译）

## 文件

| 文件 | 内容 |
|---|---|
| `00_header.txt` | 语言/编译器/镜像基址/md5 |
| `01_memory_blocks.txt` | 段布局（1 个 rwx block `0x0-0xc3ffff`）|
| `02_functions.txt` | **16468 个函数**清单 |
| `03_string_xrefs.txt` | 目标符号串交叉引用（**全部 0**）|
| `04_strings.txt` | 21806 条已定义字符串 |
| `05_scalar_refs.txt` | 34115 个被引用标量 |
| `10_control.txt` | ★ **对照组**（证明 Ghidra 引用机制有效）|
| `11_string_xref_stats.txt` | ★ 全量字符串引用率 = **4.10%** |
| `12_gamma_anchor_probe.txt` | 0x754000-0x755FFF 被引用标量（仅 3 个，经核为子串误匹配）|
| `13_decompiled.txt` | 高引用函数反编译（**含 Reset 的 MMU 初始化**）|
| `14_vtables.txt` | 1838 个 vtable 候选段 |
| `20_mmu.txt` | ★★ MMU 分析（`DAT_00000230=0xc09` = Cortex-A9）|
| `21_vtable_ctor.txt` | vtable → 构造函数（733 候选，未验证）|
| `22_namesearch.txt` | ❌ 名字搜索**全 0 = 方法失效**（p7 无符号表）|
| `23_reset_chain.txt` | Reset 后续启动链 |
| `30_sma_access.txt` | ★ SMA `0x94000000` 访问者 + **16B/记录内存布局表** |
| `31_ep_access.txt` | ★★ EP 物理基址 = **镜像里完全没有** |
| `32_float_tables.txt` | 浮点表指纹（原始候选）|
| `33_dataseg.txt` | 每 256KB 可打印/零密度（定位 rodata 边界）|
| `40_sma_consumers.txt` | SMA 引用者反编译（★ 经核为 ASCII 假阳性）|
| `41_map_consumers.txt` | 内存布局表消费者（含 **53KB 巨型函数** `FUN_0012a440`）|
| `42_float_cands.txt` | ❌ 浮点候选**全零值 = 判据太弱** |

## 核心结论

1. **p7 = Cortex-A9 上的 ARM 态 OS 镜像**（`0xc09` 静态 + 实机 `/proc/cpuinfo` 双向验证）
2. **p7 启用 MMU** ⇒ 排除 Cortex-M（只有 MPU）
3. **p7 的符号名/键名是孤儿数据**（4.1% 引用率，对照组通过）
4. **p7 里没有 EP 物理基址字面量** —— 但这不等于"不访问EP"（MMU 使虚拟地址可用）
5. **p7 就是 ISP 固件**（排除 p8 全零/ boot1 是 M4 显示+PMIC / p6p13 是 Linux）
6. `scanreg.py`/`arlit.py`/`fnref.py` **退休**（为 ARM ELF 写，裸镜像无段边界 = 全镜像乱扫）

## 补充：veneer thunk 机制（2026-10-06 11:50）

p7 有大量 **4 字节定长 veneer**：`[2B] movs Rd,Ra` + `[2B] b <real>`，
用 `0x1EFF 0x2FE1`（Thumb `nop`/`nop.w`）补齐，**且多层串联**。

Ghidra 识别不出这种表 ⇒ 把整段建成"20 字节坏函数"，反编译出 `halt_baddata()`。
**看到 `halt_baddata()` / `Bad instruction` 先查 veneer，不要怀疑前面的分析。**

用 `test_server/isp/veneer.py`（capstone 驱动）解：
```bash
python veneer.py scan 0x3f3f64 0x54   # 解 veneer 表
python veneer.py dis  0x3f3a80 0x50   # 解反汇编
python veneer.py all                   # 全镜像扫 veneer 段
```

## 关键文件补充

| 文件 | 内容 |
|---|---|
| `50_page_table.txt` | ★★ MMU 页表解算（16 个 PTE，1:1 映射确认）|
| `50_virt2file.txt` | 虚拟地址 → file 偏移换算表 |
| `51_boot_chain.txt` | 从 Reset 出发的启动链 |
| `52_pseudocode_index.txt` | 16466 函数伪代码索引（addr/size/name/行号）|
| `53_all_pseudocode.c` | ★★ **20.7MB 全量伪代码**（主检索对象）|

## 主干检索（推荐入口）

```bash
cd test_server/isp
python ps_scan.py stats      # 函数数/行数/EP 触及数
python ps_scan.py ep         # ★ EP 寄存器访问全表（20 个块 / 82 函数）
python ps_scan.py matrix     # 3x3 色彩矩阵候选
python ps_scan.py callers FUN_004b6894   # 反向调用表
python ps_scan.py callees FUN_003f3fa4   # 正向调用表
```

## ISP 调参链路（已定位）

```
FUN_003f3fa4(ctx, ID)          ← veneer switch，按 ID 取参数（Ghidra 解不出，用 veneer.py）
  ↓
FUN_004b6894(idx, struct, flag)  ← 760B，写 EP 0x20821300 参数块（28 个调用者）
FUN_004b6b98(idx, struct, flag)  ← 688B，写 EP 0x20821700 参数块（27 个调用者）
FUN_004afe3c(idx, mode)         ← 188B，写 NOG 0x20821c00（颗粒/sigma/gamma/seed）
  ↓
EP 硬件
```
命令分发表在 `0x3f6xxx`–`0x3fbxxx`（14 个连续函数）。
⇒ **不必改 p7 指令**——让 `FUN_003f3fa4` 返回我们想要的值即可。

---

## ISP 模块描述符表（2026-10-06 12:30 破译）

**描述符形态**（Ghidra 伪代码）：
```c
iVar1 = DAT_xxxxxxxx;                          // 模块状态结构体基址（运行时数据区）
if (*(char *)(DAT_xxxxxxxx + F) == '\0')       // +F = 激活标志
   *(u32 *)(DAT_xxxxxxxx + F+4) = *(u32 *)(*(u8 *)(DAT_xxxxxxxx + F+1) + EP_BASE);
*(u32 *)(*(u8 *)(iVar1 + F+1) + EP_BASE) = *(u32 *)(iVar1 + F+4);
```

| 通道 | 模块基址 | flag | 通道索引 | EP 通道阵列 | 函数 |
|---|---|---|---|---|---|
| 0x11(17) | `DAT_004c8698` | +0x10 | 0x11 | `0x20830900` | `FUN_004c8584` /276B |
| 0x19(25) | `DAT_004c87b8` | +0x18 | 0x19 | `0x20830900` | `FUN_004c86a4` /276B |
| 0x11(17) | `DAT_004ccce8` | +0x10 | 0x11 | **`0x20831000`** | `FUN_004ccbe0` /264B |
| 0x19(25) | `DAT_004ccdf4` | +0x18 | 0x19 | **`0x20831000`** | `FUN_004cccec` /264B |
| 0x51(81) | `DAT_004c8fa0` | +0x50 | 0x51 | `0x20830500` | `FUN_004c8f24` /124B |
| 0x59(89) | `DAT_004c901c` | +0x58 | 0x59 | `0x20830500` | `FUN_004c8fac` /112B |
| 0x51(81) | `DAT_004cd514` | +0x50 | 0x51 | **`0x20830c00`** | `FUN_004cd498` /124B |
| 0x59(89) | `DAT_004cd590` | +0x58 | 0x59 | **`0x20830c00`** | `FUN_004cd520` /112B |

**★ 同一通道索引成对出现在两个 EP 阵列 ⇒ 大概率 View / Still 双通路。**

## 其它已定位的 EP 写入器

| 函数 | 大小 | 目标 | 调用者 |
|---|---|---|---|
| `FUN_004b6894` | 760B | `0x20821300` 参数块 | **28** |
| `FUN_004b6b98` | 688B | `0x20821700` 参数块 | **27** |
| `FUN_004afe3c` | 188B | `0x20821c00` **硬件 NOG**（颗粒/sigma/gamma/seed 位域）| 1 |
| `FUN_004c817c` 等 16 个 | 124-552B | `0x20830500/0600/0900` 通道阵列 | — |

命令分发表：`0x3f6xxx`–`0x3fbxxx`（14 个连续函数）

## 关键工具

```bash
cd test_server/isp
python modules.py            # ★ 模块描述符表
python schema.py 0x3f3f64 0x60# ★ 参数 schema（veneer 末端字段偏移）
python p7trace.py classify    # EP 块功能分类
python p7trace.py chain 0x3f3fa4   # veneer 递归追链
python ps_scan.py ep          # EP 访问全表
```

## ⚠️ 伪代码陷阱

`DAT_xxxxxxxx` **不保证在数据段**——Ghidra 只表示"已知的 4 字节标量"，
它常常落在函数体内部（函数内字面量池）。dump 前必须确认它是不是函数起点
（对照 `02_functions.txt`）。**正确姿势是从使用方式反推语义。**

---

## ⚠️ 重大修正（2026-10-06 11:50）：`0x4c8xxx`/`0x4ccxxx` 是 **OSD**，不是 ISP

**上溯到唯一入口后的定性**：
```
8 个通道写入器 → 6 个中层 → 3 个上层 → ★唯一入口 FUN_003d0b4c(84B)
                                            ↓
                                     FUN_003d34e4(552B)
```
`FUN_003d34e4` 的参数运算：
```c
local_58 = param_2 + 6;                // x + 6
local_54 = param_3 + 6;                // y + 6
local_50 = param_2 + param_4 - 6;      // x + w - 6
local_4c = param_3 + param_5 - 6;      // y + h - 6
```
⇒ **带 6 像素边距的矩形框 = OSD / overlay 窗口定位**，不是色彩管线。

### 子系统定性表

| 子系统 | 写入器 | EP 目标 | 用途 |
|---|---|---|---|
| **OSD/显示** | `FUN_004c817c/8200/83ac` + 8 个通道写入器<br>入口 `FUN_003d0b4c` | `0x20830500/0600/0900/0c00`<br>+ `0x20831000` | 矩形窗口/叠加 |
| **ISP 调参** | `FUN_004b6894`(760B,28 调用者)<br>`FUN_004b6b98`(688B,27 调用者) | `0x20821300`<br>`0x20821700` | ★★ 真正的 ISP 参数块 |
| **颗粒 NOG** | `FUN_0017a658`(184B) → `0x4afdxx` 族 | `0x20821c00` | ★★ 硬件颗粒 |
| EP 全局 | 9 个函数 | `0x20820000` | 顶层控制 |

### ISP 侧调用链 5 层收敛（seed = 3 个真ISP 写入器）
```
[d1] 30 个（含 0x3f6xxx 命令表 14 个）
[d2] 28 个   [d3] 24 个   [d4] 7 个   [d5] 0 ← 收敛
```
**7 个 ISP 对外入口候选**（魔灯挂载点）：
```
FUN_00139994  696B  @ 0x139994      FUN_0018e9c0 1016B  @ 0x18e9c0
FUN_0018e670  624B  @ 0x18e670      FUN_00191d6c 1104B  @ 0x191d6c
FUN_001de268  392B  @ 0x1de268      FUN_001f7658  988B  @ 0x1f7658
FUN_003feda4  444B  @ 0x3feda4
```

### NOG 子系统完整破译
`FUN_0017a658`（NOG 唯一入口）→ 6 个同族函数：

| 函数 | 大小 | 语义 |
|---|---|---|
| `FUN_004afd2c` | 36B | memset 32 字节状态区（`param_1` 选两个实例之一）|
| `FUN_004afd58` | 100B | 操作 `DAT_20821c08` / `DAT_20821c0c` + `DAT_817d7e64` |
| `FUN_004afdbc` | 64B | `*p = (*p & 0xfd) \| (v & 1) << 1` — **bit1 开关** |
| `FUN_004afdfc` | 64B | `*p = (*p & 0xfe) \| (v & 1)` — **bit0 开关** |
| `FUN_004afe3c` | 188B | ★ **寄存器下发**（`0x20821c00`/`0x20821c04`），3 字节/项 × 32 项表 |
| `FUN_004aff08` | 336B | 上层 API |

**`DAT_817d7e64` / `DAT_817d7e84` = NOG 运行时控制结构**（`0x81xxxxxx` 在 `0x81000000` 运行时数据区）
⇒ **NOG 有 2 个实例**，每实例 32 字节状态，寄存器偏移 `0 / 0x30`。
⇒ 魔灯的"颗粒强度/粒径/颜色"旋钮 ⇒ 映射到那张 32 项表里的某几项。

### ⚠️ 关键判据（已成铁律 40）

**"写同一个硬件块"不等于"同一个功能"。** 本项目曾因形态相似
（`描述符 + u8 偏移 → 写 EP 块`）把 OSD 误判成 ISP，浪费一轮。
**必须上溯到调用者收敛点，看入口函数的参数语义才能定性。**

---

## 主干检索工具（`test_server/isp/`，全部基于本目录的伪代码）

```bash
cd test_server/isp
python trace.py up FUN_004b6894 5      # ★ 上溯找入口（定性必经）
python trace.py qual FUN_入口           # ★★ 定性：看参数参与什么运算
python trace.py settle FUN_004afe3c    # 自动上溯+ 逐层定性
python trace.py fanin 0x2082           # 某 EP 段的所有写入者
python ps_scan.py ep                   # EP 访问全表
python ps_scan.py matrix               # 3x3 色彩矩阵候选
python p7trace.py classify             # EP 块功能分类
python schema.py 0x3f3f64 0x60         # veneer 末端字段偏移（参数 schema）
python modules.py                      # 模块描述符表
```

### 定性速查（2026-10-06 血泪）

| 入口里出现 | 定性 |
|---|---|
| `x+6 / y+6 / w-6 / h-6`（成对加减同一常数）| ★ **矩形窗口 = OSD/显示** |
| `*(u32*)(param+4)` / `param[8]` | ★ **配置结构体 = 参数下发入口** |
| `& 0xfd \| (v&1)<<1` | ★ **开关/模式选择** |
| `*(u8*)(desc+0x11) + 0x2083xxxx` | ★ **EP 块 + 寄存器偏移（OSD 与 ISP 都长这样，不能凭这个定性！）** |

---

## NOG 硬件寄存器布局（2026-10-06 13:00，`FUN_004aff08` 逐条解出）

```c
undefined4 FUN_004aff08(undefined1 *param_1, int param_2) {
  if (param_1 == 0) { 报错 0x79; return -1; }
  bVar4 = (param_2 == 0);
  iVar3 = DAT_004b0058 + (bVar4 ? -0x20 : 0);      /* 实例1 的中转区 */
  *(u8*)(iVar3+0x10..0x13) = param_1[0..3];
  *(u32*)&DAT_20821c10 = *(u32*)(iVar3+0x10);
  ... param_1[4..7]   -> 0x20821c14
  ... param_1[8..11]  -> 0x20821c18
  ... param_1[12..15] -> 0x20821c1c
  /* param_2 != 0 -> 全部 +0x30: 0x20821c40/44/48/4c */
}
```

| 寄存器 | 源 | 语义 |
|---|---|---|
| `0x20821c00` / `0x20821c04` | — | `FUN_004afe3c` 写：3B/项 × 32 项 表下发口 |
| `0x20821c08` / `0x20821c0c` | — | `FUN_004afd58` 读写 |
| **`0x20821c10/14/18/1c`** | `param_1[0..3]/[4..7]/[8..11]/[12..15]` | ★★ **实例0 的 4 个 32 位参数** |
| **`0x20821c40/44/48/4c`** | 同上（+0x30） | ★★ **实例1 的 4 个 32 位参数** |

⇒ **NOG 参数 = 16 字节 = 4 个 32 位寄存器 × 2 个实例**
控制结构 `DAT_817d7e64` / `DAT_817d7e84`（差 0x20），bit0/bit1 开关。

工具：`test_server/isp/nog_map.py`

## ⚠️ 实机探针（`nogdump.c`）：SIGBUS 根因 = 相机不在拍摄态

对照实验：把**前一天跑通**的 `epdump9.arm` 原样上传 → **同样 SIGBUS（RC=135）**。
相机状态检查全部正常（version.info 对、`iqr` 有响应、设备节点都在）。
⇒ **EP 寄存器按需初始化，不在拍摄流程里就没有映射。**
⇒ ★ **跑 EP/NOG 探针前必须确认相机在 Liveview 或拍摄态**（已成铁律 42）。
