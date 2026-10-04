# NX500 胶片模拟：全部可行路径（2026-10-04 14:10 评估）

> 前提：木一明确"不想只做机内原有自定义"。
> 本文把能走通的路和死路都列出，标注实测状态与代价。

## 一、先说被堵死的三条（都已实机验证，别再投时间）

| 路径 | 状态 | 实测证据 |
|---|---|---|
| 3D LUT 注入 | ❌ **死路** | `d5_ep_3dlut_op_init` → SIGSEGV，handle 是内核态对象 |
| PW 直写内核 API | ❌ **死路** | `yccmixer` 经 `nog_seed_load_switch` 取寄存器组 → 返回 0 → 写 0x280 → SIGSEGV |
| 硬件颗粒 NOG 直调 | ❌ **死路** | `.bss` 指针数组由内核填充，用户态读到 0 |

**共性：所有 ISP 底层寄存器/对象的控制权在内核态。用户态只有"读符号"权限。**

## 二、属性总线已扫完（0–126 全部实机验证）

**结论：机内属性总线上没有颗粒/噪点维度。**

| 索引 | 名称 | 与画质相关 |
|---|---|---|
| 20 | PW_TYPE | ★ 7 维风格 |
| 21 | SMARTRANGE | ★ |
| 25 | FACETONE | ★ 肤色 |
| 27/28 | SMARTART / LEVEL | ★ 艺术效果 |
| 34 | WBBRKSET | ★ |
| 62/63 | SMARTFILTERTYPE / 强度 | ★★ 14 种效果 |
| 67 | HDR_OFF | 可能 |
| 69 | IZOOM | 可能 |
| 81 | SMARTPROMODE | ★ 智能滤镜场景 |
| 83 | EFS_ON | 电子防抖 |
| 108 | OLEDCOLOR | ★ 屏幕 |
| **121** | **GOLFREVERSE_ORIGINAL** | ★ 高光降噪 |
| **122** | **RAWQUALITY_LOSSLESS** | ★★ RAW 格式 |
| **123** | **RAW_SAVE_OFF** | ★★ 是否存RAW |
| **124** | **SSIF_RAW_OFF** | |
| **125** | **RAW_BIT_14BIT** | ★★ 14bit RAW |
| **126** | **RAW_PACK_PACK** | 打包 |

**★ 新发现（14:10）**：`GOLFREVERSE_ORIGINAL`（高光降噪）是一个**独立的机内降噪维度**，
能单独控制高光区噪声——这是"降噪"这个胶片要素在机内唯一的抓手。
另外 RAW 相关 5 个索引可控 RAW 的保存/位深/打包。

## 三、真正能走通的路径

### 路径 A：PC 端 RAW 域仿真 ★★★ 唯一能达到打印级的路
**原理**：rawpy 解码 → 线性化 → 完整 ISP 模拟（tone curve / 色彩矩阵 / 颗粒 / halation）
→ 导出 16bit
**已验证**：rawpy 0.27.1 解码 `SAM_3187.SRW` 成功，6496×4336 / 14bit / BGGR / 0.6s
**能做**：per-channel curve、亮度分区、split toning、**真实胶片颗粒**、halation
**代价**：36MB 传输（20.5s）+ 处理时间
**评估**：★ 画质天花板，但不出机内

### 路径 B：机内扩展维度组合 ★★ 已验证可用
**原理**：把属性总线上所有画质维度组合起来
**已验证可用维度**：
- PW 7 维（R/G/B/HUE/SAT/SHARP/CONTRAST）
- WB K值 + tint（A/B 两轴）
- SmartFilter 类型 14 种 + 强度
- SmartRange、SmartArt、SmartProMode
- Facetone（肤色）
- **GOLFREVERSE（高光降噪）← 新发现**
**组合空间**：7 维连续 + 14×5 滤镜 + ... = 远超 8 个配方
**代价**：全在机内，ISP 渲染，**CPU 零开销**，**实时**
**评估**：★★ 覆盖 90% 的胶片观感，但受"全局标量"天花板限制，做不了真曲线

### 路径 C：机内 JPG 后期处理 ★ 半条路
**原理**：相机拍完 JPG，用机内 ImageMagick（`tools/usr/bin/convert`）做二次处理
**能做**：JPG 域也能做曲线、色彩平衡（虽然不如 raw 域准）
**代价**：二次编码损失 + 单核 ARM 慢（JPEG 28MP 处理可能十几秒）
**评估**：★ 意义不大，JPG 域做胶片是伪模拟

### 路径 D：机内 X11 半透明叠加层 ★ 玩法向
**原理**：X11 已验证可挂全屏窗口（720×480），可以画半透明胶片 LUT 预览叠加
**做法**：PC 渲染 LUT 预览图 → push 到相机 → X11 窗口 alpha 混合叠加在取景器上
**能做**：**所见即所得的胶片效果预览**（不改变拍摄结果，只做参考）
**代价**：需要 liveview 帧（`st cap live dump` 未打通）→ **前提不成立**
**评估**：★ 卡在 liveview，可先降级为"外接屏模拟"

