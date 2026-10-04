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

**English (international communities)**

- [`docs/DEVELOPMENT_REPORT_EN.md`](docs/DEVELOPMENT_REPORT_EN.md) — FilmLab + system-level RE progress report
- [`docs/SYSTEM_LAYER_FINDINGS_EN.md`](docs/SYSTEM_LAYER_FINDINGS_EN.md) — ISP internals, 3D LUT control chain, hardware constraints, tooling
- [`docs/FORUM_POST_EN.md`](docs/FORUM_POST_EN.md) — ready-to-post summary (long / short / two-paragraph versions)

**中文**

- [`docs/DEVELOPMENT_REPORT_2026-10-05.md`](docs/DEVELOPMENT_REPORT_2026-10-05.md) — 双语开发进展报告
- [`docs/SYSTEM_LAYER_FINDINGS_2026-10-04.md`](docs/SYSTEM_LAYER_FINDINGS_2026-10-04.md) — 系统层结论（中文详版）
- [`docs/FORUM_POST.md`](docs/FORUM_POST.md) — 论坛分享文案（详细 / 精简 / 英文三版）
- `SYNC.md` — 安装 / 增量同步 / WiFi push / 回滚（双语）
- `scripts/nx-rc/thumb/README.md` — 缩略图模块部署（双语）
- `scripts/nx-rc/push/README.md` — WiFi push 用法（双语）

> 胶片仿真探索（recipe + .cube LUT + capdtm ISP）在独立仓库  
> [nx500-filmsim](https://github.com/WApaperplane/nx500-filmsim)。
>
> **Found dead ends?** See §10 of the English findings doc — 7 refuted paths that are easy to lose hours on.  
> **已经走过的弯路？** 见中文详版 §10 —— 7 条已证伪路线，都是很容易浪费几小时的坑。
