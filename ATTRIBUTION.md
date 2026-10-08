# ATTRIBUTION — Metol 的上游血缘与许可证状态

> 目的：**在许可证审计完成前，明确不把本项目包装成"全新原创"**。
> 每一项上游都必须有**名字 + 许可证状态 + 用在哪**。生成：2026-10-08（工作流 D8）。

---

## 1. 代码/脚本血缘

| 上游 | 用途 | 许可证状态 | 备注 |
|---|---|---|---|
| **`nx500_nx1_modding`**（本项目为其 fork） | `scripts/` 的绝大多数脚本、`info.tg`、`nx_cs.adj`、`mod_gui`、`gui_*.NX500` 菜单母本 | **AGPL**（据 fork 血缘；**需向上游 README/LICENSE 复核具体版本**） | ★ 这是**决定本项目整体许可证**的那一条：若上游确为 AGPL-3.0，则**本项目必须同为 AGPL-3.0**（已按此落地 `LICENSE`） |
| **NX-KS 2.88**（作者 **KinoSeed**） | 原始 mod 的血脉（版本号 2.88 即来自此） | ★ **待考**（未见明确 LICENSE 文件） | 产品 `VERSION` 标注血脉来源；**发布前必须联系作者或查清其声明** |
| **capstone** | 研究侧反汇编工具（`test_server/isp/`） | BSD-3-Clause（仓库内已有其 LICENSE） | 研究仓依赖 |
| **ge0rg/samsung-nx-hacks** | 机型表 / 固件格式参考 | 见其仓库（未复制代码，仅参考） | 参考，不含代码 |

## 2. 工具链（不进产品仓，仅研究流程使用）

zig 0.13.0 · binwalk 2.3.3 · unblob 26.6.4 · QEMU 11.1.0 · Ghidra 12.1.4 · arm-linux-gnueabihf-binutils
—— 均为独立工具，**不属于本项目的派生作品**。

## 3. 证据基座（不可再生资产）

`raw8/emmcbak/`（eMMC 分区备份）、`p7_full.bin`、官方 SLP 固件、相机 rootfs
—— ★ **三星原厂内容**，**不得随公开仓发布**；应放私有仓 / Release assets / LFS。
其版权归 Samsung Electronics，仅作**私有备份与互操作性研究**用途。

## 4. ★ 发布前必做（未完成，勿标"ready"）

- [ ] 复核 `nx500_nx1_modding` 上游的确切许可证与版本（决定本仓 LICENSE 是否保持 AGPL-3.0）
- [ ] 查清 **NX-KS（KinoSeed）** 的许可证声明；若不明，**联系作者取得许可或书面说明**
- [ ] 产品仓**不得**包含任何 `.uploads/fw/*`、`raw8/**`、rootfs dump
- [ ] README 顶部保留本文件链接（不得只写"原创"）
