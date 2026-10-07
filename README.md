# NX-KS2

Samsung NX500 / NX1 (Tizen / DRIMe5) 增强固件 mod —— 基于社区  
[nx500\_nx1\_modding](https://github.com/SamsungNX500/nx500_nx1_modding) 上游改造与扩展。

> An enhancement mod for the Samsung NX500 / NX1, built on the community  
> `nx500_nx1_modding` upstream.

**分支说明 / Branches**: `master` = 上游原始历史(勿动)；**`nx-ks2` = 本项目源码(本文档所在分支)**。

## 特性亮点 / Highlights

- Web 遥控 (`nx-rc`) 网页相册：**折叠目录模型** —— 目录倒序、默认只展开最新目录、  
  按需加载 + 缩略图缓存，根治单核 CPU 上目录多导致的首屏卡顿。
- 相册**实时目录源**：8080 端口 `dirlist` CGI 每次请求直接 readdir SD 卡，  
  新拍照片立即可见（80 端口 daemon 的目录列表是启动快照，新照片永不出现）。
- **缩略图预热**：开启遥控后台自动铺缓存（网格 320px 最新 300 张 + 灯箱 1024px  
  最新 60 张，`nice -n 19` 不影响拍摄），前端显示预热进度；加载失败自动重试。
- **主菜单直显 IP + 一键 Telnet/FTP**：每次打开菜单动态生成，最后一行显示  
  当前 IP 与 Telnet 状态，点击即开关（替代 EV+WiFi 组合键）；不再反复弹 IP 弹窗。
- 相机端缩略图 CGI（ImageMagick DCT 缩放 + SD 缓存 + `nice` 降权），前端心跳去抖 +  
  并发限流，WiFi 假断开根治。
- **8080 服务群**（busybox httpd）：`thumb`(缩略图) / `dirlist`(实时目录) /  
  `prewarm`(预热进度) / `push`(WiFi 在线推送前端，免拔卡)。
- 拍摄参数 Web API（`capdtm`）、键位/码率/黑场等原 NX-KS 模块保留。
- 全新**同步链路**：SD 卡"智能引导器"插卡即增量同步（永不误卸载）+ WiFi 在线 push。

## 相机菜单速查 / Camera menu

| 菜单项                     | 作用                                                      |
| ----------------------- | ------------------------------------------------------- |
| `IP: x.x.x.x [Telnet关]` | 显示当前 WiFi IP；**点击 = 开/关 Telnet(23) + FTP(21)**，popup 反馈 |
| `远程控制` (checkbox)       | 开关 Web 遥控（80 端口），同时拉起 8080 服务群与缩略图预热                    |

菜单每次打开时重新生成（`gen_menu.sh`），IP / Telnet 状态始终最新。  
PC 端排障工具：`test_server/telnet_run.py <相机IP> '命令'`（非交互 telnet，root 空密码）。

## 快速开始 / Quick start

把以下文件放 SD 卡根目录，插入相机即自动执行（相机固件触发链，  
`info.tg` → `nx_cs.adj` → 自动运行 `install.sh`），安装完成后，在设置中开启蓝牙，即开始初始化：

```
info.tg  nx_cs.adj  install.sh   <- 仓库根(智能引导器: 未装=全量安装, 已装=增量同步)
scripts/                          <- 整个目录(模块母本, 会被同步到相机内部)
```

- 支持固件：NX500 **1.12** / NX1 **1.41**（其它版本会拒绝）。
- **已装过后再插卡 = 增量同步**，只覆盖不删除、永不卸载；SD 上 `scripts/` 母本保留。
- 卸载请用相机菜单里的 `uninstall.sh`。

## 日常更新两条路 / Daily updates

| 方式        | 命令 / 操作                                                           | 适用             |
| --------- | ----------------------------------------------------------------- | -------------- |
| SD 智能引导器  | 最新 `scripts/` + `info.tg`/`nx_cs.adj`/`install.sh` 拷进 SD → 插卡自动同步 | 大版本 / 新增模块     |
| WiFi push | `scripts/nx-rc/push/push.sh <相机IP>`                               | 只改 web 前端时，免拔卡 |

详见 [SYNC.md](SYNC.md)（中英双语安装/同步/回滚指南）。

## 目录结构 / Layout

| 路径                                 | 说明                                                                    |
| ---------------------------------- | --------------------------------------------------------------------- |
| `install.sh` `info.tg` `nx_cs.adj` | SD 卡根触发三件套（装机/同步入口）                                                   |
| `scripts/`                         | 全部模块母本，同步目标 = 相机内部 `/opt/usr/nx-ks/`                                  |
| `scripts/nx-rc/`                   | Web 遥控：`web_root/`(前端)、`thumb/`(缩略图)、`capdtm/`(参数API)、`push/`(WiFi同步) |
| `scripts/update_nxrc.sh`           | 只更新 nx-rc 模块的增量脚本（相机端）                                                |
| `test_server/`                     | PC 端开发/验证环境（模拟相机 API + playwright 用例）                                 |
| `backup_original/`                 | 原厂文件备份（不入库上传）                                                         |

## 文档 / Docs

> ★ **文档按时效分区**：`docs/current/`（现行权威）/ `docs/archive/`（历史归档）/ `docs/evidence/`（逆向证据）。
> 完整索引见 [`docs/README.md`](docs/README.md)。**2026-10-07 已做全面清理**：
> 过时/错误旧文档移入 `archive/`，并逐条更正了 3 处历史错误结论。

**现行权威 / Current（★ 先读这里）**

- [`docs/current/HANDOVER_2026-10-07.md`](docs/current/HANDOVER_2026-10-07.md) — ★★★ **项目交接总纲**：现状 / 死路 / 已验证 / 阻塞 / 纪律 / 待办
- [`docs/current/ERROR_CORRECTIONS_2026-10-07.md`](docs/current/ERROR_CORRECTIONS_2026-10-07.md) — ★★★★★ **错误结论修正报告**：mod/固件/系统三层 9 处纠错（C1~C9）
- [`docs/current/FIRMWARE_BREAKTHROUGH_2026-10-07.md`](docs/current/FIRMWARE_BREAKTHROUGH_2026-10-07.md) — ★ 固件层突破口：ISP 参数块已解 / 魔灯三路评估
- [`docs/current/P7_DISPATCH_AND_LSC_2026-10-07.md`](docs/current/P7_DISPATCH_AND_LSC_2026-10-07.md) — ★★ 跳转表机制纠正（ARM 索引表 ≠ veneer）+ 镜头阴影描述符已解
- [`docs/current/STRATEGY_2026-10-07.md`](docs/current/STRATEGY_2026-10-07.md) — 开发策略定案
- [`docs/current/FEATURE_MATRIX_2026-10-07.md`](docs/current/FEATURE_MATRIX_2026-10-07.md) — 功能矩阵（定案版）
- [`docs/current/3DLUT_API_GUIDE.md`](docs/current/3DLUT_API_GUIDE.md) / [EN](docs/current/3DLUT_API_GUIDE_EN.md) — 3D LUT 操作手册
- [`docs/current/3DLUT_DEEP_DIVE_2026-10-07.md`](docs/current/3DLUT_DEEP_DIVE_2026-10-07.md) / [EN](docs/current/3DLUT_DEEP_DIVE_2026-10-07_EN.md) — 3D LUT 深度调查档案
- [`docs/current/P7_3DLUT_PATHS_2026-10-07.md`](docs/current/P7_3DLUT_PATHS_2026-10-07.md) — ★★★★★ 3D LUT 三条 C++ 路径全部解出（RTTI + 3 vtable）；★ 证明 View 与 Still 独立 ⇒ 改 View 表不影响照片
- [`docs/current/NATIVE_UI_DESIGN_2026-10-07.md`](docs/current/NATIVE_UI_DESIGN_2026-10-07.md) — 原生 UI 设计：控件映射 / CJK 决策 / 实施序列
- [`docs/current/CAMERA_MENU_ARCHITECTURE_2026-10-07.md`](docs/current/CAMERA_MENU_ARCHITECTURE_2026-10-07.md) — ★★★★★ **相机系统菜单渲染档案**：彻底区分 mod 菜单 vs 系统菜单；证明 **p7 无菜单**（显示层只做取景器叠加层）；菜单状态机全表 / Edje 主题 / 可扩展性三路评估
- [`docs/current/CAMERA_APP_STRUCTURE_2026-10-07.md`](docs/current/CAMERA_APP_STRUCTURE_2026-10-07.md) — ★★★★ **相机官方 App 结构盘查**（面向 App 开发）：di-camera-app 四模块（UI 153/GUI 83/Service 6）/ Manager 总线 + State 状态机 / 111 个 .so 依赖分五族 / 实机安装布局 + 25 个 Edje 主题 / 三条开发路线评估
- [`docs/current/ILAUNCHER_FIRMWARE_FLASH_2026-10-07.md`](docs/current/ILAUNCHER_FIRMWARE_FLASH_2026-10-07.md) — ★★★★★ **iLauncher 固件刷写机制逆向 + 本地文件刷写可行性**：★ 证明它**不直刷相机**（只是把固件拷到 SD 卡，由相机自升级）；FnA.dll 五参数签名 + 完整流水线还原；两处断点定位；★ 推荐「彻底绕开 iLauncher」方案
- [`docs/current/NX500_ARCHITECTURE.md`](docs/current/NX500_ARCHITECTURE.md) — 完整系统架构（含 EP 寄存器 dump 全表）
- [`SYNC.md`](SYNC.md) — 安装 / 增量同步 / WiFi push / 回滚（双语）

**历史归档 / Archive（结论可能已被取代，见 archive/README）**

- [`docs/archive/`](docs/archive/) — 2026-10-05 / 10-06 阶段性报告；含已被推翻的结论（如 mod_gui「13 键」、p6/p13「主备内核」）

**逆向证据 / Evidence**

- [`docs/evidence/p7/`](docs/evidence/p7/) — p7 固件 Ghidra 关键片段
- [`docs/evidence/discovery/`](docs/evidence/discovery/) — 3D LUT 发现期脚本与中间产物

**模块文档 / Module docs**

- `scripts/nx-rc/thumb/README.md` — 缩略图模块部署（双语）
- `scripts/nx-rc/push/README.md` — WiFi push 用法（双语）

---

## ★★ 3D LUT / EP 通路（2026-10-06 实测突破）

★ **用户态3D LUT 寄存器写入已实机打通**：写入后画面确实变化（用户目视确认）。

### 已彻底解决

| # | 能力            | 验证                                                 |
| - | ------------- | -------------------------------------------------- |
| 1 | EP 10 块权威物理地址 | `ioctl(fd, _IOR('h',100,...))` → **10/10 与历史实测吻合** |
| 2 | EP 寄存器读写      | `mmap(phys, PROT_WRITE, /dev/drime5_ep)`           |
| 3 | CMA 内存读写      | `mmap(phys, PROT_WRITE, /dev/d5_sma)`              |
| 4 | p7 权威 6 步写入序列 | 复现后**画面确实变了**                                      |

### p7 固件的 3D LUT 权威寄存器定义

```
+0x000 bit0      OnOff 总开关      FUN_004cf3d4
+0x004 bits[1:0] SelCbCr          FUN_004cf3fc
+0x004 bits[5:4] SelLUT 通道      FUN_004cf414
+0x004 bit8      LUT0 数据源      FUN_004cf42c
+0x004 bit12     LUT1 数据源      FUN_004cf444
+0x008 bit0      写启动脉冲★     FUN_004cf45c
+0x008 bit8/bit4 读侧清理         FUN_004cf484
+0x00c           LUT0 数据地址    FUN_004cf4b4
+0x010           LUT1 数据地址
```

★ **完整 6 步序列，一步都不能少**（②⑥ 漏掉则完全无效）：

```c
b[0x000] |= 1;  b[0x008] &= ~1UL;  b[0x008] |= 1UL;
b[0x00c] = lut_phys;  b[0x004] &= 0xffffffcfUL;  b[0x008] &= ~0x100UL;
```

★ 客观判据：**执行后 `+0x008` 保持 1= 硬件接受了启动**。  
★ 硬约束：**LUT 物理地址必须 256 字节对齐**（`(addr & 0xff) == 0`）。

### ★ 三星内置的 4 套 LUT 方案（已读出内容）

| 缓冲           | 特征     | 方案          |
| ------------ | ------ | ----------- |
| `0x81101e00` | 完美线性   | ★纯 identity |
| `0x81115200` | R↑ G↓  | ★ 暖色调 / 肤色  |
| `0x810fd100` | 非单调    | 风格化曲线       |
| `0x81106b00` | 同第 1 个 | 同上          |

LUT 格式 = **17³ 三维 LUT，16-bit 三通道交织**（R 从 `0x0001` 递增、G/B 同步递减）。

### ⇒★★ 魔灯的最终实现路径：改 P7 固件

★ 那4 个 LUT 缓冲在 `0x81xxxxxx`，**超出 Linux `mem=512M`，p7 页表也只覆盖  
`0x80000000..0x80ffffff`** ⇒ **Linux 用户态永远无法读写它们。**  
⇒ 这不是"写入者在 p7"，而是"**LUT 数据缓冲本身就在 p7 的地址空间里**"。  
⇒ ★ 切入点已锁定：`FUN_0009a3e8`（从 4 个常量选一个返回的地方）。

### ★★ 零风险立即可用：4 档色彩切换

★ **不需要改固件** —— 把 3DLUT 的 `+0x0c` 写成 `0x810fd100` / `0x81106b00` /  
`0x81115200` / `0x81101e00` 之一，即可在 4 套内置方案间切换。

**文档 / Docs**

- [`docs/archive/WORK_REPORT_2026-10-06.md`](docs/archive/WORK_REPORT_2026-10-06.md) / [EN](docs/archive/WORK_REPORT_2026-10-06_EN.md) — ★ 当日工作报告（打通过程 + 7 个自我修正 + 9 条铁律）
- [`docs/archive/_2026-10-06_purged/EP_3DLUT_WRITE_EXPERIMENTS_2026-10-06.md`](docs/archive/_2026-10-06_purged/EP_3DLUT_WRITE_EXPERIMENTS_2026-10-06.md) — ★ 11 次写入实验全记录（部分结论已被 10-07 修正，见 `docs/current/ERROR_CORRECTIONS_2026-10-07.md`）
- [`docs/archive/EP_PATH_OPEN_2026-10-06.md`](docs/archive/EP_PATH_OPEN_2026-10-06.md) — 内核 ioctl + mmap 通路
- [`docs/archive/LIBUDD5_EP_API_MAP_2026-10-06.md`](docs/archive/LIBUDD5_EP_API_MAP_2026-10-06.md) / [EN](docs/archive/LIBUDD5_EP_API_MAP_2026-10-06_EN.md) — libudd5 API 图谱

**English summary**

Verified on a real NX500: **userspace 3D LUT register writes work and visibly change the image.**
All 10 EP block addresses come authoritatively from the kernel
(`ioctl(fd, _IOR('h',100,...))`, 10/10 matching earlier `/dev/mem` measurements), and the
6-step write sequence was reproduced from the P7 firmware's own decompilation — steps ② and ⑥
(clear pulse bit, clear read-side flag) were the reason the first five attempts did nothing.
**Objective success criterion: after the sequence, `+0x008` stays at 1** (hardware accepted the start).

Then the decisive finding: P7 holds **four preset LUT buffers**
(`0x810fd100` / `0x81106b00` / `0x81115200` / `0x81101e00`) which read out as Samsung's four
built-in colour profiles (identity / warm-skin / stylised curves), format = **17³ 3D LUT,
16-bit × 3 channels interleaved**. Those addresses sit above the Linux 512MB limit and outside
the P7 page table, so **Linux userspace can never read or write them** ⇒ Magic Lantern must
patch P7 — not because "the writer is in P7", but because **the LUT buffers themselves live in
P7's address space**.

★ **Shippable today with zero risk**: writing one of those four addresses into 3DLUT's `+0x00c`
switches between the four built-in profiles — no firmware patch required.

**工具 / Tools**（`test_server/isp/` + `test_server/sysarch/`）

- `udd5.py` — 自研 ELF+Capstone 反汇编器（pyelftools 16/16 交叉验证）
- `regmap.py` — EP 寄存器偏移自动提取 · `crosscheck.py` — 对照验证
- `epinfo` / `epdump2` / `epwr` / `eplut10` / `rd` — 只读与写入探针（ARM）

---

## ★ 逆向成果速览 / Reverse engineering highlights

2026-10-05 实测推翻了三个框架级判断（2026-10-06 追加修正见上）：

| 早先判断              | 实测结论                                                            |
| ----------------- | --------------------------------------------------------------- |
| `d5_ipcc` 是主要跨核通道 | ❌ **空壳**：ioctl 返回 0 但不回填；`size=8` 编码直接 SIGILL                   |
| 双核隔离，无法通信         | ❌ `drime5_ep` 中断 **149 万次**；`d5_sma` 有 144MB 共享区 @ `0x94000000` |
| 3D LUT 硬件未初始化     | ❌ **OnOff 实测 = 1（开着）**；且**寄存器写入已实机验证会改变画面**                     |
| handle 墙不可破       | ⚠️ 只对厂商库成立。直接 mmap 硬件**绕过 handle**（**读+写均已实测**）                 |

> ★★ **2026-10-06 重大修正**：早先写的"**绝不写 EP 寄存器**/只能拔电池"  
> **已被实测证伪**。真相是：
>
> - EP 块是 `/dev/drime5_ep` 的纯 mmap 设备，`open` **零硬件初始化**（源码证实）
> - 按p7 固件的 6 步序列写入，用户目视确认**画面确实变化**
> - 风险远低于预想：**LUT 是软状态，触屏/对焦后即自动恢复**
> - ⚠️ 但"用户态写 LUT **数据**"不可行 —— 缓冲在 p7 地址空间（详见上文）

> 胶片仿真探索（recipe + .cube LUT + capdtm ISP）在独立仓库  
> [nx500-filmsim](https://github.com/WApaperplane/nx500-filmsim)。

**已经走过的弯路？** 见综合报告 **§7 方法论铁律** 与 **§9.3 已排除的路径**  
（9 条已证伪路线 + 13 条硬件/交叉编译约束，都是很容易浪费几小时的坑）。  
**English:** see §7 and §9.3 of the consolidated report.
