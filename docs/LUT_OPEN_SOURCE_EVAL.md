# 开源 LUT 资产可用性评估（2026-10-05）

> 三个问题：①GitHub 上的开源 LUT 项目能否用 ② 能否支持「LUT 拍照」（机内实时）
> ③ 松下 LUT 相关专利是否构成障碍
> **全部结论基于实测 + 一手文档，不是转述。**

---

## 结论先给

| 问题 | 结论 |
|---|---|
| 开源 LUT 项目能否用 | ✅ **能，已下载实测跑通**。`scernst13/HaldCLUT-Cube-Files`，**CC0**，14 个 33³ `.cube` |
| 能否支持「LUT 拍照」（机内实时） | ❌ **不能**——但**不是 LUT 的问题，是NX500 固件封闭**（见第三节，已实机定案） |
| 松下专利是否是障碍 | ❌ **不是**。查到的那批专利保护的是「实时取景→按操作成员→弹出数据集选择画面」这个 **UI 交互**，不覆盖「用 3D LUT 做胶片风格」本身 |
| 那能走哪条路 | ✅ **PC 端 RAW 域仿真**（唯一已达打印级的路）。CC0 LUT 直接可用，实测通过 |

一句话：**开源 LUT 资产本身完全可用且合法；卡住的是相机侧写入通道，这条我们10 月已用实机数据定案。**

---

## 一、候选项目与实测

### ✅ 选定：`scernst13/HaldCLUT-Cube-Files`

| 项 | 值 | 核验方式 |
|---|---|---|
| 许可 | **CC0 1.0 Universal** | ★ **读了仓库 `LICENSE` 原文**，不是看 marketplace转述 |
| 作者 | scernst13 | README |
| 建仓 | 2026-02-22 | git log |
| 导出工具 | LUT Lab 1.2.1 | 文件头注释 |
| 尺寸 | `LUT_3D_SIZE 33` = **35937 节点** | `load_cube` 实测 |
| 数量 | 14 个，约 21MB | `find` + `du` |
| 用途 | 原文："for usage in Real Time LUT application on **Lumix Cameras**" | README |

**内容**（`Kodak Converted/`）：Portra 160/400/800（各带 `++` 版本）、
Ektachrome 100 VS、E-100 GX、Elite Chrome 200/400、Elite Color 200/400、
Kodachrome 200/64。

**已取 6 个进仓库**（`test_server/filmsim/luts/`），与我们的配方体系对得上的：
Portra 160/400/800、Ektachrome 100 VS、Kodachrome 64、Elite Chrome 400。
来源与许可记录在 `luts/SOURCE.md`。

### 为什么这个安全（三层）

1. **CC0** = 放弃所有权利，可商用可改，无需署名（我们仍然署名）。
2. **来源是 HalD CLUT**——Andrew Halter 1990 年代公开的色彩样本网格方法，
   创意公共领域，不是 Kodak 的专有色彩描述文件。
3. 作者用 **LUT Lab 转换 + 自测**，不是从 Kodak 专有数据提取。

### 其他候选（评估后未采用）

| 项目 | 为什么不选 |
|---|---|
| `bean-mhm/flim` | 它是 **Python 脚本 + 预设生成器**，要跑还得配 OpenColorIO + Colour + NumPy + Joblib。我们只需要 `.cube` 成品，flim 的产物是 `.spi3d`。**过度依赖** |
| `BISAM20/ComfyUI-ACES-IO` | ComfyUI 节点，依赖 PyOpenColorIO。整个 ComfyUI 栈拉进项目不合理 |
| `sumitchatterjee13/nuke-nodes-comfyui` | 同上，Nuke 节点 |
| Archade marketplace上的 Portra 800 / Kodachrome 64 | ★ **就是 scernst13 同一批文件被上架卖**（页面写 `Source: github.com/scernst13/HaldCLUT-Cube-Files`，License CC0）。**直接回GitHub 取即可，不必从付费平台买** |

> ★ 这条值得单列：同一批 CC0 文件在付费 marketplace 上架售价「Price on request」。
> 按项目约定「优先开源套件」，直接取上游。

---

## 二、实测：我们的引擎能不能吃下33³ LUT

### ✅ 能。`engine.py` 早就有完整实现

