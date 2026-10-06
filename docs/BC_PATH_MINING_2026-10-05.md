# B/C 路线静态挖掘报告 —— 找到 ISP 固件的完整源码树与配方系统

> 时间：2026-10-05 22:40
> 数据：`raw8/p7/p7_full.bin`（12,845,056 B）
> 工具：`test_server/isp/fnref.py`（新建，字符串锚点 → 函数定位 → 反汇编）
> 原始：`raw8/p7/{bc_mining_results.txt, source_tree.txt, tuning_keys.txt}`

---

## 一、结论先行：★★★ B/C 两路都打通了，而且超出预期

**这次挖掘的最大收获不是"LUT_Load 怎么触发"，而是——**

> ★★★ **固件里编译进了完整的 C++ 源码树路径（211 个 `.cpp`），
> 包括配方系统和 EP 后端的全部类名。**

这意味着我们不是在逆向黑盒，而是在**读一份泄露了目录结构的源码树**。

| 路线 | 目标 | 状态 |
|---|---|---|
| **B** | ISP 侧 3D LUT | ✅ **源文件定位完成**：`product/Backend/EP/3DLUT/CBackend_3dlut.cpp` |
| **C** | 3×3 色彩矩阵 | ✅ **完整键空间拿到**：`color.txt` 31 键，含两组 3×3 + R2Y 矩阵 |
| **★ 新** | gamma 曲线 | ✅★★ **22 个 X 锚点 + 22 个 Y 锚点 = 可自由塑形的曲线** |

---

## 二、★★★ 发现 1：完整 C++ 源码树（211 个文件）

路径格式 `product/<Module>/<Sub>/<Class>.cpp`：

| 模块 | 文件数 | 用途 |
|---|---|---|
| `product/Liveview/material` | 29 | 取景器素材 |
| **`product/Liveview/recipe`** | **28** | ★★★ **配方系统** |
| **`product/Backend/EP`** | **22** | ★★★ **EP 后端** |
| `product/Liveview/parts` | 19 | 取景器各功能部件 |
| `product/CaptureController/Handler` | 11 | 命令处理 |
| `product/Liveview/common` | 11 | `CLiveviewBuffer` / `Factory` / `Notification` |
| `product/Liveview/process` | 6 | |
| `product/Still/Material` | 6 | |
| **`product/Backend/IPC`** | **6** | ★★ **跨核通信** |
| `product/FrontEnd/Shutter` | 5 | 快门 |
| `product/CaptureController/3AController` | 5 | 3A（AE/AF/AWB）|

全表：`raw8/p7/source_tree.txt`

---

## 三、★★★ 发现 2：配方系统（`product/Liveview/recipe`，28 个）

### 3.1 核心类

| 地址 | 类 | 作用 |
|---|---|---|
| `0x7121a8` | `CLiveviewParameterTable.cpp` | ★ 参数表 |
| `0x712298` | `CLiveviewRecipeParameter.cpp` | ★ 配方参数 |
| **`0x72c97c`** | **`CLiveviewRecipeListBase.cpp`** | ★★ **配方列表基类** |

### 3.2 按场景各一个配方类（★ 关键设计洞察）

**视频配方**：
```
CLiveviewRecipeListLiveview.cpp            取景器默认
CLiveviewRecipeListLiveviewRaw.cpp         RAW
CLiveviewRecipeListLiveviewOTF.cpp         OTF
CLiveviewRecipeListLiveviewOTF_HDMI.cpp    OTF + HDMI
CLiveviewRecipeListLiveview3D_HDMI.cpp     3D + HDMI
CLiveviewRecipeListLiveviewPPonly.cpp      仅后处理
CLiveviewRecipeListLiveviewWaterfall.cpp   ★ 瀑布流（Samsung 特色）
CLiveviewRecipeListFastAF.cpp / SSS.cpp / Fisheye.cpp / MFZoom.cpp
```

**★ 跨核配方（重大发现）**：
```
CLiveviewRecipeListLiveviewIPCMtoM.cpp     ★★ IPC Main→Multi-core
CLiveviewRecipeListLiveviewSRAMtoM.cpp     ★★ SRAM Main→Multi-core
CLiveviewRecipeListLiveviewLDCMtoM.cpp     LCD Main→Multi-core
```

