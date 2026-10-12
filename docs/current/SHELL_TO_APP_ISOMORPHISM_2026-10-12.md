# shell → App 同构替换设计（mod 脚本面向 App 官方通道收敛）

> **定位**：把 mod 的 shell 脚本里"绕过 App、直接操底层"的做法，**分批**替换为 App 的官方命令通道。
> 本文 = 接口清单 + 映射表 + 分批路线 + 落地规范 + 判据/回滚。
> 依赖：`DICAM_MOD_DESIGN_2026-10-11.md`（App 通道原理）+ `MOD_DECISION_P7_APP_2026-10-12.md`（D-4 C-2）。
> 口径：✅ = 离线已证 ｜ 🔶 = 待上机 ｜ ⛔ = 无对应，保留 shell ｜ ★ = 本轮新增证据

---

## 0. 一句话

**不是"用 shell 调 App"，而是"让 App 当动作执行器"** ——
凡 App 有命名命令能做的事，就不要再靠「按键注入 / 裸数字 id 写属性 / 跨会话环境变量传状态」这三类脆弱做法。
App 命令名是**接口契约**（换固件大概率不变），魔数与按键码不是。

**三条收益**（都不是审美问题）：
1. **不依赖内核按键消费顺序**（铁律：内核先消费按键，注入时机不可控）；
2. **App 内部状态机自己联动**（硬写单个属性只改一个点，模式/驱动切换要改一串）；
3. **可带参数**（`st key click s2` 说不了"用 fine 质量、daylight 白平衡拍一张"，`st app` 能）。

---

## 1. ★ App 命令接口全表（2026-10-12 新解，离线）

### 1.1 顶层命令表 `@vaddr 0x449d28`（**32 条**，8B/项 `{name_ptr, handler_ptr}`）

| # | 命令 | handler | 说明 |
|---|---|---|---|
| 00 | `help` | `0xc92e0` | 用法回显 |
| 01 | `info` | `0xccf04` | 设备信息（★ 含 CES version 查询） |
| 02 | `format` | `0xccc54` | 格式化 |
| 03 | `rtc` | `0xcca24` | 子：`get` / `set` |
| 04 | `led` | `0xcc6e0` | 指示灯 |
| 05 | `test` | `0xcbefc` | 单动作测试（`finit`/`flash`/`tt`/`oor`/`vconf`/`n1`/`n2`/`c0-c2`/`r1`/`r2`/…）**慎用** |
| 06 | `show` | `0xcd0bc` | 子：`liveview` / `lock3a` / `pro_shift` / `cap` / `mov` |
| 07 | `volum` | `0xcbe30` | 子：`off` / `low` / `mid` / `high` |
| 08 | `bb` | `0xcbc60` | 子：`lcd` / `evf` / `tv` / `on` / `off` / `osd` |
| 09 | `video` | `0xcbb60` | 视频输出 |
| 10 | `isfull` | `0xcbb08` | 存储是否满 |
| 11 | `changemode` | `0xcba9c` | 子：`next` / `prev` |
| 12 | **`mode`** | `0xcb8a4` | 换拍摄模式（`m`/`a`/`s`/`p`/`auto`/`smart-pro`/`custom1`/`custom2`）★ mod 已在用 |
| 13 | `drive` | `0xcb8a4` | 驱动模式（同 handler） |
| 14 | `lens` | `0xcb7d8` | 子：`info` / `pzoom tele\|wide\|stop` |
| 15 | **`set`** | `0xcb198` | 子：`izoom 1.0\|1.2\|1.4\|1.7\|2.0` / `efs on\|off` / `sf vig\|min_h\|min_v\|war\|neg\|red\|gr\|bl` / `disp_timer 0.5\|1\|3\|5\|10` / `power_timer …` |
| 16 | `disp` | `0xcaf74` | 子：`lcd` / `evf` / `auto` ★ install.sh 已用 |
| 17 | `data` | `0xc9ddc` | 子：`save`（菜单值落盘） |
| 18 | `wifidirect` | `0xcad4c` | `start` / `stop` |
| 19 | `softap` | `0xcab1c` | 软 AP |
| 20 | **`nx`** | `0x2753b4` | ★★ **命令树根**（见 §1.2） |
| 21 | `strobe` | `0xcaae4` | 闪光灯 |
| 22 | `af` | `0xc95a8` | AF 控制（老接口） |
| 23 | `ap` | `0xc9824` | 应用相关 |
| 24 | `power` | `0xcaaa8` | 电源 |
| 25 | `lang` | `0xca8b4` | 语言 |
| 26 | `uscap` / 27 `uscom` / 28 `usetc` | — | UserSpec 表 dump / 写（**勘察工具**；`uscom` 是 C-2 改名为 `film` 的宿主） |
| 29 | `rr` | `0xc9f1c` | — |
| 30 | `flip` | `0xc9674` | 翻转 |
| 31 | `cmode` | `0xc91b4` | 子：`pre` / `pref` / `reset` / `upload` / `make` / `logon` / `logoff` |

