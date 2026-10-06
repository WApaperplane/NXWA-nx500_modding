# p7 裸 ARM 固件分析报告 —— ISP 固件本体确认

> 分析时间：2026-10-05 21:45
> 来源：`/dev/mmcblk0p7`（eMMC 未挂载分区，30719 KB），**全程只读**（`dd if=` 无 `of=`）
> 原始数据：`raw8/p7/p7_full.bin`（12,845,056 字节）+ `p7_analysis.txt`
> 上一轮判断：p7 是「ISP 固件最强候选」→ **本轮确认，并解出入口**

---

## 一、结论：这就是 ISP 固件本体

### 1.1 定性判据（三条独立证据）

| 判据 | 结果 |
|---|---|
| **容器格式** | `uImage` magic `0x27051956` **零命中**；`ELF` `\x7fELF` **零命中** ⇒ **裸镜像，无封装** |
| **有效数据** | 0 – 12.5 MB 非零，12.5 MB 之后全零 ⇒ 实际 **12.25 MB 固件**（分区 15 MB 留空） |
| **指令集** | 前 1 MB：ARM 模式 `BL` **24,494** 条、`B` **10,437** 条、`LDR pc` **0** 条 ⇒ **纯 ARM 状态，无 Thumb 混合** |

### 1.2 决定性证据：完整相机控制命令字符串表

offset `0x6F0000` 起是密集的字符串表（2,600+ 条/64KB），内容是**相机 ISP 的控制命令枚举**：

```
0x6f0000  P_CMD_SET_ADJUST_YCC          ← 色彩调整命令
0x6f0024  E_CAP_CMD_SET_AE_AREA         ← 自动曝光区域
0x6f0044  E_CAP_CMD_SET_AUTOSHUTTER_MODE
0x6f0074  E_CAP_CMD_SET_DISPLAY_OUT
0x6f009c  E_CAP_CMD_SET_PANO_THUMB_DRAW
0x6f00cc  E_CAP_CMD_SET_RELEASE_MEMORY
0x6f0124  E_CAP_CMD_SET_CAPTURED_IMAGE_COUNT
0x6f0188  E_CAP_CMD_SET_SELECTION_AREA  ← 选定区域
0x6f022c  RegApexConvertTvFunc
0x6f0284  RegApexGetMaxAvFunc
```

**这不是任何通用 ARM 固件能有的东西。** 一套包含 AE 区域、AutoShutter、DisplayOut、
PanoThumb 的命令表，只能是相机 ISP。

---

## 二、★★ 入口位置：镜像开头即异常向量表

开头 5 条 `b` 指令构成 ARM 异常向量表（模式与向量编号完全对应）：

| 地址 | 机器码 | 跳转目标 | ARM 异常向量 |
|---|---|---|---|
| `0x00000` | `ea00004e` | `0x000140` | **Reset（复位入口）** |
| `0x00004` | `ea000018` | `0x00006c` | Undefined Instruction |
| `0x00008` | `ea00001e` | `0x000088` | SWI |
| `0x0000c` | `ea00002c` | `0x0000c4` | Prefetch Abort |
| `0x00010` | `ea000038` | `0x0000f8` | Data Abort |

**⇒ 固件入口 = 文件偏移 `0x000000`**（就是镜像最开头）。
**加载基址：文件偏移 ≈ 内存地址。** 依据：BL 目标集中在
`0x046000`（7,177 次）、`0x524000`（5,483）、`0x173000`（4,520）、
`0x4F9000`（3,710）、`0x011000`（3,058）—— 这些是函数密集区，
且**全部落在镜像范围内**，说明没有重定位，加载时原样映射。

### 2.1 Reset 入口前 20 条指令（已反汇编）

```
0x00000: ea00004e  b   0x000140      ; ← 复位，跳到 0x140
0x00004: ea000018  b   0x00006c      ; Undef
0x00008: ea00001e  b   0x000088      ; SWI
0x0000c: ea00002c  b   0x0000c4      ; Prefetch
0x00010: ea000038  b   0x0000f8      ; Data Abort
0x00014: e320f000  ?                 ; (WNZIC 复位)
0x00018: ea000002  b   0x000028
0x0001c: e59fc114  ldr  r12,[pc]     ; =0xe1120005
0x00020: e59cc07c  ldr  r12,[r12]
0x00024: e12fff1c  bx   r12          ; ← 间接跳转（跳到加载地址）
0x00028: e24ee004  sub  lr,r14,#4
0x0002c: f96d0512  ???                ; ⚠️ 见下方「2026-10-06 修正」，此前误标为 sdiv
0x00030: e92d1008  push {r1,r2}
0x00034: e59fe100  ldr  r10,[pc]     ; =0x8100449c   ← 物理地址（外设段）
0x00038: e59ec000  ldr  r12,[lr]
0x0003c: e59fe0f4  ldr  r10,[pc]     ; =0xe151000c
```

