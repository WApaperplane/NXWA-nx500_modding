# NX-KS2 功能矩阵（UI 覆盖基线）

> 2026-10-06 · 用途：**P7 功能设计的输入**。P7 的 UI 必须 100% 覆盖本表，且不破坏任何现有项。
> 铁律约束：★ 标签 ≤6 全角字符｜★ 禁装饰横线（会挤掉真字）｜2 列网格｜单页 ≤24 按钮

---

## 一、现有功能全集（NX-KS2 v2.88 · 社区基线）

### 1.1 主菜单（`gui_tpl.NX500`）— 6 项
| 标签 | 目标 | 备注 |
|---|---|---|
| 延时摄影 | `gui_tl.NX500` | mod_lapse |
| 实用功能 | `gui_func.NX500` | 12 项子菜单 |
| 对焦 & 配置文件 | `gui_focus.NX500` | 6 项 |
| 系统设置 | `gui_settings.NX500` | 7 项 |
| 休眠 | `hibernate.sh` | |
| 远程控制 | `nx-rc.sh` | checkbox |
| IP: %%IP%% | `telnet_toggle.sh` | 动态标签 |

### 1.2 实用功能（`gui_func`）— 10 项
| 类型 | 标签 | 命令 | 状态 |
|---|---|---|---|
| checkbox | Remote Save | `rem.sh` | 社区 |
| button | Video Bitrates | `@gui_br` | 社区 |
| button | ZoomZoom | `zoomzoom.sh` | 社区 |
| button | Mod Resolutions | `@gui_res` | 社区 |
| button | Batch Recording | `brec.sh` | 社区 |
| button | HDR | `1HDR.sh` | 社区 |
| button | Mod v2.88 | `ver.sh` | 社区 |
| checkbox | Camcorder Mode | `camcorder_mode.sh` | 社区 |

### 1.3 分辨率（`gui_res`）— 8 项（全部 checkbox）
`DC as UHD` / `UHD as DC` / `DC as 2.5K` / `UHD as 2.5k` /
`DC as 1080p` / `UHD as 1080p` / `VGA as DC` / `VGA as UHD`

### 1.4 对焦 & 配置（`gui_focus` + `gui_profiles`）— 12 项
| 标签 | 命令 |
|---|---|
| Focus Stacking | `fstack.sh` |
| Focus Buttons | `focus_buttons` |
| Profiles | `@gui_profiles` |
| Focus-Pull Speed | `fpspeed.sh` |
| Save/Load EV+UP | `save_UP.sh` / `EV_UP.sh` |
| Save/Load EV+DN | `save_DOWN.sh` / `EV_DOWN.sh` |
| Save/Load FullBackup | `FullSave.sh` / `FullLoad.sh` |

### 1.5 系统设置（`gui_settings`）— 7 项（全部 checkbox）
| 标签 | 命令 | ⚠️ 备注 |
|---|---|---|
| Silent Shutter | `rolling_shutter.sh` | |
| OFF menu-button | `z_button.sh` | |
| No Rec Limit | `r-limit.sh` | |
| Refocus on Boot | `refocus.sh` | |
| No Lens Release | `nolens.sh` | |
| Enable Bluetooth | `bt.sh` | ★ **mod 初始化唯一触发点** |
| Overlay | `ov.sh` | |
| Uninstall Mod | `uninstall.sh` | ★ 危险 |

---

## 二、我们新增（NX-KS2 88 分支）

### 2.1 FilmLab胶片仿真— ✅ 实机全通
| 标签 | 命令 | 状态 |
|---|---|---|
| 胶片配方 FilmLab | `@gui_filmlab.NX500` | ✅ 动态生成，9 配方 |
| 配方引擎命令 | `list/show/apply/preset/reset/quick/dump/slots/wb/wbdump/cycle/mkgui` | ✅ 11 个子命令 |
| 配方库 | SD 卡 `/mnt/mmc/filmlab/recipes.json` | ✅ 数量不限 |
| Web 相册 | SD 卡同步 + `push.sh` WiFi 推送 | ✅ |
| PC RAW 管线 | `m1_raw.py` 半尺寸 1.2s 出16bit TIFF | ✅ |

### 2.2 ISP 调参（3D LUT / EP）— ⏳ **本轮新做，UI 尚未挂载**
| # | 功能 | 命令 | 状态 |
|---|---|---|---|
| N1 | ★ **4 档内置色彩切换** | `3dlut_preset.sh <0-3>` | ⏳ **待实机验证（G3）** |
| N2 | `SelCbCr_ch` 通道/模式设置 | `3dlut_ch.sh <0-3>` | ⏳ 取值表未解 |
| N3 | 3D LUT 状态读回 | `3dlut_stat.sh` | ⏳ `+0x008` 保持 1 = 已启动 |
| N4 | EP 寄存器读侧（诊断） | `epreg.arm` 只读 | ✅ 可用 |
| N5 | ★ **USB 有线安全通道** | 装 Dropbear SSH | ⏳ 社区方案已定位（见 `USB_SAFE_CHANNEL`）|

### 2.3 诊断/维护（新增）
| # | 功能 | 命令 | 状态 |
|---|---|---|---|
| D1 | ★ **`iqr` 运行时快照** | `iqr_dump.sh` | ✅ 197 行表，**判断生效的唯一客观判据** |
| D2 | FilmLab 验证 | `flab-verify.sh` | ✅ 已在 |
| D3 | 备份完整性校验 | `emmcbackup.py verify` | ✅ 10 分区 |
| D4 | p7 单分区回滚 | — | ❌ **未验证（G5）** |

