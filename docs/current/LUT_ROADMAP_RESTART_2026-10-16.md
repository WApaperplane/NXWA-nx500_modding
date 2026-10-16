# LUT 路线重启方案（2026-10-16）

> **背景**：LUT 线于 10-09 冻结（工具链落地 + U6 波待上机）；A2/PW 线 10-15 达成后重启（用户指令：「LUT 路线还是要再提上日程了」）。
> **输入**：`LUT_PIPELINE_DESIGN_2026-10-09`（链路）、`3DLUT_TABLE_FORMAT_2026-10-08`（表格式）、`3DLUT_VIEW_STILL_ISOLATION_2026-10-08`、`P7_RECLAIM_COUNTERMEASURE_2026-10-09`（守护）、`3DLUT_APPLY_PATHS_2026-10-08`（线路）、`test_server/u6/runbook.txt`。
> **性质**：现状盘点 + 资产修复（本日已执行）+ 路线设计 + 上机批设计。

---

## 0. 结论（先读）

1. **资产已修复**（本日）：3 个部署产物从 mod 工作副本恢复入库 + **2 个缺失工具重建**（`cmasafe.arm` / `lutsentinel.arm`，chroot 冒烟 PASS）——`deploy_luts.py` 的推送链**恢复完整**。
2. **三条路线**：
   - **R-A 保底（已通）**：ksfilm 后处理（取景器不动，成片定稿）。
   - **R-B 主线（待上机终验）**：CMA 直灌 LUT1 + `lutsentinel` 守护 → 取景器所见即所得；成片是否跟随 = U6 §[6] 判据。
   - **R-C 进阶（★ 新契机，三个离线候选）**：**表进「p7 档位池」**——从根上消灭「被抢回」：
     - **C1 刷机式**：改 p7 镜像内静态表池（镜像内现成 20+22 槽）→ 「LUT 固件包」（复用 A1/A2 刷机链）。**纯离线可做。**
     - **C2 运行时通道**：`st cap mem`（p7 T-Kernel 调试通道，能力待验证）写运行时池 → 免刷机换表。
     - **C3 补丁式**：p7「表写入器」微补丁（A2 V3 式：从 CMA 拷 19652B 到档位池槽 + 触发）——离线设计 + QEMU 验证。
3. **近期执行序**：U7 上机批（R-B 终验 + E1 sel=1 首测 + 守护实测）；同时 C1/C3 离线开工。
4. **待决策 3 项**（§5）。

---

## 1. 现状盘点

### 1.1 链路能力矩阵

| 环节 | 状态 | 证据 |
|---|---|---|
| `.cube` → 硬件表（4913×4B，槽 0x4D00） | ✅ 已解+工具 | `3DLUT_TABLE_FORMAT`（逐字节自证）；`test_server/isp/nx3dlut.py` |
| 表推送（FTP + md5 清单） | ✅ 落地 | `test_server/lutpipe/deploy_luts.py build/push` |
| CMA 落点安全闸（四查） | ✅ 落地 | `u6/cmasafe.c`（范围为二 CMA 区、黑名单 `0x94000000+0x5000`、4KB 对齐、全零） |
| 写入通道（sel=0 厂商通道） | ✅ 历史验证 | `lutapi.arm sel=0`；`lutload.arm restore` 常备 |
| **取景器显示（View）** | ◐ **待上机终验** | U6 §[4] R3-A/B（identity 中性 / Portra 风格） |
| **成片（Still）** | ❓ **待上机判据** | U6 §[6]：不半按拍 1-2 张，成片 vs 取景器比对 |
| 抢回对策（双通道 + 守护） | ✅ 设计+产物就绪 | `P7_RECLAIM_COUNTERMEASURE`；`lutsentinel`（**从未上机**；E1 = sel=1 首次实测） |
| 一键操作 | ✅ 落地 | `lutpick.sh list/apply/off/status`（+`--ch1/sentinel`） |
| 保底后处理 | ✅ 已通 | ksfilm（4 配方，跨环境逐字节一致） |

### 1.2 关键事实（引用）

- **表格式**：4913 项 × 4B `{R,G,B,pad=0}`，索引 `((B*17+G)*17+R)*4`，**槽步长 `0x4D00`**（19712B）。
- **表池三处**：
  - **镜像内静态池**（`p7_full.bin`，VA `0x808847C0` 起，Block A 20 槽 + Block B 22 槽）——**可直接离线读写**；
  - **运行时池（View/Still）**：标准 `0x810FD100` / 黑白 `0x81101E00` / 电影 `0x81106B00` / 肤色 `0x81115200`（镜像外 BSS）；
  - **MCB 池**：`0x813D8800 / 0x813DD500 / 0x813E2200 / 0x813E6F00`。