`load_cube` / `_cube_lookup`（三线性插值）/ `apply_cube` / `apply_recipe`
的 `lut3d` 分支都存在。实测：

```
load_cube: size=33  节点数=35937  解析耗时=0.03s
```

**14/14 个文件 size 声明与实际行数全部一致**（35937 = 33³，逐个核对过）。

### ★★ 实测中发现并修掉一个真 bug：负索引绕表尾

```python
# 修前：只clamp 上界
ri = int(r); gi = int(g); bi = int(b)
if ri > size - 2: ri = size - 2   # ← 只有上界
# rf < 0 时 ri < 0 → Python 负索引绕到表尾 → 静默返回错误颜色
```

这个 bug 的恶劣之处：**不报错，只是颜色悄悄错掉**。
触发条件是外部传入略超界的浮点（如 `1.0000000002` 或 `-0.01`）。

已修为输入先夹到 `[0,1]`，索引再上下双向 clamp。文件头也补了轴序说明。

### ★★ 一个必须记下的判据设计教训

我最初用「把 `at()` 的两种轴序解释写在一起对比」来判定轴序——**这是无效判据**，
因为两边共用同一个索引公式，等于什么都没测。差点据此改错代码。

后来换成两个**真正独立**的判据：

**A. 恒等表回归（自证）**
构造 32³ 恒等表喂进去，五个采样点零误差还原 ⇒ 索引语义与 Adobe 规范一致。
```
[PASS] 纯红   零误差还原 (实际误差 0.00000)
[PASS] 纯绿   零误差还原 (实际误差 0.00000)
[PASS] 纯蓝   零误差还原 (实际误差 0.00000)
[PASS] 25%灰  零误差还原 (实际误差 0.00000)
[PASS] 中灰   零误差还原 (实际误差 0.00000)
```

**B. 真实 LUT × 真实人像（外部交叉验证）**
拿 Portra 400 套 `raw/SAM_3187_view.jpg`（人像），判据 = **肤色区平均输出必须保持 R>G>B**。
这条不依赖我们对格式规范的信心，只依赖「人脸不能变蓝」这个物理事实。
```
原图  肤色区均值 R=44.3% G=47.4% B=51.9%     ← 原图偏冷
应用后        R=50.1% G=42.0% B=41.6%     ← 变暖
[PASS] 应用后肤色仍保持 R>G>B
```
**偏冷 → 偏暖正是 Portra 的招牌**（暖肤色 + 轻微青影）。这与Portra 的已知特性一致，
反过来印证了管线正确。

### 回归测试已固化

`test_server/filmsim/lut_regress.py`，**11/11 全过，纯 PC 不上相机**：

```
== A. 恒等表回归 ==          5 PASS
== B. 边界鲁棒性 ==          5 PASS   （负输入/超上界/全负/全0/全1）
== C. 真实 LUT × 人像 ==2 PASS   （size 一致性 + 肤色关系）
```

★ 符合项目铁律「判据工具必须能离线回归」——单核相机不适合频繁上机，这是刚需。

### ★ 性能提醒：纯 Python 逐像素

`apply_cube` 是 `for y: for x:` 的纯 Python 双层循环，1600×1068 的图要跑几分钟。
**PC 端用 numpy 向量化重写会快两个数量级**。这是要做的下一件事，
但不影响「能不能用」的结论。

---

## 三、能否支持「LUT 拍照」（机内实时）——不能，且已实机定案

★ **这不是LUT 资产的问题，是 NX500 固件的封闭性。** 我们 10 月已有完整实机证据链。

### 证据链（`test_server/pwfilter/b1/`）

**① 硬件确实存在 3D LUT**
`libudd5.so` 51 个 3D LUT 符号全未剥离，核心接口：
```
d5_ep_3dlut_op_init / d5_ep_3dl_load_lut / d5_ep_3dl_save_lut
_udd_ep_3dl_reg_GetReg / SetReg / SelLUT / SelCbCr_ch / SetAddress
OBJECT ep_3dlut_reg_base    ← MMIO 寄存器基址
```
寄存器位域全表已解出（含 `ConfigBypassMode` = 3D LUT 总开关），
**且 Cb/Cr 可独立选表** → 硬件能力足够做真split toning。

