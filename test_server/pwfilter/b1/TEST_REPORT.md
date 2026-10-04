# 3D LUT / PW 直写路线实机测试报告（2026-10-04 13:00–13:30）

## 一、测试序列与结果

| # | 测试 | 命令 | 结果 |
|---|---|---|---|
| 1 | dlopen/dlsym 探测 | `lut3dl_probe.arm` | ✅ **EXIT=0，26/27 符号拿到** |
| 2 | 3D LUT op_init | `lut3dl_read.arm 1 0 0` | ❌ **RC=139（SIGSEGV）** |
| 3 | PW yccmixer 直写 | `pw7_ycc.arm 1 00000000` | ❌ **RC=139（SIGSEGV）** |
| 4 | 先NOG init 再写 | `pw7_v2.arm 1 00010101` | ⚠️ **RC=2，`nog_init_rc=48`（假返回值）** |
| 5 | **属性总线写 PW** | `st cap capdtm setusr 20 0x140000` | ✅ **成功：PW_VIVID → PW_STANDARD** |

## 二、★★★ 唯一的成功：属性总线可实时写

```
st cap capdtm getusr 20   →  UserData is PW_VIVID (0x140001)
st cap capdtm setusr 20 0x140000  →  UserData is set
st cap capdtm getusr 20   →  UserData is PW_STANDARD (0x140000)
```
另外确认：
```
getusr 62 → SMARTFILTERTYPE_OFF (0x3e0000)
getusr 21 → SMARTRANGE_ON (0x150001)
```
**→ `setusr` 是当前唯一可用的实时写入通路，且已实机验证生效。**

### setusr 语法（社区文档没写，是踩坑试出来的）
```
st cap capdtm setusr <索引> <完整 DATA ID 十六进制>
```
第二参数**必须是完整 DATA ID**（如 `0x140001`），不是裸枚举值。
传错会返回 `UserData is not set -1179648`，容易被误判为 dfmsd 未启动。

**DATA ID 结构 = `0x<索引的十六进制><枚举值 4 位>`**
例：索引 20 = `0x14` → PW 枚举 = `0x140000`~`0x14000d`（14 个 CUSTOM/STANDARD等）

### 已扫描的索引映射（0–24 + 62）

| 索引 | DATA ID 前缀 | 含义 |
|---|---|---|
| 0 | 0x00 | DIALMODE_APERTURE |
| 1 | 0x01 | SHOOTINGMODE_APERTURE |
| 2 | 0x02 | IMAGESIZE_NORMAL_28M |
| 3 | 0x03 | IMAGEASPECTRATIO_3_2 |
| 4 | 0x04 | IMAGEQUALITY_FINE |
| 5 | 0x05 | ISO_AUTO |
| 19 | 0x13 | MULTIEXPOSURETYPE |
| **20** | **0x14** | **PW_TYPE（14 个风格）** |
| 21 | 0x15 | SMARTRANGE |
| 22 | 0x16 | MOVIESMARTRANGE |
| 23 | 0x17 | AFPRIORITYRLS |
| 24 | 0x18 | OIS |
| **62** | **0x3e** | **SMARTFILTERTYPE（14 种效果）** |
| 63 | 0x3f | SMARTFILTER 强度 |

**→ 索引 25–61 未扫完（脚本超时），PW 的 7 维子参数索引仍未知。**

## 三、★★★ 三条内核级路线的失败原因（同一堵墙）

| 路线 | 入口 | 失败点 | 机制 |
|---|---|---|---|
| 3D LUT | `d5_ep_3dlut_op_init` | SIGSEGV | 需要**三级指针句柄** |
| PW 直写 | `d5_ep_mc_set_custom_param_yccmixer` | SIGSEGV | 经 `nog_seed_load_switch` 取寄存器组，返回 0 → 写 0x280 |
| 硬件颗粒 | `_udd_ep_nog_set_std_sigma` | 未测（预期同机制） | `.bss` 指针数组由内核填充 |

