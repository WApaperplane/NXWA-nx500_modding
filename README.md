# NX-WA

Samsung NX500 / NX1 (Tizen / DRIMe5) 增强固件 mod —— 基于社区上游  
[`ottokiksmaler/nx500_nx1_modding`](https://github.com/ottokiksmaler/nx500_nx1_modding) 改造与扩展。

> An enhancement mod for the Samsung NX500 / NX1, built on the community
> `nx500_nx1_modding` upstream.  
> **English version: [README_EN.md](README_EN.md)**

**仓库 / Repository**：**[WApaperplane/NXWA-nx500_modding](https://github.com/WApaperplane/NXWA-nx500_modding)**
（fork 自社区上游；旧地址 `WApaperplane/nx500_nx1_modding` 仍可重定向访问，**项目名以下载页显示名为准**。相机端安装路径 `/opt/usr/nx-ks/` 保持不变。）

**分支 / Branches**：`master` = 上游原始历史（勿动）；**`nxwa` = 本项目源码（本文档所在分支，亦是默认分支）**。

**许可证与血缘 / License**：**AGPL-3.0**（派生自社区上游，已复核上游为 AGPL-3.0）—— 上游血缘表与发布前核对清单见 [ATTRIBUTION.md](ATTRIBUTION.md)。

**发布物 / Releases**：见 [Releases](https://github.com/WApaperplane/NXWA-nx500_modding/releases)（含 SD 卡安装包 zip）。

---

## 特性亮点 / Highlights

- **FilmLab 胶片配方（68 条）**：负片 / 反转 / 黑白 / 电影 / 风格五族，菜单分 4 页自动生成。配方库在 SD 卡（可编辑、可扩充）。
- **PW 直推（三维即时生效）**：`EV+AEL` → 点配方，**SAT / SHARP / CONTRAST 三维直接推送进 ISP，画面秒级变化**（`pwsend.arm` + 完整 32 位编码，已上机回归）。
  ★ 诚实边界：**全 7 维（含 R/G/B/HUE）无外部通路** —— p7 的归一化器只认 `0x100–0x12e`，`0x130–0x133` 一律拒收（上机负结论 + 静态机制铁证）。要全维生效，需在机身「画面向导」里选一次「自定义1」，或改 p7（待 G4）。
- **客观判据**：`sh /opt/usr/nx-ks/filmlab.sh check` 直接读 ISP 手上那 7 维并与配方槽位比对（只读、零风险）——**"值变了" ≠ "被消费"**，这一条是全项目的判据基准。
- **3D LUT 链路**：任意 `.cube` → 原生表 → 预览直灌（LUT1 + `lutsentinel` 守护）；`.cube ⇄ 原生表` 双向工具齐备。
- **Web 遥控 (`nx-rc`) 网页相册**：折叠目录模型（目录倒序、默认只展开最新），按需加载 + 缩略图缓存，根治单核 CPU 上目录多导致的首屏卡顿。
- **相册实时目录源**：8080 端口 `dirlist` CGI 每次请求直接 `readdir` SD 卡，新拍照片立即可见（80 端口 daemon 的目录列表是启动快照，新照片永不出现）。
- **缩略图预热**：开启遥控后台自动铺缓存（网格 320px 最新 300 张 + 灯箱 1024px 最新 60 张，`nice -n 19` 不影响拍摄），前端显示预热进度；加载失败自动重试。
- **主菜单直显 IP + 一键 Telnet/FTP**：每次打开菜单动态生成，最后一行显示当前 IP 与 Telnet 状态，点击即开关（替代 EV+WiFi 组合键）；不再反复弹 IP 弹窗。
- 相机端缩略图 CGI（ImageMagick DCT 缩放 + SD 缓存 + `nice` 降权），前端心跳去抖 + 并发限流，WiFi 假断开根治。
- **8080 服务群**（busybox httpd）：`thumb`(缩略图) / `dirlist`(实时目录) / `prewarm`(预热进度) / `push`(WiFi 在线推送前端，免拔卡)。
- 拍摄参数 Web API（`capdtm`）、键位/码率/黑场等原 NX-KS 模块保留。
- 全新**同步链路**：SD 卡"智能引导器"插卡即增量同步（永不误卸载）+ WiFi 在线 push。初次安装请在显示“安装完成”后手动开启蓝牙以初始化mod。
## 相机菜单速查 / Camera menu

| 菜单项 | 作用 |
| --- | --- |
| `IP: x.x.x.x [Telnet关]` | 显示当前 WiFi IP；**点击 = 开/关 Telnet(23) + FTP(21)**，popup 反馈 |
| `远程控制` (checkbox) | 开关 Web 遥控（80 端口），同时拉起 8080 服务群与缩略图预热 |
| **`EV + AEL`**（组合键） | ★ **FilmLab 配方菜单**（4 页 / 每页 22 项）：点配方 → 写槽 + 切槽 + **三维直推**；再按一次 = 关闭 【NX500 专属】 |

菜单每次打开时重新生成（`gen_menu.sh`），IP / Telnet 状态始终最新。  
PC 端排障工具：`test_server/telnet_run.py <相机IP> '命令'`（非交互 telnet，root 空密码）。

## FilmLab 胶片配方 / FilmLab recipes

> **实际链路（2026-10-09 起）**：`EV + AEL` 打开配方菜单 → 点选配方  
> → `apply` 一步内完成 **①写槽（prefman slot9）②切槽（setusr）③PW 三维直推**（`FILMLAB_PW=1`）。
> ③ 生效后画面秒级变化；**R/G/B/HUE 四维**因 p7 归一化器域外拒收而**无法由 shell 直推**，
> 需机身「画面向导 → 自定义1」确认一次（该步同时把 7 维全部搬进 ISP）。

### 内置 68 条配方（4 页菜单）

| 族 | 示例（共 68 条） |
| --- | --- |
| 彩色负片 | Portra 400/800/160 / Gold 100/200/400 / Ektar 100 / UltraMax 400 / Superia 200/400 / ColorPlus 200 / ProImage 100 / Fuji C200/400H/9000 / Vista 200/400 / Lomo 100/800 / Reala 100 / Solaris 100 |
| 反转片 | Velvia 50/50 风光/100/100F / Provia 100F/400X/1600 / Sensia 100 / Astia 100F / Ektachrome / Ektachrome E100 / EliteChrome 100 / Kodachrome / EK Cyan 冷调 |
| 黑白 | TriX 400 / TriX 400 推档 / HP5 Plus / HP5 推1600 / Delta 100 / Delta 3200 / T-MAX 100/400 / Acros 100 / FP4 Plus / Pan F Plus 50 / Neopan 100 / Kentmere 400 / XP2 Super / MonoWarm 暖调 / MonoCool 冷调 |
| 电影卷 | CineStill 800T / CineStill 50D / Vision3 250D / Vision3 500T / Double-X 5222 / Cine Teal |
| 风格 | 青橙 / 暖旧 / 冷峻 / 褪色 / 高调 / 低调 / 棕褐 / 漂白 / 蓝调时刻 / X-Pro 交叉 |

- 黑白配方用 `SAT=0`（真黑白）；**MonoWarm / MonoCool 是暖调 / 冷调黑白**（保留 R/B 增益差）。
- 配方 = Picture Wizard 7 维向量（R/G/B 增益 + HUE/SAT/SHARP/CONTRAST），固定写入 UI 的「自定义1」槽，位置恒定、可预期。
- 彩色配方靠 R/G/B 增益相对差 + 饱和度/对比度实现胶片色偏（比 HUE 更可控）。

### 改配方 / 加配方（不用改代码、不用重刷）

```
权威配方库（引擎直接读）：/mnt/mmc/filmlab/recipes.json
加一条：编辑该 JSON → 拷回 SD 卡 → 重新打开菜单（菜单自动重建）
```

- 仓库中的**权威源**：`scripts/filmlab/recipes.json`（68 条；`flab.py` 的 `add/edit/rm/lint/conf/deploy` 一条龙都基于它）。
- 上机一条龙：`python test_server/filmlab/flab.py add …` → `lint` → `deploy`（推 JSON + 重建菜单 + 回收核对）。
- 离线回归（无需相机）：`sh test_server/filmlab/flab_sim.sh`（12 断言）。
- ⚠️ `test_server/filmsim/recipes/nx500_recipes.txt` 是**早期 18 条源表**，已滞后，仅供追溯；**不要**再以它为权威源。

### 已知边界（诚实说明）

- `mod_gui` 固有「点击即退」：不能滚动对比；要对比就连点两个配方看变化。
- **全 7 维不能一键**：`R/G/B/HUE` 需机身「画面向导」确认（原因见上）；这是 p7 固件的结构性限制，不是脚本 bug。
- 白平衡不在配方内：WB 请在机身 UI 自行调整（配方只管色彩风格）。
- 配方是**全局色彩向量**，做不出高光滚降 / 分区曝光。
- 配方为 **NX500 专属**（prefman 偏移仅在 NX500 1.12 上实证）；NX1 上 `EV+AEL` 自动回退社区原版「长录像」脚本（`EV_AEL.community.sh`）。
- 进阶（telnet）：`filmlab.sh list` 列配方 / `dump` 读全部槽位 / `reset` 恢复中性 / `cycle` 轮换下一个。

## 3D LUT / LUT pipeline

| 能力 | 现状 |
| --- | --- |
| 表格式 | 已解：`4913×4B {R,G,B,pad}`，索引 `((B*17+G)*17+R)*4`，槽步长 `0x4D00`，17 等距电平 |
| 导入 | `.cube ⇄ 原生表` 双向（`test_server/isp/nx3dlut.py`、`test_server/lutpipe/deploy_luts.py`） |
| 预览 | `lutpipe/lutpick.sh apply` — 落点探测 → 安全闸（`cmasafe` 四查）→ `lutapi load`，取景器秒级变化 |
| 存活 | ★ **写表生效律**：写前必须处于"p7 抢回态"，否则写入不生效；快门必触发抢回 ⇒ `lutsentinel.arm` 守护 + 双通道隔离（表进 LUT1，p7 只碰 LUT0） |
| 成片 | ★ **定式：预览直灌（LUT1 + 守护）/ 成片后处理（ksfilm）**。"成片直灌"已实测为死路（拍片流程会主动重配置 LUT 档位池） |

## 快速开始 / Quick start

把以下文件放 SD 卡根目录，插入相机即自动执行（相机固件触发链：  
`info.tg` → `nx_cs.adj` → 自动运行 `install.sh`），安装完成后，在设置中开启蓝牙，即开始初始化：

```
info.tg  nx_cs.adj  install.sh   <- 仓库根(智能引导器: 未装=全量安装, 已装=增量同步)
scripts/                          <- 整个目录(模块母本, 会被同步到相机内部)
```

- 支持固件：NX500 **1.12** / NX1 **1.41**（其它版本会拒绝）。
- **已装过后再插卡 = 增量同步**，只覆盖不删除、永不卸载；SD 上 `scripts/` 母本保留。
- 卸载请用相机菜单里的 `uninstall.sh`。
- ★ **一键包**：`NX-WA-<version>.zip`（见 Releases）= 上表全部内容，解压到 SD 卡根即可。

## 日常更新两条路 / Daily updates

| 方式 | 命令 / 操作 | 适用 |
| --- | --- | --- |
| SD 智能引导器 | 最新 `scripts/` + `info.tg`/`nx_cs.adj`/`install.sh` 拷进 SD → 插卡自动同步 | 大版本 / 新增模块 |
| WiFi push | `scripts/nx-rc/push/push.sh <相机IP>` | 只改 web 前端时，免拔卡 |

详见 [SYNC.md](SYNC.md)（中英双语安装/同步/回滚指南）。

## 目录结构 / Layout

| 路径 | 说明 |
| --- | --- |
| `install.sh` `info.tg` `nx_cs.adj` | SD 卡根触发三件套（装机/同步入口） |
| `scripts/` | 全部模块母本，同步目标 = 相机内部 `/opt/usr/nx-ks/` |
| `scripts/filmlab.sh` | ★ **FilmLab 引擎**（相机端运行版）：配方读写 / 应用 / 菜单生成 / `apply --fast` |
| `scripts/filmlab/recipes.json` | ★ **权威配方库**（68 条；首次安装时自动拷到 SD 卡 `/mnt/mmc/filmlab/`） |
| `scripts/EV_AEL.sh` | FilmLab 入口（`EV+AEL` 组合键）；NX1 自动回退 `EV_AEL.community.sh` |
| `scripts/gui_filmlab*.NX500` | FilmLab 菜单：`1b`=配方主菜单（默认）；`2/3/4`=预设槽 / WB / 诊断页 |
| `scripts/nx-rc/` | Web 遥控：`web_root/`(前端)、`thumb/`(缩略图)、`capdtm/`(参数API)、`push/`(WiFi同步) |
| `test_server/` | PC 端开发/验证环境（模拟相机 API + 工具链 + 门控） |
| `test_server/pwsend/` | ★ PW 直推工具（`pwsend.arm` / `pwcalib.sh` / `gen_pwpush.py`）+ 上机 runbook |
| `test_server/lutpipe/` `test_server/isp/` | LUT 部署/守护工具与 `.cube ⇄ 原生表` 转换 |
| `test_server/u6/` `test_server/u1/` | 上机实验包与 runbook（含 LUT 闭环、输入事件侦察） |
| `deploy/filmlab/` | 早期 FilmLab 部署件（`nxfilmui` 原生 UI 实验，保留作参考） |
| `uninstall_pkg/` | 相机菜单卸载入口（手动确认，不会误触） |

## 文档 / Docs

> ★ **文档按时效分区**：`docs/current/`（现行权威）/ `docs/archive/`（历史归档）/ `docs/evidence/`（逆向证据）。
> 完整索引见 [`docs/README.md`](docs/README.md)。

**现行权威 / Current（★ 先读这里）**

- [`docs/current/TASKFLOW_2026-10-10.md`](docs/current/TASKFLOW_2026-10-10.md) — ★★★★★ **当前执行序**（离机 P1–P7 / 上机 W-1→W-2→W-3 / 门槛后 A）—— "接下来做什么"只看这一页
- [`docs/current/RE_PROGRESS_2026-10-08.md`](docs/current/RE_PROGRESS_2026-10-08.md) — ★★★★★ 逆向进度总览（单文件收口）
- [`docs/current/HANDOVER_2026-10-07.md`](docs/current/HANDOVER_2026-10-07.md) / [`ERROR_CORRECTIONS_2026-10-07.md`](docs/current/ERROR_CORRECTIONS_2026-10-07.md) — 交接总纲 / 历史纠错 C1–C9
- [`docs/current/PW_PARAM_CHANNEL_2026-10-08.md`](docs/current/PW_PARAM_CHANNEL_2026-10-08.md) — ★★★★★ PW 三通道上机定论（①存储 ②选择 都打不到 ISP；③参数唯一有效）
- [`docs/current/PW_ID_MAP_FULL_2026-10-10.md`](docs/current/PW_ID_MAP_FULL_2026-10-10.md) — ★★★★★ PW id 全图 + **为什么外部够不到 R/G/B/HUE**（归一化器域 `0x100–0x12e`）
- [`docs/current/PW_APPLY_TRIGGER_CHAIN_2026-10-10.md`](docs/current/PW_APPLY_TRIGGER_CHAIN_2026-10-10.md) — ★★★★★ 「画面向导→自定义1」在 p7 侧的触发链 + **路 A（复刻 app 类别消息）证伪**
- [`docs/current/ATTR_BUS_MCB_2026-10-09.md`](docs/current/ATTR_BUS_MCB_2026-10-09.md) — ★★★★★ 属性总线传输层全解（`SetVariableDataMCB → SetParam(CID 0x81) → ipcc`）
- [`docs/current/3DLUT_TABLE_FORMAT_2026-10-08.md`](docs/current/3DLUT_TABLE_FORMAT_2026-10-08.md) / [`3DLUT_APPLY_PATHS_2026-10-08.md`](docs/current/3DLUT_APPLY_PATHS_2026-10-08.md) — ★★★ 表格式全解 / 五条应用线路 + QEMU 复现
- [`docs/current/U6_ONMACHINE_RESULT_2026-10-09.md`](docs/current/U6_ONMACHINE_RESULT_2026-10-09.md) — ★★★★★ U6 上机结果（写表生效律 / 判据重构 / E1✓ E3✓ E4✗）
- [`docs/current/P7_RECLAIM_COUNTERMEASURE_2026-10-09.md`](docs/current/P7_RECLAIM_COUNTERMEASURE_2026-10-09.md) — ★★★★★ 抢回处理方案（双通道隔离 + `lutsentinel` + 实验矩阵）
- [`docs/current/LUT_PIPELINE_DESIGN_2026-10-09.md`](docs/current/LUT_PIPELINE_DESIGN_2026-10-09.md) / [`FLAB_DATAFLOW_DESIGN_2026-10-09.md`](docs/current/FLAB_DATAFLOW_DESIGN_2026-10-09.md) — LUT 链路 / 数据流设计
- [`docs/current/FW_NATIVE_UI_ONEKEY_FEASIBILITY_2026-10-10.md`](docs/current/FW_NATIVE_UI_ONEKEY_FEASIBILITY_2026-10-10.md) — ★★★★★ 「原生 UI 一键滤镜」可行性链路（G-UI / G-ONEKEY / G-FILTER 拆解）
- [`docs/current/MODGUI_SPEED_AND_RECIPES_2026-10-10.md`](docs/current/MODGUI_SPEED_AND_RECIPES_2026-10-10.md) — ★★★★ 菜单弹出提速 4× + 配方 35→68
- [`docs/current/CAMERA_MENU_ARCHITECTURE_2026-10-07.md`](docs/current/CAMERA_MENU_ARCHITECTURE_2026-10-07.md) — ★★★★★ 相机系统菜单渲染档案（**证明 p7 无菜单**）
- [`docs/current/CAMERA_APP_STRUCTURE_2026-10-07.md`](docs/current/CAMERA_APP_STRUCTURE_2026-10-07.md) / [`ILAUNCHER_FIRMWARE_FLASH_2026-10-07.md`](docs/current/ILAUNCHER_FIRMWARE_FLASH_2026-10-07.md) — 官方 App 结构 / iLauncher 刷机机制
- [`docs/current/NX500_ARCHITECTURE.md`](docs/current/NX500_ARCHITECTURE.md) — 完整系统架构（含 EP 寄存器 dump 全表）
- [`SYNC.md`](SYNC.md) — 安装 / 增量同步 / WiFi push / 回滚（双语）

**历史归档 / Archive**：`docs/archive/`（含已被推翻的结论：mod_gui「13 键」、p6/p13「主备内核」、View/Still「独立」等）  
**逆向证据 / Evidence**：`docs/evidence/p7/`、`docs/evidence/discovery/`

**模块文档 / Module docs**：`scripts/nx-rc/thumb/README.md`、`scripts/nx-rc/push/README.md`

---

## ★★ 勘误与更正（2026-10-10 文档审查）

本仓历史文档存在若干**已过时或被后续实测推翻**的表述。以下为本次审查确认的更正面，**以本节为准**：

| # | 旧表述 | 更正面 | 依据 |
| - | --- | --- | --- |
| 1 | 本 fork 仓库 = `github.com/WApaperplane/nxwa` | 规范仓库 = **`github.com/WApaperplane/NXWA-nx500_modding`**（fork；默认分支 `nxwa`；旧名 URL 仍重定向） | `gh repo view` 实测 |
| 2 | 上游 = `github.com/SamsungNX500/nx500_nx1_modding` | 上游（fork parent，其自身 parent 为空）= **`ottokiksmaler/nx500_nx1_modding`**；`SamsungNX500/...` 这个仓库**不存在** | `gh repo view` 实测 |
| 3 | 内置 18 条配方 | **68 条**（4 页菜单） | `scripts/filmlab/recipes.json` |
| 4 | 配方权威源 = `nx500_recipes.txt` | 权威源 = **`scripts/filmlab/recipes.json`**；`.txt` 为早期 18 条旧表 | `flab.py` 数据流 |
| 5 | 「点配方立即生效 / 两步出片」 | **三维（SAT/SHARP/CON）可直推即时生效；全 7 维需机身「画面向导→自定义1」确认一次** | `PW_PARAM_CHANNEL` / `PW_ID_MAP_FULL` |
| 6 | 「View 与 Still 独立 ⇒ 改 View 表不影响照片」 | ❌ **已证伪**：`View 4 档 ⊆ Still 18 档`，View 独有 = 空 ⇒ 两路**共用同一缓冲池**，软件层无法隔离 | `3DLUT_VIEW_STILL_ISOLATION_2026-10-08.md` |
| 7 | 「用户态写 LUT 数据不可行」 | **已修**：用户态可 `lutapi load` 自有表（LUT1 + 守护）；**不可**读写的是 p7 那 4 个内置缓冲（`0x81xxxxxx`，超出 Linux 映射） | `U6_ONMACHINE_RESULT` / `3DLUT_APPLY_PATHS` |
| 8 | 「内置 LUT 之一是纯 identity / 可作中性基准」 | ❌ **判据作废**：出厂表**全是风格表**（所谓 identity 槽实为低对比灰调） | `U6_ONMACHINE_RESULT` |
| 9 | 「`setvar` 可写 PW 变量」 | ⛔ **禁区**：id 由 p7 运行时注册，盲扫曾写死 capture 服务 | `ERROR_CORRECTIONS` / `PW_PARAM_CHANNEL` |

> 其余已知死路（不改 p7 就做不到的事）集中记录在 `docs/current/RE_PROGRESS_2026-10-08.md` §8 与 `docs/current/ERROR_CORRECTIONS_2026-10-07.md`。

---

## ★ 逆向成果速览 / Reverse engineering highlights

**已打通（可复现）**

| 能力 | 状态 |
| --- | --- |
| PW 三维直推进 ISP | ✅ 上机回归 3/3（完整 32 位编码 `(raw16<<16)\|0xD80A`，官方编码 LUT 17/17 逐位一致） |
| 3D LUT 用户态装载 | ✅ `lutapi load`（写前须"p7 抢回态"）+ 双通道隔离 + 守护 |
| `.cube ⇄ 原生表` | ✅ 表格式已解（4913×4B / `0x4D00` 槽步长） |
| 相机系统菜单扩展 | ✅ mod_gui 覆盖层（4 控件 / 4 keysym；只取代不迭代） |
| Web 相册实时目录 | ✅ 8080 `dirlist` readdir |

**结构性天花板（诚实列出）**

- **全 7 维 PW 无外部通路**（p7 归一化器域 `0x100–0x12e`）—— 需机身确认一次或改 p7。
- **p7 无 UI**（Font/DrawText/Dialog/Widget 全 0 命中）⇒ 系统菜单只能在 Linux 侧 `di-camera-app` 里改（无源码，成本极高）。
- **长按 / 连击 / 组合键架构性不可得**（内核先消费按键）⇒ "一键"上限 = 一次按键一个动作。
- **成片直灌 LUT 是死路**（拍片流程主动重配置档位池）⇒ 定式：预览直灌 / 成片后处理。
- **出厂 LUT 表全是风格表** ⇒ 不可用"写 identity 得中性"做判据。

**工具链**：Ghidra（p7 静态）、QEMU/Unicorn（离线复现）、zig 交叉编译（`arm-linux-gnueabi.2.15`，**必须 `-O0`**）、`gate_flow.py`（门控）、`check_scripts.py`（CI）。

**已经走过的弯路**：见 `docs/current/ERROR_CORRECTIONS_2026-10-07.md`（C1–C9）与 `RE_PROGRESS` §8 死路清单 —— 都是很容易再浪费几小时的坑。

> 胶片仿真引擎与 `.cube` 素材另见独立仓库
> [nx500-filmsim](https://github.com/WApaperplane/nx500-filmsim)（public）。