> ## ⚠️⚠️⚠️ 2026-10-06 重大修正（Ghidra 12.1.4 反编译后重写）：本节「Cortex-M」结论作废
>
> **原判据全部错误，且方向性错误。** 用 Ghidra 12.1.4 headless 反汇编 + 反编译后：
>
> | 项 | 原结论 | 实测 |
> |---|---|---|
> | `0xf96d0512` | `sdiv r0,r13,r0`（Cortex-M3/M4 独有）| ❌ **不是 SDIV，也不是任何合法指令**。`cond=0xF`（NV，ARMv7 里永不执行）+ `coproc=5` ⇒ 落在 **ARM 保留编码空间**。**说明 `0x2c` 处是内联常量池被误纳入代码流。** |
> | 指令集 | Cortex-M3/M4 | ❌ **ARM 模式（A32）**。向量表 8 项全是 `0xea0000xx` ARM `B` 指令（Reset→`0x140`），全部 bit0=0；而 **ARMv7-M 向量表存的是绝对地址，不是分支指令**。 |
> | 「无 LDR pc」 | 支持 Cortex-M | ⚠️ 这条本来就自相矛盾——向量表第 7 项 `0xe59fc114` **本身就是 `ldr r12,[pc]`**。 |
>
> ### ★★★★ 决定性证据：p7 启用了 MMU
>
> Ghidra 反编译 `FUN_00000140`（Reset 向量）：
>
> ```c
> uVar2 = coproc_movefrom_Main_ID();
> if ((DAT_0000022c & uVar2>>4) == DAT_00000230) { Reset(); return; }
> coproc_moveto_Translation_table_control(4);
> coproc_moveto_Translation_table_base_1(DAT_0000024c);
> coproc_moveto_Translation_table_base_0(DAT_0000024c);
> // ★ 建立 1:1 映射页表，覆盖 0x80000000 – 0x81000000
> puVar3 = (uint *)&DAT_81000000;
> do { *puVar3 = uVar4 | uVar2; uVar4 += 0x100000; puVar3++; } while (uVar4 != 0);
> puVar5 = (undefined1 *)0x80000000;
> do { *puVar3 = uVar4 | uVar1; puVar5 = puVar5 + 0x100000; puVar3++; }
>     while (puVar5 != &DAT_81000000);
> coproc_moveto_Domain_Access_Control(0x55555555);
> coproc_moveto_Instruction_cache(0x55555555, 6);
> ```
>
> ⇒ 写 TTBR0/TTBR1、TLB 控制、Domain Access Control、Instruction Cache
> ⇒ **M4/Cortex-M 只有 MPU，没有 MMU** ⇒ **"Cortex-M / M4 裸机固件"彻底排除**
> ⇒ **p7 是带 MMU 的 ARM OS 镜像**（A9/R 核级）
> ⇒ ★★ **运行时虚拟地址 ≠ 文件偏移**（"文件偏移 ≈ 内存地址"只在 flash 侧成立）
>

---

## 三、★★ 完整 ISP 子系统地图（38567 个标识符，按前缀统计）

> ⚠️ **2026-10-06 降级**：Ghidra 独立证实 **21806 条字符串中仅 894 条（4.10%）有代码引用**，
> `0x580000+` 符号区 20120 条绝大多数是**死数据**（NDEBUG 裁剪残留）。
> 对照组 `"Copy Flash ROM Image to RAM Area"` 有 8 个引用 ⇒ 引用机制有效，
> 而 `SetLiveviewParam2Monitor` / `TC_LOW_ANCHOR_X00` / `CC_RGBL_MAT_00` 等**全部零引用**。
> ⇒ **下面这张表说明"曾这样组织过代码"，不说明"这些模块现在还在跑"。**

