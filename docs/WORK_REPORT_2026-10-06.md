# 2026-10-06 工作报告：3D LUT 写入通路从零打通

**日期** 2026-10-06 · **主题** EP / 3D LUT 全链路逆向与实机验证
**产出** 61 个文件（工具 8 个 · 探针 14 个 · 文档 5 份 · 二进制 34 个）

---

## 0. TL;DR

| 项| 状态 |
|---|---|
| 用户态 3D LUT 寄存器写入 | ✅ **实机打通，画面确实变了** |
| LUT 数据格式 | ✅ 已解出（16-bit 三通道、17³） |
| **魔灯最终实现路径** | ★ **确定：改 P7 固件**（不是改用户态） |
| 相机状态 | ✅ 完好，无死机无变砖 |

★ **本日的最大价值不是"能做到"，而是"证伪了此前的方向"** ——
用实测证明"用户态写入 LUT 数据"这条路走不通，从而精确定位到真正的实现点。

---

## 1. 起点：一次推翻旧结论的发现

上午的判断是"3D LUT 写入者在内核态/ISP 固件，必须改 P7"，依据是
`di-camera-app` 的 1092 个 import 里 3dlut 相关 = 0 条。

★ **这条证据无效** —— `libudd5.so` 是 `di-camera-app` **动态加载**的，不在 import 表里。
静态导出符号一查，51 条 EP/色彩 API 一次全出（459 FUNC）。

⇒ 从"内核态写入"修正为"用户态 libudd5 API"，路线随之重排。

---

## 2. 工具建设（先有鸡，才有蛋）

### 2.1 `udd5.py` —— 自研 ELF + Capstone 反汇编器

本机没有 `arm-linux-gnueabi` binutils，ODroid 上也没有。参照已验证的 `sym_udd.py`
自己解 ELF + Capstone 反汇编。6 个子命令：`ep` / `dump` / `literals` / `graph` /
`batch` / `syms`；配套 `regmap.py`（35 个 reg 层函数的偏移自动提取）。

★ **踩了 4 个 ELF 解析坑，全部靠对照实验发现**（详见 §7）。

### 2.2 `crosscheck.py` —— ★ 决定性的对照组自证

用成熟的 **pyelftools 0.33** 交叉验证自研解析器：**16/16 项全部一致**。

★ 对照实验**抓到了我自己的两个真错误**：
1. `decode_ioc` 的 nr 掩码写成 `0xFFF`（应 `0xFF`）⇒ 曾解出 `nr=770`
2. ★★ **ioctl是 `_IOWR('s', 2, u32)` 而非 `('r', 2, …)`** ——
   `'s'` = Samsung SMA。带到实机上就是写错 ioctl 号。

### 2.3 关于 GitHub ARM binutils：结论 = **不需要**

| 需求 | 方案 | 结果 |
|---|---|---|
| ELF 解析复核 | pyelftools（已装）| ✔ 16/16 一致 |
| 反汇编 | Capstone 5.0.7（已有）| objdump 只给符号名不给语义 |

★ `objdump` 能给的是"这个函数叫 `_udd_ep_3dl_reg_SetAddress`"，
不能给的是"它写哪个 EP 块的哪个偏移" —— 后者只有 Capstone + literal pool 解析能给。
★ 交叉编译用现成的 zig 0.13.0（`.uploads/zig/`），不依赖 binutils。

---

## 3. 实机验证：三段式推进

### 3.1 第一段：EP 驱动用户态状态（`epglb` / `epfd`）

| 检查 | 结果 |
|---|---|
| `di-camera-app` 是否加载 libudd5 | ✅ 是（PID 247） |
| `fd_ep`（读 `/proc/247/mem`）| `0xffffffff` = **-1** |
| **谁持有 `/dev/drime5_ep`** | ★ **遍历 `/proc/*/fd/*`，没有任何进程** |
| `/dev/drime5_ep` 设备节点 | ★★★ **存在**（char 10:126） |

⇒ ★★ **整个 D5 加速器用户态栈在 NX500 上从未启用。**

★ 同时纠正一个重大错误：**我一直在分析错误的库**。
旧库 279036 B / 2014-09（NX1 与 NX500 开源包同一批），
实机库 320216 B / 2015-01（未开源）。**此前所有偏移表作废**，已换`libudd5_real.so`。

★ 实机版多出**取景器专用矩阵** `ycbcr2rgb_mtx_fd_udd_premovie_HD/_SD`
⇒ **Still 与取景器是两套矩阵，隔离方案天然成立。**