**共性：寄存器组指针全部由内核态分配并填入 `.bss`，用户态进程读到的都是 0。**

### 我犯的一个反汇编错误（已修正）
`yccmixer` 里的 `ldr r2,[pc,#0xfc]` 目标 `0x54450`，我查 `.rel.dyn` 查不到，
就断定它是"MC 寄存器基址全局变量"。**实际它是 `.got.plt` 里的 PLT 槽，
`.rel.plt` 显示指向 `_udd_ep_nog_seed_load_switch`。**

**方法论铁律：PC-relative 常量必须同时查 `.rel.dyn` 和 `.rel.plt`。**
查不到 ≠ 是普通全局变量，很可能是 PLT 槽。

## 四、★★★ 顺带发现：NX500 有硬件颗粒发生器

| 地址 | 大小 | 符号 | 作用 |
|---|---|---|---|
| 0x105cc | 36 | `d5_ep_nog_set_bypass` | NOG 总旁路 |
| 0x105f0 | 240 | `d5_ep_nog_set_noisegen` | 顶层：设全部噪声参数 |
| 0x20070 | 248 | `_udd_ep_nog_reg_struct_init` | 清零寄存器组（**不返回值**） |
| 0x20168 | 232 | `_udd_ep_nog_set_random_seed` | 随机种子 |
| 0x20250 | 176 | `_udd_ep_nog_seed_load_switch` | 种子表切换（表0 / 表0x30） |
| 0x20300 | 176 | `_udd_ep_nog_select_rv_type` | **噪声分布类型** |
| 0x203b0 | 432 | `_udd_ep_nog_set_std_sigma` | **标准差 = 颗粒强度** |
| 0x20560 | 684 | `_udd_ep_nog_set_gamma` | **gamma = 颗粒大小分布** |
| 0x2080c | 240 | `_udd_ep_nog_set_bypass` | 模块旁路 |
| 0x34f98 | 1640 | `_udd_ep_mux_nog_rdxi` | MUX 读 |
| 0x38968 | 1032 | `_udd_ep_mux_nog_wdxi` | MUX 写 |
| 0x3bf68 | 140 | `_udd_ep_demux_nog_rdxi` | DEMUX 读 |
| 0x3c8f4 | 288 | `_udd_ep_demux_nog_wdxi` | DEMUX 写 |

### 这推翻了我此前的结论
我判定"**机身无颗粒维度**，TriX/HP5 的颗粒感用 SHARP 近似"。
**实际 NX500 有独立硬件噪声发生器**，可控：强度（sigma）、分布（gamma）、噪声类型（rv_type）。

**真实胶片颗粒不是锐化，是随亮度分布的随机噪声。** 机身能做且是硬件级真随机。
**→ 能力评估要改：胶片仿真的"颗粒"这一维，机身有硬件支持。**

`d5_ep_nog_set_noisegen(p)` 调用序列（反汇编还原）：
```c
int d5_ep_nog_set_noisegen(struct *p) {   // p 至少 0x14 字节
    int rc = 0;
    _udd_ep_nog_reg_struct_init();// 清零，不返回
    rc |= _udd_ep_nog_set_random_seed(p->[0x08]);
    rc |= _udd_ep_nog_select_rv_type(p->[0x10], p->[0x08]);
    rc |= _udd_ep_nog_set_std_sigma(p->[0x00], p->[0x08]);   // 强度
    rc |= _udd_ep_nog_set_gamma(p->[0x04], p->[0x08]);       // gamma
    rc |= <p->[0x0c] 相关>;
    return rc;
}
```

## 五、★★ 一个重要的否证：getusr 第二参数不是查询值

试过用 `getusr <idx> <枚举>` 逐个枚举探测，但**无论传什么枚举，
回显的都是当前值**（传 `0x140003` 仍回显 `PW_STANDARD (0x140000)`）。
**→ 枚举扫描这条路不通，setusr 只能"写"，不能"查具体枚举"。**
**→ 写某个具体值后只能靠 getusr 看是否变成对应名字。**