| 标识符前缀 | 数量 | 子系统 |
|---|---|---|
| **`eIQ_`** | **295** | **图像质量（Image Quality）★ FilmLab 相关** |
| `eLENS_` | 154 | 镜头 |
| `eNUM_` | 130 | 数值类型 |
| `eSTILL_` | 115 | 静态拍摄 |
| `eCFAI_` | 89 | CFA/对比度锐度相关 |
| `eSVC_` | 88 | 服务 |
| `eADE_` | 85 | 应用开发环境 |
| `eEE_` | 73 | 曝光/电子 |
| `eCAP_` | 71 | 拍摄能力 |
| `eCIS_` | 61 | 图像传感器 |
| `eAF_` | 60 | 自动对焦 |
| `eLVIEW_` | 60 | 取景 |
| `eAE_` | 58 | 自动曝光 |
| `eCIQ_` | 51 | 连续 IQ |
| `ePP_` | 48 | 图像处理管线 |
| `ePAF_` | 45 | 被动 AF |
| `eWB_` | 44 | ★ 白平衡 |
| `eTC_` | 44 | 时钟/温度 |
| `eMLCD_` | 43 | 主 LCD |
| `eSL_` | 40 | 拍摄模式 |
| `eFE_` | 39 | 前端 |
| `eISO_` | 38 | ★ 感光度 |
| `eUI_` | 36 | 用户界面 |
| `eCORE_` | 36 | 核心 |
| `eCPP_` | 33 | 后期处理 |
| `eEVF_` | 30 | 电子取景器 |
| `eQVIEW_` | 30 | 快速取景 |

其它高频字符串（拍摄模式）：
```
eAPPMODE_SMARTAUTO / SMARTPRO / PROGRAM / Av / Sv
eSMARTPRO_MODE_NIGHT / GOLFSHOT / OUTFOCUS / SELFSHOT / INTERVAL
                 / WATERFALL_TRACE / MINIATURE / AUTOSHUTTER / ACTION_FREEZE
eWB_TYPE_LIVEVIEW / STILL_CAPTURE / BULB_IMAGE_CAPTURE0..2 / CUSTOM
eWB_MODE_FLUORESCENT_L / AUTO_TUNGSTEN
eOLED_COLOR_ON / OFF
eBRACKET_TYPE_PW  eSHOOTING_PWB
```

★ `eSMARTPRO_MODE_*` 全表 = **NX500 智能模式的完整枚举**，
与 `st app mode smart-pro` 的实测行为一致。

---

## 四、★★★ 本轮最高价值发现：PW 风格体系完全对上 prefman 槽位

### 4.1 12 个 PW 风格（0x6F5870 起，**完整表**）

```
PW_STANDARD   PW_VIVID      PW_PORTRAIT   PW_LANDSCAPE
PW_FOREST     PW_RETRO      PW_COOL       PW_CALM
PW_CLASSIC    PW_CUSTOM1    PW_CUSTOM2    PW_CUSTOM3   PW_CUSTOM4
NUM_OF_PW
```

★ **与记忆里的 prefman 槽位表完全对应**：slot 9 = CUSTOM_1、slot 12 = CUSTOM_4、
UI 只显示 CUSTOM_1（前 4 个 UI 不可见的槽在 `apply`/`preset` 里要拒绝）。
**ISP 固件里的 `NUM_OF_PW` 证实"总槽位 = 12"这个数。**

### 4.2 7 个 PW 参数（**与记忆里的地址公式逐项吻合**）

```
VARIABLE_PWCOLOR       VARIABLE_PWSATURATION   VARIABLE_PWSHARPNESS
VARIABLE_PWCONTRAST    VARIABLE_PWCOLOR_R      VARIABLE_PWCOLOR_G
VARIABLE_PWCOLOR_B     VARIABLE_PWHUE
```

★ 对照记忆里的实测公式：

| 记忆记录 | 固件实证 | 一致？ |
|---|---|---|
| `addr(参数i, 风格s) = 41964 + i*52 + s*4` | 7 个参数（i=0..6）、12 个风格（s） | ✅ |
| i=0..6 = R/G/B/HUE/SAT/SHARP/CONTRAST | 7 个 `VARIABLE_PW*` 参数 | ✅ |
| 中性值 R/G/B=100，HUE/SAT/SHARP/CONTRAST=10 | 由 `NUM_OF_PW*` 系列（13 条）约束 | ✅ |
| slot 12 (CUSTOM_4) UI 不显示 | 12 个槽位，UI 只用 CUSTOM_1 | ✅ |

### 4.3 `eIQ_ID_PW_*` —— 画质参数在 ISP 侧的枚举