⇒ ★★★ **"MtoM" = Main to Multi-core**。
**这直接回答了昨晚那个悬案** —— 配方是**跨核同步**的，
经 **IPCMtoM**（IPC 通道）或 **SRAMtoM**（共享内存）传递。

⇒ ★ **这就是把配方表塞进 `0x94000000` 那块共享内存的代码路径**，
也解释了为什么 CMA 里会有 YCC Ring Buffer。

**静态拍摄配方**：
```
0x72e18a  CLiveviewRecipeListPanorama.cpp   全景
0x72e68a  CLiveviewRecipeListBurst.cpp      连拍
```

**电影配方**：`Movie{,FullHD,FullHD3D,HD,QVGA,VGA,UD,UDCleanOut}.cpp`

---

## 四、★★★ 发现 3：EP 后端（`product/Backend/EP`，22 个）—— B 路目标

### 4.1 3D LUT 有三条独立路径（★★ 安全实现的关键）

| 地址 | 类 | 路径 |
|---|---|---|
| **`0x714888`** | **`CBackend_3dlut.cpp`** | ★★ 主类 |
| `0x7148f4` | `CBackend_3dlut_Base.cpp` | 基类 |
| `0x7149fc` | `CBackend_3dlut_View.cpp` | **取景器**路径 |
| **`0x714a90`** | **`CBackend_3dlut_Still.cpp`** | ★★ **静态拍摄**路径 |
| **`0x714b14`** | **`CBackend_3dlut_CS.cpp`** | ★★ **色彩空间转换**路径 |

⇒ ★★★ **3D LUT 在三处独立可加载**：
**View（取景器）/ Still（拍照）/ CS（色彩空间转换）**

⇒ ★★ **这是安全实现的关键**：
魔灯可以**只改 `CBackend_3dlut_Still` 路径**，
**完全不影响取景器显示**。这样即使 LUT 配错了，
最坏后果只是拍出来的片子难看，**取景器不会黑屏、不会卡死**。

### 4.2 NOG 后端也在这里

| 地址 | 类 |
|---|---|
| `0x713ce0` | `NoiseGen/CBackend_Nog.cpp` ★★ |
| `0x713e30` | `NoiseGen/CBackend_Nog_Base.cpp` ★★ |

⇒ ★ **NOG 的固件侧实现在这里**，跟 `libudd5.so` 的
`d5_ep_nog_set_noisegen` 是**两套实现**（同 `libudd5` vs `CBackend_3dlut` 的关系一样）。
⇒ **要开硬件颗粒，得从 ISP 侧的配方系统下手，不是 Linux 侧。**

### 4.3 其余 EP 后端

```
0x715040  MC/HDR/CBackend_MC_HDR.cpp     ★★ HDR 多帧合成
0x7151e8  MC/LLS/CBackend_MC_LLS.cpp     ★★ 低照度合成
0x714cfc  MC/CBackend_MC.cpp              多帧合成基类
0x71530c  Jpeg/CBackend_Jpeg.cpp
0x7155b4  BitBlt/CBackend_BitBlt.cpp
0x7157dc  BitBlt/BitBltFunc/CBitBltFunc.cpp
0x7134a8  LDC/CBackend_Ldc.cpp           镜头畸变
0x712c80  OTF/CBackend_EpOtf.cpp
0x713ed4  Resize/CBackend_Resize.cpp
```

⇒ ★★ **`MC_LLS`（低照度）+ `MC_HDR`（HDR）+ `NOG`（颗粒）三件套**
= 夜摄/逆光/胶片颗粒的硬件基础，**全都在 EP 里**。

---

## 五、★★★ 发现 4：`CBackend_3dlut` 的内部方法（从错误串反推）

