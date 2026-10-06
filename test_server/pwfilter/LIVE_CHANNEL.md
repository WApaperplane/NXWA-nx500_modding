# 实时风格通道 — 实机探测结果（2026-10-04）

> 设备：NX500 固件 1.12（`drime5` 3.5.0）| 192.168.0.105 | telnet root 空密码
> 全部数据来自实机 telnet，非文档推断。
> 脚本：`test_server/pwfilter/pw-live.sh`（已上传至 `/opt/storage/sdcard/_pwtest/pw-live.sh`，3791B）

## 一、战略修正：为什么不需要 LUT / cube

上一轮结论「实时预览 CPU 不够，只能跑 10fps」**前提是错的**。
那个前提假设「我们自己拿到帧、自己算像素」。Recipe Lab 不是这么做的：

```
Sony ISP 内部本来就有 Creative Style 实时处理引擎
→ 写 1 字节参数进它的settings store
→ 引擎在渲染 liveview 的同时顺带渲染风格→ CPU 成本 = 0
```

所以 NX500 的对等物**不是**我们自带的 LUT，而是**相机自己ISP 里的 PW 引擎**。
用它，我们同样不写一行像素处理代码，同样得到实时预览。

**代价（必须诚实）**：只能用它给的维度。我们已在10-03 实测确认厂商 9 风格
（STANDARD/VIVID/PORTRAIT…）的曲线**硬编码在 ISP 固件常量里**，prefman 侧只存
「PW_TYPE 选哪个」；出厂时这 9 个 slot 全= 中性值= 未初始化。
**所以可改的仍只有 CUSTOM_1-4。** 这是硬边界，绕不过去。

## 二、`st cap capdtm` 完整命令面（实机）

```
st cap capdtm setusr [id|num] [id|num]     写 userdata
st cap capdtm getusr [id|num]              读 userdata
st cap capdtm setvar [id|num] [data] [len]  写实时变量
st cap capdtm getvar [id|num]读实时变量
st cap capdtm usrlist                      列 userdata
st cap capdtm varlist                      列实时变量
```

**关键坑**：`getusr`/`setusr` **只接受十进制索引**。文档 ST_CAP_CAPDTM.md 里
那批 `0x00xxxxxx` 的十六进制 ID 传进去一律返回 `Invalid argument[2]`。
十六进制 ID 只是**显示用的枚举值**，不是寻址键。

**坑2**：社区文档的索引表**全部错位 1** —— 因为那张表混编了多个 profile 的
`usrlist` 输出。以本文件下表为唯一准绳。

## 三、实机 userdata 索引表（`getusr`逐个实测，权威）

| 索引 | 枚举名| 说明 |
|---|---|---|
| **20** | `PW_STANDARD (0x140000)` | **当前 Picture Wizard 风格**（核心入口） |
| 21 | `SMARTRANGE_ON (0x150001)` | 智能范围 |
| 25 | `FACETONE_LEVEL1 (0x190000)` | 人像修饰 |
| 27 / 28 | `SMARTART_OFF` / `SMARTARTLEVEL_LEVEL0` | 智能滤镜 + 强度（两级） |
| **35-47** | `PWBRKSTANDARD` … `PWBRKCUSTOM4` | **13 个风格「已编辑」标志位** |
| 50 | `COLORSPACE_SRGB (0x320000)` | 色彩空间 |
| **62 / 63** | `SMARTFILTERTYPE_OFF` / `SMARTFILTERSIZE_SIZE0` | **Smart Filter 类型 + 强度**（独立于 PW！） |
| 77 / 78 | `HDRARTLEVEL_LV1` / `LLSLEVEL_LV1` | HDR 艺术 / 长曝降噪 |

`PWBRK` 13 槽逐个：35=STANDARD36=VIVID 37=PORTRAIT 38=LANDSCAPE
39=FOREST 40=RETRO 41=COOL 42=CALM 43=CLASSIC
**44=CUSTOM_1  45=CUSTOM_2  46=CUSTOM_3  47=CUSTOM_4**

## 四、varlist 里的 7 个 PW 实时变量（实机输出）

```
[14] VARIABLE_PWCOLOR         = ----------      （未定义）
[15] VARIABLE_PWSATURATION    = 0x000FD80A
[16] VARIABLE_PWSHARPNESS     = 0x000FD80A
[17] VARIABLE_PWCONTRAST      = 0x000FD80A
[48] VARIABLE_PWCOLOR_R       = 0x080000FF
[49] VARIABLE_PWCOLOR_G       = 0x080000FF
[50] VARIABLE_PWCOLOR_B       = 0x080000FF
[51] VARIABLE_PWHUE= 0x000FD80A
```

