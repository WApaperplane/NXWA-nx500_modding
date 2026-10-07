# ISP 核 / DSP_NX500GLU 入口追踪 — 调查报告

> 日期：2026-10-05 21:20
> 目标：定位 ISP 固件核 `DSP_NX500GLU0APC1_SR1` 的入口与可写面
> 手段：**纯离线**（相机 192.168.0.x ping 不通），用 NX1 官方 GPL 包里的
> `libudd5.so` 做反汇编。相机本身 ping 超时，本轮**零实机接触**。

---

## 结论（先给骨架）

**1. "DSP_NX500GLU 入口"在 Linux 侧不是一个可直接调用的函数。**
`DSP_NX500GLU0APC1_SR1` 是**运行在独立 ISP 核上的裸机固件**（版本串来自
`/etc/version`，不是文件）。Linux 侧没有它的符号、没有加载它的代码路径。
能追到的最远边界是：

```
用户态 API (libudd5.so)
   → ioctl /dev/drime5_ep
      → EP 硬件寄存器（0x80506864 十子块）
         ←—— 这条链路里【没有 ISP 固件参与】
```

**2. 上一轮"NOG 是空的、硬件颗粒发生器未启用"的结论要修正。**
NOG（Noise Generator = 硬件颗粒发生器）**用户态 API 完整存在**，
且我已从反汇编里解出它在 regset 结构体内的**真实寄存器偏移**。
"数据区全零"只说明**当前配置下没启用**，不等于"没有这个硬件"。

**3. 铁律不变：仍然不要写 EP 寄存器。**
本报告给出的是**可观测性**和**用户态正规通道**，不是"可以安全裸写寄存器"。

---

## 二、EP 子块基址：10 组 `{start,size}` 交错（已验证）

`/usr/include/media/drime5/ep/d5_ep_type.h` 原文：

```c
struct ep_reg_info {
    struct ep_reg_phys_info reg_base_top;    // ← top
    struct ep_reg_phys_info reg_base_ldc;
    struct ep_reg_phys_info reg_base_mc;
    struct ep_reg_phys_info reg_base_rsz;
    struct ep_reg_phys_info reg_base_lvr;
    struct ep_reg_phys_info reg_base_bblt;
    struct ep_reg_phys_info reg_base_fd;
    struct ep_reg_phys_info reg_base_jpeg;
    struct ep_reg_phys_info reg_base_3dlut;
    struct ep_reg_phys_info reg_base_nog;    // ← NOG
};
```

★ **这就是记忆里 `epdump2.c` 修过的那个 bug 的官方证据**：
不是"两个数组"，而是 10 组 `{start,size}` 交错，共 160 字节。
取得通道 = `EP_IOCTL_GET_PHYS_REG_INFO` = `_IOR('h', 100, struct ep_reg_info)`
= **`0x80506864`**，必须发到 `/dev/drime5_ep` 的 fd（发到 `/dev/mem` 返回 RC=3）。

| # | 字段 | 已实测基址 | 大小 |
|---|---|---|---|
| 8 | `reg_base_3dlut` | `0x2082b000` | 0x1000 |
| 9 | `reg_base_nog` | `0x20821c00` | 0x100 |

---

## 三、★★★ 本轮核心突破：NOG 寄存器偏移（反汇编自证）

### 3.1 用户态 API 全部存在（503 个导出符号中）

| 层 | 符号 | 作用 |
|---|---|---|
| 公开 API | `d5_ep_nog_set_noisegen` | ★ 顶层入口，参数 = `d5_ep_nog_op_info` |
| 公开 API | `d5_ep_nog_set_bypass` | 旁路开关 |
| 内部 | `_udd_ep_nog_set_std_sigma` | 标准差（噪声强度） |
| 内部 | `_udd_ep_nog_set_gamma` | 噪声权重 gamma 曲线 |
| 内部 | `_udd_ep_nog_set_random_seed` | 随机种子 |
| 内部 | `_udd_ep_nog_select_rv_type` | UNIFORM / GAUSSIAN |
| 内部 | `_udd_ep_nog_seed_load_switch` | 种子装载开关 |
| 内部 | `_udd_ep_nog_regset0` / `regset1` | `.bss` 里的 regset 结构指针 |
| 全局 | `ep_nog_reg_base` | `.bss @ 0x4d644`，运行时 = mmap 后的 EP 基址 |

