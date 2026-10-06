# 实机验证报告：EP 驱动在用户态完全未启用

**日期** 2026-10-06 · **执行** 步骤 1（只读，零风险）
**工具** `epglb.arm`（自进程）、`epfd.arm`（跨进程，只读 `/proc/PID/mem`）
**安全边界** 全程未调用任何 libudd5 函数、未写任何寄存器、未 attach/ptrace

---

## 结论一句话

★★★ **`di-camera-app` 虽然 `dlopen` 了 libudd5，但从不调用 `d5_ep_open()`。
EP 驱动的用户态通路完全未启用** —— 这不是"没找到"，是**确认不存在**。

---

## 证据链

| 检查项 | 方法 | 结果 |
|---|---|---|
| `di-camera-app` 是否加载 libudd5 | `/proc/247/maps` | ✅ **是**，3 段映射 |
| `fd_ep` 值| `lseek+read /proc/247/mem` | `0xffffffff` = **-1** |
| `ep_3dlut_reg_base` | 同上 | **0，映射未建立** |
| `ep_nog_reg_base` | 同上 | **0** |
| `path_ep_cs0` | 同上 | **0** |
| **谁持有 `/dev/drime5_ep`** |遍历 `/proc/*/fd/*` | ★★ **没有任何进程** |
| `di-camera-app` 实际持有 | `ls -la /proc/247/fd` | 只有 `drime5-thermister`（fd 28）|
| **`/dev/drime5_ep` 设备节点** | `ls -la /dev/drime5*` | ★★★ **存在**（char 10:126）|

---

## ★ 工具自证（避免"grep 零结果"陷阱）

同一批读取中，**其它符号都读出了合理值**，证明地址换算正确、不是随机噪声：

| 符号 | 值 | 判定 |
|---|---|---|
| `ep_mc_default_config` | `7` | ★ **与我在自己进程 dlopen 读到的完全一致** |
| `g_d5_dev_ctx` | `0x15` (21) | 设备上下文索引 |
| `ycbcr2rgb_mtx_fd_udd` | `0x200` | 有效配置 |
| `ycbcr2rgb_mtx_fd_udd_premovie_HD` | `0x254` | 与 `_SD` 同值 |
| `g_dd_mutex_lock` 邻域 `0x55570` | `0x64` (100) | — |

⇒ **`fd_ep = -1` 是真实读数，不是地址算错的假象。**

---

## ★★★★ 两条重要的方法论修正

### 1. `st_value` → 运行时地址公式

```
runtime_addr = seg_map_base + (st_value - seg_va_page)
```

⚠️ **`seg_va_page` 必须取 PT_LOAD 的页对齐 `p_vaddr`，不能用 `/proc/pid/maps` 里的
`file_offset`。** maps 的 file_offset 已页对齐，与 `sh_offset` 差 `0x8000`/`0x97d8`。
我在这一点上错了两次（第一次算出 `0x4b0e8 < 0x4c000` 被自己的探针拒绝，
第二次算出落在 `---p` 段）。

实机 `libudd5`：`PT_LOAD[2] off_page=0x4c000 va_page=0x54000`
⇒ `fd_ep st_value=0x5556c` → `runtime = 0xb0e75000 + 0x156c = 0xb0e7656c` ✓

### 2. ★★★★★ 我一直分析的是**错误的库**

| | 我分析的 | **实机的** |
|---|---|---|
| 大小 | 279036 B | ★ **320216 B** |
| md5 | `abcbaaf7…` | ★ **`40c7b087…`** |
| FUNC 符号 | 453 | **459** |
| `.data` sh_addr | `0x4a828` | **`0x548e0`** |

旧库来自 **NX1 GPL 包**，实机那份是 **NX500 1.12 自带**的。
⇒ ★★★ **此前所有 st_value / 寄存器偏移表全部作废**，今后必须用 `libudd5_real.so`。