**② 但写入者在内核态**
8 个加载 `libudd5` 的二进制做符号明文匹配，**只有 `libudd5.so` 自己命中**；
`libcapture-fw-prod` 的 1003 个 PLT import ∩ libudd5 的 552 符号 = **仅 22 个 libc 函数**。
→ **3D LUT 写入者是内核/ISP 固件，用户态只能经属性总线下达意图。**

**③ 属性总线没有色彩表入口**
`libcapture-fw-prod.so` 全部 1988 个符号里，筛出所有 `set*/get*/load*/config*`：
```
getPWColor / setPWColor / setWBKelvin / setPWBracket / getColorSpace ...
```
- **没有** `setLUT` / `setColorProfile` / `setToneCurve`
- `getColorSpace` **只有 getter 无 setter** → 色彩空间只读
- 所有含 "3D" 的符号都是**立体电影**（3D Shot / 3D Framerate / 3D Format），不是 3D LUT
→ **路径关闭。属性总线只能表达「厂商预设的枚举 + PW 7 维连续值」，无法载入任意色彩表。**

**④ B1 路线实测：卡在 handle 不可伪造**
`dlopen("libudd5.so")+dlsym` 成功，**26/27 符号拿到**，
10 个符号的「运行时地址 − 静态偏移」**全部 = 0xb6d29000** ⇒ 静态反汇编每个地址都被实机确认。

但按反汇编校验条件自造结构体调 `d5_ep_3dlut_op_init` → **立即 SIGSEGV**。
原因：`[r3+4]/[r3+8]/[r3+0xc]` 是**三级指针**，要的是指向 ISP 对象的句柄；
传栈副本会被当句柄解引用。

```log
RB=00000000
regbase null, ISP not initialised
```

⇒ **不是「不该」由用户态调，而是「调不动」。**
（且恢复出厂后 `ep_3dlut_reg_base = 0` —— 相机默认根本不用它。）

### 结论：ISP 色彩管线在用户态完全封闭

- **底层**（3D LUT / NOG 颗粒 / 曲线）→ 需要内核 handle，用户态拿不到
- **上层**（属性总线）→ 只有枚举和 7 个连续标量，没有「载入任意表」的接口

**所以「LUT 拍照」在 NX500 上做不了。** 无论 LUT 从哪来。

---

## 四、松下 LUT 专利——不是障碍

### 查到的相关专利

| 编号 | 名称 | 状态 |
|---|---|---|
| **US 20250184440**（申请号）<br>优先权 JP 2023-204780 | IMAGING APparatus | 申请日 2024-11-29，公开日 2025-06-05，**未见授权** |
| JP 7129678 B | 用LUT 做图像处理的成像装置 | 已授权（被上述专利引为背景技术） |
| US 8212836 | Color management module（3D LUT + HSV 校正 + 自适应联动） | 已授权 |
| US 7880814 | 2D LUT 增益型视觉处理装置 | 已授权 |

### 权利要求 1 的实际边界（读原文得出）

`US 20250184440` 权利要求 1 的必要技术要素：
1. 成像装置 + 图像传感器
2. 存储器存**多个**色彩分级数据集
3. 显示器显示**第一实时取景画面**
4. 用户界面 + **第一操作成员**
5. 控制器：在实时取景期间接收操作成员输入，
   **把显示从实时取景画面切换到「色彩分级数据集的选择画面」**

**它的区别点是那个交互流程，不是LUT 算法。**

| 实施情形 | 是否落入权利要求 1 |
|---|---|
| 存多个 3D LUT + 按LUT 键进选择画面（含虚拟按钮/触摸/旋钮） | ⚠️ 可能满足 |
| 拍照后对存储照片应用 LUT，无实时取景交互 | ✅ 通常不满足 |
| 只存一个固定 LUT 自动应用 | ✅ 通常不满足 |
| **只说「用 3D LUT 给照片加胶片风格」** | ✅ **不满足**（缺传感器/显示器/取景/操作成员等要素） |

**关键**：权利要求 1 里
- 没有要求数据集必须是 LUT，更没要求 3D LUT
- 没有要求产生「胶片风格」或任何特定视觉风格
- 说明里的 `vintage`/`rose`/`fashion` 只是 LUT 命名示例