> 表在 `0x449e28` 遇零词结束。名字串多复用相邻串尾部（如 `ap` 复用 `softap` 的尾、`nx` 紧邻 `softap`）——**这是编译器串合并，不是重复项**。

### 1.2 ★★ `st app nx …` 命令树（`nx_cmd_handler @0x2753b4`，手写 strcmp 链）

```
st app nx
├─ help
├─ mode [show,name]        → cmd_capture_mode       换拍摄模式
├─ menu <子>               → cmd_menu_handler
│    help / test-mode / format / flash / afmode / powersave on|off /
│    s2-trace on|off / capture-end-trace / full-af-box / af-box / af-box-cluster /
│    large-box / set …
├─ key <子>                → cmd_key_handler        ★ 按键的"官方注入"入口
│    show / push / release / single
├─ capture <子>            → cmd_capture_handler    ★★ 拍照族（最有价值）
│    help / single            ← 拍一张（无参数）
│    af-mode caf|auto|manual  ← AF 模式
│    quality fine|norm|raw|raw+sfine|raw+fine|raw+norm   ← ★ 质量/RAW
│    wb auto-tungsten|tungsten|day|cloud|fluorescent-w|fluorescent-n|
│       fluorescent-d|flash|custom                        ← ★★ 白平衡
│    resolution / drive / drive-unit / count / unit / basic|full / cap-ready / run / stop
├─ record <子>             → cmd_record_handler     ★ 录像族
│    start / stop / pause / resume / resolution / run / count / unit / single / basic / full
├─ timing <子>             → cmd_timing_handler
│    start / stop / free / show / save / mask|print on
├─ run / stop              → cmd_scenario_start / cmd_scenario_stop
├─ rand-move / rand-key    （厂测：随机动作/随机按键）
├─ browser / thumb / rotate （回放/缩略图/OSD 旋转）
└─ （"CAPTURE TEST: COUNT/ERROR"、"Wait S1/PB" 等为厂测日志格式串）
```

### 1.3 ★ 本轮的直接功能增益

| # | 增益 | 依据 |
|---|---|---|
| **G1** | **白平衡可脚本化** ⇒ README 里"WB 不在配方内，请机身 UI 自行调整"的**已知限制可解除** | `st app nx capture wb <9 档>` 存在（`cmd_set_white_balance`） |
| **G2** | **照片质量/RAW 可脚本化** | `st app nx capture quality fine\|norm\|raw\|raw+sfine\|raw+fine\|raw+norm` |
| **G3** | **录像 pause/resume 可脚本化**（原 NX-KS 没有） | `st app nx record pause\|resume` |
| **G4** | **可用 `nx key push/release` 替代 `st key`**（同一按键语义，但走 App 命令通道、可被 App 状态机校验） | `cmd_key_handler` 子命令 |
| **G5** | **"是否可拍"可查询**（`UI_Is_Enable_Capture_Possible`）⇒ 拍摄脚本可先判可否再动手 | `nx_cmd_handler` 调用表 |

---

## 2. 现状盘点（scripts/ 244 文件实测）

| 类别 | 命中 | 文件 | 性质 |
|---|---|---|---|
| **A. 按键注入 `st key`** | 14 处 | `1HDR.sh`(6) `zoomzoom.sh`(1) `brb.sh`(1) `nrec.sh`(2) `FullLoad.sh`(1) `timelapse.tp`/`ramplapse.tp`(已注释) | ★ **本批主目标** |
| **B. 裸数字 id 属性写 `capdtm setusr <数字> <魔数>`** | ~20 处 | `filmlab.sh`（`setusr 20 0x14000N` = PW 风格槽；`setusr 6 0x0600xx` = WB 模式）、`nx-rc/flab-verify.sh` | 部分有官方命令（WB）；PW 槽无 ⇒ 需 C-2 桥 |
| **C. 跨会话状态传参 `systemctl set-environment`** | ~30 处 | `brec.sh` `br_menu.sh` `br_set.sh` `br_up.sh` `EV_S1.sh` | mod 自有设计；非 App 范畴，属工程卫生 |
| **D. 机型分支 `st cap capt single start`** | 5 处 | `1HDR.sh` | 已是"半同构"（有 fallback 结构） |