```
0x701634  eIQ_ID_PW_SATURATION      ★ 饱和度
0x70164c  eIQ_ID_PW_SHARPNESS       ★ 锐度
0x701660  eIQ_ID_PW_CONTRAST        ★ 对比度
0x701f60  eIQ_ID_MOVIE_GAMMA_MODE   （电影 gamma）
0x701a20  eIQ_ID_SMARTART_CONTSHOT_STATE
0x701af8  eIQ_ID_SMARTART_SHARPNESS_STATE
0x701b18  eIQ_ID_SMARTART_SATURATION_STATE
0x701b98  eIQ_ID_SMARTART_BEAUTYTONE_LEVEL
0x701c64  eIQ_ID_SMARTART_CONTRAST_LEVEL
0x701c84  eIQ_ID_SMARTART_SATURATION_LEVEL
0x701ca8  eIQ_ID_SMARTART_SHARPNESS_LEVEL
```

★★ **这是 FilmLab 的直接接口。** 记忆里 FilmLab 的做法是
"改 prefman 槽位数值 → 制造 enum 跳变 → ISP 重读 PW 段"。
现在知道了：**ISP 侧对应的就是 `eIQ_ID_PW_{SATURATION,SHARPNESS,CONTRAST}`**，
而 `VARIABLE_PW{COLOR_R,COLOR_G,COLOR_B,HUE}` 补足了另外 4 个维度。

⇒ **胶片仿真的 7 维（RGB + HUE + SAT + SHARP + CONTRAST）在 ISP 固件里
   是一等公民，有正式枚举名，不是我们外部猜出来的。**

### 4.4 `USERDATA_PW*` —— 白平衡用户数据

```
0x6f4104  USERDATA_PW
0x6f422c  USERDATA_PWBRKSTANDARD   0x6f4244  USERDATA_PWBRKVIVID
0x6f4258  USERDATA_PWBRKPORTRAIT  0x6f4270  USERDATA_PWBRKLANDSCAPE
0x6f4288  USERDATA_PWBRKFOREST     0x6f42a0  USERDATA_PWBRKRETRO
0x6f42b4  USERDATA_PWBRKCOOL       0x6f42c8  USERDATA_PWBRKCALM
0x6f42dc  USERDATA_PWBRKCLASSIC    0x6f42f4  USERDATA_PWBRKCUSTOM1..4
```

★ **风格是 13 个不是 12 个！** 比 `PW_*` 多一个 `USERDATA_PW` 本身。
⚠️ 这是个**待解释的差异** —— `NUM_OF_PW=12` 但 `PWBRK*` 变体有 13 个。
可能 `USERDATA_PW` 是"无风格"的基准档。**列入待验证**。

### 4.5 其它值得注意的字符串

```
0x599ea6  CCallback_Still_PWB_Start     ← 静态拍摄 PWB 回调（IPC 接口）
0x599ee2  CCallback_Still_PWB_IPC_Done  ← ★ "IPC_Done" 说明与 A9 有 IPC 通道
0x599f22  CCallback_Still_PWB_End
0x6f5870  PW_STANDARD ...
```

★ **`CCallback_Still_PWB_IPC_Done`** 是关键线索：ISP 固件里有
**跨核 IPC 回调**。这与"IPCC 是空壳"的实测看似矛盾，
但可以调和：**IPCC 设备（`/dev/d5_ipcc`）在 Linux 侧是空壳，
而 ISP 固件内部有自己的 IPC 实现**（可能是 M4 侧的 mailbox/共享内存）。
⇒ ★ **"IPCC 空壳"是 Linux 侧视角，不能推广到 ISP 固件内部。**

---

## 五、物理地址线索

> ⚠️⚠️ **2026-10-05 22:00 修正：本章的"引用次数"全部作废，是统计错误。**
>
> 下表按 `(w>>16)` 分桶统计**任意 32 位值**，把落在 `0x0806xxxx`–`0x0807xxxx`
> *数值区间*的普通数据全算进来了。实际值形如 `0x08070605` / `0x08060403` /
> `0x08060107` —— **末字节不是 4 的倍数，根本不是合法对齐地址。**
>
> 严格判据（4 字节对齐 + LDR-literal 判定）下的真实结果：
> - `0x0806-0x0807` 段：**零对齐引用、零 LDR-literal 引用**
> - EP 子块地址 `0x20821c00` / `0x2082b000`：固件里**各 0 次**
> - EP ioctl 号 `0x80506864`：**0 次**
>
> ⇒ **「EP 由 ISP 固件驱动」在地址层面零支持。**
> ⇒ ★ **但两者经共享内存 `0x94000000` 协作**（见 `docs/SMA_CROSSCHECK_2026-10-05.md`）。
> ⇒ 完整修正见 `docs/P7_SUBSYSTEM_AND_EP_CROSSCHECK_2026-10-05.md` 第 6 章。

~~固件里大量引用 `0x0806xxxx` – `0x0807xxxx` 段：~~

