# p7 与 di-camera-app 修改决策记录（2026-10-12）

> **定位**：把"改 p7"与"改 App"两条修改线的**选型、排序、投递、回滚、判据**钉成决策（ADR 风格）。
> 执行序看 `TASKFLOW_2026-10-12.md`；原理与地址看 `A1_P7_PATCH_PACK_2026-10-11.md` / `DICAM_MOD_DESIGN_2026-10-11.md`。
> 口径：✅ = 已证 ｜ 🔶 = 待上机 ｜ ⛔ = 明确不做 ｜ ❓ = 未验证（附验证方法）

---

## 0. 决策一览

| # | 决策 | 结论 | 依据 | 状态 |
|---|---|---|---|---|
| **D-1** | p7 修改路线 | **方案 G**（归一化器越界分支重定向 + 24B 恒等特判块），备选 H 保留 | 静态验证链闭环 + QEMU 12 边界用例 ALL PASS | ✅ 已定 |
| **D-2** | 刷机分档 | **step1 灰度先行，禁止直刷 full** | 唯一未知风险 = 零区被运行期覆盖；step1 就是该风险的探针 | ✅ 已定 |
| **D-3** | 特判块选址 | **候选 A：`0x11504`**（引导参数块尾部 254B 零区） | 字面量 0 命中；4B 对齐；备选 B `0x11010` / C `0x57xxxx` | ✅ 已定（附弃用条件） |
| **D-4** | App 修改路线 | **C-2**（`uscom`→`film` 改名 + 16B 桩），成本 13 字节 | QEMU T1–T4 全绿；不动 UI 状态机 | ✅ 已定 |
| **D-5** | ★ App 补丁投递 | **T2 bind-mount**（补丁体在 p14，init.sh 复挂）；T1 仅作首验 | ❓ 刷机大概率重写 rootfs（SLP idx6 = rootfs）⇒ T1 会被冲掉 | 🔶 已决，附判决实验 |
| **D-6** | ★ C-2 桩版本 | **v2（拼接版）为交付族**；v1 仅作首验灰度 | v1 有"短路径 + 单参数"两处别扭 | 🔶 待实现（O1） |
| **D-7** | 两线排序 | **同批上机**；序：W-1 → W-2 → W-3 → W-4 → W-5 | 机制正交（p7 分区 vs rootfs 内 app）+ T2 抗刷机 | ✅ 已定 |
| **D-8** | 明确不做 | 加第 4 自定义槽 ｜ 长列表 ｜ 全量重编 ｜ 改 State 状态机 | 见 §5 | ⛔ |

---

## 1. D-1 / D-2 / D-3：p7 修改决策（A1 方案 G）

### 1.1 背景（为什么只能改归一化器）

外部（Linux 侧）一切参数推送都经 MCB 两扇门：`SetUserDataMCB(|0x1100)` / `SetVariableDataMCB(|0x1300)`。
变量门 → p7 侧唯一处理器 = **归一化器 `FUN_00051090`**。它的域检查只认 `0x100–0x12e`，
**输出集合不含 `0x130–0x133`** ⇒ R/G/B/HUE 外部直推被拒。

替代路已穷举证伪：复刻 app 类别消息（5 路取证全 0）｜键注入（实测不生效）｜外部直推 R/G/B/HUE（上机负结论）。

### 1.2 决定：方案 G（2 处改动，28 字节）

| # | 位置 | 原内容 | 新内容 | 大小 |
|---|---|---|---|---|
| 1 | file `0x510b0` | `ea 00 00 b7`（`b 0x80051394` 拒收） | `13 01 ff ea`（`b 0x80011504`） | 4B |
| 2 | file `0x11504` | 24B 全零 | 24B 恒等特判块（`sub/cmp/bhi/str/mov/b`） | 24B |

**为什么优于上游设想**：上游方案"扩跳转表 + 补 4 个 handler"要动跳转表、4 个新 handler、
收尾代码搬迁 + 46 处 `b` 修正；本方案**表、handler、收尾全部零改动**，只新增一条越界分支的重定向。

### 1.3 风险与弃用条件

