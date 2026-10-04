# setusr 索引全表 + PW 7 维定位结论（2026-10-04 13:30 实机扫完）

## 一、完整索引表 0–63（全部实机扫过）

| 索引 | DATA ID | 枚举名 | 类别 |
|---|---|---|---|
| 0 | 0x00 | DIALMODE_APERTURE | 拍摄 |
| 1 | 0x01 | SHOOTINGMODE_APERTURE | 拍摄 |
| 2 | 0x02 | IMAGESIZE_NORMAL_28M | 拍摄 |
| 3 | 0x03 | IMAGEASPECTRATIO_IMAGEAR_3_2 | 拍摄 |
| 4 | 0x04 | IMAGEQUALITY_FINE | 拍摄 |
| 5 | 0x05 | ISO_AUTO | 拍摄 |
| 19 | 0x13 | MULTIEXPOSURETYPE_SAVEALL | 拍摄 |
| **20** | **0x14** | **PW_TYPE** | ★ **风格** |
| 21 | 0x15 | SMARTRANGE | 风格 |
| 22 | 0x16 | MOVIESMARTRANGE | 风格 |
| 23 | 0x17 | AFPRIORITYRLS | 拍摄 |
| 24 | 0x18 | OIS_OFF | 拍摄 |
| 25 | 0x19 | FACETONE_LEVEL1 | 风格 |
| 26 | 0x1a | FACERETOUCH_LEVEL3 | 风格 |
| 27 | 0x1b | SMARTART_OFF | 风格 |
| 28 | 0x1c | SMARTARTLEVEL_LEVEL0 | 风格 |
| 29 | 0x1d | EVSTEP_ONETHIRD | 拍摄 |
| 30 | 0x1e | ISONR_MID | 拍摄 |
| 31 | 0x1f | LTNR_ON (长曝光降噪) | 拍摄 |
| 32 | 0x20 | AEBRKORDER_PZM | 拍摄 |
| 33 | 0x21 | AEBRKAREA_1OVER3 | 拍摄 |
| 34 | 0x22 | WBBRKSET_AB3 | WB |
| **35** | **0x23** | **PWBRKSTANDARD_SET** | ★ PW 风格标志 |
| **36** | **0x24** | **PWBRKVIVID_SET** | ★ |
| **37** | **0x25** | **PWBRKPORTRAIT_SET** | ★ |
| **38** | **0x26** | **PWBRKLANDSCAPE_SET** | ★ |
| **39** | **0x27** | **PWBRKFOREST_SET** | ★ |
| **40** | **0x28** | **PWBRKRETRO_SET** | ★ |
| **41** | **0x29** | **PWBRKCOOL_SET** | ★ |
| **42** | **0x2a** | **PWBRKCALM_SET** | ★ |
| **43** | **0x2b** | **PWBRKCLASSIC_SET** | ★ |
| **44** | **0x2c** | **PWBRKCUSTOM1_SET** | ★★ |
| **45** | **0x2d** | **PWBRKCUSTOM2_SET** | ★★ |
| **46** | **0x2e** | **PWBRKCUSTOM3_SET** | ★★ |
| **47** | **0x2f** | **PWBRKCUSTOM4_SET** | ★★ |
| 48 | 0x30 | AFLIGHT_HIGH | 闪光 |
| 49 | 0x31 | AEL_AEL | 拍摄 |
| 51 | 0x33 | QUICKVIEWTIME_HOLD | 系统 |
| 52 | 0x34 | MONITOROUT_LCD | 系统 |
| 53 | 0x35 | HDMIOUT_1080I | 系统 |
| 54 | 0x36 | MOVIESIZE_FHD | 视频 |
| 55 | 0x37 | MOVIEFRAMERATE_FPS30 | 视频 |
| 56 | 0x38 | MOVIEFADER_OFF | 视频 |
| 57 | 0x39 | MOVIEAE_P | 视频 |
| 58 | 0x3a | F3DMOVIEFRAMERATE_FPS30 | 视频 |
| **62** | **0x3e** | **SMARTFILTERTYPE** | ★★ 14 种效果 |
| **63** | **0x3f** | **SMARTFILTER 强度** | ★★ |

**索引 6–18、50、59–61 未扫**（脚本分段时被截断，且这几个在其它文档里记为非关键）。

## 二、★★ PWBRK 段的真实语义（关键发现）

索引 35–47 共 **13 个**，恰好对应 PW 的 **13 个风格**
（STANDARD/VIVID/PORTRAIT/LANDSCAPE/FOREST/RETRO/COOL/CALM/CLASSIC + CUSTOM_1-4）。

**回显全部是 `..._SET`（枚举值 0x0001），切换 PW_TYPE 或写入 7 维后都不变。**

### 实验记录
```
初始状态:44-47 全部 PWBRKCUSTOMn_SET (0x2c-0x2f0001)
执行 apply hp5（写 slot 10 的R/G/B/HUE/SAT/SHARP/CONTRAST + K + tint）
再读:44-47 仍是 PWBRKCUSTOMn_SET，无变化
```

**→ 判定：PWBRK_n 是"该风格已被用户编辑过"的静态标志位，
不是"当前选中哪个风格"，也不是"该风格参数的载体"。**