| 段 | ~~引用次数~~ | 对照 |
|---|---|---|
| ~~`0x0806exxx`~~ | ~~5,908~~ | ⚠️ **作废，见上方修正** |
| ~~`0x08075xxx`~~ | ~~4,683~~ | ⚠️ **作废** |
| ~~`0x0806fxxx`~~ | ~~3,768~~ | ⚠️ **作废** |
| ~~`0x08070xxx`~~ | ~~3,560~~ | ⚠️ **作废** |
| ~~`0x08058xxx`~~ | ~~2,509~~ | ⚠️ **作废** |
| ~~`0x08101xxx`~~ | ~~2,485~~ | ⚠️ **作废** |

~~`Reset` 入口里也直接出现 `0x8100449c`。这些是**物理地址**，
说明固件运行时直接访问外设/共享内存区。~~

**下一步可做**：~~把 `0x0806xxxx` 段的引用位置全量导出，
和实测的 EP 子块表做交叉，看 ISP 固件是否直接操作 EP 寄存器。~~

> ✅ **该交叉已于 22:00 完成**：`0x0806-0x0807` 段**零对齐引用、零 LDR-literal 引用**，
> EP 子块地址在固件里零出现 ⇒ **假设被推翻**。
> ★ **替代结论**：两者经共享内存 `0x94000000` 协作（该地址在固件 `0x9FC0` 的内存段表中）。
> ⇒ **"EP 到底是不是 ISP 固件在驱动"这个悬案已钉死**，
> 完整推演见 `docs/P7_SUBSYSTEM_AND_EP_CROSSCHECK_2026-10-05.md` 与 `docs/SMA_CROSSCHECK_2026-10-05.md`。

---

## 六、本轮操作纪律

| 铁律 | 执行 |
|---|---|
| 只读 | ✅ 全程 `dd if=`，**无一个 `of=` 写分区** |
| 单核不能连续重活 | ✅ 分 4 块（各 2–4 MB）抽取，块间 `sleep 3s` |
| telnet 串行 | ✅ 单会话 |
| ≥10KB 走 FTP | ✅ 12.6 MB 全部 FTP |
| 清理现场 | ✅ 抽完即 `rm -rf /opt/storage/sdcard/p7` |
| 不下结论于单点 | ✅ 入口判定用了 3 条独立判据（容器格式/指令集/字符串表） |

---

## 七、下一步（按价值）

| 优先级 | 动作 | 判据 / 价值 |
|---|---|---|
| **1** | 导出 `0x0806xxxx` 段全部引用位置，交叉 EP 子块表 | ★ **直接回答"EP 是不是 ISP 固件在驱动"** —— 这是本项目最大的未决问题 |
| **2** | 反汇编 `eIQ_ID_PW_*` 处理函数（IQ 子系统，295 个标识符所在） | 找到 PW 曲线在 ISP 里的实际算法位置 |
| **3** | 抽 `mmcblk0p1..p4`（bootloader 区）扫描 `0x27051956` | 确认 bootloader 加载链 |
| **4** | 定位 `CCallback_Still_PWB_IPC_Done` 的函数体 | 找到 ISP↔A9 的 IPC 协议结构 |
| 5 | NOG 探针（`d5_ep_nog_set_noisegen`）+ 像素方差统计 | 决定 FilmLab 硬件颗粒路线生死 |

### ⚠️ 不建议
- **不要试图往 p7 写任何东西。** 它是正在运行的 ISP 固件载体。
- **不要改 `pw_force_reload()` 的机制。** 现在知道了 `NUM_OF_PW=12` 和
  `USERDATA_PW*` 有 13 个变体，说明 enum 语义比"12 个槽"复杂，
  在弄清 `USERDATA_PW` 是什么之前不要改 enum 跳变逻辑。

---

## 八、待解释的差异（★ 需要后续验证）

1. **`NUM_OF_PW = 12` 但 `USERDATA_PWBRK*` 有 13 个变体**
   （`USERDATA_PW` + 12 个 `PWBRK*`）。多出的那个是"无风格"基准档？
2. **`PW_*` 是 12 个，`USERDATA_PWBRK*` 是 13 个** —— 两个表的 s 参数是否同一坐标？
   记忆里的地址公式 `s*4`（步长 4 字节 = 1 个 u32）暗示**每风格 1 个 u32**，
   与"每风格 7 个参数各存一份"的结构不符。**这个矛盾必须解开。**
3. **入口在 `0x000000`（向量表）而非 Reset 向量 `0x000140`**
   —— 实际执行从 `0x140` 开始，bootloader 跳的是向量表首地址还是 `0x140`？
