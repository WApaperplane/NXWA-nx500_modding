# NX-WA 2.88.0-nxwa.2

> 基于 2.88.0-nxwa.1：**全 7 维 PW 一键直推达成**（A2 通道）+ 投递链修订 + 大量逆向成果。
> 构建自 commit `77173c8`（分支 `nxwa`）。

## 这个包是什么

**SD 卡安装包**：解压到 SD 卡根目录 → 插入相机 → 自动安装（首次）/ 增量同步（已装过）。

- 支持固件：**NX500 1.12** / **NX1 1.41**（其它版本会被拒绝）
- 已装过再插卡 = **增量同步**：只覆盖不删除，**永不误卸载**；SD 上的 `scripts/` 母本保留
- 卸载请用相机菜单里的 `uninstall.sh`
- 安装完成后，在设置里**开一次蓝牙**即开始初始化

## ★ 本版亮点（相对 2.88.0-nxwa.1）

| 能力 | 说明 |
| --- | --- |
| ★★ **全 7 维 PW 一键** | `filmlab.sh apply <配方>`（或 `pwpush <配方>`）：R/G/B/HUE/SAT/SHARP/CON **一次全部直进 ISP**——A2「档位池直写」通道（`0x134..0x13B`），上机实测**逐维精确命中**。**需 NXWA-A2 p7 固件**（见「诚实边界」） |
| **投递链修订** | T2 安装/回滚脚本去 `restart`（10-13 实测：restart 会卡死整机）；新增 **P5 前置挂载三件套**（`t2_premount.sh` + `dicam_p5_install/rollback.sh`，就绪待用） |
| **逆向成果入库** | PW 全链解析：7 维 UI 值项 id（`0xDC..0xE2`）、菜单面结构（`_INIT_105`/选项表）、`0xF00xx` 编码（=`0xF0000`+枚举）、`.mo` 文案链（gettext）——详见 `docs/current/UI_R1*` |
| 门控与证据 | 门控 G1–G4 复测 FAIL=0；A2 回读/功能验证证据入 `raw8/gates/a2/` |

## ★ 诚实边界（务必先读）

- ★★ **全 7 维一键依赖 NXWA-A2 固件**：`slp_a2_p7_v117.bin`（md5 `44b61efc0625874b62ef6a45517ffda8`）；p7 段 `p7_a2.bin`（md5 `712c6fd0a49371ec05ce94c367b0d5c7`）。**固件体积（352 MB SLP）超 GitHub 分发限制，不经本 Release 提供**——请从项目渠道获取并**自担风险**。
- **未刷 A2 的机器**：`apply` 的「直推段」静默无效（旧固件对 `0x134-0x13B` 拒收，不会崩）——其余功能不受影响；全维效果请继续用「**画面向导 → 自定义1**」保底。
- **3D LUT**：预览可直灌；**成片需后处理**（ksfilm）。「成片直灌」为死路（已实测）。
- **菜单是 mod_gui 覆盖层**：点击即退，不能滚动对比；只取代不迭代。
- **长按 / 连击 / 组合键架构性不可得**（内核先消费按键）⇒「一键」上限 = 一次按键一个动作。
- 配方（`scripts/filmlab/recipes.json`）为 **NX500 专属**；NX1 上 `EV+AEL` 自动回退社区原版长录像脚本。
- A2 固件为 **NX500 专属**（NX1 无对应构建）。

## 安装三步

```
1. 解压本 zip 到 SD 卡根目录（得到 install.sh / info.tg / nx_cs.adj / scripts/ ...）
2. 插入相机 → 自动执行安装/同步 → 弹窗提示 → 自动重启
3. 拔卡；在相机设置里开一次蓝牙 → 初始化完成
```

## 校验

```
md5: 812fec339ce4cf11f3cb7c7593b5abaa   NX-WA-2.88.0-nxwa.2.zip
```

包内 `NX-WA-MANIFEST.txt` 含**逐文件 md5**、版本号与构建提交（本包构建自 commit `77173c8`，分支 `nxwa`）。

## 本版变更台账

- `scripts/filmlab.sh`：`pw_direct` → A2 八连发（`0x134..0x13A` 原始值 + `0x13B` 触发）；弃用 `PWID_*`/编码依赖
- `scripts/dicam/`：**新增** `t2_premount.sh`、`dicam_p5_install.sh`、`dicam_p5_rollback.sh`；`dicam_patch_install/rollback.sh` 去 restart
- `VERSION`：`2.88.0-nxwa.1` → `2.88.0-nxwa.2`
- 文档：`docs/current/` 新增 UI_R0 / UI_R1A–C / UI_R1_SUPPLEMENT / UI_R2R3_DESIGN / T2_DELIVERY_REVISION / A2_READBACK_VERDICT / MEM_INJECTION_EVAL / NATIVE_UI_ROADMAP（10-15）、A2 验证证据等