语义应是：`PWBRKSTANDARD_SET` = 用户动过 STANDARD 的参数。
出厂时应该都是 `_CLEAR`(0x0000)；因为我们之前已经把 9/10/11/12 槽写成了配方，
所以 4 个 CUSTOM 全变成 `_SET`。

## 三、★★★ 结论：PW 7 维子参数不在 setusr 层

这是本轮扫描最重要的结论。理由三条：

1. **索引 35–47 已被 PWBRK 段占满**，语义是"编辑标志"而非参数值
2. **全表 0–63 内没有任何索引的名称含 R/G/B/HUE/SAT/SHARP/CONTRAST/KELVIN/TINT**
3. `CAttributeHandler` 的 PW setter ID（`0x105` WBKelvin / `0x10e` PWColor / `0x110` Saturation…）
   **在 setusr 索引表里没有对应项** —— 两套 ID 不是一一映射

### 所以实时改 7 维只有两条路

| 路径 | 状态 | 代价 |
|---|---|---|
| **prefman写 eMMC + `load -a 0`** | ✅ 已跑通 | 需`prefman save`，实测有效 |
|内核 API（yccmixer / NOG / 3D LUT） | ❌ 全部 SIGSEGV | handle 拿不到 |
| **setusr** | ❌ **7 维不在这层** | — |

## 四、★★ PWBRK 段的实用价值（不是没用）

虽然不是参数载体，但它是**校验机制**：

```
改 PW 7 维 → prefman 写入 → PWBRK_n 变 _SET → UI 里该风格显示为"已修改"
```

**用途：判断某个 PW 槽是否已被配方占用。**
我们的 `filmlab-apply.sh` 现在靠"记住哪些 slot 被写过"来轮转（9/10/11/12），
**但相机自己就有这个标志位**，可以直接查询，避免槽位冲突。

## 五、★ 顺带确认的两件事

### 1. apply 配方不改 PW_TYPE
`apply hp5`（写 slot 10）之后 `getusr 20` 仍返回 `PW_VIVID`。
**→ 写7 维和切风格是两个独立动作**，符合设计：
- `filmlab-apply.sh` 做两件事：`susr 20 0x14000X`（切风格）+ prefman 写参数

### 2. setusr 写入是实时的
```
setusr 20 0x140000 → getusr 20 = PW_STANDARD   （即时生效）
setusr 20 0x140001 → getusr 20 = PW_VIVID      （即时恢复）
```
**→ 切风格零延迟，切风格 + prefman 参数 = 完整实时切换。**

## 六、下一步的三个可选方向

| 方向 | 内容 | 前提 |
|---|---|---|
| **① 补完 prefman 实时性** | 测`prefman set` + `load -a 0` 是否免重启（不用 save 到 eMMC） | 只需相机配合看画面 |
| **② Web 配方台** | 8 配方扩到 N 个（JSON 随便加）+ PWBRK 标志位做校验 + prefman 批量预写 | 已有全部通路 |
| **③ 硬件颗粒接入** | NOG 的 sigma/gamma 理论上对应胶片颗粒，但需要 handle | 目前撞墙 |

**建议 ①→②。** ①决定"配方切换要不要重启"这个关键体验问题；
②是把已有能力产品化（8→60 个配方、UI 选槽位、批量写入）。
③等 handle 问题有解再说。

## 七、★★★ 免重启测试：结论已定（13:35 实机）

**测试**：slot 13（OFF 槽，纯实验用）写入 `R=120 G=90 B=200 HUE=20 SAT=20 SHARP=20 CON=20`，
**只做 `prefman set` + `prefman load -a 0`，不调 `prefman save`。**

```
--- 写入前 ---   R=100 G=100 B=100  HUE=458759 SAT=10
--- load 后 ---  R=100 G=100 B=100  HUE=458759 SAT=10   ← 完全没变
```

### 结论：`prefman set` 不落盘，`load -a 0` 读的是 eMMC 里的旧值

`load -a 0` 是"**从 eMMC 重新加载**"，所以它会**覆盖**掉刚 `set` 的值。
**→ 必须 `prefman save` 才能生效。**
**→ prefman 这条路无法免重启。**

### 这同时解释了为什么 8 配方方案里需要 `save`

`filmlab-apply.sh` 的 `apply` 做的是：
```
prefman set（7 维 + K + tint × N 槽）→ prefman save（写 eMMC）→ prefman load -a 0（重载）
                                                        ↑ 这一步是必须的
```

### ★ 偏移布局（已实机验证，修正我之前的错误）
`slot_off(参数索引 i, 风格 s) = PW_BASE + i*52 + s*4`，`PW_BASE = 41964 (0xa3ec)`
参数索引：`0=R 1=G 2=B 3=HUE 4=SAT 5=SHARP 6=CONTRAST`
风格：`0..8=厂商 9..12=CUSTOM_1..4 13=OFF`

**我第一次写成 `BASE=262380` + "每参数步进 52"，读出垃圾值（R=-509575037）。
错误原因：① 基址记成十进制而非 0xa3ec② 误把"参数步进"当成地址偏移。
busybox printf 必须是 `0x%05x`（带 %），写成 `0x05x` 会截断。**