| 风险 | 级别 | 判据 | 处置 |
|---|---|---|---|
| **`0x11504` 零区被运行期覆盖** ★ 唯一真未知 | 中 | W-2 序 4：回读该区内容 | 变垃圾 ⇒ 停止，改候选 B（`0x11010`）；位置敏感 ⇒ 用 `asm_verify.sh` 改 `-Ttext` 重生成 |
| 重定向/中转编码有误 | 低 | W-2 序 5：`setvar 0x12f` 仍被拒收 | 回滚 + 复查 `asm_verify` |
| UI 判灰（版本不高于设备） | 低 | W-1 序 3 读设备版本 | 用 `slp_version_bump.py` 再提包内版本 |
| R/G/B/HUE 写后 `varlist` 变而画面无感 | — | W-5 序 3/5 | **已知边界，不在本 patch 范围**（渲染消费侧是另一层任务） |

### 1.4 回滚（三条路）

1. **原地回滚**（最省）：只动 2 处，原字节已知（`ea 00 00 b7` + 24B 零）⇒ 重打一版即回原样
2. **官方件回滚**：`slp_version_bump.py` 把官方 1.12 提到 1.17 再刷（内容仍是官方原样）
3. **分区级参照**：`raw8/emmcbak/p7.bin`（md5 `f19441df58f8c2b0116ce99773bd5143`）= p7 从未被触碰的原始态

> ★ **boot0/boot1 绝不碰**。

### 1.5 判据（写死）

- W-2：p7 分区回读**逐字节 == step1 包内 p7 镜像**（`1e0be7df…`）+ `0x11504` 区未被覆盖 + `0x12f` 仍拒收
- W-5：p7 回读 == full 镜像（`2ee98811…`）+ `probe3` readback **命中 == 目标**（`0x130..0x133`）+ `0x110` 回归不变 + 端到端画面可见变化

---

## 2. D-4：App 修改决策（路线 C-2）

### 2.1 决定

| # | 位置(file) | old | new | 说明 |
|---|---|---|---|---|
| P1 | `0x3656dc` | `"uscom\0"` | `"film\0\0"` | 命令名就地改名（**全镜像唯一引用**） |
| P2 | `0xc23a8`（= `FUN_000ca3a8` 头部） | dumper 前导字节 | **16B 桩**（v1）/ 拼接桩（v2） | handler(argc,argv) |

- 命令表项本身**不动**（名字指针仍指向那串、handler 指针仍指向 FUN 头部）——只改 8+8 字节内容
- 调用形态：`st app film <短命令>`（v1，参数 ≤19 字符）/ `st app film apply 23`（v2）
- 链路（离线已证 ✅）：`st` → SysV 队列 `0x8828` → App 线程 "shell_di_app" → 注册回调 `ui_shell_command`(0xc91a0) → App 命令表(0x449d28) → 桩 → `system()`

### 2.2 为什么不做别的

| 项 | 原因 |
|---|---|
| ⛔ 加第 4 个自定义槽 | App 内**没有** `CAP_MENU_CUSTOM_MODE_4` / `MSG_MENU_PW_CUSTOM04`（两副本全查）；要动槽位表 + 名→msg 表 + handler/计数 + 资源接线 ⇒ 为"+1 格"做真补丁，性价比不合格 |
| ⛔ 长列表（95 条滚轮） | 等于重写 View/State，撞单核红线 |
| ⛔ 全量重编 / 改 State 状态机加页 | 无源码；需求已被路线 0 + C-2 覆盖 |
| ⛔ 路线 0 单用 | `st app` 零补丁但**加不了新命令**；它是"驱动层"，C-2 才是"给驱动层加一个词" |

> **配套认知**：路线 0（`st app`，零补丁）**今天就能用** —— `st app mode m` / `st app drive bracket` /
> `st app disp lcd`，以及勘察工具 `st app uscom` / `st app uscap`（打印 UserSpec 全表）。
> C-2 只是给这个通道**加一个直达 mod 脚本的词**。

---

## 3. D-5 ★ App 补丁投递：T2 胜出（本日核心决策）

### 3.1 背景与关键事实

**SLP 容器分区表（`SLP_CONTAINER_FORMAT_2026-10-08.md`）**：