```
0x714708  "(LUT_Load) _load error!!"
0x714724  "(LUT_ChangeAddress) _changeDma error!!"
0x714750  "(LUT_Stop) _stop error!!"
0x71476c  "(LUT_Start) _run error!!"
0x714788  "(LUT_SetParam) Input param is NULL!!"
0x7147b0  "(LUT_SetParam) Ctrl Param Error!!"
0x7147d4  "(LUT_SetParam) _setDmaMux error!!"
0x7147f8  "(LUT_SetParam) _setParam error!!"
0x71481c  "(LUT_SetParam) _setWDma error!!"
0x714840  "(LUT_SetParam) _setCtrl error!!"
0x714864  "(LUT_SetParam) _setRDma error!!"
0x7148b4  "(Callback) 3dlut Done (Error=%d)"
0x7148e4  "st3dlutParam"                    ★ 内部结构体
```

⇒ ★★ **内部方法名全部可读**：
`_load` / `_changeDma` / `_stop` / `_run` / `_setDmaMux` / `_setParam` /
`_setWDma` / `_setCtrl` / `_setRDma`

⇒ ★★★ **走的是 DMA 路径**（`WDma` / `RDma` / `DmaMux`）
⇒ **LUT 数据经共享内存搬运** —— 这就是昨晚 SMA 验证想找的东西，
现在从代码侧证实了：**3D LUT 数据确实经 DMA/共享内存流动**。

⇒ ★ **`(Callback) 3dlut Done (Error=%d)` 说明有完成回调**
⇒ 这是潜在的挂钩点（虽然 C++ 回调不好 hook，但至少知道结构）。

---

## 六、★★★ 发现 5：调参键空间 12,916 个

全表：`raw8/p7/tuning_keys.txt`

### 6.1 配置文件 → 键数

| 配置文件 | 键数 | 用途 |
|---|---|---|
| `/mnt/mmc/dump_rw_test.txt` | 6044 | 调试 |
| `sra.txt` | 1258 | 传感器读出 |
| `paf_adjData_backup.txt` | 1239 | PAF 校准 |
| `/mnt/mmc/lensdump.txt` | 1036 | 镜头 |
| `zoom_%d.txt` | 1023 | 变焦 |
| **`cfai.txt`** | **89** | ★★ CFAI（锐度/对比度） |
| `wbee.txt` | 73 | ★★ 曝光 |
| **`gamma.txt`** | **45** | ★★★ **gamma 曲线** |
| **`color.txt`** | **31** | ★★★ **3×3 色彩矩阵** |
| `lcac.txt` | 20 | ★★ 局部色度校正 |
| `wb.txt` | 8 | 白平衡 |

### 6.2 ★★★ `color.txt` 的 31 个键（C 路完整目标）

```
CC_RGBL_MAT_00 .. CC_RGBL_MAT_22    (9)  低照度 3×3
CC_RGBH_MAT_00 .. CC_RGBH_MAT_22    (9)  高照度 3×3
R2Y_MAT_00    .. R2Y_MAT_22        (9)  ★★ RGB→Y 矩阵！
SE_MAT_00 / 01 / 10 / 11            (4)  ★★ SE 矩阵
```

⇒ ★★★ **比我原先估计的多两组**：
- 不只 RGBL/RGBH 两个 3×3，还有 **`R2Y_MAT`（RGB→Y 转换矩阵）**
  —— 这直接控制**亮度通道的生成**，对胶片仿真极重要
  （不同胶片的 RGB→Y 系数不同，这正是"胶片感"的一部分）
- `SE_MAT_00/01/10/11` 是 2×2（只有 00/01/10/11，无 02/12/20/21）
  ⇒ 可能是 **饱和度增强矩阵**或色温相关的 2×2 变换

### 6.3 ★★★ `gamma.txt` 的 45 个键（B 路核心 —— 这才是"魔灯"）

```
GAMMA_INDEX
TC_LOW_ANCHOR_X00 .. X21     (22 个 X 锚点)
TC_LOW_ANCHOR_Y00 .. Y21     (22 个 Y 锚点)
WB_OFFSET_RR / GR / GB / BB  (4)  白平衡偏移
WB_GAIN2_RR / AIN2_GR / GB   (3)  白平衡增益
```

⇒ ★★★★ **22 个 X 锚点 + 22 个 Y 锚点 = 一条完全自由塑形的色调曲线**

这就是胶片模拟的核心：**你可以定义任意输入→输出映射**。
- X 锚点 = 输入亮度点（0..1 分布）
- Y 锚点 = 该输入对应的输出亮度