### 路径 E：3D LUT 的最后一线 ★★ 有条件可行
**思路**：`libcapture-fw-prod.so` 的 `CAttributeHandler` 是**用户态属性服务端**，
它能通过 IPCC 让 ISP 执行设置。
**关键问题**：它有没有暴露"载入色彩表"的属性 ID？
**做法**：反汇编 `CAttributeHandler` 全部 1988 个符号，找 `setXXXLUT` / `loadColorProfile` 类的方法
**已有线索**：`getColorSpace()` 存在（0x93000）→ 说明有色彩空间概念
**评估**：★★ 值得花 1 小时反汇编验证。成了就是机内真曲线

## 四、我的建议

### 主力：路径 A（PC RAW）+ 路径 B（机内组合）分工
```
拍摄时 → 路径B：机内 7 维 + SmartFilter + GOLFREVERSE 实时预览（ISP 渲染，零开销）
出片时 → 路径 A：下载 RAW，PC 端做完整胶片曲线 + 颗粒 + halation，导出成片
```
**理由**：两条路不冲突，且各自补对方的短板。B 解决"拍的时候就要对"，A 解决"成片质量要打印级"。

### 值得花时间的：路径 E（反汇编 capture-fw-prod 找色彩表入口）
一小时工作量，如果找到就能在机内用真 3D LUT，那路径 B 的天花板直接被拆掉。

### 明确不做：路径 C（二次编码）、路径 D（liveview 前提不成立）

## 五、路径 E 的具体验证步骤（如果要做）

```bash
# 1. 列出 capture-fw-prod 全部 1988 符号，找色彩/LUT 相关
python -c "
import struct
d=open('libcapture-fw-prod.so','rb').read()
# 见CAPTURE_FW.md 的解析方法（PT_DYNAMIC + DT_HASH nchain）
"
# 关键词：LUT, Color, Profile, Curve, Tone, Gamma, 3D, Table

# 2. 重点可疑符号
#    CAttributeHandler::getColorSpace  @0x93000  (36 字节，只读)
#    CAttributeHandler::setColorSpace  ?  如果存在 → 有色彩空间可设
#    CCapImage::GetRawHeadColor        @0x772f0
#    CAttributeHandler::setPWBracketEhh @0x965f4
```

**如果 capture-fw-prod 里有 setColorSpace / setLut 之类的方法，
就能通过属性总线（和 setPWColor=0x10e 一样）让 ISP 加载色彩表。**

## 六、★★★ 路径 E 已验证关闭（14:15）

反汇编 `libcapture-fw-prod.so` 全部 1988 个符号，筛出所有 `set*/get*/load*/config*`
中与 `Color|Curve|Profile|LUT|Tone|Gamma|Table|CCM|Space|Matrix|3D` 相关的：

```
0x0772f0   40  CCapImage::GetRawHeadColor
0x077368   40  CCapImage::Get3DFormat
0x086d5c   88  CMCBAdapter::set3DInfo
0x091df4   36  CAttributeHandler::getPWColor
0x09205c  104  CAttributeHandler::get3DInfoLowLevelLight
0x09223c   36  CAttributeHandler::get3DFramerate
0x092bc8   36  CAttributeHandler::getResolution
0x092e50   36  CAttributeHandler::getMovieResolution
0x093000   36  CAttributeHandler::getColorSpace      ← 只有 getter
0x093120   36  CAttributeHandler::get3DShot
0x094e84  132  CAttributeHandler::setPWColor
0x09524c  116  CAttributeHandler::set3DInfoLowLevelLight
0x0954ec  104  CAttributeHandler::set3DFramerate
```

### 结论：属性服务端没有色彩表入口

- **没有 `setLUT` / `setColorProfile` / `setToneCurve` / `setColorSpace`**
- `getColorSpace` 只有 getter 无 setter → 色彩空间是只读的
- 所有含 "3D" 的符号都是**立体电影**（3D Shot / 3D Framerate / 3D Format），不是 3D LUT
- 唯一的 `set` 入口仍是 PW 那批（`setPWColor` / `setPWBracket` / `setWBKelvin`…）

**→ 路径 E 关闭。属性总线只能表达"厂商预设的枚举 + PW 7 维连续值"，
   无法让ISP 加载任意色彩表。**

### ★ 这实际上是个有价值的"负面定论"

它把整件事的性质定清楚了：
**NX500 的 ISP 色彩管线在用户态是完全封闭的。**
- 底层（3D LUT / NOG 颗粒 / 曲线）→ 需要内核 handle，用户态拿不到
- 上层（属性总线）→ 只能传枚举和7 个连续标量，没有"载入任意表"的接口

**→ 想要真曲线，只有两条路：**
1. **PC 端 RAW 域仿真**（已验证 rawpy 可解码，是唯一能达到打印级的路）
2. **改内核/ISP 固件**（NX1 GPL 包只有内核+packages，ISP 固件是闭源二进制，改不了）