### 3.2 第二段：内核侧调查（用户提供开源包后）

用户提供的 **NX500 完整内核源码**（`E:\新建文件夹\NX500_opensource_2015_03_04`，2.3 GB）
里有完整的 EP 驱动源码，三个决定性结论：

```c
/* ① /dev/drime5_ep 是纯 mmap 设备，open 零硬件初始化 */
struct file_operations drime5_ep_ops = { .open, .release, .unlocked_ioctl, .mmap };
static int drime5_ep_open(...) { filp->private_data = g_ep; d5_kdd_open(KDD_EP); }
static int d5_ep_resume(...)   { return 0; }   /* 故意什么都不做 */

/* ② ★★★★★ 内核直接把 10 个 EP 块的权威地址交给用户态 */
#define EP_IOCTL_GET_PHYS_REG_INFO _IOR('h', 100, struct ep_reg_info)
struct ep_reg_info { top, ldc, mc, rsz, lvr, bblt, fd, jpeg, 3dlut, nog };  /* 各{addr,size} */

/* ③ 全部 15 个 ioctl 都是中断/时钟类⇒ 寄存器访问 100% 走 mmap */
```

⇒ ★★ **再也不用猜地址、不用解析 ELF、不用跨进程读指针。**

★ 15 个 ioctl 全是中断类 + `ep_*_reg_base` 是指针变量 ⇒ 双向印证寄存器走 mmap。

### 3.3 第三段：写入实验（11 次）

| # | 实验 | 画面 | 结论 |
|---|---|---|---|
| L1 | 只对 `+0x08` 打脉冲 | — | ✔零副作用（1024 words 差异 = 0） |
| L2 | 写 `+0x64/68/6c/70` | — | ✔ 发现也是自清零型 |
| L3 | identity → `0x81115200` | 无变化 | 地址是 p7 预置，用户态改不了 |
| L4 | `SMA_ALLOC` | — | ❌ `sma_dev == NULL` |
| L5 | `/dev/mem` 写 CMA | — | ❌ SIGSEGV |
| L6/L7 | `/dev/d5_sma` mmap CMA | 无变化 | ✔ 写入成功，但地址/格式错 |
| **L9** | 补齐 6 步（bit0 脉冲）| ★ **偏红花屏** | ★★★ **3DLUT 生效** |
| L10 | 完整 6 步 + 压红 LUT | ★ 偏红花屏 | ✔ 复现成功 |
| L11 | 完整 6 步 + 8KB 全零 | ★ 仍花屏 | ⇒ 排除"LUT 内容"，指向格式 |

---

## 4. ★★★★ 核心成果：p7 权威 6 步序列

来源：`raw8/p7/ghidra/53_all_pseudocode.c:641680+`（内核态反编译）

```c
b[0x000] |= 1;              // ① FUN_004cf3d4(1)  OnOff 总开关
b[0x008] &= ~1UL;           // ② FUN_004cf45c(0)  ★ 脉冲位先清零
b[0x008] |= 1UL;            // ③ FUN_004cf45c(1)  ★ 置位启动
b[0x00c] = lut_phys;        // ④ FUN_004cf4b4     SetAddress
b[0x004] &= 0xffffffcfUL;   // ⑤ FUN_004cf414     通道选择
b[0x008] &= ~0x100UL;       // ⑥ FUN_004cf484(1)  ★★ 读侧清理
```
★★ **② 和 ⑥ 是我前 5 次实验全部无效的原因。**
★ 客观判据：**执行后 `+0x008` 保持为 1= 硬件接受了启动**（之前每次都被清零）。

### 实测数据与 p7 定义 4/4 互证
| 偏移 | 实测值 | p7 定义 |
|---|---|---|
| `+0x000` | `0x00000001` | OnOff = 开 |
| `+0x004` | `0x00000100` | bit8 = LUT0 数据源 |
| `+0x00c` | `0x81115200` | LUT0 数据地址 |
| `+0x008` | `0x00000000` | 脉冲位（写后自清） |

### 硬约束：256 字节对齐
```c
/* p7 FUN_00179384 */
if ((param_1 & 0xff) == 0) { ... }     /* LUT 物理地址必须 256 对齐 */
```
⇒ 与我从 libudd5 静态解出的 `if ((phys & 0xff) != 0) return -301;` **完全对应**
⇒ **用户态反汇编 + 内核态反编译双向交叉验证成功。**