---

## 3. ★ 映射表（现状 → 同构目标）

| # | 现状 | 落点 | 同构目标 | 批次 |
|---|---|---|---|---|
| 1 | `st key push s1 && st key click s2 && st key release s1`（拍一张） | `1HDR.sh`×5, `zoomzoom.sh` | `st app nx capture single` | **1** |
| 2 | `st key click s1`（对焦） | `1HDR.sh:42` | `st app nx capture single`（含 AF）或 `st app nx key single` | **1** |
| 3 | `st key click rec`（开/停录像） | `brb.sh`, `nrec.sh` | `st app nx record start` / `stop` | **1** |
| 4 | 已注释的 `st key …`（改了一半） | `timelapse.tp:30`, `ramplapse.tp:57` | 删注释残留，统一用 `stapp "app nx capture single"` | **1** |
| 5 | `st cap iq af mv 10 <Δ> <speed>`（AF 手动推） | `EV_S1.sh` | `st app nx capture af-mode manual` +（若需微调）保留 `iq af mv` | **2** |
| 6 | `st cap capdtm setusr 6 0x06000a`（WB 模式魔数） | `filmlab.sh` | **`st app nx capture wb <name>`** ★ 已有官方命令 | **2** |
| 7 | `st cap capdtm setusr 20 0x14000N`（PW 风格槽魔数） | `filmlab.sh`, `flab-verify.sh` | `st app film pw <N>`（**C-2 桥**；把魔数封进 App 命令名之后） | **3** |
| 8 | `systemctl set-environment rec=/p_1=…`（跨会话传参） | `brec.sh` `br_*.sh` `EV_S1.sh` | `$D/state/<key>` 小文件（或 `$D/stated` 守护）；**不属 App 同构** | **4** |
| 9 | `st key click pwoff`（电源键） | `FullLoad.sh` | ⛔ App 无对应命令 ⇒ 保留 | ⛔ |

---

## 4. 分批路线（每批独立可回滚）

### 批次 1 ★ 零补丁：按键注入 → App 命令（**本日落地**）

- **设计原则：三级 fallback，绝不删原路径** ——
  ```sh
  nx_shoot() {                                    # 拍一张
      st app nx capture single >/dev/null 2>&1 && return 0   # ① App 命令（同构目标）
      st cap capt single start  >/dev/null 2>&1 && return 0   # ② 老 st cap 路径
      st key push s1; st key click s2; st key release s1      # ③ 按键注入（原路径，兜底）
  }
  ```
  任何一级成功即返回 ⇒ **行为最坏等于现状**，不可能更差。
- **判据**：① 静态：`bash -n` 全过、LF、无 CRLF；② 上机：拍照成功（照片落 DCIM）+ `loadavg` 无飙升 + 连拍 5 张无丢失。
- **回滚**：`git revert` 即可（纯 shell，无落盘资产）。
- **范围**：`1HDR.sh` / `zoomzoom.sh` / `brb.sh` / `nrec.sh`（+ 清理 2 个 .tp 的注释残留）。

### 批次 2 ★ 零补丁：属性魔数 → 官方命令 —— **代码已落地（2026-10-12）**

> **落地内容**：
> - `scripts/filmlab.sh` 新增 `wb_set_mode()`：**双路可切换** —— 默认走原路；`FILMLAB_WB_APP=1` 走 App 命令；
>   App 路失败**自动回落**原路（三级 fallback 同款思路）。
> - 对照实验脚本 `test_server/dicam/wb_compare.sh`（相机端跑，逐档位输出 `name | App 路读回 | 原路读回 | 判定`）。
> - ★ **静态发现一个必须上机裁决的疑点**：App 的 `wb` 名字枚举是 `1..9`
>   （`auto-tungsten`=1 / `tungsten`=2 / `day`=3 / `cloud`=4 / `f-w`=5 / `f-n`=6 / `f-d`=7 / `flash`=8 / `custom`=9，
>   无参=0），而本地 `WB_TYPE` 真值表是 `0/1/2/3/4/8/9/10` ⇒ **疑差 1**。
>   ⇒ 因此**默认仍走原路**，等 `wb_compare.sh` 实机对照后再决定是否切默认（这正是"逐渐替换"的正确姿势）。