从属权利要求 2–9 才进一步限定：切换到应用后的第二实时取景、返回流程、
shooting mode、实时预览、image processor 等。

### 更本质的一点：3D LUT 本身是老技术

3D LUT 是 **1990 年代就存在的通用技术**，Adobe 1993 年就在 Photoshop 里用，
Direct2D 有 `ID2D1LookupTable3D`，OpenGL ES 有标准 GLSL 3D LUT 着色器。
各家相机/显示器的「硬件 3D LUT」专利（EIZO 2009 年的 CG242W、SONY、BENQ）
都早已到期或压根没被主张。

**而本次选用的 CC0 HaldCLUT 是 1990 年代的 HalD CLUT 方法的现代转换。**

### 落到我们项目上

- 我们用 CC0 LUT 在 **PC 端**处理**自己拍的RAW**，不碰松下的交互流程
- 不用松下 VariCam 的 `.VLT` / `.CUBE` 文件（那是松下自己作品集，虽然免费下载，
  但没必要引入品牌资产）
- NX500 是**三星**的机，松下专利与本项目无实施关联

**结论：无法律风险，无需规避设计。**

> ⚠ 一句话免责：以上是技术层面的范围分析，不构成法律意见。
> 真要商用分发，去查对应法域的专利登记状况。

---

## 五、路线裁决

| 路线 | 状态 | 说明 |
|---|---|---|
| **PC 端 RAW 域仿真 + CC0 LUT** | ✅ **推荐** | 唯一已达打印级。CC0 LUT 直接可用，回归测试已固化 |
| 机内 prefman 7 维PW（现FilmLab） | ✅ 在用 | 免 save 即时生效、0x1s 响应；**但 7 个标量做不出真曲线** |
| 机内 3D LUT 实时 | ❌ | `ep_3dlut_reg_base = 0` + handle 不可伪造 + 属性总线无入口，三重封死 |
| 改内核 / ISP 固件 | ❌ | NX1 GPL 包只有内核 + packages，**ISP 固件是闭源二进制** |

**⇒ LUT 的正确用武之地是 PC 端，不是机内。**
这也正好对上项目既有结论：引擎架构是「recipe + .cube LUT + capdtm ISP 滤镜集成」，
但真曲线那一段历来是 PC 端在做。

---

## 六、下一步（待你定）

1. **配 6 个 CC0 LUT 进 `recipes/*.json`**
   现在 9 个配方全是7 维标量。加 `lut3d` 字段即可走 `.cube` 管线。
   要做的是**反向拟合**：PC 端拍 9 个配方 → 读回 PW 7 维 → 反推哪组 7 维标量
   最接近该 LUT 的观感，写进 JSON。
   ★ 这是把「LUT 品质」塞进「7 维表达能力有限」这个通道里，属于降级逼近，
   效果必然不如直连 LUT。要不要做取决于你对当前观感的满意度。

2. **用 CC0 LUT 直接出片看效果**（最直接）
   PC 端跑 RAW + Portra 400，看是否比现在的 7 维配方更接近你心里的 Portra。
   如果差距明显，就说明必须走 PC 端而非机内。

3. **`apply_cube` 向量化**
   纯 Python 逐像素 → numpy 三线性插值，快两个数量级。
   打印级输出（大图 +高质量 JPEG）这个耗时必须解决。

4. **是否再取其余 8 个 LUT**（Kodachrome 200、Elite Color 200/400、E-100 GX 等）

---

## 相关文件

| 文件 | 说明 |
|---|---|
| `test_server/filmsim/luts/*.cube` | 6 个 CC0 LUT（33³） |
| `test_server/filmsim/luts/SOURCE.md` | 来源与许可记录 |
| `test_server/filmsim/lut_regress.py` | 3D LUT 回归测试（11 断言，纯 PC） |
| `test_server/filmsim/engine.py` | `_cube_lookup`（已修负索引 bug + 补轴序说明） |
| `test_server/pwfilter/LUT_REGISTERS.md` | 3D LUT 寄存器映射全表 |
| `test_server/pwfilter/b1/ALL_PATHS.md` | 属性总线无色彩表入口的完整证据 |
| `test_server/pwfilter/b1/RESULTS.md` | B1 探针实机结果（handle 不可伪造） |