**`d5_ep_nog_op_info` 结构（`ep_type.h` 原文，作者 Junhee Jeong）：**

```c
typedef struct {
    u8                      std;          // 标准差 = 噪声强度
    u8                     *gamma;        // gamma 表指针
    d5_ep_cs_id             cs_id;        // context switch group
    d5_ep_nog_seed_switch   seed_switch;  // DISABLE=0 / ENABLE=1
    d5_ep_nog_rv_type       rv_type;      // UNIFORM=0 / GAUSSIAN=1
} d5_ep_nog_op_info;
```

### 3.2 ★★ 关键判据：NOG 寄存器组在 regset 内偏移 = `+0x30`

反汇编 5 个**互相独立**的 NOG 函数，全部出现同一条
`ADD rX, rY, #0x30`（机器码 `e28330xx`）：

| 函数 | 命中指令 | 语义 |
|---|---|---|
| `_udd_ep_nog_set_bypass` | `ADD 0x30 (r0 → r2)` | 取 NOG 寄存器组 |
| `_udd_ep_nog_set_gamma` | `ADD 0x30 (r0 → r3)` | 同 |
| `_udd_ep_nog_seed_load_switch` | `ADD 0x30 (r0 → r2)` | 同 |
| `_udd_ep_nog_select_rv_type` | `ADD 0x30 (r0 → r2)` | 同 |
| `_udd_ep_nog_set_std_sigma` | `ADD 0x30 (r0 → r3)` | 同 |

**5/5 命中 = 交叉验证通过。** 这不是猜的，是编码级证据。
含义：`_udd_ep_nog_regset0/1` 指向的结构体，**偏移 0x30 处是 NOG 寄存器组**。

### 3.3 NOG 组内寄存器偏移（从 `set_std_sigma` 解出）

`_udd_ep_nog_set_std_sigma` 是信息量最大的一个（sz=432）：

```
ADD 0x60 (r0 → r3)     ← 另一组寄存器（可能是 LDC/MC 区）
ADD 0x30 (r0 → r3)     ← NOG 组
ADD 0x67 (r0 → r1)     ┐
ADD 0x66 (r0 → r1)     ├ 连续 3 个字节寄存器：0x65 / 0x66 / 0x67
ADD 0x65 (r0 → r1)     ┘
SUB 0x1f               ← 与 0x1f 做 AND ⇒ 位宽 mask（5 bit）
```

⇒ **NOG 组内相对 `+0x30` 基址的三个字节寄存器 = `+0x35 / +0x36 / +0x37`**，
掩码 `0x1f`。`_udd_ep_nog_reg_struct_init` 里 16 个 `SUB 0x4` 是 16 个
`void*` 字段逐个清零 = **regset 结构体共 16 个指针槽（64 字节）**，
`0x30` 正好是第 12 个槽（`12 × 4 = 0x30`）——**两路推算互相印证**。

### 3.4 `_udd_ep_nog_set_gamma` 的循环结构

sz=684，是最长的 NOG 函数。反汇编出清晰的循环：

```
for (i = 0; i < 4; i++) {          // 4 次
    LDR  0xc  (r11 → r1)           // gamma[i]
    LDR  0x18 (r11 → r2)           // regset
    ...
    LDR  0x10 (r11 → r2)
    SUB  0x10 (r2 → r2)  → +0x10  ┐
    LDR  0x14 (r1 → r1)           ├ 步进 +0x10，跨 4 次
    LDR  0x18 (r11 → r2)           │
    SUB  0x14 (r2 → r2)  → +0x14  │
    LDR  0x18 (r1 → r1)           │
    SUB  0x18 (r2 → r2)  → +0x18  │
    LDR  0x1c (r1 → r1)           ┘
}
```
⇒ gamma 写入 NOG 组内 `+0x40 / +0x44 / +0x48 / +0x4c` 四个 32-bit 槽
（相对 `+0x30` 基址），**步长 0x10，共 4 项**。与 `D5_EP_LUT_CBCR_CH01`
"CH0+CH1 平均"的 3 档枚举对不上，**说明 gamma 是 4 档曲线**。

---

## 四、3D LUT 侧（对照）