★ 实机版**多出取景器专用矩阵**：
```
ycbcr2rgb_mtx_fd_udd_premovie_HD
ycbcr2rgb_mtx_fd_udd_premovie_SD
```
（另有非 premovie 版）⇒ ★★ **Still 与 Premovie 是两套独立矩阵，取景器隔离方案天然成立。**

---

## ★ 关于 ARM binutils：不需要

用**成熟工具做对照组自证**已经解决了需求：

| 需求 | 方案 | 结果 |
|---|---|---|
| ELF 解析复核 | **pyelftools 0.33** | ✓ `crosscheck.py` **16/16 全一致** |
| 反汇编 | Capstone 5.0.7（已有） | objdump 只给符号名不给语义 |

★ 对照实验**抓到我两个真错误**：
1. `decode_ioc` 的 nr 掩码写成 `0xFFF`（应 `0xFF`）⇒ 曾解出 `nr=770`
2. ★★ **ioctl 是 `_IOWR('s', 2, u32)`，不是 `('r', 2, …)`** —— `'s'` = Samsung SMA。
   这个错带到实机上就是写错 ioctl 号。

`zig 0.13.0` 已在 `.uploads/zig/`，交叉编译不依赖 binutils。

---

## 修正此前的判断

| 此前结论 | 修正 |
|---|---|
| "3DLUT 写入者是 `libudd5` 用户态" | ⚠️ **半对**：API 确实在用户态，但**没人在调用** |
| "EP 基址 10/10 双向闭环" | ⚠️ 结论方向对（地址是对的），但**基于错误的库**，需用 real 版重做 |
| "只需 `d5_ep_open()` 即可" | ⚠️ 现在才知道：**EP 驱动用户态从未被启用过** |

---

## ★★★ 路线重新决策

`/dev/drime5_ep` **节点存在**（char 10:126）⇒ 驱动编译进了内核，只是没人 open它。

| 路线 | 做法 | 风险评估 |
|---|---|---|
| **A. 自己 open** | `open("/dev/drime5_ep")` + `d5_ep_open()`，在自己进程里建映射 | ★ 中。节点在，但相机为何不开？可能与 ISP 固件抢硬件 |
| **B. `/dev/mem` 直写** | `epfull.arm` 已验证读侧可行，写侧未试 | ★ **最低**。不碰驱动，只碰内存 |

★★ **建议先做一件事**：查 `/dev/drime5_ep` 的 `open` 在内核里会做什么
（`grep drime5_ep /proc/kallsyms` 找处理函数，看它是否 `request_irq` / `ioremap` 整块 EP）。
若它会重初始化硬件 ⇒ **绝不能走路线 A**（会和正在工作的 ISP 固件冲突）；
若它只是 `ioremap` 一块内存 ⇒ 路线 A 可行且更"干净"。

---

## 产物

| 文件 | 说明 |
|---|---|
| `epglb.c` / `.arm` | 自进程 dlopen + 读全局（14/14 API 符号存在）|
| `epfd.c` / `.arm` | 跨进程只读 `/proc/PID/mem`，支持 `-B` 批量 |
| `sh.py` | telnet 命令执行器（绕开静默回显）|
| `crosscheck.py` | pyelftools 对照验证（16/16）|
| `libudd5_real.so` | ★ **实机版本**（320216 B）|
| `raw5/epglb_v1.txt` | 步骤 1 原始输出 |
| `raw5/epfd_batch.txt` | 跨进程批量读取输出 |

---

## 铁律新增（实机操作层）

| # | 规则 |
|---|---|
| **43** | telnet 对已登录会话**静默回显** ⇒ 唯一可靠读出 = 重定向到 `/mnt/mmc/_xfer/` 再 FTP 拉回 |
| **44** | `/proc/PID/mem` 用 **`lseek`+`read`**，**不用 `pread`**（老内核 `pread` 直接 EINVAL）|
| **45** | FTP 拒绝对 `/usr/lib` 等系统目录 `cwd`（550 Error）⇒ 先 `cp` 到 `/mnt/mmc/_xfer/` |
| **46** | 登录用 `minitel.MiniTel`（已处理 IAC 协商），root 空密码 |