| idx | 内容 | 大小 |
|---|---|---|
| 5 | **p7 / rtos**（本方案目标） | 12,075,648 B |
| 6 | **rootfs**（LZOP，含 `/usr/apps/com.samsung.di-camera-app/`） | 280,505,658 B |

⇒ **A1 是"官方整包容器换掉 idx5"**，而 **idx6 的 rootfs 仍按官方原样放入容器**。
⇒ ❓ **推断**：走官方升级路径刷 A1 包时，**rootfs 会被重写为官方版** ⇒ **T1（rootfs 原地补丁）会被冲掉**。

> ❓ 该推断**尚未实测**（也可能"只写有差异的分区"）。**判决实验 = W-2 序 3 顺带做**：
> 刷机前后各取一次 `md5sum /usr/apps/com.samsung.di-camera-app/bin/di-camera-app`。
> 变 ⇒ 全写；不变 ⇒ 只写差异。**无论结果如何，D-5 的结论不变**（T2 都更优）。

### 3.2 两路对照

| 维度 | T1 rootfs 原地补丁 | ★ T2 bind-mount |
|---|---|---|
| 补丁体位置 | rootfs（`/usr/apps/...`） | **`/opt/usr/nx-ks/dicam/`（p14，刷机不覆盖）** |
| 抗固件刷机 | ❌ 刷机即被覆盖，需重打 | ✅ **每次开机由 init.sh 复挂** |
| rootfs 写入 | 是（原地改写，不占空间；rootfs 96% 满） | ❌ 零写入 |
| 首次安装 | 一次性动作 + 备份 + 回滚 | 放文件 + init.sh 加一行 |
| 回滚 | 按 `bytepatch.json` 逆写 | umount + 删 init.sh 一行 |
| 依赖 | 无 | **bind-mount 时序**：init.sh（bluetoothd 钩子）须早于 `di-camera-app.service`（`After=hib_ready/xorg/wm_ready/deviced`）⇒ 时序上成立，🔶 需上机验 mount namespace |
| 风险 | 中（写错字节 = App 崩，5 min 内可还原） | 低（不动任何字节；失败 = umount） |

### 3.3 决定

> **T2 为交付族；T1 仅作为首验（若 T2 的 mount 时序在 W-3 被证伪，退回 T1 并在每次刷机后重放补丁器）。**

- 补丁体：`/opt/usr/nx-ks/dicam/di-camera-app.c2`（+ 官方件备份 `di-camera-app.v1.12.orig`）
- 复挂：`init.sh` 内**带存在性判断**的 `mount --bind`（文件不在则不挂 ⇒ 幂等安全）
- 回滚：`dicam_patch_rollback.sh`（umount + 去行 + restart）
- 纪律：**绝不塞进日常增量同步链**（info.tg→install.sh 不碰 rootfs）；补丁器 = 独立、一次性、显式触发

### 3.4 判据

| 项 | 判据 |
|---|---|
| 机制 | `mount \| grep di-camera-app` 有行；restart 后画面正常（W-3） |
| 功能 | `st app film "…"` ⇒ 目标脚本执行 + `st rc=0`；`st app uscom` 不再输出 dump（W-4） |
| 回归 | `st app mode p→a` / `st app disp lcd` 与原行为一致 |
| 抗刷机 | **刷 A1 包后** `dicam_patch_status.sh` 仍显示已挂 + `st app film` 仍可用（★ W-2 后复查） |
| 回滚 | rollback 后 `st app uscom` 又可用（W-4 序 6） |

> ⚠ **失败模式**：App 崩（画面黑）⇒ telnet 仍活 ⇒ 还原（umount 或按 bytepatch 逆写）+ `systemctl restart di-camera-app`。
> ★ 记牢：unit 里 `Restart=always` **被注释** ⇒ **崩了不会自愈，必须手动拉**。

---

## 4. D-6：桩 v1 / v2

| 版本 | 语义 | 优点 | 缺口 |
|---|---|---|---|
| **v1**（现状，已生成） | `cmp r0,#2; bxcc lr; ldr r0,[r1,#4]; b system@plt` | 16B、极简、QEMU T1–T4 全绿 | 执行 `system(argv[1])` **裸命令串** ⇒ 需短路径（`/f` 符号链接）或 PATH 依赖；**单参数 ≤19 字符** |
| **v2**（交付族，待实现 O1） | `"sh /opt/usr/nx-ks/f.sh " + argv[1..n]` 拼接入静态缓冲 → `system(buf)` | `st app film apply 23` 自然可用；零 PATH 依赖；多参数 | 60–100B 汇编；需保证不越入下一函数（FUN 遗体 ~640B） |