## 七、★★ setusr 索引全表（0–63，已扫完）

| 索引 | 前缀 | 含义 | 备注 |
|---|---|---|---|
| 0 | 0x00 | DIALMODE_APERTURE | |
| 1 | 0x01 | SHOOTINGMODE_APERTURE | |
| 2 | 0x02 | IMAGESIZE_NORMAL_28M | |
| 3 | 0x03 | IMAGEASPECTRATIO_3_2 | |
| 4 | 0x04 | IMAGEQUALITY_FINE | |
| 5 | 0x05 | ISO_AUTO | |
| 19 | 0x13 | MULTIEXPOSURETYPE | |
| **20** | **0x14** | **PW_TYPE** | ★ 14 个风格，`0x140000`~`0x14000d` |
| 21 | 0x15 | SMARTRANGE | |
| 22 | 0x16 | MOVIESMARTRANGE | |
| 23 | 0x17 | AFPRIORITYRLS | |
| 24 | 0x18 | OIS | |
| 25 | 0x19 | FACETONE | LEVEL1 |
| 26 | 0x1a | FACERETOUCH | LEVEL3 |
| 27 | 0x1b | SMARTART | OFF |
| 28 | 0x1c | SMARTARTLEVEL | LEVEL0 |
| 29 | 0x1d | EVSTEP | ONETHIRD |
| 30 | 0x1e | ISONR | MID |
| **31–37** | **0x1f–0x25** | **PWBRK × 7** | ★ 与 `CAttributeHandler::setPWBracket` 的 ID 段`0x1b..0x25` 对齐 |
| **38–43** | **0x26–0x2b** | **PWBRK 各风格 _SET** | ★ LANDSCAPE/FOREST/RETRO/COOL/CALM/CLASSIC |
| 51 | 0x33 | QUICKVIEWTIME | HOLD |
| 52 | 0x34 | MONITOROUT | LCD |
| 53 | 0x35 | HDMIOUT | 1080I |
| 54 | 0x36 | MOVIESIZE | FHD |
| 55 | 0x37 | MOVIEFRAMERATE | FPS30 |
| 56 | 0x38 | MOVIEFADER | OFF |
| **62** | **0x3e** | **SMARTFILTERTYPE** | ★ 14 种效果 |
| 63 | 0x3f | SMARTFILTER 强度 | |

### ★★ 关键对齐：两套 ID 系统的对应关系找到了

`CAttributeHandler::setPWBracket` 的 ID 段是 **`0x1b..0x25`（27–39）**，
而 setusr 索引 **27=SMARTART、28=SMARTARTLEVEL、29=EVSTEP、30=ISONR、31–37=PWBRK×7**。

**→ `CAttributeHandler` 的属性 ID 段 = setusr 索引 + 偏移，且顺序一致。**
这说明两者是**同一张属性表的两个视图**：`setusr` 是 capdtm 的视图（按索引分域），
`CAttributeHandler` 是按连续 ID 的视图。

**→ 推论：PW 7 维的子参数应该也在 PWBRK 段附近（索引 31–43 区间）。**
这是下一步唯一该扫的地方。

## 六、下一步（收敛到两条）

| 方向 | 做法 | 前景 |
|---|---|---|
| **A. 继续刷 setusr 索引** | 把 25–61 扫完，找 PW 7 维的子参数索引。分批执行避免超时 | ★★★ 唯一已验证可写的路 |
| **B. 沿属性 ID 走** | `CAttributeHandler` 已给出 `setPWColor=0x10e` 等 ID，需要找 `capdtm` 里对应的 setusr 索引映射 | ★★★ |

**核心判断：B 路线的内核级写入全部撞墙（handle 拿不到），
但属性总线（setusr）可写且已验证。→ 应该把力气集中在"用 setusr 表达更多维度"，
而不是继续攻内核级 API。**