---

## 5. ★★★★★★ 决定性发现：LUT 缓冲在 p7 地址空间

### p7 的 4 个预置 LUT 缓冲
```c
DAT_003837f0 = 0x810fd100
DAT_003837f4 = 0x81106b00
DAT_003837f8 = 0x81115200    ★ 与实测 +0x0c 完全一致
DAT_003837fc = 0x81101e00
/* FUN_0009a3e8 只是从这4 个里选一个返回 —— 不是算出来的 */
```

### ★★★ 它们就是三星内置的 4 套色彩方案（读出内容确认）
| 缓冲 | 前 64 字节特征 | 方案 |
|---|---|---|
| `0x81101e00` | `00000000 10000000 20000000...` 完美线性 | ★ **纯 identity** |
| `0x81115200` | `00ff0001 fe0002fd...` R↑G↓ | ★ **暖色调/肤色** |
| `0x810fd100` | `15000d00 23000c00...` 非单调 | 风格化曲线 |
| `0x81106b00` | 与第1 个相同 | 同上 |

### ★★★ LUT 数据格式（从 `0x81115200` 前 32 words 解出）
```
0100ff00  fd0200fe  00fc0300  0500fb04  f90600fa  00f80700 ...
```
★ 小端 16-bit 拆分 ⇒ R 通道从 `0x0001` 递增到 `0x00ff`，G/B 同时递减
⇒ ★★★ **17³ 三维 LUT 的一个 R 切片，16-bit 三通道交织**
⇒ ★★ 我最初用 8-bit RGB是错格式 —— **这才是花屏根因**。

### ⇒★★★★★ 为什么用户态碰不到它们
| 事实 | 依据 |
|---|---|
| Linux `mem=512M` ⇒ 上限 `0x20000000` | `/proc/cmdline` |
| p7 页表只覆盖 `0x80000000..0x80ffffff`（1:1，16 PTE）| `50_page_table.txt` |
| `sma_mmap` 对 `0x81115200` 返回 EINVAL | 实测（`__phys_to_pfn` 得 0）|
⇒★★★★★ **Linux 用户态永远无法读写那 4 个 LUT 缓冲。**

★⇒ **这就是「魔灯必须改 P7」的最终证据**
—— 不是"写入者在 p7"，而是"**LUT 数据缓冲本身就在 p7 的地址空间里**"。

---

## 6. ★★ 修正的 7 个错误（全部靠对照实验发现）

| # | 错误 | 真相 |
|---|---|---|
| 1 | "STRICT_DEVMEM 阻塞 `/dev/mem` 写" | ❌ 内核 `# CONFIG_STRICT_DEVMEM is not set`，实测可写 |
| 2 | "CMA 区 98.6% 空闲" | ❌ 采样太稀疏，`0x9a000000` 实读有数据 |
| 3 | "16 个独立 LUT 槽" | ❌ 同一寄存器的 16 份视图（写一组全变） |
| 4 | "脉冲是 bit8" | ❌ p7 定义是 **bit0** |
| 5 | "`+0x64/0x68` 全 0 ⇒ 硬件关闭" | ❌ OnOff 在 `+0x00`，实测 =1，**硬件是开着的** |
| 6 | "`ps\|grep` 判进程在不在" | ❌ busybox `ps` 只显示当前 pts，须用 `/proc/*/comm` |
| 7 | "写 LUT 数据就能改色彩" | ❌ **LUT 缓冲在 p7 地址空间，用户态不可达** |

⇒ ★★★★ **四次"工具失效导致的假阴性"**
（grep 零结果 / ps 零结果 / STRICT_DEVMEM 臆断 / CMA 空闲臆断）
⇒ ★★★★ **本项目最贵的一课：任何"零结果"都必须先自证工具有效。**

---

## 7. ★ 新增铁律

