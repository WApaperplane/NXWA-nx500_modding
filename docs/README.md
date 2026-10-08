# NX-KS2 文档索引 / Documentation Index

> 本目录按**时效**分区，避免"旧结论淹没新结论"。
> 更新：2026-10-08 · 分支：`nx-ks2`

## 目录结构

```
docs/
├── README.md        ← 本文件（索引）
├── current/         ← ★ 现行权威：据此做决策
├── archive/         ← 历史归档：仍可参考，但结论可能已被取代
└── evidence/        ← 逆向证据片段（可复现的原始数据/脚本）
```

---

## 1. current/ — 现行权威（★ 先读这里）

| 文档 | 定位 |
|---|---|
| [`RE_PROGRESS_2026-10-08.md`](current/RE_PROGRESS_2026-10-08.md) | ★★★★★ **逆向进度总览（单文件收口 / 新）**：一张总表看清"解了什么 / 卡在哪 / 什么是死路"——系统硬件层 / p7 静态 / 容器与升级链 / 通信层 / 用户态接口（PW+ISP参数块+3D LUT）/ 原生 UI / 门控 1-of-5 / **死路清单 10 条** / 未解缺口 / 资产索引 / 下一步。★ 对外交付与新人上手的第一入口 |
| [`HANDOVER_2026-10-07.md`](current/HANDOVER_2026-10-07.md) | ★★★ **项目交接总纲**：现状 / 死路 / 已验证 / 阻塞 / 纪律 / 待办 |
| [`ERROR_CORRECTIONS_2026-10-07.md`](current/ERROR_CORRECTIONS_2026-10-07.md) | ★★★★★ **错误结论修正报告**：mod/固件/系统三层 9 处纠错（C1~C9） |
| [`AUDIT_2026-10-07.md`](current/AUDIT_2026-10-07.md) | 整体盘查报告：按键槽位静态解 / 版本管理风险 / 文档一致性 |
| [`FIRMWARE_BREAKTHROUGH_2026-10-07.md`](current/FIRMWARE_BREAKTHROUGH_2026-10-07.md) | ★ 固件层突破口：ISP 参数块已解 / 魔灯三路评估 |
| [`P7_DISPATCH_AND_LSC_2026-10-07.md`](current/P7_DISPATCH_AND_LSC_2026-10-07.md) | ★★ **跳转表机制纠正**（ARM 索引表 ≠ veneer）+ **镜头阴影描述符解出** |
| [`STRATEGY_2026-10-07.md`](current/STRATEGY_2026-10-07.md) | 开发策略定案：三层栈 / 固件准入门槛 / 三阶段路线 |
| [`FEATURE_MATRIX_2026-10-07.md`](current/FEATURE_MATRIX_2026-10-07.md) | 功能矩阵（定案版，取代 2026-10-06 版）|
| [`NATIVE_UI_DESIGN_2026-10-07.md`](current/NATIVE_UI_DESIGN_2026-10-07.md) | 原生 UI：控件映射 / CJK 决策 / 实施序列 |
| [`CAMERA_MENU_ARCHITECTURE_2026-10-07.md`](current/CAMERA_MENU_ARCHITECTURE_2026-10-07.md) | ★★★★★ **相机系统菜单渲染档案**：★ 彻底区分 mod 菜单 vs 系统菜单；★ 证明 **p7 无菜单**（显示层只做取景器叠加）；菜单状态机全表 / Edje 主题 / 可扩展性三路评估 |
| [`CAMERA_APP_STRUCTURE_2026-10-07.md`](current/CAMERA_APP_STRUCTURE_2026-10-07.md) | ★★★★ **相机官方 App 结构盘查**：di-camera-app 四模块（UI 153/GUI 83/Service 6）/ Manager 总线 + State 状态机 / 111 个 .so 分五族 / 实机安装布局 + 25 个 Edje 主题 / ★ 开发启示三条路线 |
| [`ILAUNCHER_FIRMWARE_FLASH_2026-10-07.md`](current/ILAUNCHER_FIRMWARE_FLASH_2026-10-07.md) | ★★★★★ **iLauncher 刷机机制逆向 + 本地刷写可行性**：★ 证明它**不直刷相机**（= 拷文件到 SD，由相机自升级）；FnA.dll 五参数签名 + 完整流水线；断点定位；★ 推荐方案 B（彻底绕开 iLauncher） |
| [`Q3_EP_GAMMA_PROBE_2026-10-07.md`](current/Q3_EP_GAMMA_PROBE_2026-10-07.md) | Q3 实测：EP 全 10 块 / mc 结构 / 压死相机 5 次的边界 |
| [`3DLUT_DEEP_DIVE_2026-10-07.md`](current/3DLUT_DEEP_DIVE_2026-10-07.md) · [EN](current/3DLUT_DEEP_DIVE_2026-10-07_EN.md) | 3D LUT 调查档案（权威）：寄存器全图 / p7 侧逆向 / 地址空间模型 |
| [`3DLUT_API_GUIDE.md`](current/3DLUT_API_GUIDE.md) · [EN](current/3DLUT_API_GUIDE_EN.md) | 3D LUT 操作手册（API 调用 / 工具用法）|
| [`P7_3DLUT_PATHS_2026-10-07.md`](current/P7_3DLUT_PATHS_2026-10-07.md) | ★★★★★ **3D LUT 三条 C++ 路径全部解出**（RTTI + 3 vtable）；★ **证明 View 与 Still 完全独立 ⇒ 改 View 表不影响照片** |
| [`NX500_ARCHITECTURE.md`](current/NX500_ARCHITECTURE.md) | NX500 系统与软件架构（实机抓取）|
| [`UNBLOB_WSL_QEMU_2026-10-08.md`](current/UNBLOB_WSL_QEMU_2026-10-08.md) | ★★★★ **PC 侧全链路（新）**：WSL(NXKS2，全数据在 E) + **unblob 26.6.4** + **相机 rootfs 全量提取（17,838 文件）** + **chroot+qemu-arm 运行相机二进制**（st/bash/toybox 实测）；含命令备忘与坑清单 |
| [`G5P3_IQR_EPMC_MAP_2026-10-08.md`](current/G5P3_IQR_EPMC_MAP_2026-10-08.md) | ★★★★★ **G5-3 关联表定论（新）**：槽池双写入器全解（A `FUN_004b6894` @`0x20821300` / B `FUN_004b6b98` @`0x20821700`，21 槽 × stride 0x100 × 双通道；★ **提交位图实为 `0x20821044`**，修正旧记 `0x20820044`）；★★ **架构判定：槽池 = ISP 流描述符层，iqr = 状态镜像层，两层正交，唯一强锚点 = 尺寸三元组**（s1/s2/s3 = 720×480 / 528×352 / 384×288 金字塔，`+0x08[31:12]`/`+0x20`/`+0x24` 三处编码同值）⇒ **"路径 B = EP 直写画质"降级为流描述符直写**；产物 `raw8/gates/u1/iqr_epmc_map.tsv`（G5-3 已判 OK，G5 全绿） |
| [`PW_PARAM_CHANNEL_2026-10-08.md`](current/PW_PARAM_CHANNEL_2026-10-08.md) | ★★★★★ **PW 参数通道上机定论（新）**：三通道实测 —— ①存储（prefman）/②选择（setusr）**均打不到 ISP**，仅③"画面向导确认"有效（木一机身闭环，✓/✗ 双向验证）；★ **客观判据 = `st cap capdtm varlist` 的 PW 7 维变量**（raw16 须补码还原），已做成 `filmlab.sh check`；★ `setvar` 死路确认（id 运行时注册，盲扫写死过 p7，**禁再试**）；5 条新纪律（jpeg:size 单核必带 / 无 timeout / CRLF / FTP 路径域 / MSYS）；路径 A 键注入（`st app nx key`）命令在但**注入未生效**（疑走 X11/XTest，键名表未解） |
| [`ST_RE_AND_REPRO_2026-10-08.md`](current/ST_RE_AND_REPRO_2026-10-08.md) | ★★★★ **st 逆向 + PC 复现（新）**：sasquatch 补齐（unblob 闭环）；**st = 表驱动调度器**（shell_exec / sndmsg 双路径，与 MCB 报错互证）；**ksfilm 胶片引擎在 PC 全流程跑通（4 配方）**；-L / chroot 双路线与坑 |
| [`MCB_PROTOCOL_AND_ST_TABLE_2026-10-08.md`](current/MCB_PROTOCOL_AND_ST_TABLE_2026-10-08.md) | ★★★★★ **MCB 协议档案 + st 全表（新）**：运行时装 28 条全解（gdb 经 GOT 直取）；**SysV 消息离线拦截**（key 0x8828，载荷格式）；**MCB 协议全栈**（帧格式/396B 上限/命令 ID 字典 8 域/0xB0-0xB6-cap 链路）；di-camera-app 全量反编译 7,073 函数 |
| [`QEMU_S4_AND_ENV_CLEANUP_2026-10-08.md`](current/QEMU_S4_AND_ENV_CLEANUP_2026-10-08.md) | ★★★★★ **QEMU S4 全链路 + PC 资源归位（新）**：**纯 Windows 零 WSL** 跑通「slp06 → guest 内 unlzop（18s）→ mount ext4（16021 文件）→ chroot 原生跑相机二进制」；★ `st` 24 条内置命令运行时实测；★ 两个新坑（virtio 设备号乱序 / ext4 需 crc32c）；★ C 盘审计（已迁 690MB + binwalk 配置到 E，唯 `C:\Program Files\WSL` 1.2GB 不可迁） |
| [`UNKNOWN_STRUCTURES_AND_PROJECT_FORK_PLAN_2026-10-08.md`](current/UNKNOWN_STRUCTURES_AND_PROJECT_FORK_PLAN_2026-10-08.md) | ★★★★★ **未知结构清单 + 项目外化方案（新）**：U01–U19 全部未知项按"值不值得拿"排序（p7 B 区代码地图 / ISP 21 槽语义 / `0x81000000+` 映射矛盾 / MCB 全表 / QEMU 沙盒能免相机回答什么）；★★ **新证据：p3/p8 备份实际全零、p2 只有 1779 字节非零**（推翻"p3 可回滚"）；★ 命名与拆仓建议（为什么不能用 Magic Lantern / NX-KS3）|
| [`TIER1_AND_TIER3_OFFLINE_2026-10-08.md`](current/TIER1_AND_TIER3_OFFLINE_2026-10-08.md) | ★★★★★ **Tier 1 全部完成 + Tier 3 离机尝试（新）**：★ **U04 地址模型精确重建**（p7 页表覆盖 **4GB**，非 16MB；1:1 实测判决 3969 vs 595）+ 开出一条**零风险新实验**；★ **U01 B 区代码地图**（224 模块 / 3786 函数）并**证伪铁律 116 的"零引用率"判据**（Ghidra base 0x0 看不见 0x8xxxxxxx 指针；对照组当时已报失灵）；★ **U03 发现 EP 之外 128KB 的 IPC 寄存器区**（固件自命名 `IPC_WRITE_DIRECT BASE ADDRESS is 0x20810000`）⇒ Q3「EP 侧不可解」的前提被打破；§8 补做 **RTTI 三跳（565 类）+ 调用图传播 + Thumb 找回（+667）⇒ 硬证据 48.21%，含推断 64.3%**；★ 通道① 给出 207 条**真实方法名**（含 `CFrame::Send` = MCB 帧发送器）；U12/U14 等 Tier 3 离机结论 + 4 条新铁律（117–119）|
| [`FIRMWARE_FEATURE_SPACE_2026-10-08.md`](current/FIRMWARE_FEATURE_SPACE_2026-10-08.md) | ★★★★★ **固件改写功能空间分析（新）**：★ **NX-KS 全部 40+ 功能的逐项基线**（实读自 `scripts/` 全部菜单母本）+ 四层能力栈（L1 用户态 / L2 原生 EFL UI / L3 mod_gui / L4 p7）；★ 目标功能矩阵 C1–C15 + **原生 UI 五页设计**（配方库 / **PW 7 维实时滑块** / **3D LUT 管理** / 内置 4 档 / 诊断高危）；★ 架构级天花板与可逆性地图；★★ §4.4 两条**新侧门**（`/dev/mem` 可读 DRAM → 可能直接解 3D LUT 表格式；IPC 寄存器区 → 可能解 gamma/color 判据）；三阶段路线与判据 |
| [`QEMU_S5_OFFLINE_USERSPACE_2026-10-08.md`](current/QEMU_S5_OFFLINE_USERSPACE_2026-10-08.md) | ★★★★★ **QEMU S5 离线用户态验证（新）**：★ **QEMU 能/不能替代哪些上机项**（硬件探针替代不了，用户态可以）；★★ **推翻 N04/P6 —— 相机 rootfs 自带 `SDIC_GP_US` 字体（49864 字形，CJK 100% 真轮廓）⇒ 中文标签可用**；★★ **配方引擎跨环境逐字节一致**（guest 产物 md5 == PC 侧）；★ 新工具 `check_scripts.py`（铁律 99 的 CI）**抓到 3 个真缺陷 + 136 个脚本 git 执行位为 644**；★ 新发现 evas **buffer 引擎在场** ⇒ 中文光栅化也能离线验 |
| [`WORKFLOW_PLAN_2026-10-08.md`](current/WORKFLOW_PLAN_2026-10-08.md) | ★★★★★ **未来工作流清单（★ 先读这一页）**：离机轨 D1–D8 / 上机轨 U1–U5 / **门控表 G0–G5** / **preflight 逐条打勾** / 拆仓 8 步 / 三阶段路线；★ 每条的"可做/必须上机"边界、进门条件与验收判据 |
| [`GATE_FLOW_2026-10-08.md`](current/GATE_FLOW_2026-10-08.md) | ★★★★★ **门控任务流（可执行版 / 新）**：把 WORKFLOW_PLAN §4 的**散文门控表变成可跑代码** —— 三态（PASS/FAIL/**BLOCKED**）+ MANUAL + INFO 的语义与理由、G0–G5 的判定方法与**证据文件契约**（`mem_compare.json` / `u4/acceptance.json` / `u5/rollback_drill.json` / `iqr_dump.txt`）、能力放行矩阵（L1/L2/路径B/U4/L4）、门↔轨道映射、当前状态快照（**放行 1/5**，G3 PASS，G0/G1 FAIL，G2/G4/G5 BLOCKED）；★★ 含本轮两条硬发现 —— **`scripts/EV_MOBILE.sh` 处于"武装状态"**（`55c47b89` 死循环版，`install.sh` 会原样装上机）与 **`epmc nz` 模式里 `nreg` 是结束下标**（写错会得到"看着有输出其实是空的"假结论）。工具：`test_server/tools/{gate_flow,gate_pack_u1}.py`，上机包 `test_server/u1/` |
| [`OFFLINE_VERIFICATION_2026-10-08.md`](current/OFFLINE_VERIFICATION_2026-10-08.md) | ★★★★★ **离机验证报告（新）**：★★★ **CJK 真的画出来了**（evas buffer 引擎 + qemu-arm-static，中文/日文/生僻字全部出字）并修正 S5「必须显式指定族名」的过头表述；★ 脚本 CI 3 FAIL→0 + 执行位补齐；★★ **两个 p7 补丁全部定性**（`p7_patched` = 复位期 DACR 写入被改成未定义编码，**不可刷**；`lutmod` = 第 4 个 LUT 缓冲 `0x81115200`→`0x97600000` **Linux CMA 区内**，并挖出选择器 VA `0x803837D0`）+ `scripts/EV_MOBILE.sh` 仍是社区死循环版（**上机前 P0 检查项**）；★ **p3 不是全零**（与 p2 共享 100% 记录页指纹）⇒ 备份悬案改写 |
| [`SLP_CONTAINER_FORMAT_2026-10-08.md`](current/SLP_CONTAINER_FORMAT_2026-10-08.md) | ★★★★★ **SLP 固件容器格式全解（U12 结案）**：48B 头 + 16B 标签 + **N×24B 记录表** + 连续镜像；校验 = **JAMCRC**（10/10 命中，standard 10/10 不中）；**无签名** ⇒ **可离线重打包**（附配方）；★ 三方一致性证明（SLP img5 = 机上 p7 分区 = `5fc4824f…`）|

| [`P7_EFS_MODULE_2026-10-08.md`](current/P7_EFS_MODULE_2026-10-08.md) | ★★★★★ **p7 的 EFS 模块逆向（新）**：Ghidra 伪代码 + objdump + 引用面脚本 ⇒ ★ **EFS = 一个 15,144 B 函数 `FUN_000765b0`**（日志标签 `CAP_EFS::AdjMainFunc`，源文件 `CapAdjIf.cpp`，类 `CEfsController`），含 17 条命令（`init/g_test/do_all/nand_write/nand_write2/nand_clear/rdnand/horizon_test…`）与校准系数表；★★★ **决定性：它的 `nand_write` 写的是 MMIO `0x85601000`（4×32-bit @ 偏移 `0x3e/0x42/0x46/0x4a`），不是 eMMC 分区** ⇒ **推翻**"p8 = EFS 持久化区"的推断、**p8 的 U-a 从"未决"变"已答"**；★ 顺带记录两个工具坑（Ghidra 索引的 `out_line` 是函数序号；p7 日志宏可用"模块名槽"反查同模块函数）|
| [`P8_ZERO_INVESTIGATION_2026-10-08.md`](current/P8_ZERO_INVESTIGATION_2026-10-08.md) | ★★★★ **p8（rtos_data）全零问题结案（新）**：★ 六条独立硬证据 ⇒ **最可能"从未被写入"，属设计如此而非故障**（`parttab` 里 `image=none` + 无挂载点 + 升级链不含 p8 + 无 Linux 使用者 + 未写页读 0x00）；★★ **排除一处误报** —— `delta.ua` 引用的 `/dev/mmcblk0p80/p81` 是**三星手机分区表遗留**（BOOTLOADER/TZSW/PARAM/CSC），与 NX500 的 p8 无关 ⇒ **Linux 侧引用者归零**；★★ 新发现 p7 侧 **EFS（校准/NAND）字符串指针池**（`0x78FE0`，被 **165 处 LDR** 真实引用，含 `CAP_EFS`/`AdjMainFunc`/`InitialCalibration`/`EfsOffset,V1Coeff,...`）；★ 给出 **上机一次只读即可定案** 的路径 + 写死的判据表（`/proc/diskstats` 的 p8 **写入扇区==0 ⇒ 定案**）|
| [`OFFLINE_TRACK_SUMMARY_2026-10-08.md`](current/OFFLINE_TRACK_SUMMARY_2026-10-08.md) | ★★★★★ **离机轨 D1–D8 执行总结（新）**：八项全部执行完（全程离线）；★ 一项**推翻旧结论**（D1 U11 旧入口被证伪）、两项**证伪旧假设**（D4 名字非整串存储 / D5 旧口径含 667 条重复）、一项**改了产品代码并实测**（D7）、一项**收口资产风险**（D6）、一项**准备拆仓**（D8）；含新增资产索引 + 与门控/上机轨的衔接 |
| [`UI_PAGES_OFFLINE_RENDER_2026-10-08.md`](current/UI_PAGES_OFFLINE_RENDER_2026-10-08.md) | ★★★★ **原生 UI 五页离线预渲染（新）**：相机自带 evas **buffer 引擎**出 **5 张 720×480 PNG**（`raw8/repro/ui_page_p1..p5.png`），中文**零 tofu**、全流程 **70 次 `font_set`**；★ 诚实标注 = **降级绘制**（`rect`+`text` 复现信息结构，**非**真实 `elm_*` 控件，因离线 chroot 里 elementary 初始化链不可稳定通过）；★ 布局数值证据：P2 的 7 行 × 52 px 在 480 高屏内刚好放下 |
| [`FW_UPGRADE_VERIFY_CHAIN_2026-10-08.md`](current/FW_UPGRADE_VERIFY_CHAIN_2026-10-08.md) | ★★★★★ **固件升级校验链全解（新）**：★ **无签名/证书校验**；机型校验 = 16 B `project` 串（`NX500`）；版本校验只在 App/`dfmsd` 层且**只拦降级**；★★ **「改内容 + 重算该段 JAMCRC + 保持 len/offset/flags/project」的 SLP 在校验层不会被拒**；★★ **入口强度不同** —— 相机 UI 用 `flag=1`（**逐段 CRC**），而 **`st firmware up` 无 CRC、无版本比较**；校验点清单 C1–C8 + 入口 E1–E7；附 `verify_slp.py` 复算 10 段 JAMCRC **全 PASS** |
| [`D1_U11_STATIC_ATTACK_2026-10-08.md`](current/D1_U11_STATIC_ATTACK_2026-10-08.md) | ★★★★★ **U11 3D LUT 静态攻坚（新）**：★★ **推翻**旧入口 —— `0x803837D0`/`0x80383800` **无 BL/BLX 调用者、非指针、Ghidra 判为数据** ⇒ 只凭 prologue 的旧结论不成立；★ 真引用面 = 两张数据区指针表（`0x80382B00` 12 项 / `0x80382C5C` 6 项）+ 消费函数 **`FUN_003829a4`**（按 BV 档位选指针并写 `[obj+0xd8]`）；★ **可证伪表长假设**（槽 `0x4D00` = 60 B 头 + 17³×4）+ 中点偏色三假设；★ 类归属：`0x38xxxx` 区**无 vtable** ⇒ 新入口应改走 `CBackend_3dlut*` 类（`0x11xxxx`/`0x19xxxx`）|
| [`MCB_COMMAND_ENUM_TABLE_2026-10-08.md`](current/MCB_COMMAND_ENUM_TABLE_2026-10-08.md) | ★★★★ **MCB 命令号×名字 静态全表（新）**：枚举表 = 导出函数 `capture_command_string`（`libcapture-fw-prod.so` VA `0x511e0`，2152 B），经 `mcb_debug_set_command_name_function` 注册；**8 域 68 条**（比旧采样 +28，零冲突）；★ **证伪**"名字不是整串存储"；机器可读表 `raw8/repro/mcb_command_enum_table.txt` |
| [`P7_CODE_MAP_COVERAGE_2026-10-08.md`](current/P7_CODE_MAP_COVERAGE_2026-10-08.md) | ★★★★ **p7 代码地图覆盖率提升（新）**：★ **旧 48.21% 含 667 条重复计入**（去重基线 **44.16%**）；主力 **广义 RTTI**（typeinfo vptr 签名校验，565→1047 类，覆盖全镜像）⇒ 旧口径 **67.08%**、去重 **63.03%**、含推断 78.71%；★ 纠正"②Thumb 序言"实为 **ARM 序言**（p7 基本无 Thumb）|
| [`D7_NXFILMUI_CJK_REBROADCAST_2026-10-08.md`](current/D7_NXFILMUI_CJK_REBROADCAST_2026-10-08.md) | ★★★★ **nxfilmui 反哺 CJK 结论（新）**：v4 新增 **`apply_label_font()`**（`elm_object_part_text_get` → `evas_object_text_font_source_set/_font_set`）+ **`g_ascii` 默认 1→0（中文可用）** + `ascii` 降级开关；★ 新探针 `nxlabel_probe` 用**同款调用序列**实测 **PASS**（11 项出字、负对照未设字体 = 0×0 零墨）；★ `check_abi.py` 新增第三白名单来源 `cjk_render.arm` |
| [`D8_FORK_PREP_2026-10-08.md`](current/D8_FORK_PREP_2026-10-08.md) | ★★★ **拆仓准备（新）**：落地 `VERSION`（2.88.0-metol.1，含"相机端路径保持 `/opt/usr/nx-ks/`"）+ `LICENSE`（AGPL-3.0 全文）+ `ATTRIBUTION.md`（血缘表 + 发布前必做）+ `.github/workflows/scripts-ci.yml`；CI 实测 `PASS (0 fail / 1 warn)`；★ 8 步清单 4 步已落 / 4 步待授权，附迁移命令 |

---

## 2. archive/ — 历史归档（结论可能已被取代，仅作参考）

2026-10-05 / 10-06 的阶段性成果报告与调查报告。**含已被后续推翻的结论**，
例如：mod_gui「只认 13 键」（实为 4 keysym）、p6/p13「主/备份内核」（实为两个不同构建）。
**不要**直接从这些文档取结论做决策 —— 先对照 `current/ERROR_CORRECTIONS_2026-10-07.md`。

目录内另有 `_2026-10-06_purged/`：2026-10-06 当晚即已作废的 3D LUT 探索文档。

---

## 3. evidence/ — 逆向证据片段

| 目录 | 内容 |
|---|---|
| [`evidence/p7/`](evidence/p7/) | p7 固件 Ghidra 导出的关键片段（寄存器、页表、capdtm）|
| [`evidence/discovery/`](evidence/discovery/) | 3D LUT 发现期的反汇编脚本与中间产物 |

---

## 4. 快速导航（按问题找文档）

| 我想…… | 先看 |
|---|---|
| **一次看清全部逆向进度 / 对外介绍本项目** | `current/RE_PROGRESS_2026-10-08.md`（单文件收口） |
| 弄清项目现在能做什么 / 不能做什么 | `current/HANDOVER_2026-10-07.md` |
| 知道哪些旧结论是错的 | `current/ERROR_CORRECTIONS_2026-10-07.md` |
| 找魔灯固件的技术突破口 | `current/FIRMWARE_BREAKTHROUGH_2026-10-07.md` |
| 搞清**相机系统菜单**怎么渲染 / 能不能改 | `current/CAMERA_MENU_ARCHITECTURE_2026-10-07.md` |
| **开发相机 App / 复用官方 UI 能力** | `current/CAMERA_APP_STRUCTURE_2026-10-07.md` |
| **搞懂刷机原理 / 本地刷固件** | `current/ILAUNCHER_FIRMWARE_FLASH_2026-10-07.md` |
| 用 3D LUT 的 API | `current/3DLUT_API_GUIDE.md` |
| **在 PC 上分析固件 / 跑相机二进制 / 拿 rootfs** | `current/UNBLOB_WSL_QEMU_2026-10-08.md` |
| **没有相机也想跑相机用户态（零 WSL）** | `current/QEMU_S4_AND_ENV_CLEANUP_2026-10-08.md` |
| **还有哪些东西没搞清 / 下一步打哪** | `current/UNKNOWN_STRUCTURES_AND_PROJECT_FORK_PLAN_2026-10-08.md` |
| **要不要改名、要不要拆仓** | 同上 §3 |
| **Tier 1 做完了吗 / 固件地址面到底多大** | `current/TIER1_AND_TIER3_OFFLINE_2026-10-08.md` |
| **现在到底能改出什么（含 NX-KS 全部功能）** | `current/FIRMWARE_FEATURE_SPACE_2026-10-08.md` |
| **配方 / 3D LUT 的原生 UI 怎么设计** | 同上 §3.2 |
| **不上机时 QEMU 能替我们验什么** | `current/QEMU_S5_OFFLINE_USERSPACE_2026-10-08.md` |
| **哪些旧判据被推翻了** | `current/TIER1_AND_TIER3_OFFLINE_2026-10-08.md` §2.3（铁律 116）、§3.3（Q3 前提）+ `current/ERROR_CORRECTIONS_2026-10-07.md` |
| 查历史踩过的坑 | `archive/`（对照修正报告）|
| 看原始逆向证据 | `evidence/` |