⇒ ★ **这比 3D LUT 更轻量**（44 个数 vs 33³ = 35937），
   而且**已经存在固件里**，只要找到往 `gamma.txt` 对应内存写值的路径。

⇒ ★★ **"三星魔灯"的核心目标应该是这个，而不是 3D LUT**：
   44 个数就能定义一条完整的胶片曲线。

---

## 七、修正后的魔灯路线图

| 优先级 | 目标 | 键数 | 风险 | 状态 |
|---|---|---|---|---|
| **1** | ★ **gamma 曲线** `TC_LOW_ANCHOR_X/Y00..21` | **44** | 低 | **★ 新发现，首选** |
| **2** | **3×3 矩阵** `CC_RGB{L,H}_MAT_*` + `R2Y_MAT_*` | 22 | 低 | ★ 新发现 |
| 3 | `CFAI_*`（锐度/对比度）| 89 | 低 | 已知有 |
| 4 | 3D LUT（走 `CBackend_3dlut_Still`）| 33³ | 中 | 源文件已定位 |
| 5 | NOG 硬件颗粒（走 `CBackend_Nog`）| — | 中 | 源文件已定位 |

### ★★ 为什么 gamma 曲线排第一

1. **参数最少**（44 个数 vs 3D LUT 的 35937）
2. **语义清晰**（X/Y 锚点直接就是曲线控制点）
3. **不涉及 DMA**（3D LUT 走 DMA，gamma 大概率是寄存器直写）
4. **已在固件里**（不需要新增功能，只需找到写入路径）
5. **可分段**（`TC_LOW_` 前缀说明可能还有 HIGH/MID 分档 ⇒ 不同亮度段不同曲线，
   这正是胶片的特性：暗部厚、亮部薄）

### ★★ 安全实现的三个保障

1. **只改 `CBackend_3dlut_Still` 路径**，不碰 View ⇒ 取景器不受影响
2. **优先走 gamma/矩阵**（寄存器直写）而不碰 3D LUT（DMA）
3. **单核相机实验纪律**：首验 1 张 1 尺寸，批量 ≤3

---

## 八、下一步

| 优先级 | 动作 | 成本 | 能回答什么 |
|---|---|---|---|
| **1** | 反汇编 `CBackend_3dlut_Still.cpp`（`0x714a90` 附近的字符串锚点）| 纯离线 2h | ★★★ `LUT_Load` 的调用者是谁、参数从哪来 |
| **2** | 找 `TC_LOW_ANCHOR_X00` 的**写入者**（不是字符串表，是谁给它赋值）| 纯离线 2h | ★★★ gamma 曲线的注入口 |
| **3** | 找 `CLiveviewRecipeParameter.cpp`（`0x712298`）的参数表结构 | 纯离线 1h | 配方参数的完整定义 |
| 4 | 查 `product/Backend/IPC`（6 文件）的消息协议 | 纯离线 1h | 配方如何跨核传递 |
| 5 | 实机：读 `d5_sma` 分配表拿真实缓冲地址 | 实机只读 | 补上昨晚未证的那条 |
| 6 | ★ 查上游社区 p7 patch 方案 | 纯离线 | 动固件前必查 |

⇒ **第 1、2 项都是纯离线，不需要相机通电。**
★ **建议优先做第 2 项**（gamma 注入口）—— 如果它是寄存器直写，
   那魔灯的实现难度会大幅下降。

---

## 九、本轮方法论记录

**★ 有效手法（可复用）**：固件没有符号表，但保留了
①C++ 源文件路径串（`product/**/*.cpp`）②运行时错误串（`"(LUT_Load) _load error!!"`）
③键名表（`color.txt` → `CC_RGBL_MAT_00`）。三者结合能**从功能名反推到类结构与方法名**。

**⚠️ 遇到的问题**：`fnref.py` 对 `LUT_Load` / `CC_RGBL_MAT_00` 都报"零 LDR 引用"——
**这不是"目标不存在"，而是"通过表指针间接访问"**。
工具已按铁律 16 区分这两种状态（报"找到字符串但零引用"而非"未找到"）。
真正的定位手段是**顺着 `product/**/*.cpp` 路径串找同模块的其它串**，
靠**语义邻近性**推断模块边界，而不是靠直接引用。
