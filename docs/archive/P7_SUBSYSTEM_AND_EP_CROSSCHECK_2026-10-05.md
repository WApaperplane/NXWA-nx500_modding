# p7 ISP 固件 · 子系统全景与 0x0806xxxx 交叉分析

> 时间：2026-10-05 21:55
> 数据：`raw8/p7/p7_full.bin`（12,845,056 B）
> 规模：**421 个标识符前缀 / 67,200 个标识符**
> 原始输出：`raw8/p7/subsystem_analysis.txt`
> 前置：`docs/archive/P7_ISP_FIRMWARE_ANALYSIS_2026-10-05.md`（入口定位）

---

## 一、结论先行

**1. 子系统结构已完整挖出（421 个前缀），足以作为反向设计 mod 的蓝图。**

**2. ★ `0x0806xxxx` 交叉分析：假设被推翻，而且是我的统计错误。**
上一轮报告写"固件里 `0x0806xxxx` 被引用 5908 次 ⇒ 可能直接操作 EP"——
**这个 5908 是错的**。它是按 `w>>16` 分桶统计**任意 32 位值**，
把落在 `0x0806-0x0807` *数值区间*的普通数据也算进去了。
实际那些值形如 `0x08070605` / `0x08060403` / `0x08060107` ——
**末字节不是 4 的倍数，根本不是合法对齐地址。**

⇒ 严格判据下：`0x0806-0x0807` 段**零对齐引用、零 LDR-literal 引用**。
⇒ **「EP 由 ISP 固件在驱动」在地址层面得不到支持。**

**3. ★ 挖到两套 FilmLab 可用的新接口**：`LUT_*` 函数族（ISP 侧 3D LUT）
和 `CC_RGB{L,H}_MAT_*`（完整 3×3 色彩矩阵）。

---

## 二、子系统全景（421 个前缀，前 40）

| 前缀 | 数量 | 含义 |
|---|---|---|
| **`eIQ_`** | **295** | **图像质量调校 ★ FilmLab 核心** |
| `eLENS_` | 154 | 镜头 |
| `eNUM_` | 130 | 数值类型 |
| `eSTILL_` | 115 | 静态拍摄 |
| `eCFAI_` | 89 | CFA / 对比度锐度 |
| `eSVC_` | 88 | 服务 |
| `eADE_` | 85 | 应用开发环境 |
| `eEE_` | 75 | 曝光 / 电子 |
| `eCAP_` | 71 | 拍摄能力 |
| `eCIS_` | 61 | 图像传感器 |
| `eAF_` | 60 | 自动对焦 |
| `eLVIEW_` | 60 | 取景 |
| `eSENSOR_` | 59 | 传感器驱动 |
| `eAE_` | 59 | 自动曝光 |
| `eCIQ_` | 51 | 连续 IQ |
| `ePP_` | 49 | 图像处理管线 |
| `eFE_` | 45 | 前端 |
| `ePAF_` | 45 | 被动 AF |
| `eWB_` | 44 | ★ 白平衡 |
| `eMEMORY_` | 44 | 内存管理 |
| `eTC_` | 44 | 时钟 / 温度 |
| `eMLCD_` | 43 | 主 LCD |
| `eSL_` | 40 | 拍摄模式 |
| `eISO_` | 38 | ★ 感光度 |
| `eID_` | 37 | 标识 / 索引 |
| `eUI_` | 36 | 用户界面 |
| `eCORE_` | 36 | 核心 |
| `eEFFECT_` | 35 | 特效 |
| `eCPP_` | 33 | 后期处理 |
| `eEXPAND_` | 32 | 扩展能力 |
| `eEVF_` | 30 | 电子取景器 |
| `eQVIEW_` | 30 | 快速取景 |
| **`eIPC_`** | **24** | **★ 跨核通信** |
| `eFOCUS_` | 24 | 对焦 |
| `eSTATE_` | 22 | 状态机 |
| `eDRIVE_` | 21 | 驱动模式 |
| `eLCAC_` | 20 | 缓存 |
| `eIQIF_` | 19 | IQ 接口 |
| `eEFS_` | 19 | 文件系统 |
| **`eCC_`** | **19** | **★ 色彩矩阵** |
| `eCALC_` | 18 | 计算 |
| `eFD_` | 16 | 帧描述 |
| `eSTROBO_` | 16 | 闪光灯 |
| `eLOCK_` | 15 | 锁 |
| `eMOVIE_` | 15 | 视频 |
| `eBB_` | 14 | 包围曝光 |
| `eLDC_` | 14 | ★ 镜头畸变 |
| `eAEB_` | 14 | AE 包围 |
| `eLOW_` | 13 | 低照度 |
| **`ePW_`** | **13** | **★ Picture Worth** |
| `eACC_` | 13 | 加速器 |
| `eCDD_` | 11 | 色温 |
| `eCB_` | 11 | 色彩 |
| **`eLUT_`** | **11** | **★ 3D LUT** |
| `eHW_` | 11 | 硬件 |
| `eSEQ_` | 11 | 时序 |

