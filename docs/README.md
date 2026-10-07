# NX-KS2 文档索引 / Documentation Index

> 本目录按**时效**分区，避免"旧结论淹没新结论"。
> 更新：2026-10-07 · 分支：`nx-ks2`

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
| 弄清项目现在能做什么 / 不能做什么 | `current/HANDOVER_2026-10-07.md` |
| 知道哪些旧结论是错的 | `current/ERROR_CORRECTIONS_2026-10-07.md` |
| 找魔灯固件的技术突破口 | `current/FIRMWARE_BREAKTHROUGH_2026-10-07.md` |
| 搞清**相机系统菜单**怎么渲染 / 能不能改 | `current/CAMERA_MENU_ARCHITECTURE_2026-10-07.md` |
| **开发相机 App / 复用官方 UI 能力** | `current/CAMERA_APP_STRUCTURE_2026-10-07.md` |
| **搞懂刷机原理 / 本地刷固件** | `current/ILAUNCHER_FIRMWARE_FLASH_2026-10-07.md` |
| 用 3D LUT 的 API | `current/3DLUT_API_GUIDE.md` |
| 查历史踩过的坑 | `archive/`（对照修正报告）|
| 看原始逆向证据 | `evidence/` |