---

## 三、P7 功能设计要新增的（本次设计目标）

### 3.1 设计原则
1. ★★ **零破坏**：所有 P7 功能**新增**独立子页，**一行不改**现有 6 个菜单项的语义
2. ★ **危险隔离**：所有 destructive 操作集中在单独一页，且**默认需二次确认**
3. ★ **状态可见**：每个 p7 操作都要有读回/校验，不做"写了不知道成没成"
4. ★ **降级可用**：即使 p7 通道失败，菜单其他部分不受影响

### 3.2 P7 功能页设计（4 页）

#### 页 1：`gui_p7.NX500` — P7 状态与诊断（只读，安全）
| 标签 | 命令 | 读什么 |
|---|---|---|
| P7 状态 | `p7_status.sh` | 版本 / 校验和 / 是否官方原版 |
| 备份校验 | `p7_verify.sh` | 与 PC 侧 md5 比对 |
| 色彩状态 | `3dlut_stat.sh` | 当前 3D LUT 档位 + 5 个寄存器 |
| 恢复基线 | `p7_restore_baseline.sh` | ★ **一键写回官方基线** |

#### 页 2：`gui_p7color.NX500` — 色彩方案（A 线主交付）
| 标签 | 命令 | 说明 |
|---|---|---|
| 标准 | `3dlut_preset.sh 0` | `0x810fd100` |
| 黑白 | `3dlut_preset.sh 1` | `0x81101e00`（线性） |
| 电影 | `3dlut_preset.sh 2` | `0x81106b00` |
| 肤色 | `3dlut_preset.sh 3` | `0x81115200` |
| 通道设置 | `@gui_p7ch` | SelCbCr_ch 子项 |
| 回读验证 | `3dlut_stat.sh` | ★ 每步都要能验 |

#### 页 3：`gui_p7flash.NX500` — 固件刷写（★★ 高危，独立隔离）
| 标签 | 命令 | 保护 |
|---|---|---|
| 查镜像 | `p7_checkimg.sh` | 校验 md5 + 大小 |
| 备份p7 | `p7_backup.sh` | ★ 强制先备份 |
| 刷写 SLP | `p7_flash_slp.sh` | ★★ 需 `popup_ok` 二次确认 |
| 官方恢复 | `p7_recover_official.sh` | ★★ 需输入确认词 |
| 单区回滚 | `p7_rollback.sh` | ❌ **未验证，菜单项默认隐藏** |

#### 页 4：`gui_p7dev.NX500` — 开发诊断（不进主菜单，从 IP 入口进）
| 标签 | 命令 | 说明 |
|---|---|---|
| 读取样| `epreg.arm` | EP 只读 |
| iqr 快照 | `iqr_dump.sh` | ISP 运行时 |
| SMB 探测 | `cmaprobe.arm` | CMA 内存 |
| 回滚测试 | — | ★ 留空直到 G5 验证 |

---

## 四、菜单树（完整）

```
gui_ini.NX500（主菜单，7 项）
├── 延时摄影●社区
├── 胶片配方●我们✅　→ gui_filmlab.NX500（动态 9 配方）✅
├── 实用功能●社区 → gui_func.NX500（10 项）
├── 对焦配置 ●社区 → gui_focus.NX500（6 项）→ gui_profiles.NX500（6 项）
├── 系统设置 ●社区 → gui_settings.NX500（8 项）
├── ★P7 固件 ●新增 → gui_p7.NX500（4 项）★默认隐藏，安装后才出现
│├── P7 状态  → gui_p7color.NX500（色彩，6 项）
│├── 刷写固件 → gui_p7flash.NX500（5 项，★★ 高危）
│└── 开发诊断 → gui_p7dev.NX500（4 项，主菜单不暴露）
├── 休眠       ●社区
├── 远程控制   ●社区
└── IP: %%IP%% ●社区

★ 保险设计：p7flash 页只在 p7flash.ok 标记文件存在时显示（安装成功才出现）
★ 且 mod 卸载脚本必须清掉 p7 侧的所有改动
```

---

## 五、覆盖度自检（P7 设计必须满足）

| 检查项 | 状态 |
|---|---|
| 现有 6 个主菜单项**语义零改动** | ✅ 设计约束 |
| 社区全部 8 个 `gui_*` 页面**全部保留** | ✅ 已列入矩阵 |
| FilmLab 9 配方动态生成**不受影响** | ✅ `mkgui` 独立 |
| 新功能全部挂在**新增页**，不改旧页 | ✅ 设计约束 |
| 高危操作独立成页 + 二次确认 + 默认隐藏 | ✅ 设计约束 |
| 标签全部 ≤6 全角字符 | ✅ 逐项已核 |
| 单页 ≤24 按钮 | ✅ 最多 12 项 |
| 无装饰横线 | ✅ 全部避开 |

⇒ ★★ **结论：P7 功能作为第 5 个主菜单项挂载，与现有 6 项平行，物理隔离，互不影响。**
⇒ ★ **唯一跨界点**：`gui_p7flash` 会写 p7 分区，这是**唯一**超出"用户数据"边界的操作，
　 因此它必须（a）独立页、（b）二次确认、（c）安装标记门控、（d）卸载时清理。