`ep_3dlut_reg_base` 在 `.bss @ 0x4d650`。相关 API 同样完整：

| 符号 | 作用 |
|---|---|
| `d5_ep_3dl_load_lut` | 从 DDR 装载 LUT 到硬件 |
| `d5_ep_3dl_save_lut` | 从硬件回存 LUT 到 DDR |
| `_udd_ep_3dl_reg_SetAddress` | 设 LUT 物理地址 |
| `_udd_ep_3dl_reg_SelLUT` | 选 LUT0 / LUT1 / LUT_EXT |
| `_udd_ep_3dl_reg_SelCbCr_ch` | 选 Cb / Cr / (Cb+Cr)/2 |
| `_udd_ep_3dl_reg_SetColorFormat_LUT0/1` | YCC422 / YCC420 |

★★ **`d5_ep_3dl_load_lut` 的存在直接对上记忆里的旧发现**：
3DLUT 硬件块是**使能的**（`+0x00 = 0x1`），且尾部
`0x00f0..0xfc = 0x13020619` ×8 = identity LUT。
`_udd_ep_3dl_reg_SetAddress` 反汇编出 `SUB 0xc` / `SUB 0x10` ⇒
LUT 内部有**两个地址寄存器**（LUT0 / LUT1 各一个），与
`D5_EP_LUT_SEL_LUT0/LUT1/LUT_EXT` 三档一致。

---

## 五、入口链路（修正版）

```
┌─ 用户态 ────────────────────────────────────────────┐
│ d5_ep_nog_set_noisegen(d5_ep_nog_op_info*)          │  libudd5.so
│   └→ _udd_ep_nog_set_std_sigma / set_gamma / ...    │
│        └→ regset(+0x30) → EP 物理寄存器              │
│   d5_ep_3dl_load_lut(addr, sel, fmt, timeout)        │
│   d5_ep_top_update_sreg(module)   ← 触发影子寄存器提交 │
└──────────────────────┬──────────────────────────────┘
                       │  ioctl
┌─ 内核 ───────────────▼──────────────────────────────┐
│ /dev/drime5_ep   (10,126)                           │
│   EP_IOCTL_GET_PHYS_REG_INFO  0x80506864  ← 拿 10 组基址
│   EP_IOCTL_UDD_LOCK/UNLOCK    'h',40 / 'h',41       │
│   EP_IOCTL_SET_CLK_RATE       'h',50                │
└──────────────────────┬──────────────────────────────┘
                       │  mmap(PROT_READ)
┌─ 硬件 ───────────────▼──────────────────────────────┐
│ EP @ 0x80506800 十子块                                │
│   NOG   @ 0x20821c00 (0x100)                         │
│   3DLUT @ 0x2082b000 (0x1000)                        │
└─────────────────────────────────────────────────────┘

★ 链路里【没有 ISP 固件节点】。
  ep.h 顶部 #define EP_TOP_VIRT_ADDR ⇒ 库自己 mmap，不用内核代传。
```

---

## 六、"EP 是 ISP 固件实时驱动"这个说法要修正

上一版报告写"EP 由 ISP 固件 `DSP_NX500GLU0APC1_SR1` 实时驱动"，
**这个因果链没有证据支撑**，本轮应降级为假设：

- 证据 1：dmesg 有 `DRIME5: IDS : 31(ISP), 57(ARM) PROMISE : 97`
  ⇒ **ISP 确实是独立核，ID=31**。这条成立。
- 证据 2：**整个 Linux 侧（内核模块 + libudd5）没有任何一处提到 ISP 固件**。
  `grep -i "isp\|dsp\|srp"` 在 libudd5.so 的 503 个符号里零命中。
- 证据 3：EP 走的是 `/dev/drime5_ep` ioctl + 用户态 mmap，
  是**标准 UDD（用户态驱动）模型**，与 ISP 核无直接数据面关系。

⇒ **更可能的图景**：ISP 核跑传感器/ISP pipeline，EP 是**独立的图像引擎硬件**，
由 CA9 上的 Linux 用户态直接驱动（这就是 UDD = Userspace Device Driver 的含义）。
两者通过 SRAM 交换数据，但**不是"ISP 固件在驱动 EP 寄存器"**。