- WB：`setusr 6 0x0600xx` → `st app nx capture wb day|cloud|…`（**语义等价需上机对照**：先并跑，比对 `getusr 6` 读回值）。
- AF：`EV_S1.sh` 的 `iq af mv` 是否可被 `af-mode manual` 覆盖 —— 需上机确认（`af mv` 是"推多少"，`af-mode` 是"模式"，**可能不可替代** ⇒ 保留 `iq af mv`，只把"模式声明"同构化）。
- **判据**：同一场景下两种写法得到的 ISP 读回值一致。
- **范围**：`filmlab.sh`（WB 部分）、`EV_S1.sh`。

### 批次 3 ★ 需 C-2：把无命令通道的魔数封进 App 命令名

- 现状 `setusr 20 0x14000N` 无命名命令 ⇒ 用 **C-2 的 `film` 命令**承接：`st app film pw <N>`
  （脚本侧不再出现 `0x14000N` 魔数；C-2 落地与否见决策文档 D-4/D-5）
- **前置**：C-2 上机通过（W-4）+ 桩 v2 支持带参数拼接。
- **判据**：`st app film pw 9` ⇒ `getusr 20` 读回 == `0x140009`。

### 批次 4 工程卫生（非 App 同构）

- `systemctl set-environment` → `$D/state/*` 文件；收益是可读与可调试，风险中性。排在最后。

---

## 5. 落地规范

### 5.1 新增 App 命令的规格模板（将来扩展时按此写）

```
命令名    : <小写，≤19 字符（消息槽 20B 限制）>
组/子命令 : st app <组> <名> [参数...]
宿主      : App 命令表空位 或 C-2 桩（file 0x3656dc 名字串 + 0xc23a8 桩）
参数上限  : 单个参数 ≤19 字符；多参数需 v2 桩拼接
判据      : 一条"读回 == 目标"的客观断言（iqr / getusr / 落盘时间戳）
回滚      : c2_bytepatch.json 逆写 或 umount（T2）
```

### 5.2 脚本写法规范（三级 fallback 的推广形式）

```sh
# 任何"能力替换"都写成：新路径 → 旧路径 → 原兜底；成功即 return
cmd_x() { <App 命令> && return 0; <旧 st 路径> && return 0; <原做法>; }
```
- 禁止直接删掉原路径（除非该批已上机验证 ≥ 数日）。
- 每个替换点在脚本注释里标 `# [同构 批次N]`，便于将来一次性清理。

---

## 6. 判据与回滚（汇总）

| 批次 | 离线判据 | 上机判据 | 回滚 |
|---|---|---|---|
| 1 | `bash -n` + `gate_flow.py` G1-8（CRLF/语法/执行位 CI） | 拍照成功 + 连拍 5 张无丢失 + loadavg 无飙升 | `git revert` |
| 2 | 同上 + 参数枚举对照表 | 新旧写法 ISP 读回值一致 | `git revert` |
| 3 | QEMU C-2 链（T1–T4） | `st app film pw N` ⇒ `getusr 20` 命中 | bytepatch 逆写 / umount |
| 4 | 同上 | 状态在会话间正确传递 | `git revert` |

---

## 7. 风险清单

| # | 风险 | 级别 | 缓解 |
|---|---|---|---|
| 1 | `st app nx capture single` 在**某些模式**下不拍（如回放态） | 中 | 三级 fallback；或用 G5 的"可拍查询"先判 |
| 2 | App 未运行（队列不存在）⇒ 命令静默失败 | 低 | `st app` 失败即落 fallback（设计如此） |
| 3 | `nx` 树是**厂测接口**，未来固件可能挪动 | 中 | 命令名是契约、handler 地址不是；迁移时只改 `subcmdmine.py` 重跑 |
| 4 | 改写脚本引入 CRLF（Windows 编辑） | 中 | 必跑 G1-8 CI（已有）+ 提交前 `file` 检查 |
| 5 | WB 用命令改 vs 机身 UI 改是否**完全等价** | 中 | 批次 2 用"读回值对照"证；不等价则保留原路 |
| 6 | 一次改太多脚本 ⇒ 出问题难定位 | 中 | 批次制 + 单批只碰同类替换 |

---

## 8. 复现（离线工具）

```bash
# 顶层命令表全表
python test_server/isp/dicam/dicam_dump.py 0x439d28 0x439e40
# 更好：直接解析名字（不依赖字符串表注解）
python E:/tmp/dicam_strings/cmdtab.py 0x449d28 0x449e40
# nx 子树 / 任意 handler 的子命令链
python E:/tmp/dicam_strings/subcmdmine.py nx_cmd_handler cmd_capture_handler cmd_record_handler
python E:/tmp/dicam_strings/subcmdmine.py 0xcb198 0xcd0bc 0xcbc60     # 无符号区用地址
```