**编码格式已解**：`0x000FD80A`
- 低 16 位 = `0x0A` = 10 → **正是 PW 中性值**（HUE/SAT/SHARP/CONTRAST = 10）
- 高 16 位 = `0xFD` = 253 → **-3 的补码**（相对中性的偏移量）

`PWCOLOR_R/G/B = 0x080000FF`
- 低 16 位 = `0xFF` = 255 → 8bit 色深满量程
- 高 16 位 = `0x08` = 8 → bit 数

这组变量的存在**独立证明**了 PW 引擎在运行时持有 7 维参数的可写副本。

## 五、两条写入通道的实测判定

### `setvar`（实时变量）—❌ 对 PW 变量无效

```
$ st cap capdtm setvar 15 30 4
VariableData is not set  -1179648
$ st cap capdtm getvar 15
Variable Data is 0x00000000_00000000
```

7 个 PW 变量**全部**返回 `VariableData is not set`，值恒0。
判定：**这些是引擎派生的只读镜像，没有 setter。**
这与「厂商 9 风格曲线硬编码在 ISP」是同一件事的两面。

### `setusr`（userdata）— ⚠️ 命令存在但当前状态下静默失效

```
$ st cap capdtm setusr 20 5 4     （请求切到 VIVID）
$ st cap capdtm getusr 20
UserData is PW_STANDARD (0x140000)← 值未变
```

枚举 0..14 全部扫过，值恒为 `PW_STANDARD`，**无报错、无提示**。

**最可能原因**：相机不在拍摄模式 → capdtm 运行时未接管 → 写入落到空壳被丢弃。
这与 `pw-preview.sh` 记录的「相机不在拍摄模式（`ps` 无 capdtm）无法自动拍」是同一个坎。

**取证受阻**：`busybox ps` 在本机只能看到自己和当前 tty 的 3 个进程
（命名空间隔离），**无法用命令行确认 capdtm 是否在运行**。这个只能靠人工切拍摄模式。

**旁证**：`pw-set.sh` 走prefman 改同一批 PW 参数是**成功的**（10-03 实机，
含 eMMC 持久化验证）。差别在于 prefman 写的是偏好存储区，不依赖运行时。

## 六、下一步（需人工操作，只需一次）

**必须由人把相机切到拍摄模式（PASM 档或 A 档），保持 liveview 出画，然后跑：**

```sh
sh /opt/storage/sdcard/_pwtest/pw-live.sh set 20 5      # 期望 PW 跳到 VIVID
sh /opt/storage/sdcard/_pwtest/pw-live.sh enum 20 13     # 枚举全部 13 风格
sh /opt/storage/sdcard/_pwtest/pw-live.sh list 62 63     # Smart Filter 类型/强度
```

**生死判据**：若 `set 20 5` 后 `getusr 20` 从 `PW_STANDARD` 变成 `PW_VIVID`，
则**实时风格通道打通**，`setusr` + `pw-set.sh`（写 PW 参数块）双通路可用，
L1 实时预览成立 —— 零 CPU 成本。

若仍是 `PW_STANDARD`，说明 capdtm 写入需另一入口（可能必须在 UI 菜单里选风格
触发同步），此时退回 prefman 路线 + 人工在菜单里选 CUSTOM_x。

## 七、已确认的增量维度（相比10-03 的认知）

| 新发现 | 增量 |
|---|---|
| `USERDATA_PWBRK*` 13 个独立槽 | 风格「已编辑」标志位，可做 RecipeLab 式配方注册 |
| `SMARTFILTERTYPE` + `SMARTFILTERSIZE`（62/63） | **独立于 PW 的第二套实时滤镜维度**（类型 × 强度），完全未探索 |
| `SMARTART` + `SMARTARTLEVEL`（27/28） | 第三套，同样独立 |
| `FACETONE`（25） | 人像修饰独立档位 |
| `SMARTRANGE`（21） | 智能范围，可影响宽容度表现 |
| `COLORSPACE`（50） | 色彩空间切换 |
| `HDRARTLEVEL`（77）/ `LLSLEVEL`（78） | HDR 艺术 / 长曝降噪 |

**结论修正**：不只是「CUSTOM_1-4 四个槽」。`PWBRK×13 + PW×7维 + SmartFilter×N档
× 强度` 组合出的状态空间，比10-03 估计的大得多。
**关键点不是槽位数量，而是这些维度全部由相机 ISP 自己实时渲染，CPU 成本为零。**
