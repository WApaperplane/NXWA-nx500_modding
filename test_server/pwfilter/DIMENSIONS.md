# 机身原生渲染维度全景 — slot 之外的增量（2026-10-04 实机）

> 目的：回答木一的问题——「9 个厂商风格和CUSTOM_1-4 之外，还需要什么？」
> 答案：**不需要更多槽位，需要更多维度。** Recipe Lab 的 77 个配方来自
> 26 个 1 字节settings 槽的**组合**，不是 77 条曲线。
> 本文件实测出NX500 上同样可用的维度清单。

## 一、核心认知修正

| 错误框架 | 正确框架 |
|---|---|
| 「厂商 9 风格 + CUSTOM_1-4 = 13 个槽位，不够」 | 槽位只是**载体**，维度才是**自由度** |
| 「需要新增槽位存更多曲线」 | 维度组合 = 状态空间，13 槽 × 多维已足够 |

**已确认**：9 个厂商风格也可改（木一实机确认），所以 14 个 PW 槽全部可用。
槽位数量不是瓶颈。

## 二、维度清单（全部实机确认）

### 维度 A：Picture Wizard（已用满）
- **14 个槽**（不是 13！），每个 7 维：R/G/B 增益 + HUE/SAT/SHARP/CONTRAST
- 槽位布局（`prefman info 0` 实测，按参数分组，参数步进 52= 13风格×4B，风格步进 4）：

```
0x0a3ec R_COLOR   0x0a420 G_COLOR   0x0a454 B_COLOR
0x0a488 HUE       0x0a4bc SATURATION 0x0a4f0 SHARPNESS  0x0a524 CONTRAST
```

- **★ 第 14 槽 = `APPPREF_EFFECT_OFF_*`（0x0a3d8-0x0a3e8），文档没有**：

| 字段 | 偏移 | 实测值 | 含义 |
|---|---|---|---|
| `EFFECT_OFF_COLOR` | 0x0a3d8 | **-1** | 无修正哨兵值 |
| `EFFECT_OFF_SATURATION` | 0x0a3dc | 10 | 中性 |
| `EFFECT_OFF_SHARPNESS` | 0x0a3e0 | 10 | 中性 |
| `EFFECT_OFF_CONTRAST` | 0x0a3e4 | 10 | 中性 |
| `EFFECT_OFF_HUE` | 0x0a3e8 | 10 | 中性 |

即「关闭风格时的基线」。`OFF_COLOR=-1` 是**独立于其他 4 个的哨兵**，
说明这一槽语义与其他槽不同（可能整体禁用标记）。
→ **额外可用槽位，且语义独特**。

- 实时切换：`setusr 20 0x14000N`（N=0..13），见 `SETUSER_SYNTAX.md`

### 维度 B：Smart Filter（独立于 PW，已实机枚举 13 种）
`setusr 62 0x3e000N` + 强度 `setusr 63 0x3f000M`

```
OFF / VIGNETTING / MINIATURE_H / MINIATURE_V / RANDOMMOSAIC /
COLOREDPENCIL / WATERCOLOR / WASH_DRAWING / OILPAINTING /
INKPAINTING / RADIALBLUR / FISHEYE / ACRYL / NEGATIVE
```
**这 14 种 × 多档强度 = 独立于 PW 的第二条实时渲染线**，可与任意 PW 风格叠加。

### 维度 C：★ 白平衡 tint 二维偏移（新发现，Recipe Lab 对应项）
`APPPREF_WB_*_DETAIL_BA_XY`（0x0a398-0x0a3c0），**10 个白平衡预设 × 二维偏移**：

```
0x0a398 WB_AUTO_DETAIL_BA_XY0x0a39c WB_AUTO_TUNGSTEN_BA_XY
0x0a3a0 WB_DAYLIGHT_DETAIL_BA_XY           0x0a3a4 WB_CLODY_DETAIL_BA_XY
0x0a3a8 WB_FLUORESCNTW_DETAIL_BA_XY        0x0a3ac WB_FLUORESCNTN_DETAIL_BA_XY
0x0a3b0 WB_FLUORESCNTD_DETAIL_BA_XY        0x0a3b4 WB_TUNGSTEN_DETAIL_BA_XY
0x0a3b8 WB_FLASH_DETAIL_BA_XY              0x0a3bc WB_CUSTOM_DETAIL_BA_XY
0x0a3c0 WB_K_DETAIL_BA_XY                  ← Kelvin 连续档
```