> 工具已随本轮入库：`test_server/isp/dicam/`（原有）+ `E:/tmp/dicam_strings/{cmdtab.py,subcmdmine.py}`（本轮新增，**待移入 test_server/isp/dicam/**）。

---
## 附录 A：★ f.sh —— App 命令面的 mod 侧落点（2026-10-12 落地并验证）

> `st app film <命令> [参数…]` 的接收端。仓库 `scripts/f.sh` → 相机 `/opt/usr/nx-ks/f.sh`。

### A.1 命令面（白名单分发）

| 命令 | 说明 |
|---|---|
| `help` / `status` / `log [n]` | 用法 / 状态汇总（版本·模式·PW 槽·IP）/ 最近调用日志 |
| `recipe list\|check\|cycle\|reset\|dump\|wbdump` | 转发到引擎 `filmlab.sh` |
| `recipe apply <名称> [fast]` | 应用配方（名称走字符白名单，可含空格） |
| `pw <0-12\|standard>` | PW 风格槽切换（capdtm 直写） |
| `shoot` | 拍一张（走 capdtm，**不走 App 队列**） |

**绝不 `eval`、绝不 `exec "$@"`** —— 入参经消息队列可达，白名单把爆炸半径限制在已知动作集。

### A.2 ★★ 铁律一：f.sh 内禁止调用 `st app …`（**已实验证实**）

`f.sh` 由 App 的 shell 线程 `system()` 派生；而 `st app` 正是往**同一个队列 0x8828** 发消息、
并等待该线程回执 ⇒ **自我死锁**。

**实验结果**（`demo_fsh.sh` B 段，在 App 线程内执行 `st app mode m`）：
```
[probe] ★ 8s 后 st app 仍在等待 ⇒ 队列无人服务（阻塞/死锁证实）
```

⇒ `f.sh` 只允许用 **`st cap …` / `prefman …` / 文件操作**（均不经 App 队列）。
配套 `deadlock_guard`：若 `filmlab.conf` 里 `FILMLAB_WB_APP=1` / `FILMLAB_MODE=1`
（这两个开关会让引擎内部再发 `st app`），则**拒绝执行**并提示改法。

### A.3 ★ 桩 v2 参数净化（安全修复）

**问题（已实测复现）**：v2 桩把参数拼进命令行交给 `system()`（= `/bin/sh -c`）⇒ 入参获得 shell 解释权。
未净化时 `st app film recipe apply bad;name` 在日志里变成 `recipe apply 'bad'` —— **`;` 被解释，注入成立**。

**修复**：桩内加字符白名单（`a-z A-Z 0-9 . _ + - /`），其余字符一律替换为 `_`
（参数之间的分隔空格由桩在净化之外插入，不受影响）。

| 输入 | 修复后结果 |
|---|---|
| `recipe apply bad;name`（整串作单参数） | `DENY: recipe_apply_bad_na` —— **注入被阻断** |
| `recipe apply 'bad;name'`（正常分开传） | 引擎收到 `apply bad_name` —— **正常分发，元字符已中和** |

- 桩长 156 B → **248 B**（上限 656 B）
- 新补丁 md5 **`48d94bd63e4479fc931ae1a1fee4e94b`**（旧 `697c5739…` 作废）

### A.4 超时工具的现实约束（实测）

相机 rootfs 里**既无独立 `timeout`，根 busybox 也无该 applet**；唯一可能来源是 mod 自带的
`/opt/usr/nx-ks/busybox`（其 applet 集需实测）。`f.sh` 的 `run_tmo` 会探测，取不到则降级直跑（日志留痕）。

### A.5 复跑验证

```
MSYS_NO_PATHCONV=1 wsl -d NXKS2 -- bash /mnt/e/tmp/NXWA-nx500_modding/test_server/dicam/c2_qemu/demo_fsh.sh
```
A 段 = 白名单 / 转发 / 拒绝；B 段 = 死锁实验。需将 `scripts/busybox` 一并放入 chroot（模拟已装 mod）。

---
*生成：2026-10-12 · 分支 `nxwa` · 证据：`dicam.asm` 全反汇编（7025 符号）+ `all.txt` 字符串表 + 二进制逐字节读串 + QEMU 实测（`demo_c2_app.sh` / `demo_fsh.sh`）*
