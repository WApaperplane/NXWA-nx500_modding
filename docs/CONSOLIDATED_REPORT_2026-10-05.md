# NX500 相机逆向与胶片仿真 —— 综合成果报告

# NX500 Camera Reverse Engineering & Film Simulation — Consolidated Report

> **日期 / Date**: 2026-10-04 ~ 2026-10-05
> **分支 / Branch**: `nx-ks2`　**作者 / Author**: WApaperplane
> **项目 / Project**: Samsung NX500 相机胶片仿真模组（FilmLab）+ 系统层逆向
> **平台 / Platform**: Tizen 2.2.0 · Linux 3.5.0 · 单核 Cortex-A9 · `Samsung-DRIMe5-ES`
> **相机型号判定 / Model detection**: `/etc/version.info` = `NX500` + `1.12`（或 `NX1` + `1.41`）

> **本文取代** `DEVELOPMENT_REPORT_2026-10-05.md`、`SYSTEM_LAYER_FINDINGS_2026-10-04.md`
> 及其英文版 —— 那两份里的多条结论已被 10-05 的实测推翻（见第 0 章对照表）。
> **This document supersedes** the two earlier reports: several of their conclusions were
> refuted by real-hardware measurements on 10-05 (see the correction table in Chapter 0).

---

## 目录 / Table of Contents