- **一致性**：「标准」表在镜像静态池与运行时 `0x810FD100` **逐字节一致** ⇒ 静态池 = 运行时池的内容源（复制路径待精确定位）。
- **p7 只用 LUT0**（View/Still/MCB 的 `_load` 全 `sel=0`）⇒ 我们的表放 LUT1（`sel=1`）不被覆盖；抢回只改 `Cfg.SelLUT`（一个寄存器写）⇒ `lutsentinel` 恢复。
- **CMA 两个合法区**：`0x8f800000..0x94000000` / `0x94000000..0xa6000000`；事故黑名单 `0x94000000+0x5000`。

### 1.3 资产与缺口

| 件 | 路径 | 状态（md5 短） |
|---|---|---|
| `cmapick2.arm` / `lutapi.arm` / `lutload.arm` | `test_server/sysarch/` | ✅ **本日恢复入库**（`2539e765` / `c0f81bee` / `a32dfd7f`） |
| `cmasafe.arm` | `test_server/u6/` | ✅ **本日重建**（`592db890`，6,320B） |
| `lutsentinel.arm` | `test_server/lutpipe/` | ✅ **本日重建**（`bc7c2f72`，10,920B） |
| `lutpick.sh` / `deploy_luts.py` / `nx3dlut.py` | `lutpipe/` / `isp/` | ✅ 在位 |
| 表 `.bin` 包（`build/luts/*.bin`） | — | ❌ **缺**（需 `.cube` 源；见 §5-D2） |
| `.cube` 源（Kodak 6 张等） | — | ❌ 本机无 |
| U6 实验包（runbook/cmasafe.c/u6_lut.sh 等） | `test_server/u6/` | ✅ 在位（runbook 22KB） |

---

## 2. 本日修复动作（盘点→补齐，全部离线）

1. **产物恢复**：从 mod 工作副本 `NX-WA-2.88.0-nxwa.1/scripts/sysarch/` 恢复 3 个 arm 到仓库 `test_server/sysarch/`（md5 台账见 §1.3）。
2. **缺失重建**：新脚本 `test_server/lutpipe/build_lut_tools.sh`（相机 ABI 配方：crt0 + 直链 libc-2.13）。
   - 教训入脚本：**`-D_TIME_BITS=32 -D_FILE_OFFSET_BITS=32`**（防 time64 符号）+ **glibc 2.13 的 `clock_gettime` 在 librt**（相机自家 `st` 亦 NEEDED `librt.so.1`）。
3. **chroot 冒烟**（rootfs-112 + qemu-arm-static）：
   - `cmasafe.arm` 无参数 → usage/rc=1 ✅；带非法地址 → 完整四查逻辑输出（打印两 CMA 区）+ rc=2 ✅
   - `lutsentinel.arm --sel 0 --count 1` → 正常启动至硬件调用点（`d5_ep_open rc=-2`，无硬件符合预期）✅
4. `.gitattributes` 增 `*.arm binary`。

---

## 3. 三条路线

### R-A —— 保底（已通，零阻塞）

拍原始 → ksfilm 后处理。取景器不显示 LUT。**价值**：立刻可用的成片 LUT 工作流；`FILMLAB_WHEEL_PREVIEW` 定式的一半。

### R-B —— 主线（机制齐备，待上机终验）

```
.cube → nx3dlut → 槽表(19752B) → deploy_luts.py push → /mnt/mmc/filmlab/luts/
  → lutpick.sh apply <名>（cmapick2 落点 → cmasafe 四查 → lutapi load sel=1）
  → LUT1 生效（取景器）
  → lutsentinel 守护（p7 抢回 Cfg 后写回 sel=1）
  → 成片：U6 §[6] 判据（不半按拍 1-2 张比对）
```

- **待证**：① **E1：`sel=1` 从未被实测**（历史只有 sel=0 验证；sel=2 曾花屏——**sel=1 是全新变量**）；② Still 成片是否跟随；③ 守护在真机的行为（轮询间隔/单核负载影响）。
- **回退**：`lutpick.sh off`（identity）→ `lutload.arm restore` + 半按 → 重启。

### R-C —— 进阶：表进档位池（★ 新契机，三候选）

**动机**：R-B 的「抢回」是 p7 事件驱动的表重载——**从根上消灭它的唯一方式 = 让 p7 自己拿的就是我们的表**。

| 候选 | 机制 | 离线可做 | 优点 | 未知/风险 |
|---|---|---|---|---|
| **C1 刷机式** ★首推 | 改 **p7 镜像内静态表池**（现成 20+22 槽）→ 重新打 SLP 包 → 刷机（复用 A1/A2 链） | ✅ **全离线**（表生成器 + 镜像补丁 + SLP 打包） | 真·全程所见即所得（含拍片）；**多槽 = 多 LUT**（切档换表）；抗抢回天然成立 | 静态池 → 运行时池的复制路径需定位（离线 RE）；刷机换表（低频、可接受） |
| **C2 运行时通道** | `st cap mem`（p7 T-Kernel 调试通道）写运行时池 | ◐ **能力待验**（离线查 st 二进制 + 上机试） | 免刷机、即时换表 | `st cap mem` 是否支持**写**、写 p7 内存的限制/风险 |
| **C3 补丁式** | p7「表写入器」微补丁（A2 V3 式：外部给「CMA 源地址 + 槽号」→ p7 拷 19652B 进档位池 → 触发 load） | ✅ 离线设计 + **QEMU 可验证**（a2_qemu 模式） | 即时换表 + 抗抢回；与 A2 通道同构 | 拷贝循环代码量（~60B，A2 块 80B 同级）；DMA/cache 一致性 |