> 完整 421 个前缀见 `raw8/p7/subsystem_analysis.txt`。

### 拍摄模式全枚举（`eSL_` 派生，实测印证）

```
eAPPMODE_SMARTAUTO  eAPPMODE_SMARTPRO   eAPPMODE_PROGRAM
eAPPMODE_Av         eAPPMODE_Sv
eSMARTPRO_MODE_ACTION_FREEZE / WATERFALL_TRACE / AUTOSHUTTER / GOLFSHOT
             / OUTFOCUS / SELFSHOT / NIGHT / INTERVAL / MINIATURE   (11 项)
```
★ 与 `st app mode {auto|p|a|s|m|smart-pro}` 的实测行为一致。

### 驱动模式（`eDRIVE_`，21 条，含 PW 包围）

```
DRIVE_OFF SINGLE CONTIHIGH CONTIMID CONTILOW BURST TIMER ADJUST
AEBRK WBBRK PWBRK DEPTHBRK
```
★ `DRIVE_PWBRK` = **以 Picture Worth 风格为单位的包围拍摄**。
记忆里 `USERDATA_PWBRK*`（13 个变体）在此得到解释 ——
它们是**驱动模式**，不是风格槽位。**这解决了昨晚记下的"12 vs 13"矛盾的一半。**

---

## 三、★★★ 关键发现一：`LUT_*` 函数族（ISP 侧 3D LUT）

```
0x714709  LUT_Load            ★ 从 DDR 装载 LUT
0x714725  LUT_ChangeAddress   ★ 换地址（多 LUT 切换）
0x714751  LUT_Stop
0x71476d  LUT_Start
0x714789  LUT_SetParam        （×7 条同名，偏移 0x714789..0x714865 步长 0x1c）
```

★★ **这是一套与 `libudd5.so` 完全独立的 ISP 侧 3D LUT 实现。**

| | Linux 侧（`libudd5.so`） | ISP 侧（p7 固件） |
|---|---|---|
| 入口 | `d5_ep_3dl_load_lut(addr, sel, fmt, timeout)` | `LUT_Load` / `LUT_ChangeAddress` |
| 通道 | `/dev/drime5_ep` ioctl + 用户态 mmap | 固件内部（共享内存？） |
| 归属 | UDD，Linux 用户态驱动 | ISP 固件自己实现 |

⇒ **同一个 3D LUT 硬件，两边都有操作入口。**
   这解释了此前的一个谜团：为什么 EP 硬件里装着 identity LUT
   （`0x13020619` ×8）却没被 Linux 侧动过 —— **可能是 ISP 固件自己加载的**。
⇒ ★ **设计 mod 的新思路：与其从 Linux 侧抢 EP，不如找到能触发 ISP 侧 `LUT_Load` 的路径。**

⚠️ **但要注意**：`LUT_SetParam` 出现 7 次同名，步长 0x1c，
说明有 7 个参数化入口（对应 7 个 PW 参数？），**需要逐个反汇编确认参数语义**。

---

## 四、★★★ 关键发现二：`CC_*` 3×3 色彩矩阵

```
0x75457c  CC_RGBL_MAT_00    0x75458c  CC_RGBL_MAT_01    0x75459c  CC_RGBL_MAT_02
0x7545ac  CC_RGBL_MAT_10    0x7545bc  CC_RGBL_MAT_11    0x7545cc  CC_RGBL_MAT_12
0x7545dc  CC_RGBL_MAT_20    0x7545ec  CC_RGBL_MAT_21    0x7545fc  CC_RGBL_MAT_22
0x75460c  CC_RGBH_MAT_00 ...  (H 变体，共 18 条 = 2 组 3×3)
```