**这个修正的实际影响**：既然 EP 是 Linux 用户态在驱动，
那"liveview 期间改 3DLUT 会被 ISP 同时读取"这个风险描述**可能也不准确**。
真正的风险是**改了 3DLUT 但没走 `d5_ep_top_update_sreg(D5_EP_3DLUT_SHADOW_UPDATE)`**
导致影子寄存器不提交。★ **此条需实机验证，我列入下一步，不在这里下结论。**

---

## 七、工具（新增 3 个，可复用）

| 文件 | 作用 |
|---|---|
| `test_server/isp/arlit.py` | 提取函数字面量池 / 符号表 / `--list` |
| `test_server/isp/ardec.py` | ARM 位域解码：抽 ADD/SUB/LDR/STR 立即数偏移 |
| `test_server/isp/arel.py` | 重定位表 → "哪个函数引用了哪个符号" |

### 踩坑记录（3 个真 bug，已修在工具里）

1. **共享库只有 `.dynsym`(type=11)，没有 `.symtab`(type=2)。**
   只判 `type==2` ⇒ 符号表整个被跳过，`--list` 输出 0 行。
2. **`st_info` 低 4 位是 type，高 4 位是 binding。**
   用 `info>>4 == 2` 判 `STT_FUNC` ⇒ `funcs=0`。
3. **`.bss` 里的导出全局变量在 `.text` 里搜不到绝对地址字面量**
   （编译期用 PC-relative/GOT 访问）。
   ⇒ 找"谁引用了某全局"必须走重定位表（`arel.py`），
   纯 `memmem` 搜 `.text` 会得出"零引用"的**假阴性**。

---

## 八、下一步（按价值排序）

| 优先级 | 动作 | 判据 |
|---|---|---|
| **1** | 编译一个只调 `d5_ep_nog_set_noisegen(std=1, GAUSSIAN, seed=ENABLE)` 的探针，**liveview 前后各拍一张**，做像素方差统计 | 若方差显著上升 ⇒ NOG 硬件真的在出图，**FilmLab 的"硬件颗粒"路线成立** |
| 2 | 验证 `d5_ep_top_update_sreg(D5_EP_3DLUT_SHADOW_UPDATE)` 是否是 3DLUT 生效的必要步骤 | 直接决定 .cube LUT 能否下沉到机身 |
| 3 | 实机确认 NOG 硬件存在：读 `0x20821c00` + `0x0c`（记忆里是 `0x13060911` magic） | magic 变了 = 之前读的是空配置态 |
| 4 | 冷启动 dmesg 抓 ISP 固件加载日志（本次 dmesg 是 resume 段，没有冷启动日志） | 找 `request_firmware` 或 uImage 加载行 |

### ⚠️ 下次实机的操作纪律
- 相机本轮不通（ping 超时）——**先确认 IP 和相机状态**。
- 探针必须**先 dry-run 只读**（只 `open` + `GET_PHYS_REG_INFO`，不调 `set_*`）。
- ★ **单核相机不能连续跑重活**：首验 1 张 1 尺寸，批量 ≤3。
- ★ **telnet 必串行**；≥10KB 走 FTP（`ftp_put → 一次 telnet → ftp_get`）。
- ★ **NOG 是"新颗粒"**：`d5_ep_nog_set_noisegen` 会**覆盖**厂商调校。
  动手前必须确认**回滚路径**（`d5_ep_nog_set_bypass(EP_DD_ON)` 或重启）。

---

## 九、记忆需要更新的条目

- ❌ 作废：「EP 由 ISP 固件 `DSP_NX500GLU0APC1_SR1` 实时驱动」
  → 降级为假设，无证据。
- ❌ 作废：「NX500 有硬件颗粒发生器（13 个 NOG 符号）但受厂商 handle 约束」
  → **handle 墙不存在**。NOG 有完整公开 API `d5_ep_nog_set_noisegen`。
- ✅ 新增：NOG regset 内偏移 `+0x30`（5/5 函数交叉验证）
- ✅ 新增：NOG 组内 `+0x35/+0x36/+0x37` 字节寄存器，mask `0x1f`
- ✅ 新增：gamma 4 档，槽位 `+0x40/+0x44/+0x48/+0x4c`，步长 `0x10`
- ✅ 新增：regset 结构 = 16 个 `void*` 槽（64 字节）