> **关键支撑事实**：镜像内静态池可直接离线读写（`3DLUT_TABLE_FORMAT` 逐字节自证）——**C1 的技术风险很低**，主要工作在「表→槽映射」与「打包链」。
> **与 A2 的关系**：A2 已证明「外部写 p7 槽」的通道模式（0x134..0x13B → 槽 + 触发）；C3 是其向「大块表数据」的自然延伸。

---

## 4. U7 上机批设计（R-B 终验，建议并入 ONDEVICE_SOP）

**前置**：门控重跑；SD 部署 `filmlab/`（工具 5 件 + `lutpick.sh` + 表包）；**相机停在菜单界面**（写表需要官方 API 安全闸放行）。

| 步 | 动作 | 判据 | 风险/回退 |
|---|---|---|---|
| 1 | `lutpick.sh list` | 列出表目录（空则先 push 表包） | — |
| 2 | `lutpick.sh apply <identity> --dry` | 落点探测 + 四查全过（不写） | 失败 ⇒ 等更安全时机（**不换地址硬上**） |
| 3 | `lutpick.sh apply <identity>`（**sel=1**） | **E1 首发**：Cfg 终态 `SelLUT=1`；取景器**中性**（无偏色） | 异常 ⇒ `off`/`lutload restore` |
| 4 | `lutpick.sh apply <Portra 400>` | 取景器出胶片风格（R3-B 目视） | 同上 |
| 5 | ★ **Still 判据**：不半按 → 直拍 1-2 张 | 成片与取景器一致 ⇒ **所见即所得闭环**；不一致 ⇒ R-A 保底/转 R-C | — |
| 6 | `lutsentinel --sel 1 --count 120`（1 分钟） | 半按/切档后画面**自动恢复**（日志有恢复行） | 频繁恢复告警 ⇒ 记录间隔 |
| 7 | 叠加观察：PW 一键 + LUT 同时开 | 记录观感（是否过强） | — |
| 8 | 回退演练：`off` + `restore` + 重启 | 画面回中性 | — |

- **纪律继承**：单会话单命令、结果 FTP 拉、`setsid` 脱离；（u6/runbook.txt 全文为准）。
- ⛔ 禁 `systemctl restart di-camera-app`。

---

## 5. 待决策

| # | 项 | 选项 | 建议 |
|---|---|---|---|
| **D-LUT1** | U7 上机批安排 | ① 独立一趟（LUT 专属，变量干净）② 并入下一批（省开关机） | 若与 P5/C-2 批同趟：**先做 P5/C-2 验证再做 LUT**（避免互相干扰） |
| **D-LUT2** | `.cube` 源 | ① 用户自备（他自有 LUT 库）② Kodak 官方免费 LUT（Portra 400 等）③ `make_cube.py` 从配方烘焙（自产） | ①+③ 并行：用户提供偏好 LUT，另用 ③ 生成测试件跑通链路 |
| **D-LUT3** | R-C 是否启动 | ① 先 C1（刷机式，纯离线，风险低）② 先验 C2（`st cap mem` 能力，快）③ 等 R-B 上机判据后再定 | **建议：C1 离线开工 + C2 顺手上机验**（两者都不阻塞 R-B） |

---

## 6. 证据与资产索引

- 设计：`LUT_PIPELINE_DESIGN_2026-10-09`（链路）、`3DLUT_TABLE_FORMAT_2026-10-08`（表格式）、`P7_RECLAIM_COUNTERMEASURE_2026-10-09`（守护）、`3DLUT_VIEW_STILL_ISOLATION_2026-10-08`（池⊆关系）
- 实验包：`test_server/u6/`（runbook.txt 22KB 全文判据）
- 工具：`test_server/lutpipe/{deploy_luts.py, lutpick.sh, lutsentinel.c, build_lut_tools.sh}`、`test_server/isp/nx3dlut.py`
- 产物：`test_server/sysarch/{cmapick2,lutapi,lutload}.arm`、`test_server/u6/cmasafe.arm`、`test_server/lutpipe/lutsentinel.arm`
- 冒烟：本日 chroot 输出（见 §2）

---
*生成：2026-10-16 · 离线完成（资产修复 + 冒烟 + 路线设计）；R-B 上机动作待放行。*