★ **`RGBL` = Low-light（低照度），`RGBH` = High-light（高照度）**
   —— 同一颗传感器的高/低照度两套色彩校正矩阵。

★★ **这正是胶片仿真的核心操作。** 3×3 矩阵可以做：
- 通道间串扰校正（典型的胶片特性）
- 饱和度提升/衰减
- 色调偏移（往暖/冷推）
- **白平衡微调**

⇒ ★ **这是比 3D LUT 更轻量的调色入口。** 一条 `CC_RGBL_MAT_*` 表
   就能实现一个"胶片冲印配方"，只需 9 个 32-bit 数。

⇒ **设计 mod 的两条路（现在清楚了）**：
| 路线 | 机制 | 复杂度 |
|---|---|---|
| **A. 3×3 矩阵** | 写 `CC_RGB{L,H}_MAT_00..22` = 9 个数 | **低**，效果有限但立竿见影 |
| **B. 3D LUT** | 触发 `LUT_Load` 装载 .cube | 高，效果强，需找触发路径 |
| C. PW 曲线 | 改 prefman 槽位（现有 FilmLab 路线） | 中，7 维但非线性 |

---

## 五、★★★ 关键发现三：PW 体系（复核 + 解开一半矛盾）

```
0x6f5870  PW_STANDARD  VIVID  PORTRAIT  LANDSCAPE  FOREST  RETRO
          COOL  CALM  CLASSIC  CUSTOM1  CUSTOM2  CUSTOM3  CUSTOM4
0x6f5908  NUM_OF_PW                       ← 12
0x6f8514  VARIABLE_PWCOLOR                0x6f8528  VARIABLE_PWSATURATION
0x6f8540  VARIABLE_PWSHARPNESS            0x6f8558  VARIABLE_PWCONTRAST
0x6f8854  VARIABLE_PWCOLOR_R              0x6f8868  VARIABLE_PWCOLOR_G
0x6f887c  VARIABLE_PWCOLOR_B              0x6f8890  VARIABLE_PWHUE

0x701634  eIQ_ID_PW_SATURATION    0x70164c  eIQ_ID_PW_SHARPNESS
0x701660  eIQ_ID_PW_CONTRAST
```

### 5.1 ★ 昨晚"12 vs 13"矛盾：解开一半

`USERDATA_PWBRK*` 有 13 个变体，现在看到 `eDRIVE_` 里有 **`DRIVE_PWBRK`**
（以 PW 为单位的**驱动/拍摄模式**）：

| 表 | 数量 | 语义 |
|---|---|---|
| `PW_*` | 12 | **风格槽位**（STANDARD..CUSTOM4），`NUM_OF_PW=12` |
| `USERDATA_PWBRK*` | 13 | **驱动模式的用户数据**（含 `USERDATA_PW` 本身 = "无风格"基准档） |
| `eDRIVE_*` | 21 | **拍摄驱动模式**（含 `DRIVE_PWBRK`） |

⇒ ★ **不是同一坐标。** `PWBRK` 后缀 = Picture Worth **Bracketing**（包围），
   是**拍摄驱动**，不是风格。所以"13 个"里多出的那个是"不指定风格"。
⇒ **昨晚的担心可以解除**：`pw_force_reload()` 的 enum 跳变逻辑**不用改**。

⚠️ **但仍有一个未解的矛盾**（必须继续查）：
地址公式步长 `s*4` = 1 个 u32 / 风格，而参数有 7 个。
若每风格每参数各存一份，步长应是 `7*4=28` 而非 `4`。
**要么公式里的 `s*4` 只对应某一个参数（另 6 个参数另有基址），
要么 7 个参数是打包在一个 u32 里（每参数 4-5 bit）。**
这个必须看 prefman 实际 dump 才能定。

### 5.2 白平衡子表

```
eWB_MODE_FLUORESCENT_L    eWB_MODE_AUTO_TUNGSTEN
eWB_TYPE_LIVEVIEW / STILL_CAPTURE / STILL_CAPTURE_IMAGE / STILL_CAPTURE_BLACK
       / BULB_IMAGE_CAPTURE0..2 / BULB_BLACK_CAPTURE0..2 / CUSTOM
eOLED_COLOR_ON / OFF
```

