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
`info.tg` → `nx_cs.adj` → 自动运行 `install.sh`）：

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

**主文档 / Main documents**

- [`docs/CONSOLIDATED_REPORT_2026-10-05.md`](docs/CONSOLIDATED_REPORT_2026-10-05.md) — ★ **10-04 + 10-05 综合成果报告（中英双语）**：handle墙绕道、双核三通道实测、FilmLab、方法论铁律、避坑清单
- [`docs/NX500_ARCHITECTURE.md`](docs/NX500_ARCHITECTURE.md) — 完整系统架构（677 行，含 EP 寄存器 dump 全表；**第 14 章 = handle墙绕道实证**）
- [`docs/NX500_FIRMWARE_FRAMEWORK_2026-10-05.md`](docs/NX500_FIRMWARE_FRAMEWORK_2026-10-05.md) / [EN](docs/NX500_FIRMWARE_FRAMEWORK_2026-10-05_EN.md) — ★ **固件层整体框架**（89 份实机抓取）：存储拓扑、进程/库全景、内核层、**eMMC 分区 uImage 扫描 → ISP 固件定位**
- [`docs/ISP_NOG_ENTRY_2026-10-05.md`](docs/ISP_NOG_ENTRY_2026-10-05.md) / [EN](docs/ISP_NOG_ENTRY_2026-10-05_EN.md) — ★ **ISP 核 / DSP_NX500GLU 入口追踪**：libudd5.so 反汇编解出 NOG 硬件颗粒发生器寄存器偏移
- [`docs/LUT_OPEN_SOURCE_EVAL.md`](docs/LUT_OPEN_SOURCE_EVAL.md) — 开源 LUT 资产可用性评估（CC0 实测 + 松下专利核查）
- [`docs/SHARING_COPY.md`](docs/SHARING_COPY.md) — 分享文案：Reddit / 小红书 / 通用短版，可直接复制
- [`SYNC.md`](SYNC.md) — 安装 / 增量同步 / WiFi push / 回滚（双语）

**FilmLab 子专题 / FilmLab sub-topics**

- [`docs/FILMLAB_ONEKEY_UI.md`](docs/FILMLAB_ONEKEY_UI.md) — 一键 UI 需求裁决（三个需求，两个撞硬墙）
- [`docs/FILMLAB_WIFI_JOG.md`](docs/FILMLAB_WIFI_JOG.md) — WiFi 键直达 + 波轮 UI 可行性
- [`docs/FILMLAB_ONEKEY_VERIFY.md`](docs/FILMLAB_ONEKEY_VERIFY.md) — `pw_force_reload()` 验证清单

**模块文档 / Module docs**

- `scripts/nx-rc/thumb/README.md` — 缩略图模块部署（双语）
- `scripts/nx-rc/push/README.md` — WiFi push 用法（双语）

---

## ★ 逆向成果速览 / Reverse engineering highlights

2026-10-05 实测推翻了三个框架级判断（详见综合报告 §0）：

| 早先判断 | 实测结论 |
|---|---|
| `d5_ipcc` 是主要跨核通道 | ❌ **空壳**：ioctl 返回 0 但不回填；`size=8` 编码直接 SIGILL |
| 双核隔离，无法通信 | ❌ `drime5_ep` 中断 **149 万次**；`d5_sma` 有 144MB 共享区 @ `0x94000000` |
| 3D LUT 硬件未初始化 | ❌ 寄存器在 Linux 侧 **mmap 可读**，里面装着 **identity LUT**（`0x13020619` × 8 @ `0x2082b000`） |
| handle 墙不可破 | ⚠️ 只对厂商库成立。直接 mmap 硬件**绕过 handle**（**读已实测，写不测且不测**） |

> **为什么绝不写 EP 寄存器**：不可中断写入 + 并发读风险 ⇒ 位域错乱；
> 且 `di-camera-app` 杀不掉（`launchpad_preloading_preinitializing_daemon` 会拉起）⇒ **只能拔电池**。
> **⇒ 绕道换来的真实收益是「可观测」，不是「可写」。**
>
> **2026-10-05 21:20 修正**：早先写的"EP 由 ISP 固件实时驱动"**无证据，已降级为假设**——
> 冷启动 dmesg 里 `request_firmware`/`uImage`/`rom.bin`/`devicem4.bin`/`srp` 全零命中，
> 且 libudd5.so 503 个符号零 ISP 引用。EP 走标准 UDD 模型（ioctl + **用户态自己 mmap**）。
> ⇒ 更可能：EP 是**独立图像引擎，由 Linux 用户态直接驱动**；真正风险不是"被 ISP 同时读"，
> 而是**改了 3DLUT 没走 `d5_ep_top_update_sreg(3DLUT_SHADOW_UPDATE)` 导致影子寄存器不提交**（待实机验证）。

> 胶片仿真探索（recipe + .cube LUT + capdtm ISP）在独立仓库  
> [nx500-filmsim](https://github.com/WApaperplane/nx500-filmsim)。

**已经走过的弯路？** 见综合报告 **§7 方法论铁律** 与 **§9.3 已排除的路径**
（9 条已证伪路线 + 13 条硬件/交叉编译约束，都是很容易浪费几小时的坑）。
**English:** see §7 and §9.3 of the consolidated report.