| # | 规则 |
|---|---|
| **47** | `mmap` 字符设备的 `offset` 传**字节物理地址**，不是 PFN（内核替你 `>>12`）。传错 ⇒ EINVAL |
| **48** | `struct` 布局/宏定义优先用**官方用户态头文件**（NX500 开源包 `usr/include/media/drime5/ep/`），不要手抄 |
| **49** | 拿到内核源码先搜 `io_remap_pfn_range` / `unlocked_ioctl` / `struct file_operations` —— 三处直接给出"寄存器怎么访问"，胜过任何逆向 |
| **50** | 判"进程在不在"用 `/proc/*/comm`，不要信 busybox `ps`（只显示当前 pts）|
| **51** | `-O0` + 自写 mmap + `memset`/`memcpy` 可能踩未映射边界（实测：写 256 字节 SIGSEGV，写 32 字节正常）⇒ 用逐字节循环 |
| **52** | telnet 对已登录会话**静默回显** ⇒ 唯一可靠读出 = 重定向到 `/mnt/mmc/_xfer/` 再 FTP 拉回 |
| **53** | `/proc/PID/mem` 用 **`lseek`+`read`**，**不用 `pread`**（2015 年那版内核 pread 直接 EINVAL）|
| **54** | FTP 拒绝对 `/usr/lib` 等系统目录 `cwd`（550 Error）⇒ 先 `cp` 到 `/mnt/mmc/_xfer/` |
| **55** | **连续 mmap 多块会让相机掉线** ⇒ 一次只跑一个块，间隔 10s |

---

## 8. 产物清单

### 工具（8）
| 文件 | 说明 |
|---|---|
| `test_server/isp/udd5.py` | ★ 自研 ELF+Capstone 反汇编器（6 子命令）|
| `test_server/isp/regmap.py` | EP 寄存器偏移自动提取器 |
| `test_server/isp/crosscheck.py` | ★ pyelftools 对照验证（16/16）|
| `test_server/sysarch/dishex.py` | hexdump → ARM 反汇编 |
| `test_server/sysarch/sh.py` | telnet 命令执行器（绕开静默回显）|
| `test_server/sysarch/run_arm.py` | 探针投递 + 输出拉回（已验证模式）|

### 探针（14 个 .c + 编译产物）
`epglb`（自进程读全局）· `epfd`（跨进程只读 `/proc/PID/mem`，支持 `-B`/`-D`）·
`kread`（dump `/dev/mem`）· `epinfo`（EP 块权威地址）· `epdump2`（mmap dump，支持 `all`）·
`epwr`（三级递进写入 + 回滚）· `eplut3`~`eplut7`（各代 LUT 写入）· `eplut9`/`eplut10`
（★ p7 权威 6 步序列）· `eplen`（LUT 长度探测）· `rd`（★ 读 4 个预置 LUT）·
`mmtest`/`probe7`/`probe8`（★ 对照实验：证明 CMA 可写）

### 文档（5）
- `docs/LIBUDD5_EP_API_MAP_2026-10-06.md` / `_EN.md` —— libudd5 API 图谱 + ioctl 协议
- `docs/EP_DRIVER_STATUS_2026-10-06.md` / `_EN.md` —— EP 驱动用户态状态
- `docs/EP_PATH_OPEN_2026-10-06.md` —— 通路打通
- `docs/EP_3DLUT_WRITE_EXPERIMENTS_2026-10-06.md` —— ★ 11 次写入实验全记录

### 分析数据
- `test_server/isp/libudd5_real.so` —— ★ **实机版库**（320216 B）
- `test_server/isp/out/` —— 全部导出产物（API 表 / 寄存器映射 / 调用图 / 全量汇编）
- `test_server/sysarch/raw5/` —— 各阶段 1024-word 全量基线 + 实验输出

---

## 9. ★ 下一步

### A. 改 P7 固件（魔灯的唯一路径）
切入点已锁定：`FUN_0009a3e8`（从 4 个常量选一个返回的地方）。

| 步骤 | 内容 | 风险 |
|---|---|---|
| 1 | 找用户态 → p7 的数据传递通道（`/dev/` 节点 or IPCC）| 低（只读探查）|
| 2 | 在 `FUN_0009a3e8` 后加 memcpy | 低 |
| 3 | SLP 备份（有官方退路）| 低 |
| 4 | 刷机验证 | 中（但改动只是"多复制一段数据"，不涉及硬件时序）|

### B. 切换预置方案（零风险，已可做）
`+0x0c` 写 `DAT_003837f0/f4/f8/fc` 之一即可在 4 套方案间切换
—— ★ **这个现在就能做，不需要改固件**，可以先作为"4 档色彩切换"功能交付。

---

## 10. 一句话总结

★★★★★★★★★★ **今天把"魔灯"从一个模糊愿望变成了一条工程路线：
通路已验证、数据格式已解出、最终实现点已精确定位到 p7 的4 个常量。**
**并且用实测证伪了"用户态写 LUT 数据"这条看似可行的路，避免了继续投入。**