**★ 打包格式已解**：全部读出 `458759` = `0x00070007`
（与 varlist 的 `VARIABLE_WBADJUST` 同值）→ **高 16 位 = 一个偏移，低 16 位 = 另一个偏移**，
即机身内部的 **A-B / G-M 二维 tint**。中性 = `0x00070007`（7,7 是归一化中点，非0）。

这是**胶片配方的核心维度之一**（暖=偏红、黄=偏绿）。Recipe Lab 用
`WB Kelvin/A-B/G-M ±7` 做到77 个配方，NX500 这里有同样的机制。

### 维度 D：其他已确认可写维度
| 维度 | 索引 | DATA ID 前缀 | 备注 |
|---|---|---|---|
| SMARTRANGE | 21 | 0x15 | 智能范围（宽容度表现） |
| FACETONE | 25 | 0x19 | 人像修饰 |
| SMARTART | 27 | 0x1b | 智能滤镜 |
| SMARTARTLEVEL | 28 | 0x1c | 智能滤镜强度 |
| COLORSPACE | 50 | 0x32 | 色彩空间 |
| SMARTFILTERTYPE | 62 | 0x3e | 13 种 |
| SMARTFILTERSIZE | 63 | 0x3f | 强度档 |
| HDRARTLEVEL | 77 | 0x4d | HDR 艺术 |
| LLSLEVEL | 78 | 0x4e | 长曝降噪 |
| PWBRK×13 | 35-47 | — | 风格「已编辑」标志位 |
| WB_TYPE | 0x0a390 | — | 白平衡模式（preman侧） |
| WB_K_VALUE | 0x0a394 | — | **色温 K 值** |

**`WB_K_VALUE`（0x0a394）** 配合 `WB_K_DETAIL_BA_XY`（0x0a3c0）=
**完整 Kelvin + tint 二维调节**，对应 Recipe Lab 的 `WB Kelvin` 那一维。

## 三、维度组合空间估算

```
14 PW 槽（各7 维可独立调）
× 14 SmartFilter × 3-4 档强度
× 10 WB 预设 × tint 二维（每维 ±范围待测）
× SMARTRANGE / SMARTART / FACETONE / COLORSPACE / LLSLEVEL / HDRART
```

即便只取「14 槽 × 7 维 × 每维 5 档」，已是 `5^7 × 14 ≈ 5.5 亿` 种状态。
**槽位数量从来不是瓶颈，维度组合才是配方数量的来源。**

## 四、FilmLab 配方模型（最终设计）

一个配方 = **一个维度向量**，不是一条曲线：

```json
{
  "name": "Portra 400",
  "pw_slot": 10,
  "pw": { "r":103, "g":105, "b":83, "hue":8, "sat":10, "sharp":10, "contrast":5 },
  "wb": { "preset": "DAYLIGHT", "tint_a": 9, "tint_b": 4 },
  "smart_filter": { "type": 0, "size": 0 },
  "smart_range": 1,
  "facetone": 0,
  "color_space": 0
}
```

切换配方 =写 prefman（持久化）+ setusr（实时）双通路。

**注意**：`wb.tint_a/tint_b` 的**取值范围和符号约定未测**（当前只有中性值 0x00070007），
需先探测±方向。这是下一步的实测目标。

## 五、下一步实测（必做）

**目标：测出 WB tint 二维的取值范围和符号。**

```sh
# 预读
prefman get 0 0x0a3a0 l          # DAYLIGHT_DETAIL_BA_XY  当前 458759
# 试探上界（注意：prefman 不裁剪，超界值原样接受 → 需备份）
prefman set 0 0x0a3a0 l 0x000F000F
prefman get 0 0x0a3a0 l
# 取景器看 WB tint 是否变化、方向如何
# 回滚
prefman set 0 0x0a3a0 l 458759
```

**风险提示**：`APPPREF_CHECKSUM(0x0fcbc)` 恒为 108、不随参数变化（10-03 实测），
所以改这些不需要重算 checksum，变砖风险已排除。但**WB tint 可能影响出片**，
测完务必回滚。

## 六、诚实的边界

- **仍是全局向量，不是 tone curve**。14 槽 × 7 维= 逐像素同值。
  做不出高光滚降/阴影染色/分区曝光。
- 能做「滤镜风格」，做不了「胶片响应曲线」。
- 但**这正是 Recipe Lab 的水平**（它也做不出 tone curve，作者明确写了）。
  要真曲线只能回 PC raw 域（L2.5 直出烘焙）。
- 两层不冲突：**机内实时预览 + 决定构图 → PC raw域出打印级成品**。