- [第一部分 · 中文](#第一部分--中文)
  - [0. 今日修正的旧结论](#0-今日修正的旧结论)
  - [1. ★ 最主要的发现：handle 墙绕道](#1--最主要的发现handle-墙绕道)
  - [2. 双核通信：三条通道的实测判决](#2-双核通信三条通道的实测判决)
  - [3. FilmLab 胶片仿真模组](#3-filmlab-胶片仿真模组)
  - [4. 用户态控制面（prefman / PW / setusr）](#4-用户态控制面prefman--pw--setusr)
  - [5. 硬件约束表](#5-硬件约束表)
  - [6. 死机调查：10 次假设被自己的实验推翻](#6-死机调查10-次假设被自己的实验推翻)
  - [7. 方法论铁律](#7-方法论铁律)
  - [8. 工具链](#8-工具链)
  - [9. 能力边界与未走通的路](#9-能力边界与未走通的路)
  - [10. 致谢](#10-致谢)
- [Part II · English](#part-ii--english)
  - [E0. Corrections to earlier conclusions](#e0-corrections-to-earlier-conclusions)
  - [E1. ★ Headline finding: bypassing the handle wall](#e1--headline-finding-bypassing-the-handle-wall)
  - [E2. Three inter-core channels, measured](#e2-three-inter-core-channels-measured)
  - [E3. The FilmLab module](#e3-the-filmlab-module)
  - [E4. Userspace control surface](#e4-userspace-control-surface)
  - [E5. Hardware constraints](#e5-hardware-constraints)
  - [E6. The freeze investigation: 10 hypotheses killed by experiment](#e6-the-freeze-investigation-10-hypotheses-killed-by-experiment)
  - [E7. Methodology rules](#e7-methodology-rules)
  - [E8. Tooling](#e8-tooling)
  - [E9. Capability boundaries](#e9-capability-boundaries)
  - [E10. Acknowledgements](#e10-acknowledgements)
- [附录 / Appendix](#附录--appendix)

---
---

# 第一部分 · 中文

---

## 0. 今日修正的旧结论

> 逆向工程里最贵的资产不是"找到什么"，是"推翻什么"。
> The most expensive asset in RE is not what you find, but what you refute.

两天里 10 个假设被自己的实验推翻，其中 3 个是会影响路线判断的**框架级错误**。
这三条是本项目最重要的修正：

Of the ten hypotheses killed by experiment across two days, three were
**framework-level** errors that changed the project's direction. These three matter most:

| 早先判断 / Earlier claim | 实测结论 / Measured reality | 依据 / Evidence |
|---|---|---|
| `d5_ipcc` 是主要跨核通道 | ❌ **IPCC 是空壳**。ioctl 返回 `r=0` 但 mailbox 字段完全不回填；`_IOWR('t',nr,8)` 直接 SIGILL 打死进程 | §2.1 |
| 双核隔离，无法通信 | ❌ **`drime5_ep` 中断 1,490,995 次**（全系统最高频）；`d5_sma` 有 144MB 共享区 @ `0x94000000` | §2.2 |
| 3D LUT / NOG 硬件未初始化（`ep_3dlut_reg_base = 0`） | ❌ **那个 `0` 是驱动内部变量**。硬件寄存器基址一直存在，Linux 侧 mmap 可读，且里面装着 identity LUT | §1.2 |
| handle 墙不可破 | ⚠️ **只对厂商库成立**。直接 mmap 硬件**根本不存在 handle 这个概念** | §1.4 |

**⇒ 准确的说法**：用户态**不能通过厂商 API 做超出边界的配置**（handle 不变量检查拦的是这一条），
但**可以直接观测硬件寄存器**——这是一条之前没有被利用的通道，也是本项目目前最有价值的技术资产。

**⇒ The accurate statement**: userspace *cannot* configure the hardware *through vendor APIs*
beyond their invariants, but it *can observe hardware registers directly*. That channel was
previously unexploited and is now the project's most valuable technical asset.

---

## 1. ★ 最主要的发现：handle 墙绕道

### 1.1 墙是什么

`libudd5.so` 的 3D LUT 入口都要求传入一个 `handle`：

```c
d5_ep_3dlut_op_init(handle, ...)   // 内部检查 handle + 0x0c == 1
```

这个 `handle` 是厂商库在用户态构造的运行时对象，**不是内核句柄、不是文件描述符**。
所有 3D LUT / NOG 的厂商封装（`_udd_ep_3dlut_reg_SetReg`、`d5_ep_nog_set_std_sigma` …）
都要求它先通过这个检查。

**⇒ 这个墙只拦"调用厂商 API 的人"，不拦硬件本身。**

### 1.2 绕道方法（两步，均为只读实测）

**第一步：从内核拿到物理基址**

```c
/* /dev/drime5_ep, ioctl 号 = _IOR('h', 100, struct ep_reg_info) = 0x80506864 */
struct ep_reg_info { unsigned long start[10]; unsigned long size[10]; };
ioctl(fd_ep, 0x80506864UL, &reg);   /* r=0, 10/10 子块全部非零 */
```

返回的 EP 十个功能子块物理基址：

| 子块 | 物理基址 | 大小 | 用途 |
|---|---|---|---|
| `top` | `0x20820000` | `0x1c00` | 顶层控制 |
| **`nog`** | **`0x20821c00`** | `0x100` | 硬件颗粒发生器 |
| `ldc` | `0x20823000` | `0x1000` | 镜头畸变校正 |
| `mc` | `0x20824000` | `0x2000` | 运动补偿 / `yccmixer` |
| `rsz` | `0x20826000` | `0x1000` | resize |
| `lvr` | `0x20827000` | `0x1000` | 降噪 |
| `bblt` | `0x20828000` | `0x1000` | BB LT |
| `fd` | `0x20829000` | `0x1000` | 人脸检测 |
| `jpeg` | `0x2082a000` | `0x1000` | JPEG 编码 |
| **`3dlut`** | **`0x2082b000`** | `0x1000` | **3D LUT** |

**第二步：`/dev/mem` + `mmap(PROT_READ)` 直接读物理寄存器**

```c
/* ★ 关键：物理地址可能不对齐，映射要从向下取整的页边界开始，访问时再加页内偏移。
     直接 mmap(addr) 会 EINVAL。 */
off_t pa_off = addr & ~(pg - 1);
off_t offs   = addr - pa_off;
void *p = mmap(NULL, len + offs, PROT_READ, MAP_SHARED, fd_mem, pa_off);
unsigned *q = (unsigned *)((char *)p + offs);
/* 访问：q[i] */
```

### 1.3 ★ 读到了什么：identity LUT 的直接证据

`0x2082b000`（3DLUT）完整窗口 dump：

```
[0x0000] 0x00000001  0x00000100  0x00000000  0x81115200   ← +0x00 使能位已置 1
[0x0004] 0x00000100  0x00000000  0x81115200  0x00000000
[0x0008] 0x00000000  0x81115200  0x00000000  0x00000000
[0x000c] 0x81115200  0x00000000  0x00000000  0x00000000
...
[0x00f0] 0x00000000  0x00000000  0x00000000  0x13020619
[0x00f4] 0x13020619  0x13020619  0x13020619  0x13020619
[0x00f8] 0x13020619  0x13020619  0x13020619  0x13020619
[0x00fc] 0x13020619
```

- `+0x00 = 0x00000001` → **使能位已置 1**，3D LUT 硬件是开着的
- `+0x0c = 0x81115200` → 三星 ISP 典型配置位域（`0x81` 起始 = 8bit 精度）
- 尾部 `0x00f0..0x00fc` = **`0x13020619` 重复 8 次**
  逐字节 = `19 / 2 / 6 / 25` —— 这是 8bit 三通道 **identity LUT 的标准 4bit 量化打包值**

**⇒ 与「刚恢复出厂、无胶片效果」的当前状态完全吻合。**

对照组（先证明测量手段本身可信）：读 liveview 帧缓冲 `0xbbaea500` 得到
`0xebebebeb 0xebebebeb 0xececebeb 0xecebebec` —— 典型 24bpp 像素值。

**可重复性**（立因果的第二条必要条件）：**两次独立进程读数完全一致**。

### 1.4 handle 墙的准确性质

| | 内容 |
|---|---|
| **不是** | 文件权限、root 权限、ioctl 权限位 |
| **不是** | 「寄存器不存在」或「3D LUT 硬件没初始化」 |
| **是** | 厂商**驱动库**在用户态构造 handle 对象时的**不变量检查**（`handle + 0x0c == 1`），只拦厂商 API 的调用者 |
| **绕道** | ★ **直接 mmap 硬件寄存器，完全不经过厂商库** ⇒ 不存在 handle |

### 1.5 ⚠️ 本项目绝不写 EP 寄存器

这不是保守，是事实约束：

- 写 EP 寄存器是**不可中断操作**
- EP 由 ISP 固件 `DSP_NX500GLU0APC1_SR1` **实时驱动**
- liveview 期间改 3DLUT 会被 ISP 同时读取 ⇒ **位域错乱**
- 后果：画面损坏、EP 卡死，且 `di-camera-app` **杀不掉**
  （`launchpad_preloading_preinitializing_daemon` 会重新拉起）⇒ **只能拔电池**

**⇒ handle 墙绕道带来的真实收益是「可观测」，不是「可写」。**
但这已经够用了：它把 ISP 侧成像链路从黑盒变成了**可以只读监视的仪表盘**。

---

## 2. 双核通信：三条通道的实测判决

### 2.1 `d5_ipcc` —— 空壳（推翻旧结论）

| 编码 | 返回 | 结果 |
|---|---|---|
| `_IOWR('t',nr,4)`（`0xc00474xx`），nr=2..5 | `r=0` | ✅ 安全，但 **mailbox 字段完全不回填**（`buf[1..3]` 保持哨兵 `0xA5A5A5A5`；`buf[0]` 只回显传入的 `core_id`） |
| `_IOWR('t',nr,8)`（`0xc00874xx`），nr=2 | `r=0` | ✅ 安全，同样不回填 |
| `_IOWR('t',nr,8)`，nr=3/4/5 | — | ❌ **SIGILL 直接打死进程** |

**⇒ NX500 的 IPCC ioctl 只接受 `size=4` 的编码。`size` 字段参与内核派发匹配，
`size=8` 走进错误分支——不是返回 `ENOTTY`，是处决进程。**

8 个 `core_id` 枚举（`CA7_1` / `CA7_2` / `CA9_1` / `CA9_2` / `CM4_1..3` / `SRP`）全部无对应实现。

> **注意 ABI 不一致**：NX1 GPL 头文件里 `struct ipcc_available_info` 是 8 字节，
> NX500 实机只认 4 字节。**照抄 GPL 头文件会直接 SIGILL。**

### 2.2 `d5_sma` —— 真实共享内存

| ioctl | 值 |
|---|---|
| `SMA_GET_REGION_START_ADDR` | `0x94000000` |
| `SMA_GET_REGION_SIZE` | `0x09000000` = **144 MB** |
| `SMA_GET_ALLOCATED_SIZE` | `0x12000000` = **288 MB** |

> `ALLOCATED_SIZE > REGION_SIZE` ⇒ 两者语义**不是**「已用 / 总量」。
> 记下原始数值即可，**不要据此推断内存压力**。

### 2.3 `drime5_ep` —— 真正的主通道

- 中断计数 **1,490,995**，全系统最高频中断源
- 十个功能子块（§1.2 表）覆盖 `top` / `ldc` / `mc` / `rsz` / `lvr` / `bblt` / `fd` / `jpeg` / `3dlut` / `nog`
- 通过 `_IOR('h',100,...)` 可取回全部子块物理基址
- `nr=100` 的 `size` = 80 / 44 / 40 / 72 四种编码全部 `r=0` 安全

---

## 3. FilmLab 胶片仿真模组

### 3.1 架构

```
SD 卡 /mnt/mmc/filmlab/recipes.json   ← 配方唯一真相源（数量不限）
        ↓ mkgui
mod_gui 动态菜单（上限 22 按钮）
        ↓ 一键
filmlab.sh apply
        ↓ prefman set ×7  +  st cap capdtm setusr 20
ISP 实时生效（约 2 秒）
```

### 3.2 核心设计决策

| 决策 | 理由 |
|---|---|
| **固定写 slot 9（UI「自定义1」）** | 「不确定写到哪」等于不够一键。相机 UI 恒显示自定义1，按一下取景器立刻变 |
| 配方存 SD 卡，不存相机 | 改配方不用重刷，且数量不限 |
| `mkgui` 动态生成菜单 | 加配方 = 只改 JSON，菜单零改动 |
| 按 S1 键轮换配方 | `EV_S1.sh` 挂 `EV_FLAB.sh`（原文件备份为 `.orig`） |

### 3.3 已实现的 9 个配方

`portra400` / `velvia50` / `trix400` / `ektachrome` / `hp5` / `superia400` /
`monowarm` / `ektachrome_cyan` / `cine_teal`

**`monowarm` 是机身独有能力**：`SAT=0`（纯黑白）同时保留 R/B 增益差 = 暖调黑白。
PC 端矩阵引擎做不到这个。

### 3.4 ★ 一键生效：一次真实的 enum 跳变

**问题**：`apply` 的收尾动作原本是「写完再切一次，让 ISP 重读」：

```sh
st cap capdtm setusr 20 0x140009
```

但 FilmLab **固定写 slot 9** ⇒ **enum 恒为 9** ⇒ 第二次写入的是与当前
**完全相同的值** = **空操作**。ISP 收不到「风格变了」的通知 ⇒ 不重读 PW 段 ⇒
**按 S1 没反应，必须回 GUI 把图片向导切走再切回来才生效。**

**这不是延迟，是那次 `setusr` 根本没生效。**

**修复**（`filmlab-apply.sh:109` 的 `pw_force_reload()`）：同值时先切 `0x140009` 再切回，
制造真实跳变，切完用 `getusr` **回读自证**。

> **★ 铁律：涉及"是否生效"的判定必须用可自证的客观通道，不能用"让用户看一眼"。**
> `setusr` 的返回码不算证据，**回读才算**。

### 3.5 能力边界（★ 重要的诚实说明）

**7 维 = 逐像素同值的全局向量**（R/G/B 增益 + HUE/SAT/SHARP/CONTRAST）。

| | |
|---|---|
| ✅ 能做 | 胶片风格化、色彩偏移、反差曲线 |
| ❌ 不能做 | 真正的 tone curve、亮度分区调整、**胶片颗粒** |

参照 `voxivoid/recipe-lab-sony-pmca`（Sony 同级方案，26 个 1 字节槽位做出 77 个配方）
——这说明本方案已达到同级别的控制粒度。

> **为什么机身做不到真曲线与分区**：`di-camera-app` 从不 import 3D LUT 相关符号
> ⇒ **没有 GOT 槽可劫持**。硬件颗粒发生器（NOG）虽存在（13 个符号），
> 但同样受厂商 API 的 handle 约束。

### 3.6 GUI 前置性能约束

**X11 满屏窗口在 NX500 上吃满单核**——720×480 满屏窗会导致连 `echo >/tmp/x` 都执行不完。
⇒ **交互式 GUI 只走 `mod_gui`，不自写 X11 窗口。**

`mod_gui` 组件仅 **8004 字节**，是薄壳结构，重写成本低。
但原生 `mod_gui` 的 `key_down_callback` 只认 13 个键，**方向键与 JOG 波轮全部落进
`else → quit_app()`** ⇒ 想支持波轮必须自写 UI。

---

## 4. 用户态控制面（prefman / PW / setusr）

### 4.1 prefman 完整用法（已实测）

```sh
prefman info {ID}            # 命名条目表（info 0 = 672 条）
prefman set                  # ★免 save 即时生效（毫秒级、零 eMMC 写入）
prefman load -a0             # ★★ 千万别加！从 eMMC 重载会【覆盖】刚 set 的值
prefman save                 # 只在想持久化时用
prefman save_file {ID} <路径># ★真写到指定路径（安全）
prefman load_file {ID} <路径># 恢复（实测有效）
prefman fetch {ID} <路径>    # ★★ 忽略路径！写进 /opt/pref/pref_app.bin（污染活动文件）
```

> **`prefman set` 免 save 即时生效是本项目唯一可靠的写入通道。**
> CHECKSUM（`0x0fcbc`）恒为 108，无需重算。prefman 不裁剪值域，调用方自己夹紧。

### 4.2 PW 参数块

```
addr(参数i, 风格s) = 41964 + i*52 + s*4
i = 0..6 = R / G / B / HUE / SAT / SHARP / CONTRAST

★ 中性值：R/G/B = 100，HUE/SAT/SHARP/CONTRAST = 10（不是 Sony 的 ±3）
```

**slot 12（`CUSTOM_4`）在 prefman 里完整存在但 UI 不显示** ⇒ `apply` / `preset` 一律拒绝该槽。

### 4.3 `st cap capdtm` 命令树

```sh
st cap capdtm usrlist      # userdata 索引 0-86 全表
st cap capdtm getusr <id>  # ★ 与 varlist 是【两套编号】，不能混用
st cap capdtm setusr <id> <val>
st cap capdtm setvar <id> <data> <len>   # 作用范围待测
st cap capdtm varlist
st cap iqr                  # 183 项 IQ 节点（★ 只读，且是 ISP 常量表）
st cap lockinfo             # 读取 ISP 内部拍摄状态
st cap sh                   # ★ 自动快门（判据通道用）
```

> **★ NX500 系统性特征**：任何「列表命令」打印的索引**都不能**假定可用于读写命令。
> 必须「读列表 → 读命令验证 → 写命令验证」三步对齐。
> （在 `setusr` / `getvar` / `varlist` 上连续踩了三次同一个坑。）

### 4.4 `adj_*` 段 = 只读常量（5 处写入实验证实）

| 段 | 大小 | 非零率 | 判断 |
|---|---|---|---|
| 6 `adj_iq` | 3.5 KB | 1.6% | 空段 |
| 7 `adj_vfpn` | 24 KB | 90.6% | 满数据（固定模式噪声校正） |
| 8 `adj_cs` | 64 KB | 49.5% | 色彩空间 |
| 9 `adj_dpc` | 5.2 MB | — | 去马赛克 |
| 10 `adj_dpc2` | 1 MB | 10.5% | 去马赛克制表 |

**每段只有一条命名条目（整块 blob），无字段级语义标注。写进去读回正常但 ISP 不理。**

`/opt/pref/default/` 有**完整未污染的出厂副本**，比被 `fetch` 污染过的 `/opt/pref/*.bin` 可靠。

### 4.5 物理→虚拟地址换算（实测两样本一致）

```c
virt_of_phys(p) = p - 0xB7FC000
```

| 物理地址 | 虚拟地址 | 来源 |
|---|---|---|
| `0x94000000` | `0x88804000` | CMA 288 MiB 区 |
| `0x85400000` | `0x79c04000` | ISP 段（落在 `/proc/252/maps` 的 `71d74000-79d74000 rw-s /dev/mem`） |

**这是统一线性映射，不是分段表。**

### 4.6 可直接调用的静态单例（`libcapture-fw-prod.so`）

这些是**静态函数、无 `this` 参数**，所以在独立探针进程里可以安全调用。
对写 ARM 探针很有用（省掉 `GetCameraIfHandle()` 那个必崩的路径）：

| 单例 | `getInstance` 静态地址 | 用途 |
|---|---|---|
| **`CCapVirtualAddrIf`** | **`0x626e4`** | ★ 地址映射层（`GetVirtTopAddr`） |
| `CCaptureController` | `0x3d1d4` | 捕获控制 |
| `CTraceLog` | `0x3e178` | trace 日志 |
| `CCapturePublisher` | `0x80f14` | 捕获发布 |
| `CMCBAdapter` | `0x871f0` | MCB 适配 |

实测调用 `SingletonI<CCapVirtualAddrIf>::getInstance()` 得到的实例：

```
instance = 0x0006f230
vtable   = 基址 + 0xb0010   (_ZTV17CCapVirtualAddrIf ✓)
+0x04 = 0x94000000   ← 与 dmesg "cma: reserved 288 MiB at 94000000" 一致
+0x08 = 0xbfffffff   ← 4GB-1，地址空间上限
+0x0c = VirtTopAddr  ← GetVirtTopAddr() 实调返回 0x887f8000
```

> **★ 为什么重要**：`CCapVirtualAddrIf` 的 `+0x04` 独立返回 CMA 物理基址
> `0x94000000`，**与 `d5_sma` 的 `SMA_GET_REGION_START_ADDR` 返回值完全一致** ——
> 这是「用户态厂商库」与「内核 SMA 驱动」指向同一块共享内存的**交叉验证**。

---

## 5. 硬件约束表

| 约束 | 实测结果 | 影响 |
|---|---|---|
| **`/dev/mem` + `mmap(PROT_READ)`** | ✅ **成功** | ★ 可以直接读硬件寄存器（推翻旧的 `STRICT_DEVMEM` 结论） |
| `/dev/mem` + `pread` | ✗ `-1` | 但 `mmap` 路径可行 |
| `/proc/<pid>/mem` 读设备映射区 | ✗ `-1` | 内核禁止跨进程读设备映射区 |
| **`poker` 写 `.text`** | ✗ `Buffers not the same: ERROR` | 代码段不可写 ⇒ **劫持调用点不可行** |
| **`poker` 写 `.data`** | ✅ 成功 | 数据段可自由读写 |
| **CPU NX 位** | **无**（`Features` 无 `nx`） | ARMv7；`.data` 里的代码**可能可执行** |
| 根文件系统 | `/dev/root` ext4 **`ro`** | 换不了 `.so` |
| `/opt/usr` | `rw`，剩余 2.1 GB | mod 唯一可持久化的大容量区域 |
| **CPU** | ARMv7 rev1 (v7l) Exynos，**带 NEON** | |
| **内存** | `mem=512M`，CMA 静态预留 288+72 MiB | **实际可用仅 ~142 MB** |
| 内核模块 | `/proc/modules` 仅 6 个（WiFi/蓝牙/exfat） | **相机/ISP/MIPI 全部 built-in，无模块可加载** |
| 内核性能接口 | `/proc/softirqs`、`/proc/PID/io` 不可用 | 常规 Linux 性能工具链失效 |
| `LD_LIBRARY_PATH` | `:/usr/lib:/usr/lib/driver` | 空首项=cwd，但 cwd=`/` ⇒ 不可利用 |

**`/dev/mem` mmap 的两个硬性要求**：
1. **offset 必须页对齐**，否则 `EINVAL`（照 ge0rg `liveview.c` 的做法向下取整）
2. 访问时用 `base + (addr & (pagesize - 1))`

---

## 6. 死机调查：10 次假设被自己的实验推翻

> ⚠️ **本项目最重要的方法论资产。** 这份调查的结论是：
> **根因未找到。** 但排除了 10 个方向，证伪了一整类推理方式。

### 6.1 症状（★ 逐字拆解限定词）

进入相册后**只有删除键卡死**，其他键正常、快门可用、画面正常；拨盘关不掉机，必须拔电池。

**★ 关键的方法论动作是逐个拆解这些限定词**：

| 限定词 | 含义（不是字面意思） |
|---|---|
| 「发灰」 | 解码失败，不是崩溃 |
| 「快门可用」 | **两条链路是独立的** |
| 「重启无效」 | 状态**在文件里**，不在内存里 |
| 「要拔电池」 | 走的是**不可中断等待** |
| 「只有删除键」 | **只有它**碰缩略图链路 |
| 「进相册才死」 | 触发条件是**上下文**，不是动作 |

> 我前三轮全在 ISP 层找根因，**因为把"只有删除键卡死"当成了"删除照片失败"**。

### 6.2 10 个被推翻的假设

| # | 我的结论 | 被什么推翻 |
|---|---|---|
| 1 | slot 12 脏数据 | 清成中性后**仍卡** |
| 2 | `iqr` hi16 是 PW 实时值 | 写 0，**纹丝不动**（是 ISP 常量表） |
| 3 | `.thumbcache` 0 字节文件 | 删完 31 个，**仍卡** |
| 4 | `ipcc_ioctl` 死锁链 | **重启后完全正常时它也卡** → 是常态 |
| 5 | 改配方是触发条件 | `PW_TYPE=STANDARD`（配方没生效）**也卡** |
| 6 | 拍照累积 / 内存泄漏 | `MemFree` 稳定 27 MB |
| 7 | `FaceLinuxThread` 空转 | 修正 jiffies 除数 + stat 字段错位后**增量为 0** |
| 8 | `CAttributeHandler` 属性总线可用 | 堆扫描**零命中** → 死代码 |
| 9 | `iqr` 挂死是先行指标 | 看门狗全程 `IQR=ok`，**判据从未触发** |
| 10 | `400x82` 是相册用的尺寸 | 清空后**它一个都没生成**，相机只写 320x75 / 1024x85 |

**共同模式（10 次全部同一个错）**：把「**同时出现的现象**」当成原因。

### 6.3 ★ 缩略图方向整体证伪

| 实验 | 结果 |
|---|---|
| 一个月用 0906 prewarm 形态 | 从未死机（**数据一致却不死**） |
| 恢复出厂后 0 缩略图 | 也不死 |
| 恢复出厂设置 | ✅ 现象消失 |

⇒ **「缺失」与「不一致/污染」两条假设都错了。**

**最强候选（纯静态可得，未实机证实）**：`flab_guard.sh` 看门狗**误判** →
`kill -QUIT di-camera-app`。它每 13 秒起一个 `st cap iqr` 探针给单核加压
（而 `iqr` 健康态本身也会卡 0-1 s）；实测**假警报率 5:1**，误判即杀 app
——**杀 app 与「进相册死机」在用户感知上完全无法区分。**
⇒ 该 guard 是**净负债**，已删除。

**比按删除键更早的判据**：① 监视脚本日志写入中断 ② 拨盘关不掉机。

---

## 7. 方法论铁律

> 这一章是本文档最值钱的部分。技术会过期，推理错误会重犯。

### 7.1 立因果的双重条件

**必须同时满足两条**：

1. `A 发生时 B 必发生`
2. **`消除 A 后 B 消失`**

单靠"同时出现"或"时间线吻合"**不成立**。

> 2026-10-04 一天内因此连续 4 次给错根因（slot12 / iqr / 缩略图 0 字节 / ipcc 死锁链），
> 全部被后续实验推翻。

### 7.2 ★ 「崩溃点在哪」必须精确到源码行

**不能靠崩溃栈的函数名猜。**

2026-10-05 连踩 4 次 `SIGILL`，崩溃栈**始终显示"在 ioctl 附近"**，
于是先后错误地怀疑过：`printf` 变参、stdio 缓冲、栈溢出、ioctl 派发路径、
`/dev/null` vs `/dev/d5_sma` 的区别、连内联 `svc 0` syscall 都试了 —— **全是错方向**。

**真正定位方法**：把 callstack 的偏移（`main + 0x84`）**换算回源码行**，
发现它在**打印 ioctl 编码那段代码**里 ⇒ **根本没进内核**。

> **判据**：如果一个"外部原因"（内核/固件/硬件）假设，推导出它**必须解释所有观测**，
> 但观测里有一条它解释不了（此处：「连 `/dev/null` 的 ioctl 也崩」），
> **就说明假设错了，问题在自己的代码里。**

### 7.3 其余铁律

| # | 规则 |
|---|---|
| 3 | **静态快照只能描述状态，不能解释机制。** 看到异常值先问「正常状态下它是否也一样」—— `ipcc_ioctl` 健康时同样卡着，就这样被推翻 |
| 4 | **拿到现象描述，逐个拆解其中的限定词**，不要按自己预设的方向理解用户的话（见 §6.1） |
| 5 | **找【每次都出现】的结构性事件**，不是【某次操作之后出现】的事件 |
| 6 | **"接口 A 不暴露参数" ≠ "系统不可写"。** 三层存储：capdtm 运行时 userdata / prefman 持久化偏好 / ISP 固件常量。按"层"划边界，不按"app" |
| 7 | **库"在 maps 里" ≠ "被调用"。** 判定深挖之前先在目标进程内存里搜该库关键地址 |
| 8 | **写前逐槽只读预检 + 写后 dump 复读比对 + `load_file` 回滚**，防半写 |
| 9 | **"是否生效"的判定必须用可自证的客观通道**，不能用"让用户看一眼" |
| 10 | **静态反汇编**：PC-relative 常量必须同时查 `.rel.dyn` 和 `.rel.plt`；ARM 指令必须按位域规则解码；`varlist` 索引 ≠ `getvar` 索引 |
| 11 | **物理→虚拟地址是统一线性映射** `virt = phys - 0xB7FC000`（两样本实测一致） |
| 12 | **穷举/钻系统前，先把同主题社区主仓库完整读一遍**（README + 全文件名列表 + 全文遍历打印） |
| 13 | **「安装脚本装的东西」≠「仓库里存在的东西」。** 写前置检查文案前必须回 `install.sh` 的 `cp` 语句核实 |

### 7.4 ★ 交叉编译铁律（zig 0.13 → `arm-linux-gnueabi.2.15` softfp）

| # | 规则 |
|---|---|
| 1 | **必须 `-O0`**。`-O1`+ 实测段错误 |
| 2 | **★ 自定义 `IOC` 宏在 32 位 int 上有符号溢出**。`#define IOC(d,t,nr,sz) (((d)<<30)\|...)` 中 `(2)<<30` = `0x80000000` ⇒ zig ARM 后端在 `-O0` 下生成**非法指令 ⇒ `SIGILL(signal=4)`**。<br>**症状极具误导性**：崩溃点永远看起来在"第一次 ioctl"附近，实际根本没进内核（连 `/dev/null` 的 ioctl 都崩）。<br>**解法**：所有 ioctl 号用 Python **预计算成字面量常量表**（`0x80506864UL`），运行时只查表，不做任何移位 |
| 3 | **`-static` 对 zig 无效**（被 `cc` 忽略），别浪费时间验证 |
| 4 | **本地缺库 ≠ 真机缺符号。** 凭 EFL/POSIX 版本记忆写 ABI 声明必错。正确证据源 = **真机上跑通过的 ARM 二进制的 `.dynsym` UNDEF 符号** |
| 5 | **链接期 stub 库只有 soname 严格一致才安全**。但所属库本地完全没有的符号**绝不能走 stub** —— extern + stub ⇒ 静态解析 ⇒ 真机调空函数 ⇒ **"窗口能开但按键全无反应且不报错"**。这类符号用 `dlsym(RTLD_DEFAULT, ...)`，失败要**显式非零退出** |
| 6 | **自写十进制/十六进制打印必须双向验证。** `pdec()` 曾把 `395`（正好是 `FMT_BUFFER_SIZE`）打成 `593`，差点变成假证据。`b[m++]=u%10` 是低位在前 ⇒ 打印要倒着打 |
| 7 | **`ecore_event_handler_add` 必须 `dlsym(RTLD_DEFAULT,...)`**。用 stub 链接后导入表里直接消失 ⇒ 波轮死 |

### 7.5 远程操作铁律（单核相机）

| # | 规则 |
|---|---|
| 1 | **telnet 必串行**（并发打挂单核）。**≥10KB 一律走 FTP** |
| 2 | **CRLF 是头号坑**。远端 md5 一致却语法错 ⇒ 必是行尾，`od -c` 唯一可靠手段 |
| 3 | **单核相机不能连续跑重活**。首次验证只跑 1 张 1 尺寸；小批量 ≤3 张；全量必须后台 + `nice -n 19`。症状：跑完 telnet+FTP 双挂 = 相机被压死，要拔电池 |
| 4 | **禁用 `cat /proc/iomem`**（触发内核段错误并打死 shell）；**禁用 `find /sys/...`**（单核上跑 3 分钟不返回，SIGHUP 把整个脚本带走）|
| 5 | **busybox**：无 `pidof`（读 `/proc/[0-9]*/comm`）、无 `$!`、`nohup` 不认 → 直接 `prog &`；无 `base64`；`nice` 不能调 shell 函数；**`killall -q busybox` 会自杀**（`telnetd`/`ftpd`/`httpd` 全是它的软链接） |
| 6 | **telnet 会吃掉命令里的引号**，多参数程序传参用脚本内部拼好 |
| 7 | **shell case 同名分支**：插新分支前先 grep 旧分支，否则表现为"传参被忽略" |

---

## 8. 工具链

### 8.1 架构抓取与探针（`test_server/sysarch/`）

| 工具 | 用途 |
|---|---|
| `minitel.py` | 自写 telnet（Python 3.13 无 `telnetlib`）：socket + IAC 剥离 + 全拒协商 |
| `probe_arch.py` … `probe4.py` | 分批只读采集脚本 |
| **`run_arm.py`** | ★ **通用 ARM 程序投递器**：FTP 投 → telnet 跑 → FTP 拉回 |
| `run_ipt.py` | IPCC 逐格探测驱动器（每格一个独立进程 + 独立 telnet 会话） |
| `probe_src/epinfo3.c` | ★ EP/SMA/IPCC 只读探针（ioctl 号全部预计算成字面量表） |
| `probe_src/epreg.c` | ★ EP 寄存器可读性验证（页对齐 mmap 技巧） |
| `probe_src/epdump.c` | 寄存器窗口 dump（逐行立即落盘，崩溃也能看到前面已输出的内容） |
| `probe_src/t0.c` … `t9.c` | ★ 二分定位用的 10 个最小测试程序（完整 SIGILL 定位档案） |
| `raw/`(23) `raw2/`(14) `raw3/`(33) `raw4/`(28) `raw5/`(90) `raw6/`(9) | 原始采集数据（197 文件） |

### 8.2 PC 侧静态分析（`test_server/pwfilter/`）

| 工具 | 用途 |
|---|---|
| **`symref.py <maps> <eip...>`** | ★核心：eip → 落在哪个 so + 库内偏移 + **符号名** |
| **`pltscan.py <elf> [kw]`** | PLT/GOT 映射 + 定位函数调用点（★用来判定死代码） |
| `elfmap.py` / `libscan.py` / `cxx.py` | ELF32 段布局 / 符号筛选 / C++ 类结构 |
| **`arm2.py` / `armdis.py`** | ★ ARM32 反汇编（按位域规则解码，正确） |
| `enumscan.py` / `rodump.py` / `pltfind.py` | `E_*` 枚举 / `.rodata` 字符串 / PLT import 筛选 |
| `dynsym.py` / `check_abi.py` | ★ 符号表解析与 ABI 核对（可复用，ELF32 通用） |
| `shotstat.py` | ★ JPG 像素统计判据工具（`local` / 相机 IP 双数据源，可离线回归） |

### 8.3 相机侧探针（`test_server/pwfilter/b1/src/`）

| 探针 | 用途 |
|---|---|
| **`heapscan`** | 直读 `/proc/pid/mem` 批量扫内存（3.4 MB/秒）—— ★判定死代码的核心工具 |
| **`ispprobe`** | `dlopen` + `dlsym` 解析运行时地址 + `SingletonI::getInstance()` 调通 |
| `lut3d_probe` | 3D LUT / NOG 控制链探针（38 个符号 + 9 个寄存器组） |
| `memread` / `regscan` | 设备内存读取 |

### 8.4 传输

| 脚本 | 注意 |
|---|---|
| `ftp_put.py` / `ftp_get.py` | ★ 远端路径**必须写 `/mnt/mmc/...` 前缀**（FTP 根 = SD 卡） |
| `telnet_run.py <ip> <cmd>` | ★ **必须串行**；telnet 需登录（`read` → 发 `root` → 发空行） |

---

## 9. 能力边界与未走通的路

### 9.1 能否做 Magic Lantern 水平固件？

| ML 的核心能力 | NX500 可达性 | 原因 |
|---|---|---|
| init task 替换 / 劫持 | ❌ | 需要与厂商固件**同核同地址空间**运行 |
| task dispatch 劫持 | ❌ | 同上 |
| 任意代码注入相机进程 | ⚠️ 部分 | `poker` 写 `.data` 可行、无 NX 位，但 `.text` 不可写、3D LUT 无 GOT 槽 |
| 读 ISP 寄存器 | ✅ | **本项目已实现**（§1） |
| 写 ISP 寄存器 | ⚠️ 理论可行 | 不可中断 + ISP 实时驱动 ⇒ 只能拔电池 |
| 相机控制（曝光/白平衡） | ✅ | `prefman` + `setusr` 已完整掌握 |

**结论**：NX-KS 路线的天花板在**"调用厂商 API"这一层**。
但**"直接观测硬件"这一层刚刚打开，几乎没有社区在做**——这是本项目后续最有价值的方向。

### 9.2 双原生 ISO

❌ **硬件级不可达。** 传感器由独立 ISP 固件直控，Linux 侧**无 V4L2**，
拿不到两路不同增益的原始数据。
✅ **可行替代**：PC 端分区降噪 + 阴影重建。

### 9.3 已排除的路径（避免社区重复踩坑）

| 路径 | 撞到的墙 |
|---|---|
| 3D LUT 直写寄存器（10-04 结论） | ⚠️ **10-05 部分推翻**：`mmap` 只读是可行的 |
| 3D LUT 劫持 GOT 槽 | `di-camera-app` **零个 3D LUT import** → 无槽可改 |
| 劫持 `CAttributeHandler` | **死代码**（堆扫描零命中） |
| `poker` 改 `.text` | 内核只读内存保护 |
| `capdtm setvar` 直写 PW | `varlist` 与 `getvar/setvar` 是**两套编号** |
| `iqr` 直写 | 是 ISP 固件的**常量表** |
| `adj_*` 段（6-10）写入 | ★ **只读常量**（5 处实验证实） |
| 修 `.thumbcache` 解决死机 | ❌ 方向整体证伪（§6.3） |
| 用 NX1 GPL 头文件写 IPCC ioctl | ❌ ABI 不一致，`size=8` 直接 SIGILL |

### 9.4 三个待做的只读实验

| # | 实验 | 能证什么 |
|---|---|---|
| 1 | 拍照前后各 dump 一次 3DLUT 窗口 | **3D LUT 真的参与成像** |
| 2 | 不同 ISO 下重复 dump `0x20821c00`（NOG） | 硬件 NOG 颗粒发生器存在 |
| 3 | **prefman 切配方时 dump 全部 EP 块** | **哪些寄存器是 ISP 侧真正吃配方的地方** |

> 实验 3 价值最高：它能把「配方写到 prefman」到「ISP 真正生效」之间的黑箱
> 缩到几个具体寄存器，**直接决定 FilmLab 引擎能否从 PC 端下沉到机身**。

---

## 10. 致谢

感谢 NX-KS 社区提供的 `poker`（进程内存读写）、`nx-remote-controller-daemon`、
`mod_gui` 框架、`capdtm`，以及 ge0rg 的 `liveview.c`（`/dev/mem` 页对齐 mmap 技巧）
和 voxivoid 的 `recipe-lab-sony-pmca`（同级方案的粒度参照）。
没有这些工具，本文档里的系统层结论不可能拿到。

---
---

# Part II · English

---

## E0. Corrections to earlier conclusions

Three **framework-level** errors were corrected by measurement. These changed the
project's direction and are the most valuable content in this document.

| Earlier claim | Measured reality | Evidence |
|---|---|---|
| `d5_ipcc` is the main inter-core channel | ❌ **IPCC is a shell.** ioctl returns `r=0` but never fills the mailbox fields; `_IOWR('t',nr,8)` raises `SIGILL` and kills the process | §E2.1 |
| The two cores are isolated, no communication | ❌ **`drime5_ep` logged 1,490,995 interrupts** (highest in the system); `d5_sma` exposes a 144 MB shared region at `0x94000000` | §E2.2 |
| 3D LUT / NOG hardware is uninitialised (`ep_3dlut_reg_base = 0`) | ❌ **That `0` is a driver-internal variable.** The hardware base addresses exist, are mmap-able from Linux, and contain an identity LUT | §E1.3 |
| The handle wall is unbreakable | ⚠️ **It only holds for the vendor library.** Mapping hardware registers directly means there is no such thing as a handle | §E1.4 |

**⇒ The accurate statement**: userspace *cannot* configure the hardware *through vendor
APIs* beyond their own invariants, but it *can observe hardware registers directly*.
That channel was previously unexploited.

---

## E1. ★ Headline finding: bypassing the handle wall

### E1.1 What the wall actually is

All 3D LUT entry points in `libudd5.so` require a `handle`:

```c
d5_ep_3dlut_op_init(handle, ...)   // internally checks handle + 0x0c == 1
```

This `handle` is a **userspace runtime object constructed by the vendor library** — not a
kernel handle, not a file descriptor. Every vendor wrapper (`_udd_ep_3dlut_reg_SetReg`,
`d5_ep_nog_set_std_sigma`, …) requires it to pass this check first.

**⇒ The wall only blocks callers of vendor APIs. It does not block the hardware.**

### E1.2 The bypass (two steps, both read-only)

**Step 1 — get the physical base addresses from the kernel**

```c
/* /dev/drime5_ep, ioctl = _IOR('h', 100, struct ep_reg_info) = 0x80506864 */
struct ep_reg_info { unsigned long start[10]; unsigned long size[10]; };
ioctl(fd_ep, 0x80506864UL, &reg);   /* r=0, all 10 sub-blocks non-zero */
```

| Sub-block | Physical base | Size | Purpose |
|---|---|---|---|
| `top` | `0x20820000` | `0x1c00` | top control |
| **`nog`** | **`0x20821c00`** | `0x100` | hardware grain generator |
| `ldc` | `0x20823000` | `0x1000` | lens distortion correction |
| `mc` | `0x20824000` | `0x2000` | motion compensation / `yccmixer` |
| `rsz` | `0x20826000` | `0x1000` | resize |
| `lvr` | `0x20827000` | `0x1000` | noise reduction |
| `bblt` | `0x20828000` | `0x1000` | BB LT |
| `fd` | `0x20829000` | `0x1000` | face detection |
| `jpeg` | `0x2082a000` | `0x1000` | JPEG encode |
| **`3dlut`** | **`0x2082b000`** | `0x1000` | **3D LUT** |

**Step 2 — map the physical registers read-only**

```c
/* ★ The physical address may be unaligned: map from the page boundary below and
     add the in-page offset. mmap(addr) directly returns EINVAL. */
off_t pa_off = addr & ~(pg - 1);
off_t offs   = addr - pa_off;
void *p = mmap(NULL, len + offs, PROT_READ, MAP_SHARED, fd_mem, pa_off);
unsigned *q = (unsigned *)((char *)p + offs);
```

### E1.3 What was actually read: direct evidence of an identity LUT

```
[0x0000] 0x00000001  0x00000100  0x00000000  0x81115200   ← +0x00 enable bit is SET
[0x0004] 0x00000100  0x00000000  0x81115200  0x00000000
...
[0x00f0] 0x00000000  0x00000000  0x00000000  0x13020619
[0x00fc] 0x13020619
```

- `+0x00 = 0x00000001` → the 3D LUT hardware is **enabled**
- `+0x0c = 0x81115200` → typical Samsung ISP config bitfield (`0x81` = 8-bit precision)
- Tail `0x00f0..0x00fc` = **`0x13020619` repeated 8 times**
  Bytes = `19 / 2 / 6 / 25` — the **standard 4-bit-packed identity LUT** for 8-bit RGB

**⇒ Exactly consistent with the current state: factory-fresh, no film effect applied.**

Control group (proving the measurement method itself was sound): reading the liveview
frame buffer at `0xbbaea500` yields `0xebebebeb 0xebebebeb 0xececebeb 0xecebebec` —
typical 24bpp pixel values.

**Reproducibility**: two independent processes produced **byte-identical** reads.

### E1.4 The accurate nature of the wall

| | |
|---|---|
| **Not** | file permissions, root, ioctl permission bits |
| **Not** | "the register does not exist" or "the 3D LUT hardware was never initialised" |
| **It is** | an **invariant check on a userspace handle object** built by the vendor library (`handle + 0x0c == 1`); it only blocks callers of vendor APIs |
| **Bypass** | ★ **map the hardware registers directly, bypassing the vendor library entirely** ⇒ no handle exists |

### E1.5 ⚠️ This project will never write EP registers

This is a factual constraint, not caution:

- Writing EP registers is a **non-interruptible** operation
- The EP is **actively driven** by ISP firmware `DSP_NX500GLU0APC1_SR1`
- Modifying the 3D LUT during liveview means the ISP reads it concurrently ⇒ **bitfield corruption**
- Consequence: corrupted frames, wedged EP, and `di-camera-app` **cannot be killed**
  (`launchpad_preloading_preinitializing_daemon` respawns it) ⇒ **battery pull only**

**⇒ The real benefit of the bypass is observability, not writability.**
That is still enough: it turns the ISP imaging path from a black box into a
**read-only instrumented dashboard**.

---

## E2. Three inter-core channels, measured

### E2.1 `d5_ipcc` — a shell

| Encoding | Return | Result |
|---|---|---|
| `_IOWR('t',nr,4)` (`0xc00474xx`), nr=2..5 | `r=0` | ✅ safe, but **mailbox fields never filled** (`buf[1..3]` keep the `0xA5A5A5A5` sentinel; `buf[0]` merely echoes the `core_id` passed in) |
| `_IOWR('t',nr,8)` (`0xc00874xx`), nr=2 | `r=0` | ✅ safe, likewise no fill |
| `_IOWR('t',nr,8)`, nr=3/4/5 | — | ❌ **SIGILL kills the process** |

**⇒ The NX500 IPCC ioctl only accepts `size=4` encodings. The `size` field participates in
kernel dispatch matching, and `size=8` takes a wrong branch — not `ENOTTY`, but process
termination.**

All 8 `core_id` enumerations (`CA7_1` / `CA7_2` / `CA9_1` / `CA9_2` / `CM4_1..3` / `SRP`)
have no implementation.

> **ABI mismatch warning**: the NX1 GPL headers define `struct ipcc_available_info` as 8 bytes.
> The NX500 only accepts 4. **Copying the GPL header verbatim triggers SIGILL.**

### E2.2 `d5_sma` — real shared memory

| ioctl | Value |
|---|---|
| `SMA_GET_REGION_START_ADDR` | `0x94000000` |
| `SMA_GET_REGION_SIZE` | `0x09000000` = **144 MB** |
| `SMA_GET_ALLOCATED_SIZE` | `0x12000000` = **288 MB** |

> `ALLOCATED_SIZE > REGION_SIZE` ⇒ the two are **not** "used / total" semantics.
> Record the raw values; **do not infer memory pressure from them**.

### E2.3 `drime5_ep` — the real main channel

- **1,490,995 interrupts** — the highest-frequency interrupt source in the system
- Ten functional sub-blocks (§E1.2) covering `top` / `ldc` / `mc` / `rsz` / `lvr` / `bblt` / `fd` / `jpeg` / `3dlut` / `nog`
- `_IOR('h',100,...)` returns every sub-block's physical base
- `nr=100` with `size` = 80 / 44 / 40 / 72 all return `r=0` safely

---

## E3. The FilmLab module

### E3.1 Architecture

```
SD card /mnt/mmc/filmlab/recipes.json   ← single source of truth (unlimited count)
        ↓ mkgui
mod_gui dynamic menu (22 button slots)
        ↓ one tap
filmlab.sh apply
        ↓ prefman set ×7  +  st cap capdtm setusr 20
ISP takes effect in ~2 seconds
```

### E3.2 Core design decisions

| Decision | Why |
|---|---|
| **Always write slot 9 (UI "Custom 1")** | "Not knowing where it wrote" means not one-tap. The UI always shows Custom 1; one tap changes the viewfinder |
| Recipes live on the SD card, not the camera | Adding a recipe needs no reinstall, and the count is unbounded |
| `mkgui` generates the menu dynamically | Adding a recipe = edit one JSON, zero menu changes |
| S1 button cycles recipes | `EV_S1.sh` hooks `EV_FLAB.sh` (originals backed up as `.orig`) |

### E3.3 The 9 implemented recipes

`portra400` / `velvia50` / `trix400` / `ektachrome` / `hp5` / `superia400` /
`monowarm` / `ektachrome_cyan` / `cine_teal`

**`monowarm` is uniquely a body capability**: `SAT=0` (pure monochrome) while retaining an
R/B gain difference — warm-toned black and white. A PC-side matrix engine cannot do this.

### E3.4 ★ Making "one tap" actually work: a real enum transition

**The problem**: the original cleanup step was "write once more so the ISP re-reads":

```sh
st cap capdtm setusr 20 0x140009
```

But FilmLab **always writes slot 9** ⇒ the enum is permanently 9 ⇒ the second write is
**the exact same value** = a **no-op**. The ISP never receives a "style changed"
notification ⇒ never re-reads the PW block ⇒ **S1 appears to do nothing; you must go into
the GUI, switch the picture guide away and back.**

**This is not latency — that `setusr` call never took effect.**

**The fix** (`pw_force_reload()` in `filmlab-apply.sh:109`): when the value is unchanged,
switch to `0x140009` first, then switch back, creating a genuine transition — then
**read back with `getusr`** as self-proof.

> **★ Rule**: any "did it take effect?" judgement must use an **objectively verifiable
> channel**, never "let the user have a look". A `setusr` return code is not evidence;
> **the read-back is**.

### E3.5 Capability boundaries (★ an honest statement)

**7 dimensions = a global vector applied identically to every pixel**
(R/G/B gain + HUE/SAT/SHARP/CONTRAST).

| | |
|---|---|
| ✅ Can do | film stylisation, colour shifts, contrast curves |
| ❌ Cannot do | true tone curves, luminance-zone adjustment, **film grain** |

Compared against `voxivoid/recipe-lab-sony-pmca` (a comparable Sony-class scheme:
26 one-byte slots producing 77 recipes), this scheme reaches the same grade of
control granularity.

> **Why the body cannot do real curves or zone work**: `di-camera-app` never imports
> 3D LUT symbols ⇒ **there is no GOT slot to hijack**. The hardware grain generator
> (NOG) exists (13 symbols) but is bound by the same vendor handle constraints.

### E3.6 GUI performance constraint

**A full-screen X11 window saturates the single core** on the NX500 — a 720×480
full-screen window is slow enough that even `echo >/tmp/x` fails to complete.
⇒ **Interactive GUI must go through `mod_gui`; do not hand-roll X11 windows.**

`mod_gui` itself is only **8004 bytes** — a thin shell, cheap to rewrite.
But its `key_down_callback` recognises just 13 keys; **the arrow keys and the JOG dial all
fall into `else → quit_app()`** ⇒ supporting the dial requires a custom UI.

---

## E4. Userspace control surface

### E4.1 prefman (measured)

```sh
prefman info {ID}            # named entry table (info 0 = 672 entries)
prefman set                  # ★ instant, no save (milliseconds, zero eMMC writes)
prefman load -a0             # ★★ NEVER add this — reloads from eMMC and OVERWRITES what you just set
prefman save                 # only when you want persistence
prefman save_file {ID} <path># ★ genuinely writes to the given path (safe)
prefman load_file {ID} <path># restore (measured effective)
prefman fetch {ID} <path>    # ★★ IGNORES the path — writes /opt/pref/pref_app.bin (pollutes the live file)
```

> **`prefman set`'s save-free instant commit is the only reliable write channel in this
> project.** CHECKSUM (`0x0fcbc`) is always 108 — no recomputation needed. prefman does not
> clamp value ranges; the caller must clamp.

### E4.2 The PW block

```
addr(parameter i, style s) = 41964 + i*52 + s*4
i = 0..6 = R / G / B / HUE / SAT / SHARP / CONTRAST

★ Neutral values: R/G/B = 100, HUE/SAT/SHARP/CONTRAST = 10 (not Sony's ±3)
```

**Slot 12 (`CUSTOM_4`) exists fully in prefman but is not shown in the UI**
⇒ `apply` / `preset` must always refuse that slot.

### E4.3 The `st cap capdtm` command tree

```sh
st cap capdtm usrlist      # userdata index 0-86
st cap capdtm getusr <id>  # ★ a DIFFERENT numbering from varlist — never mix them
st cap capdtm setusr <id> <val>
st cap capdtm setvar <id> <data> <len>   # scope still to be probed
st cap capdtm varlist
st cap iqr                  # 183 IQ nodes (★ read-only, ISP constant tables)
st cap lockinfo             # read ISP internal capture state
st cap sh                   # ★ auto-shutter (used as the judgement channel)
```

> **★ Systematic NX500 trait**: an index printed by any "list command" **cannot** be assumed
> valid for the read/write commands. You must do "read list → verify with read command →
> verify with write command". This exact trap was hit three times in one day
> (`setusr` / `getvar` / `varlist`).

### E4.4 `adj_*` segments = read-only constants (5 write experiments)

| Segment | Size | Non-zero rate | Verdict |
|---|---|---|---|
| 6 `adj_iq` | 3.5 KB | 1.6% | empty |
| 7 `adj_vfpn` | 24 KB | 90.6% | full (fixed-pattern noise correction) |
| 8 `adj_cs` | 64 KB | 49.5% | colour space |
| 9 `adj_dpc` | 5.2 MB | — | demosaic |
| 10 `adj_dpc2` | 1 MB | 10.5% | demosaic control table |

**Each segment has exactly one named entry (a whole blob), with no field-level annotation.
Writes read back fine but the ISP ignores them.**

`/opt/pref/default/` holds **clean factory copies** — more reliable than the
`fetch`-polluted files in `/opt/pref/`.

### E4.5 Physical → virtual address mapping (two consistent samples)

```c
virt_of_phys(p) = p - 0xB7FC000
```

| Physical | Virtual | Source |
|---|---|---|
| `0x94000000` | `0x88804000` | CMA 288 MiB region |
| `0x85400000` | `0x79c04000` | ISP segment (lands in `/proc/252/maps` `71d74000-79d74000 rw-s /dev/mem`) |

**This is a uniform linear mapping, not a segmented table.**

### E4.6 Directly callable static singletons (`libcapture-fw-prod.so`)

These are **static functions with no `this` parameter**, so they are safe to call from a
standalone probe process. Useful when writing ARM probes (they avoid the always-crashing
`GetCameraIfHandle()` path):

| Singleton | `getInstance` static address | Purpose |
|---|---|---|
| **`CCapVirtualAddrIf`** | **`0x626e4`** | ★ address-mapping layer (`GetVirtTopAddr`) |
| `CCaptureController` | `0x3d1d4` | capture control |
| `CTraceLog` | `0x3e178` | trace logging |
| `CCapturePublisher` | `0x80f14` | capture publishing |
| `CMCBAdapter` | `0x871f0` | MCB adapter |

Calling `SingletonI<CCapVirtualAddrIf>::getInstance()` returned:

```
instance = 0x0006f230
vtable   = base + 0xb0010   (_ZTV17CCapVirtualAddrIf ✓)
+0x04 = 0x94000000   ← matches dmesg "cma: reserved 288 MiB at 94000000"
+0x08 = 0xbfffffff   ← 4GB-1, address space limit
+0x0c = VirtTopAddr  ← GetVirtTopAddr() actually returns 0x887f8000
```

> **★ Why this matters**: `CCapVirtualAddrIf`'s `+0x04` independently returns the CMA
> physical base `0x94000000` — **identical to what `d5_sma`'s
> `SMA_GET_REGION_START_ADDR` reports**. That is a **cross-verification** that the
> userspace vendor library and the kernel SMA driver point at the same shared memory.

---

## E5. Hardware constraints

| Constraint | Measured | Impact |
|---|---|---|
| **`/dev/mem` + `mmap(PROT_READ)`** | ✅ **succeeds** | ★ hardware registers are directly readable (refutes the earlier `STRICT_DEVMEM` conclusion) |
| `/dev/mem` + `pread` | ✗ `-1` | but the `mmap` path works |
| `/proc/<pid>/mem` on device mappings | ✗ `-1` | kernel forbids cross-process reads of device mappings |
| **`poker` write to `.text`** | ✗ `Buffers not the same: ERROR` | code is not writable ⇒ **call-site hijacking is impossible** |
| **`poker` write to `.data`** | ✅ succeeds | data segment is freely writable |
| **CPU NX bit** | **absent** (`Features` has no `nx`) | ARMv7; code placed in `.data` **may be executable** |
| Root filesystem | `/dev/root` ext4 **`ro`** | cannot replace `.so` |
| `/opt/usr` | `rw`, 2.1 GB free | the only large persistent region for a mod |
| **CPU** | ARMv7 rev1 (v7l) Exynos, **with NEON** | |
| **Memory** | `mem=512M`, CMA statically reserves 288+72 MiB | **only ~142 MB actually available** |
| Kernel modules | `/proc/modules` lists just 6 (WiFi/Bluetooth/exfat) | **camera/ISP/MIPI are all built in; nothing can be loaded** |
| Kernel perf interfaces | `/proc/softirqs`, `/proc/PID/io` unavailable | the standard Linux perf toolchain is dead |
| `LD_LIBRARY_PATH` | `:/usr/lib:/usr/lib/driver` | empty first element = cwd, but cwd=`/` ⇒ unusable |

**Two hard requirements for `/dev/mem` mmap**:
1. the **offset must be page-aligned**, else `EINVAL` (round down, following ge0rg's `liveview.c`)
2. access via `base + (addr & (pagesize - 1))`

---

## E6. The freeze investigation: 10 hypotheses killed by experiment

> ⚠️ **The most valuable methodological asset here.** The conclusion is:
> **the root cause was never found.** But 10 directions were eliminated, and an entire
> *style* of reasoning was disproved.

### E6.1 Symptom (★ dissecting the qualifiers literally)

Entering playback: **only the delete key freezes**. Other keys respond, the shutter works,
the image is fine; the dial cannot turn the camera off — battery pull required.

**★ The crucial methodological move was to take each qualifier apart**:

| Qualifier | What it actually implies |
|---|---|
| "grey" | decode failure, not a crash |
| "the shutter works" | **the two paths are independent** |
| "restart doesn't help" | the state is **in a file**, not in memory |
| "needs a battery pull" | it is a **non-interruptible wait** |
| "only the delete key" | **only it** touches the thumbnail path |
| "only when entering playback" | the trigger is a **context**, not an action |

> My first three rounds hunted in the ISP layer — **because I read "only the delete key
> freezes" as "deleting a photo fails"**.

### E6.2 Ten refuted hypotheses

| # | My conclusion | What refuted it |
|---|---|---|
| 1 | slot 12 held dirty data | neutralising it **still froze** |
| 2 | `iqr` hi16 is the live PW value | wrote 0, **nothing moved** (it is an ISP constant table) |
| 3 | zero-byte `.thumbcache` files | deleted all 31, **still froze** |
| 4 | an `ipcc_ioctl` deadlock chain | **it also stalls when healthy after a restart** ⇒ it's normal |
| 5 | changing the recipe triggers it | `PW_TYPE=STANDARD` (recipe not applied) **also froze** |
| 6 | photo accumulation / memory leak | `MemFree` steady at 27 MB |
| 7 | `FaceLinuxThread` spinning | after fixing the jiffies divisor and stat field offset, **increment is 0** |
| 8 | `CAttributeHandler` bus is usable | heap scan **zero hits** ⇒ dead code |
| 9 | an `iqr` hang is a leading indicator | the watchdog reported `IQR=ok` throughout ⇒ **the signal never fired** |
| 10 | `400x82` is the playback size | after clearing, **it generates none of them**; the camera only writes 320x75 / 1024x85 |

**The common pattern (all 10 identical)**: mistaking "**things that co-occurred**" for cause.

### E6.3 ★ The entire thumbnail direction is refuted

| Experiment | Result |
|---|---|
| One month of the 0906 prewarm configuration | never froze (**data was consistent yet it didn't freeze**) |
| Factory reset, zero thumbnails | also didn't freeze |
| Factory reset | ✅ symptom disappeared |

⇒ **Both the "missing" and the "inconsistent / polluted" hypotheses are wrong.**

**Strongest candidate (derivable statically, not confirmed on hardware)**:
the `flab_guard.sh` watchdog **mis-firing** and sending `kill -QUIT di-camera-app`.
It spawns an `st cap iqr` probe every 13 s, loading a single core
(while healthy `iqr` itself already stalls for 0-1 s); the measured **false-alarm rate is
5:1**, and a false alarm kills the app — and **"app was killed" and "froze entering
playback" are indistinguishable to the user.**
⇒ The guard was a **net liability** and has been deleted.

**Earlier indicators than pressing delete**: ① the monitor script stops writing its log
② the dial cannot power the camera off.

---

## E7. Methodology rules

> The most valuable chapter. Technology goes stale; reasoning errors recur.

### E7.1 The two conditions for establishing causation

**Both must hold simultaneously**:

1. whenever A happens, B happens
2. **when A is eliminated, B disappears**

Co-occurrence or timeline alignment alone is **not** sufficient.

> On 2026-10-04 this produced four wrong root causes in a single day
> (slot12 / iqr / zero-byte thumbnails / ipcc deadlock chain), all overturned by
> later experiments.

### E7.2 ★ "Where is the crash?" must be resolved to the source line

**Guessing from the function name in the crash stack does not work.**

On 2026-10-05 four consecutive `SIGILL`s occurred, and the stack **always pointed
"near the ioctl"**. Wrong suspects tried in turn: `printf` varargs, stdio buffering, stack
overflow, the ioctl dispatch path, the difference between `/dev/null` and `/dev/d5_sma`,
and even an inlined `svc 0` syscall — **all wrong directions**.

**What actually worked**: convert the callstack offset (`main + 0x84`) **back to a source
line**, which showed it was inside **the code that prints the ioctl encoding** ⇒
**it never entered the kernel at all.**

> **Criterion**: if an "external cause" hypothesis (kernel / firmware / hardware) logically
> **must explain every observation**, yet one observation contradicts it (here: *"even the
> `/dev/null` ioctl crashes"*), **the hypothesis is wrong and the bug is in your own code.**

### E7.3 The remaining rules

| # | Rule |
|---|---|
| 3 | **A static snapshot can only describe state, not explain mechanism.** On an anomalous value, first ask "is it the same when healthy?" — `ipcc_ioctl` stalls when healthy too, which is exactly how that hypothesis died |
| 4 | **Dissect the qualifiers in any symptom description**; do not interpret the user's words in the direction you already assumed (see §E6.1) |
| 5 | **Look for the structural event that occurs EVERY time**, not the one that happened after some operation |
| 6 | **"Interface A exposes no parameter" ≠ "the system is not writable".** Three storage layers: capdtm runtime userdata / prefman persistent preferences / ISP firmware constants. Draw boundaries by layer, not by app |
| 7 | **"Library is in maps" ≠ "it is called".** Before deep investigation, search the target process's memory for that library's key addresses |
| 8 | **Read-only pre-check per slot before writing, plus dump-and-compare afterwards, plus `load_file` rollback** — guards against half-written state |
| 9 | **Any "did it take effect?" judgement must use an objectively verifiable channel**, not "let the user have a look" |
| 10 | **Static disassembly**: PC-relative constants must be looked up in both `.rel.dyn` and `.rel.plt`; ARM instructions must be decoded by bitfield rules; a `varlist` index ≠ a `getvar` index |
| 11 | **Physical→virtual is a uniform linear mapping**, `virt = phys - 0xB7FC000` (two consistent samples) |
| 12 | **Before brute-forcing a system, read the community's main repository on the same topic end to end** (README + full file listing + full-text traversal) |
| 13 | **"What the install script installs" ≠ "what exists in the repo".** Before writing prerequisite-check text, go back to the `cp` statements in `install.sh` and verify |

### E7.4 ★ Cross-compilation rules (zig 0.13 → `arm-linux-gnueabi.2.15` softfp)

| # | Rule |
|---|---|
| 1 | **`-O0` is mandatory.** `-O1`+ segfaults in practice |
| 2 | **★ A hand-written `IOC` macro overflows a signed 32-bit int.** In `#define IOC(d,t,nr,sz) (((d)<<30)\|...)`, `(2)<<30` = `0x80000000` ⇒ zig's ARM backend at `-O0` emits an **illegal instruction ⇒ `SIGILL(signal=4)`**.<br>**The symptom is deeply misleading**: the crash always looks like it is "near the first ioctl", but it never entered the kernel (even a `/dev/null` ioctl "crashes").<br>**Fix**: precompute every ioctl number in Python as a **literal constant table** (`0x80506864UL`) and only do table lookups at runtime |
| 3 | **`-static` is a no-op for zig** (ignored by `cc`) — don't waste time verifying it |
| 4 | **"Missing locally" ≠ "missing on the camera".** Writing ABI declarations from memory of EFL/POSIX versions is guaranteed wrong. The correct evidence source is the **`.dynsym` UNDEF symbols of ARM binaries that actually run on the camera** |
| 5 | **Link-time stub libraries are safe only if the soname matches exactly.** But a symbol absent from the library entirely **must never go through a stub** — extern + stub ⇒ resolved statically ⇒ the real device calls an empty function ⇒ **"the window opens but no key does anything, with no error"**. Resolve such symbols with `dlsym(RTLD_DEFAULT, ...)` and **exit non-zero explicitly on failure** |
| 6 | **Hand-rolled decimal/hex printing must be verified in both directions.** `pdec()` once printed `395` (exactly `FMT_BUFFER_SIZE`) as `593`, nearly becoming false evidence. `b[m++]=u%10` is low-digit-first ⇒ print in reverse |
| 7 | **`ecore_event_handler_add` must come from `dlsym(RTLD_DEFAULT, ...)`.** Linked via a stub it vanishes from the import table ⇒ the jog dial dies |

### E7.5 Remote-operation rules (single-core camera)

| # | Rule |
|---|---|
| 1 | **telnet must be serial** (concurrency hangs a single core). **Anything ≥10 KB goes over FTP** |
| 2 | **CRLF is the number one trap.** Matching md5 but a syntax error ⇒ line endings. `od -c` is the only reliable check |
| 3 | **Never run heavy work back-to-back on a single-core camera.** First validation: 1 photo, 1 size; small batches ≤3; full runs must be backgrounded with `nice -n 19`. Symptom: telnet + FTP both hang afterwards = the camera is pinned and needs a battery pull |
| 4 | **`cat /proc/iomem` is forbidden** (triggers a kernel segfault and kills the shell); **`find /sys/...` is forbidden** (3 minutes without returning on one core, and SIGHUP takes the whole script with it) |
| 5 | **busybox**: no `pidof` (read `/proc/[0-9]*/comm`), no `$!`, `nohup` not recognised ⇒ use `prog &`; no `base64`; `nice` cannot adjust a shell function; **`killall -q busybox` is suicide** (`telnetd`/`ftpd`/`httpd` are all symlinks to it) |
| 6 | **telnet eats the quotes in your command** — build multi-argument invocations inside the script |
| 7 | **Identical `case` branch names**: grep the old branch before inserting a new one, or the symptom is "the argument is being ignored" |

---

## E8. Tooling

### E8.1 Architecture capture and probes (`test_server/sysarch/`)

| Tool | Purpose |
|---|---|
| `minitel.py` | hand-rolled telnet (Python 3.13 has no `telnetlib`): socket + IAC stripping + refuse all negotiation |
| `probe_arch.py` … `probe4.py` | batched read-only collection scripts |
| **`run_arm.py`** | ★ **generic ARM program deliverer**: FTP upload → run over telnet → FTP retrieve |
| `run_ipt.py` | IPCC cell-by-cell probe driver (one process + one telnet session per cell) |
| `probe_src/epinfo3.c` | ★ EP/SMA/IPCC read-only probe (all ioctl numbers precomputed as literals) |
| `probe_src/epreg.c` | ★ EP register readability proof (the page-aligned mmap technique) |
| `probe_src/epdump.c` | register window dump (each line flushed immediately, so a crash still shows prior output) |
| `probe_src/t0.c` … `t9.c` | ★ the 10 minimal test programs used to bisect the SIGILL (a complete archive) |
| `raw/`(23) `raw2/`(14) `raw3/`(33) `raw4/`(28) `raw5/`(90) `raw6/`(9) | raw capture data (197 files) |

### E8.2 PC-side static analysis (`test_server/pwfilter/`)

| Tool | Purpose |
|---|---|
| **`symref.py <maps> <eip...>`** | ★ core: eip → which so + offset within the library + **symbol name** |
| **`pltscan.py <elf> [kw]`** | PLT/GOT mapping + locating call sites (★used to determine dead code) |
| `elfmap.py` / `libscan.py` / `cxx.py` | ELF32 segment layout / symbol filtering / C++ class structure |
| **`arm2.py` / `armdis.py`** | ★ ARM32 disassembly, decoded by bitfield rules (correct) |
| `enumscan.py` / `rodump.py` / `pltfind.py` | `E_*` enums / `.rodata` strings / PLT import filtering |
| `dynsym.py` / `check_abi.py` | ★ symbol-table parsing and ABI cross-checking (reusable, generic ELF32) |
| `shotstat.py` | ★ JPG pixel-statistics judgement tool (dual source: `local` / camera IP, offline-regression capable) |

### E8.3 On-camera probes (`test_server/pwfilter/b1/src/`)

| Probe | Purpose |
|---|---|
| **`heapscan`** | reads `/proc/pid/mem` directly, bulk memory scanning (3.4 MB/s) — ★the core tool for determining dead code |
| **`ispprobe`** | `dlopen` + `dlsym` to resolve runtime addresses, plus getting `SingletonI::getInstance()` to work |
| `lut3d_probe` | 3D LUT / NOG control-chain probe (38 symbols + 9 register groups) |
| `memread` / `regscan` | device memory reads |

### E8.4 Transfer

| Script | Note |
|---|---|
| `ftp_put.py` / `ftp_get.py` | ★ remote paths **must carry the `/mnt/mmc/...` prefix** (the FTP root is the SD card) |
| `telnet_run.py <ip> <cmd>` | ★ **must be serial**; login required (`read` → send `root` → send an empty line) |

---

## E9. Capability boundaries

### E9.1 Could a Magic Lantern-class firmware be built?

| ML core capability | Reachable on NX500? | Why |
|---|---|---|
| init task replacement / hijack | ❌ | requires running in the **same address space on the same core** as the vendor firmware |
| task dispatch hijack | ❌ | same |
| arbitrary code injection into the camera process | ⚠️ partial | `poker` can write `.data`, and there is no NX bit — but `.text` is immutable and 3D LUT has no GOT slot |
| reading ISP registers | ✅ | **implemented in this project** (§E1) |
| writing ISP registers | ⚠️ theoretically possible | non-interruptible + actively driven by ISP ⇒ battery pull only |
| camera control (exposure / white balance) | ✅ | `prefman` + `setusr` fully understood |

**Conclusion**: the NX-KS route tops out at the *"call vendor APIs"* layer.
But the *"observe hardware directly"* layer has just been opened, and almost nobody in
the community is working on it — that is the most valuable direction ahead.

### E9.2 Dual native ISO

❌ **Not reachable in hardware.** The sensor is driven directly by the independent ISP
firmware; Linux has **no V4L2** and cannot obtain two raw streams with different gains.
✅ **Viable substitute**: PC-side zone-based denoising and shadow reconstruction.

### E9.3 Paths already eliminated (so the community need not repeat them)

| Path | The wall it hit |
|---|---|
| Direct 3D LUT register write (10-04 conclusion) | ⚠️ **partly refuted 10-05**: read-only `mmap` does work |
| Hijacking a GOT slot for 3D LUT | `di-camera-app` has **zero 3D LUT imports** ⇒ no slot exists |
| Hijacking `CAttributeHandler` | **dead code** (zero heap-scan hits) |
| `poker` patching `.text` | kernel read-only memory protection |
| `capdtm setvar` writing PW directly | `varlist` and `getvar/setvar` are **two different numberings** |
| `iqr` writes | an ISP firmware **constant table** |
| `adj_*` segments (6-10) writes | ★ **read-only constants** (5 experiments) |
| Repairing `.thumbcache` to fix the freeze | ❌ the entire direction is refuted (§E6.3) |
| Writing IPCC ioctls from the NX1 GPL headers | ❌ ABI mismatch; `size=8` raises SIGILL |

### E9.4 Three pending read-only experiments

| # | Experiment | What it would prove |
|---|---|---|
| 1 | Dump the 3D LUT window before and after a capture | **the 3D LUT really participates in imaging** |
| 2 | Dump `0x20821c00` (NOG) at several ISOs | the hardware grain generator exists |
| 3 | **Dump every EP block while switching prefman recipes** | **which registers the ISP side actually consumes the recipe through** |

> Experiment 3 is the highest value: it shrinks the black box between "recipe written to
> prefman" and "the ISP actually applied it" down to a handful of concrete addresses, and
> **directly determines whether the FilmLab engine can move from the PC into the body.**

---

## E10. Acknowledgements

Thanks to the NX-KS community for `poker` (process memory read/write),
`nx-remote-controller-daemon`, the `mod_gui` framework and `capdtm`; to ge0rg for
`liveview.c` (the page-aligned `/dev/mem` mmap technique); and to voxivoid for
`recipe-lab-sony-pmca` (the granularity reference for a comparable scheme).
Without these, none of the system-level conclusions above would have been reachable.

---
---

## 附录 · Appendix

### A1. 采集参数 / Capture parameters

| 项 | 值 |
|---|---|
| 相机 IP | `192.168.0.x`（DHCP，地址会变；本机常用 `telnet_run.py <ip> '命令'`） |
| FTP | 端口 21，root 空密码，根目录 = SD 卡 |
| telnet | 端口 23，需登录（`root` + 空行） |
| 相机型号判据 | `/etc/version.info` = `NX500` + `1.12` / `NX1` + `1.41` |
| 关键进程 | `di-camera-app` pid=252 |
| 触发链 | SD 根 `info.tg` + `nx_cs.adj` → `dfmsd` 自动执行 `install.sh` |

### A2. 关键 ioctl 号（全部为预计算字面量）/ Key ioctl numbers (precomputed literals)

```c
/* ★ 全部用 Python 预计算成字面量，运行时只查表，不做任何移位
     —— 见 §7.4 铁律 2（zig ARM 后端有符号溢出 → SIGILL） */
0x80506864UL   EP   _IOR('h',100, struct ep_reg_info)   size=80
0x802c6864UL   EP   nr=100 size=44
0x80286864UL   EP   nr=100 size=40
0x80486864UL   EP   nr=100 size=72

0x80047301UL   SMA  GET_REGION_SIZE
0x80047304UL   SMA  GET_REGION_START_ADDR
0x80047308UL   SMA  GET_ALLOCATED_SIZE

0xc0047403UL   IPCC _IOWR('t',3,4)   ← 唯一安全编码
0xc0087402UL   IPCC _IOWR('t',2,8)   ← nr=2 安全
0xc0087403UL   IPCC _IOWR('t',3,8)   ← ★ SIGILL
```

### A3. 10 个子块一览 / Sub-block summary

`top` `ldc` `mc` `rsz` `lvr` `bblt` `fd` `jpeg` `3dlut` `nog` —— 全部 `non-zero: 10/10`，
`size` 编码 80 / 44 / 40 / 72 四种全部 `r=0` 安全。

### A4. 文档索引 / Document index

| 文档 | 内容 |
|---|---|
| **本文** | 10-04 + 10-05 综合成果（中英双语） |
| [`NX500_ARCHITECTURE.md`](NX500_ARCHITECTURE.md) | 完整系统架构（677 行，含 EP 寄存器 dump 全表） |
| [`LUT_OPEN_SOURCE_EVAL.md`](LUT_OPEN_SOURCE_EVAL.md) | 开源 LUT 资产可用性评估（CC0 实测 + 专利核查） |
| [`FILMLAB_ONEKEY_UI.md`](FILMLAB_ONEKEY_UI.md) | 一键 UI 需求裁决（三个需求，两个撞硬墙） |
| [`FILMLAB_WIFI_JOG.md`](FILMLAB_WIFI_JOG.md) | WiFi 键直达 + 波轮 UI 可行性 |
| [`FILMLAB_ONEKEY_VERIFY.md`](FILMLAB_ONEKEY_VERIFY.md) | `pw_force_reload()` 验证清单 |
| [`../SYNC.md`](../SYNC.md) | 安装 / 增量同步 / WiFi push / 回滚 |

### A5. 许可 / License

本仓库的脚本与文档遵循仓库原有许可。**请勿将本文档中的逆向结论用于商业固件的再分发。**
Scripts and documentation in this repository follow the original license.
**Please do not redistribute the reverse-engineering findings here for commercial firmware
distribution.**

FilmLab 配方与第三方 `.cube` LUT 遵循各自作者许可（已选用的
`scernst13/HaldCLUT-Cube-Files` 为 **CC0 1.0**）。