### 5.3 视频 gamma（★ 对胶片仿真直接可用）

```
0x6f80fc  MOVIE_GAMMA_CONTROL_STANDARD
0x6f811c  MOVIE_GAMMA_CONTROL_GAMMA_V
0x6f8138  MOVIE_GAMMA_CONTROL_GAMMA_D
0x6f8170  MOVIE_LUMINANCE_LEVEL_0_255
0x6f818c  MOVIE_LUMINANCE_LEVEL_16_235
0x6f81ac  MOVIE_LUMINANCE_LEVEL_16_255
0x6f81ec  MOVIE_AF_MODE_SINGLE / CONTINUOUS / MANUAL
```

★★ **`MOVIE_GAMMA_CONTROL_GAMMA_V` / `GAMMA_D`** ——
   固件里有**显式的 gamma 档位**（V = vivid？D = ？）。
   配合 `eIQ_ID_MOVIE_GAMMA_MODE`，这是一条**比 3D LUT 轻得多的色调曲线入口**。

---

## 六、`0x0806xxxx` 交叉分析：★ 假设被推翻

### 6.1 错在哪

上一轮报告（21:50）写：

> 固件里 `0x0806exxx` 引用 **5908 次**、`0x08075xxx` 4683 次
> ★ `0x0806xxxx` 与 EP 物理基址 `0x80506864` 同段
> ⇒ 下一步：导出 `0x0806xxxx` 全部引用位置，与 EP 子块表交叉

**这个 5908 是统计错误。** 我的脚本是：

```python
c[w>>16]+=1   # ← 把任意 32 位值按高 16 位分桶
if 0x80000000<=w<0xC0000000: c[w>>16]+=1
```

⇒ 任何数值落在 `0x08060000-0x0807ffff` 区间的 32 位值都被计入，
**不管它是不是地址**。

### 6.2 严格判据下的真实结果

| 判据 | 结果 |
|---|---|
| 4 字节对齐 + `0x08000000-0x0c000000` | **19,649 处** |
| **其中 `0x0806-0x0807` 段** | **0 处** |
| `0x0805-0x0807` 段（放宽到含 0x0805） | 88 处 |
| **LDR-literal 总命中**（工具有效性自证） | **58,107 处** |
| **★ LDR-literal 指向 `0x08060000-0x0807ffff`** | **0 处** |

被误计数的那些值长这样：

```
0x08070605   ← 末字节 05，不是 4 对齐
0x08060403   ← 03
0x08060107   ← 07
0x0807060e   ← 0e
0x0807030d   ← 0d
```
**全是普通数据，不是地址。**

### 6.3 EP 地址的直接搜索：全部零命中

| 地址 | 含义 | 在 p7 固件中出现 |
|---|---|---|
| `0x08050000` | EP top 基址（推测） | 2 次 |
| `0x08050600` | EP + 0x600 | 1 次 |
| **`0x20821c00`** | **NOG 物理基址（实测）** | **0 次** |
| **`0x2082b000`** | **3D LUT 物理基址（实测）** | **0 次** |
| **`0x80506864`** | **EP ioctl 号（实测）** | **0 次** |

### 6.4 结论（★ 谨慎表述）

**「EP 由 ISP 固件在驱动」在【地址空间层面】得不到任何支持：**
- ISP 固件**零引用** EP 子块物理地址
- **零 LDR-literal** 指向 `0x0806-0x0807`
- EP ioctl 号零出现

⇒ 这与实测的「EP 走标准 UDD（`/dev/drime5_ep` ioctl + **用户态自己 mmap**）」
   **完全一致**。ISP 固件和 EP 在**地址空间上不重叠**。

**⚠️ 但这不排除它们经共享内存交换数据。** 只能说：
**没有证据表明 ISP 固件直接操作 EP 寄存器。**
真正可能的协作方式 = **共享内存传帧**（ISP 出帧 → EP 处理 → 显示/JPEG），
这需要另找证据（查 `0x94000000` SMA 段在固件里的引用）。

### 6.5 剩余 88 处的真实归属

`0x0805-0x0807` 的 88 处对齐值分布：

```
0x0805a070  11 次   ← 最高频，但【无一被 LDR 引用】⇒ 数据表里的裸值
0x08064070   9 次   ← 集中在 0x7ab738-0x7ad220 一个函数簇
0x0806b070   5 次
0x0805a074   5 次
0x0805a078   5 次
```

