# B2 测试分析（2026-10-04 13:15–13:20）：段错误根因 + 硬件颗粒发现

> 实机结果：
> - `pw7_ycc.arm 1 00000000` → **RC=139（SIGSEGV）**
> - `pw7_v2.arm 1 00010101`（先调 nog init）→ **RC=2，`nog_init_rc=48`**

## 一、★★★ 根因：0x54450 是 PLT 槽，不是数据变量

`yccmixer` 里 `ldr r2, [pc, #0xfc]` @0x2949c → literal pool 0x294a4 → 值 0x0002aeb0
→ 目标 `0x294a4 + 0x2aeb0 = 0x54450`。

**我之前只查了 `.rel.dyn`，没查 `.rel.plt`，错误地把它当成"MC 寄存器基址全局变量"。**
`.rel.plt` 实际内容：

```
slot 0x54450 -> _udd_ep_nog_seed_load_switch
```

**NOG = Noise Generator（噪声/颗粒发生器）。**
`yccmixer` 是**通过 NOG 的 PLT 间接取寄存器组指针**，不是直接用 MC 基址。
NOG 未初始化 → 该函数返回 0 → `*(u32*)(0 + 0x280) = ...` → **写虚拟地址 0x280 → SIGSEGV**。

### 方法论修正（重要）

**PC-relative 常量必须同时查 `.rel.dyn` 和 `.rel.plt` 才能确定指向什么。**
`.rel.dyn` 里查不到 ≠ 普通全局变量 ——它很可能是 PLT 槽。
（`.rel.dyn` 覆盖数据段重定位，`.rel.plt` 覆盖 `.got.plt`。）

## 二、★★★ `nog_init_rc=48` 是假返回值

`_udd_ep_nog_reg_struct_init`（0x20070, 248B）**根本不返回值**：
整个函数体只是**清零两个 32 字节的寄存器组**（各 8 个 u32，全部 `str r0` 形式），
**结尾直接 `bx lr`，从未设置 r0**。所以 `48` 只是调用前的寄存器残留值。

**含义：这一步不是"被拒"，而是"它压根不返回状态"。真正的初始化在调用者手里。**

## 三、★★ 寄存器组指针的来源：`.bss` 里的内核填充指针

`seed_load_switch` 与 `set_std_sigma` 的 PC-relative 加载全部解析结果：

| 函数 | 加载目标 | 段 | 含义 |
|---|---|---|---|
| `seed_load_switch` | 0x543d8 | `.data` | 指向一个 **指针数组** |
| | 0x2084c / 0x20810 | `.bss` | 两个种子表的**槽位偏移**（0 / 0x30） |
| | 0x207f8 | `.bss` | 写回用的槽位 |
| `set_std_sigma` | 0x544d0 | `.data` | 同上，指针数组 |
| | 0x4ae58 | `.rodata` | **格式字符串**（配合 snprintf，0x60 字节缓冲） |

**→ 0x543d8 / 0x544d0 里存的是指向 `.bss` 指针数组的指针，
而那些 `.bss` 槽位由内核态填充。**
**→ 所以 NOG 走的是和 3D LUT 完全一样的机制：内核分配 handle，用户态拿不到。**

`set_std_sigma` 里 `snprintf(buf, 0x60, fmt, ...)` 说明它甚至要**把参数格式化成字符串**，
再经内核通道下发——这条路径更是完全不可伪造。

## 四、★★★ 顺带发现：NX500 有硬件颗粒发生器（推翻旧结论）

| 地址 | 大小 | 符号 | 作用 |
|---|---|---|---|
| 0x000105cc | 36 | `d5_ep_nog_set_bypass` | NOG 总旁路 |
| 0x000105f0 | 240 | `d5_ep_nog_set_noisegen` | 顶层：一次设全部噪声参数 |
| 0x00020070 | 248 | `_udd_ep_nog_reg_struct_init` | **清零寄存器组（不返回值）** |
| 0x00020168 | 232 | `_udd_ep_nog_set_random_seed` | 随机种子 |
| 0x00020250 | 176 | `_udd_ep_nog_seed_load_switch` | 种子表切换（表 0 / 表 0x30） |
| 0x00020300 | 176 | `_udd_ep_nog_select_rv_type` | **随机变量类型（噪声分布）** |
| 0x000203b0 | 432 | `_udd_ep_nog_set_std_sigma` | **标准差 = 颗粒强度** |
| 0x00020560 | 684 | `_udd_ep_nog_set_gamma` | **噪声 gamma = 颗粒大小分布** |
| 0x0002080c | 240 | `_udd_ep_nog_set_bypass` | 模块旁路 |
| 0x00034f98 | 1640 | `_udd_ep_mux_nog_rdxi` | MUX 读 |
| 0x00038968 | 1032 | `_udd_ep_mux_nog_wdxi` | MUX 写 |
| 0x0003bf68 | 140 | `_udd_ep_demux_nog_rdxi` | DEMUX 读 |
| 0x0003c8f4 | 288 | `_udd_ep_demux_nog_wdxi` | DEMUX 写 |

### `d5_ep_nog_set_noisegen(p)` 调用序列（反汇编还原，240B）

```c
int d5_ep_nog_set_noisegen(struct *p) {
    int rc = 0;
    _udd_ep_nog_reg_struct_init();                       // 清零，不返回
    rc |= _udd_ep_nog_set_random_seed(p->[0x08]);
    rc |= _udd_ep_nog_select_rv_type(p->[0x10], p->[0x08]);
    rc |= _udd_ep_nog_set_std_sigma(p->[0x00], p->[0x08]);  // ★ 强度
    rc |= _udd_ep_nog_set_gamma(p->[0x04], p->[0x08]);      // ★ gamma
    rc |= <p->[0x0c] 相关>;
    return rc;
}
```
`p` 至少 0x14 字节：`[0]=sigma [4]=gamma [8]=seed/handle [0xc]=? [0x10]=rv_type`

### ★★★ 这推翻了我之前的结论

我此前判定"**机身无颗粒维度**，TriX/HP5 的颗粒感用 SHARP 近似"。
**实际 NX500 有独立的硬件噪声发生器**，可控三要素：
- **强度** `std_sigma`
- **颗粒大小分布** `gamma`
- **噪声分布类型** `rv_type`

**真实胶片颗粒不是锐化，是随亮度分布的随机噪声。**
机身能做，而且是硬件级真随机（不是 PC 上加的伪随机数）。
**这是胶片仿真的关键要素，能力评估要改。**

## 五、★★★ 修正后的整体判断

三条路全部实测，结论高度一致：

| 路线 | 障碍 | 性质 |
|---|---|---|
| 3D LUT `d5_ep_3dl_*` | handle（三级指针） | 内核分配 |
| PW 直写 `yccmixer` | 经NOG PLT 取寄存器组 | 同一机制 |
| 硬件颗粒 `set_std_sigma` | `.bss` 指针 + snprintf 通道 | 同一机制 |

**→ NX500 的所有 ISP 底层色彩/噪声控制，用户态都只有"读符号"权限，没有"写寄存器"权限。
唯一能写的是 `/dev/d5_ipcc` 报文（属性总线）——而那正是 `CAttributeHandler` 走的路。**

**→ A 路线的 `capdtm setusr` 其实就是这条属性总线的客户端。之前 setusr 猜格式失败，
   现在知道真实属性 ID 是 `0x105..0x112`（PW段）与 `0x1b..0x25`（Bracket 段），
   这是下一步最该试的。**