> **决定**：v2 为交付族；**v1 用于 W-4 首验灰度**（已验证过，先证链路通），v2 紧随其后替换。

---

## 5. D-8：明确不做（本日口径）

| 项 | 原因 |
|---|---|
| 加第 4 个自定义槽（3→12） | 见 §2.2；"想多条配方位"改走 **prefman slot 0–8**（完全不经 App） |
| 95 条长列表 / 滚轮 View | 撞单核红线；替代 = 路线 0 驱动层 + 键位脚本逐格换配方 |
| 全量重编 / 状态机加页 | 无源码 |
| 用 App 解决全 7 维 | 属 p7 层（A1），App 不参与 |
| 改 App 实现键位映射 / 主菜单 IP / Web 遥控 | 已由 `EV_*.sh` / mod_gui / 原生 checkbox 解决 |

---

## 6. 未验证项（❓ 带验证方法）

| # | 未验证项 | 影响 | 验证方法 | 落点 |
|---|---|---|---|---|
| **U-1** | 刷 SLP 是否**重写全部**分区（尤其 rootfs） | 决定 C-2 持久性；决定 T1 是否可用 | W-2 序 3 顺带：刷机前后 `md5sum /usr/apps/.../di-camera-app` | `raw8/gates/dicam/rootfs_rewrite_probe.txt` |
| U-2 | T2 bind-mount 的**时序与 mount namespace** 是否成立 | 决定 T2 是否可用 | W-3 序 3（bind 原文件到自己） | `raw8/gates/dicam/t2_bind.txt` |
| U-3 | `/run/tizen-mobile-env` 的写入者（D-1 LD_PRELOAD 通道） | 备选注入通道 | W-3 序 2 | `raw8/gates/dicam/env.txt` |
| U-4 | 设备当前固件版本是否 < 1.16 | 决定 A1 包是否被 UI 判灰 | W-1 序 3 读版本 | `raw8/gates/u1/version.txt` |
| U-5 | `0x11504` 零区是否被运行期覆盖 | **A1 的核心未知** | W-2 序 4 回读 | `raw8/gates/a1/step1_readback.json` |

---

## 7. 关键地址速查（NX500 v1.12）

| 对象 | vaddr | file | 说明 |
|---|---|---|---|
| A1 重定向点 | `0x800510b0` | `0x510b0` | 越界拒收分支（改前 `ea 00 00 b7`） |
| A1 特判块落点 | `0x80011504` | `0x11504` | 254B 零区（候选 A） |
| 归一化器 | `0x80051090` | `0x51090` | 域检查 `0x100–0x12e`；跳转表 `0x510b4`；共享收尾 `0x5117c`；拒收 `0x51394` |
| C-2 名字串 | `0x36d6dc` | `0x3656dc` | `"uscom"` → `"film"` |
| C-2 桩宿主 | `0xca3a8` | `0xc23a8` | `FUN_000ca3a8`（原 uscom dumper） |
| App 命令表 | `0x449d28` | `0x439d28` | ~30 项 `{name, handler}`，`end`@`0x449e28` |
| `system@plt` | `0xadd08` | — | 桩尾调用目标 |
| `ui_shell_command` | `0xc91a0` | `0xc11a0` | App 注册回调（20B thunk） |
| 队列 key | — | — | SysV `0x8828`，消息 `{mtype; argc; 20B/槽}` |

> 映射规则：`file < 0x4384ac ⇒ vaddr = file + 0x8000`，否则 `file + 0x10000`。
> p7：`VA = 0x80000000 + file_offset`。

---
*生成：2026-10-12 · 分支 `nxwa` · 上游：`A1_p7_normalizer_patch_design.md` / `A1_P7_PATCH_PACK_2026-10-11.md` / `DICAM_MOD_DESIGN_2026-10-11.md` / `c2_qemu/RESULTS.md` / `SLP_CONTAINER_FORMAT_2026-10-08.md`*