`0x0805a070` 出现在 11 个字面量池位置，但**每个都没有对应的 `LDR` 指令**。
按 ARM 编译规律，这说明它们是**结构体成员或数据表项**，不是代码引用的基址。
⇒ **`0x0805xxxx` 段是数据，不是寄存器访问。**

**这块我还没定性。** 可能是：某张寄存器映射表 / 某结构体的字段值 /
IPCC 通道配置。**列为待查。**

---

## 七、对"反向设计 mod 和软件"的意义

现在手里的牌：

| # | 入口 | 机制 | 风险 | 状态 |
|---|---|---|---|---|
| 1 | **PW 7 参数** | prefman 槽位 + enum 跳变 | 低 | **已在用**（FilmLab 现役） |
| 2 | **`CC_RGB{L,H}_MAT_*`** | 3×3 矩阵，9 个数 | 低 | **★ 新发现，未验证** |
| 3 | **`MOVIE_GAMMA_CONTROL_*`** | gamma 档位 | 低 | **★ 新发现，未验证** |
| 4 | **`LUT_Load` / `LUT_ChangeAddress`** | ISP 侧 3D LUT | 中 | **★ 新发现，需找触发路径** |
| 5 | NOG 硬件颗粒 | `d5_ep_nog_set_noisegen` | 中 | 已解出寄存器偏移，未上机 |
| 6 | 改 p7 固件本体 | 直接 patch | **极高** | ⛔ **不建议**（会砖，除非有备份+恢复方案） |

### 推荐路线

**先做 #2 和 #3**（都是"写几个数"，判据清晰、可回滚），
再考虑 #4（要找到能触发 `LUT_Load` 的 IPC 命令）。

**⛔ 不建议动 p7 固件本体。** 虽然现在有完整备份在本地
（`raw8/p7/p7_full.bin`），但：
- 写入路径未知（分区可能在 bootloader 区被保护）
- 失败 = 相机变砖，且**没有可靠恢复手段**（`st firmware up` 支持 uImage/rom.bin，
  但 p7 是**裸镜像无封装**，能否通过该命令刷回**未验证**）
- 一旦刷错版本可能永久失砖

⇒ **如果有 mod 固件仓库社区（`nx500_nx1_modding` 上游）已经做过 p7 patch，
应该先找他们的方案，而不是自己动。**（这符合"优先用现成开源套件"的原则。）

---

## 八、下一步（按价值）

| 优先级 | 动作 | 判据 |
|---|---|---|
| **1** | 查 `0x94000000`（SMA 共享区）在 p7 固件里的引用 | **★ 回答"ISP 固件与 EP 是否经共享内存协作"** —— 这是 6.4 留下的唯一可能 |
| **2** | 反汇编 `LUT_SetParam` 那 7 个入口（步长 0x1c） | 解出 7 个参数语义 —— 若是 PW 7 参数则直接可用 |
| 3 | 定位 `CC_RGBL_MAT_*` 的引用代码 | 找到"谁填这张表" = 可控入口 |
| 4 | 查 GitHub 上游社区是否有人 patch 过 p7 | **★ 动固件前必须先查**（用户偏好：优先用现成方案） |
| 5 | NOG 探针 + 像素方差统计 | 定 FilmLab 硬件颗粒路线生死 |
| 6 | 解 PW 地址公式 `s*4` vs 7 参数的矛盾 | 需 prefman 实际 dump |

---

## 九、方法论记录（★ 本轮踩坑）

**★★ 统计"某段地址被引用多少次"时，必须先验证那个值"像地址"。**

我犯的错：用 `w>>16` 分桶统计，把**任何数值落在目标区间**的普通数据都算进来。
正确判据至少要加**对齐检查**（`(w & 3) == 0`），理想情况还要加**上下文判定**
（是 `LDR` 字面量池引用，还是裸数据）。

**推论：这类"频次统计"结论必须配一条反例检查** ——
取几个最高频的值看它们到底长什么样。如果末字节是 `05`/`03`/`07`，
说明它们根本不是地址，统计从根上就错了。

⇒ 已加为铁律 17 的补充（见 `test_server/isp/scanreg.py` 的注释）。
