# UI-R1 补充：菜单面链条与文案链（2026-10-15）

> **定位**：补 `UI_R1B` U1（主菜单构建路径）与 `UI_R1A` U3/U4（名称/文案链）——本轮全手动深挖的成果。
> **口径**：✅ 实测（反编译/转储/全盘搜索）｜🔶 推断 ｜ ❓ 未决（附验证法）
> **证据**：`04_decompiled.c`（行号注明）+ `E:/tmp/ui_r1a/menu_mode_tables.txt` + WSL rootfs-112 全盘 `find -L`。

---

## 0. 结论（先读）

1. ★★ **菜单面链条全解**：主菜单 = `CAPPGUIMenuView`（四深度列表，记录步长 **0x24**）+ 顶层 4 页签（**CAMERA / MOVIE / CUSTOM / SETTING**）+ 子项集（由 `_INIT_105` 巨型构造器在启动期写入 .bss）。
2. ★★ **「画面向导」的原生接线全部就位**：菜单子项 `"CAP_FN_PW"` = `{域id 0xda, 选项数 14, 选项表 &DAT_0047F858}`——与 OSD（表①）、SmartPanel（表②）共用同一域 id 体系。**菜单面是 M1「原生入口」的可行载体（R2a 候选 C 成立）**。
3. ★ **文案链定性**：`osd_get_text()`（VA `0xB8344`）= **`dcgettext(0, msgid, 5)`**——标准 gettext 流程（default domain）。**但 rootfs-112 全盘无 `di-camera-app.mo`**（102 个 `.mo` 全属 WebKit/wrt）——文案的最终解析位置**待真机一条只读命令核实**（§5，已列入待上机清单）。
4. **CUSTOM1 之谜推进**（UI-R1A U3 更新）：选项表中三个 CUSTOM 条的「MSG 字段」**全指向 `MSG_MENU_PW_CUSTOM03`**（共享占位）；**代码中零直接改写**。其显示名的运行时来源收敛为「gettext（.mo）解析 + 可能的动态槽名机制」——待 .mo 核实后闭环。

---

## 1. 菜单结构（✅ 全实测）

### 1.1 视图与数据

| 对象 | 地址（VA） | 说明 |
|---|---|---|
| `CAPPGUIMenuView::getMenuItem` | `0x31DEA8`（136B） | **四深度取项**：`_menu_depth{1,expand,2,3}_list + _position.x * 0x24` ⇒ **menu_item 步长 = 0x24（9 词）** ✅ |
| `CAPPGUIMenuView::setMenuList` | `0x32137C`（1928B） | **构建流程**：按 `UI_Get_Value(0x7d9)`（当前模式）选静态项表 → 复制到 .bss 工作副本 → 子项过滤（`isSub1HideItem`）→ 更新计数/指针 |
| `displayTop/displaySub1/displaySub2` | `0x31D75C/0x323EEC/0x3206A8` | 分深度绘制（HDMI 另有同族一套 `0x365xxx`） |
| `SetDrawInfo` / `SetMenuTitle` / `SetMenuListStyle` | `0x32F8F4 / 0x32F338 / 0x32F4BC` | 绘制信息/标题/样式 |
| `depth1_list_get_menu_item_info` | `0x322170` | 一级列表项信息取用 |

### 1.2 顶层 = 4 页签

模式 0 表（`&DAT_0047CF78` → file `0x46CF78`，转储见 `menu_mode_tables.txt`）：

| 页签名（+0x00 指针） | 图标（+0x04） | 子项数（+0x0C） | 子项数组（+0x10，.bss） |
|---|---|---|---|
| `"CAMERA"` | `09_menu_tap_camera.png` | 12 | `0x5396B8` |
| `"MOVIE"` | `09_menu_tap_movie.png` | 8 | `0x53B3B0` |
| `"CUSTOM"` | `09_menu_tap_custom.png` | 10 | `0x53BA28` |
| `"SETTING"` | `09_menu_tap_setting.png` | 24 | `0x53C448` |

（各模式变体表在 `0x47CF78..0x47DC20` 区，`MENU_TOP_NUM` = 1/2/4。）

### 1.3 子项构造器 `_INIT_105`（VA `0x325A84`，size=18820）✅

启动期把全部子项写入 .bss `0x5389xx..0x53Axxx` 区。**每条子项 = 9 词（0x24）**：

| 偏移 | 字段 | 例（"CAP_FN_PW" 条） |
|---|---|---|
| +0x00 | **内部名**（string ptr） | `"CAP_FN_PW"` |
| +0x04 | 标记/图标 | `0`（个别子项 = `"expand"`，对应 depth1_expand 列表；顶层页签此处放图标路径） |
| +0x08 | **域 id** | `0xda` ★ |
| +0x0C | **选项数** | `0xE`（14）★ |
| +0x10 | **选项表指针** | `&DAT_0047F858` ★ |
| +0x14..0x20 | 0 | — |

**已解子项域 id 一览**（同函数内）：

| 内部名 | 域id | 选项数 | 选项表 |
|---|---|---|---|
| CAP_FN_PHOTO_SIZE | 0xcf | 13 | 0x47DC4C |
| CAP_FN_QUALITY | 0xd0 | 7 | 0x47F588 |
| MENU_SETUP_I_FUNCTION_ISO | 0xd1 | 11 | 0x47E67C |
| CAP_FN_ISO_CUSTOMIZING | 0x110 | 3 | 0x47CA8C（`+0x04="expand"`）|
| CAP_FN_OLED_COLOR | 0x12a | 2 | 0x47F684 |
| CAP_FN_WB | 0xd3 | 11 | 0x47F6CC |
| **CAP_FN_PW** | **0xda** | **14** | **0x47F858** ★ |
| PB_FN_SMARTFILTER | 0xd9 | 9 | 0x47FA50 |
| CAP_FN_AFMODE | 0xe3 | 4 | 0x47FB94 |
| CAP_FN_AFAREA | 0xe4 | 3 | 0x47FC24 |

（`&DAT_0047F858` 在同构造器中共 **4 处**引用 = 4 个模式变体的 CAMERA 页均含 PW 子项。）

---

## 2. 选项表结构（以 PW 表 `&DAT_0047F858` / file `0x46F858` 为例）✅

**每项 9 词（0x24）**：

| 偏移 | 字段 | 例（OFF 条） |
|---|---|---|
| +0x00 | 名称（内部名） | `"PICT_SETTINGS_FILE_NAME_OFF"` |
| +0x04 | **选中态图标**（_b） | `icon_pw_off_b.png` |
| +0x08..0x14 | 0（4 词） | — |
| +0x18 | 图标 | `icon_pw_off.png` |
| +0x1C | 图标（同值） | `icon_pw_off.png` |
| +0x20 | **MSG 名**（可选） | `"MSG_MENU_PW_OFF"` |

**PW 表 14 条全表**（顺序与表②同 = id 序）：OFF / STANDARD / CLASSIC / VIVID / PORTRAIT / LANDSCAPE / FOREST / RETRO / COOL / CALM / CUSTOM1 / CUSTOM2 / CUSTOM3 / PRO。

**★ 异常点（CUSTOM 共享）**：CUSTOM1/2/3 三条的 +0x20（MSG 字段）**全部 = `"MSG_MENU_PW_CUSTOM03"`**（`0x4000C0`）；PRO = `"CAP_MSG_CUSTOM_MODE_PRO"`；OFF/PORTRAIT 各有专名；STANDARD 等部分条目该字段 = 0（改由 `GetDescriptionByTitle(名称)` 走链）。

---

## 3. 文案链（定性 ✅ / 落点待核实 ❓）

```
选项表[+0x20] "MSG_名"（或 GetDescriptionByTitle 输出）
   └─ osd_get_text()  [VA 0x0B8344, 40B]
        └─ dcgettext(0, msgid, 5)     ← ★ 标准 gettext（default domain "messages"）
             └─ 预期路径 /usr/share/locale/<lang>/LC_MESSAGES/*.mo
```

- **本机全量搜索（WSL rootfs-112，`find -L`）**：`*.mo` 共 102 个，**全部属于 WebKit（ewebkit2-0）与 wrt-engine**；**无 `di-camera-app.mo`、无 `messages.mo`**；
  `res/locale` 为 symlink → `/usr/share/locale`（副本中为空目录）。
- ⚠️ **一致性断裂**：`author-signature.xml` 明确引用了 `res/locale/en/LC_MESSAGES/di-camera-app.mo`（打包树中存在）——但 rootfs-112 副本中无。⇒ **真机侧存在状态待一条只读命令核实**（§5）。
- ❓ 备选假设：文案由「另一层查表」在 dcgettext 之前解析（`MSG_名` 只是中间键）——若 .mo 在真机也不存在，则此假设升级为主假设（验证法：搜 `MSG_名` 风格字符串的其它消费者；或上机 hook `dcgettext` 返回值）。

---

## 4. 三张 PW 表总览（同一域 0xda，三个消费面）✅

| 表 | 位置（file/VA） | 结构要点 | 消费方 |
|---|---|---|---|
| ① OSD 图标表 | `0x40C6A8` / `0x4146A8` | [icon, id, name, 264B 0] | `Draw_pw`（OSD 显示） |
| ② SmartPanel 表 | `0x41754C` / `0x41F54C` | 同上 | `GetButtonInfo(0xda)` → .bss `0x596EE4` |
| ③ **选项表** | `0x47F858`（file `0x46F858`） | [名, 选中icon, 0×4, icon×2, MSG名] | 菜单渲染（子项展开的选项列表） |

**统一模型**：App 全 UI 用「**域 id**」贯通——菜单子项（`_INIT_105`）↔ SmartPanel（`SmartPanelBase::Create(?, 域id, 名, …)`，例 `Create(1, 0xda, "CAP_FN_PW", 9, …)` @ L347681/347867）↔ 选项表/图标表。**0xda 域 = PW（画面向导）**，其消费面：菜单（选项表）/ SmartPanel（表②）/ OSD（表①）。

---

## 5. 待上机（只读）清单（新增——插队优先级低）

```sh
# 一条会话一条命令；结果 FTP 拉（G1-4）；只读（G1-5）
ls -la /usr/share/locale/ ; find /usr/share/locale -name '*.mo' 2>/dev/null | head -20
ls -la /usr/apps/com.samsung.di-camera-app/res/locale/
find / -name 'di-camera-app.mo' 2>/dev/null | head -5   # 若耗时长可缩到 /usr /opt
```
- 判据：找到 `.mo` ⇒ 文案链闭环（CUSTOM1 显示名可在 .mo 中查证）；找不到 ⇒ 升级「备选假设」（另一层查表），再定向。
- **状态**：⏸ 暂缓（用户拍板「先不着急」）——与本批离线工作解耦。

---

## 6. 对 UI 路线的意义

1. **R2a 候选 C（菜单面）成立** ✅：主菜单链条已解——「画面向导」位于 CAMERA 页子项（`CAP_FN_PW`），其显示名/图标/选项全部经「选项表 + MSG 名」数据面可达。**M1「从原有菜单进入」的补丁面已可设计**（改选项表或 MSG 名，属数据级替换）。
2. **M2（三槽映射/名称显示）的接口点**：CUSTOM 槽的显示名 = 选项表 CUSTOM1/2/3 条的 MSG 字段（现为共享占位）**+ .mo 解析**——「显示配方名」的补丁候选 = **改写这三个 MSG 字段指向我们的文案键**（等长/指针法；落点 `0x47F9E0 / 0x47FA04 / 0x47FA28`）——**待 .mo 机制核实后定稿**。
3. **UI-R2b 样本 A/B 的定位不变**（OSD 面首探）；本补充给出「菜单面替换」的**第二批候选目标**（选项表字段级）。

---

## 7. 未决项（更新）

| # | 项 | 验证法 | 状态 |
|---|---|---|---|
| U-mo | `.mo` 真机存在性 | §5 只读清单 | ⏸ 暂缓 |
| U-msg | `MSG_名` 是否还有第二层解析 | 搜更多消费者；上机 hook | ❓ |
| U-cus | CUSTOM 槽动态名机制（若有） | .mo 核实后定向 | ❓ |
| U-hide | `isSub1HideItem` 的完整判定表 | 读 VA 对应函数 | ❓（低优先）|
| U-45x | `0xF00xx` 编码与 p7 的对应 | ✅ **已解（§8）** | ✅ |

---

## 8. ★ PWB 编码链闭合（0xF00xx → p7 全解，2026-10-15）

> 本节为「UI_R1C U4 / U-45x」的完结：`0xF00xx` 编码语义与到 p7 的通道全部实证。

### 8.1 编码语义（双向置换锁定）✅

- App 侧 `UI_Get_Mm_Camera_Picture_Wizards(位号+1)` → `V = 0xF0000 + σ(位号)`（σ = 轮换置换：1→8, 2→1, 3→2 … 8→7）。
- capfw 侧 `FUN_35FB0`（VA `0x35FB0`；`sub #0xF0000; cmp #12; 跳转表`）做**反置换**：输入 `0xF0000+idx` → 输出 **`0xF0000 + 标准枚举`**（idx 0..12 全表实测）。
- 验证（三例）：STANDARD：App 0xF0008 → capfw **0xF0001** = 枚举 1 ✓；VIVID：0xF0002 → **0xF0003** ✓；CUSTOM1：0xF000A → **0xF000A** ✓。
- ⇒ **`0xF00xx` 家族 = `0xF0000 + PW 风格枚举` 的双向传输编码**。

### 8.2 传输通道（capfw 内全解）✅

```
mm_camera_capture_still（capfw VA 0x2897C）
   ├─ 三次 bl FUN_35FB0（三个 PWB 值：fp+0x24/0x28/0x2C）→ 反置换 → 本地参数块
   ├─ 组装 48 字节块（fp-84..fp-36）
   └─ bl CaptureStillImage(handle, &block, 0x30)     [capfw 内 VA 0x3E288, 8052B]
        └─（按 capture 类型分发后）
             └─ CMCBAdapter::SendCommand(cmd=0x0201, len=0x30, data=&block)
                  [实证 @ 3e6f0-3e708：movw r1,#0x201; mov r2,#0x30]
                  └─ CMulticoreBridge::Send(CID 0x81, …)     [PW_APPLY §7.2 既有证据]
                       └─ p7：STILL_START_CAPTURE（0x201）handler（0x51618 / 0xa3530 区）
                            └─ …（p7 内部：写槽 0xda..0xe2 → 槽变更通知 → 全 8 项下发；PW_APPLY 既有链）
```

### 8.3 与既有研究的关系

- **cmd 0x201 = `STILL_START_CAPTURE`**（`MCB_COMMAND_ENUM_TABLE_2026-10-08.md` L92；p7 handler `0x51618/0xa3530`）。
- 补上 PW_APPLY 缺环：此前「App 的动作不产生指向 `0x107000E` 的字节流」——**现在实证：App 的 PWB 通道 = `STILL_START_CAPTURE(0x201)` 的 48B 参数载荷**（随每次拍摄启动下发）。p7 handler 内的「参数→写槽」段为下一深挖点（handler 本体在镜像中，可反汇编 `0x51618` 起）。

### 8.4 对 mod 的价值

- 「最小可复用事务」最终形态明确：**App 进程内触发 `CMCBAdapter::SendCommand(0x201, 48B, block)` 即可复刻原厂 PWB 下发**（block 布局 48B）——记入 UI-R5a 能力表候选。
- p7 侧「写槽→8 项」链不变（A1/A2 领地）；本链为「App 侧替代/复用」提供完整协议。

---
*§8 追加：2026-10-15 · 全离线（WSL objdump 反汇编 libcapture-fw-prod.so + 符号表）；零写机。*

---

## 9. ★ p7 侧 `0xF0000` 域实证（10-15 收尾深挖，全离线）

> 手段：`chunk-05.bin`（p7 固件）全量反汇编（290 万行，WSL `arm-linux-gnueabi-objdump -D -b binary -m arm --adjust-vma=0x80000000`）+ 调用图检索。**这补上了 §8 链的「p7 落点」。**

### 9.1 ★★ 命中：p7 内存在 `0xF0000+枚举` 的专用转换跳表 ✅

**位置：`0x8004F090-0x8004F0A0`**（巨型「编码重映射器」函数内，同族还有 0x65/0x66/0x67/0x37 等域的并列处理）：

```asm
8004f090: mov r4, #20
8004f094: sub ip, r1, #0xF0000      ; 输入 - 0xF0000（★ 与 capfw FUN_35FB0 同款域判别）
8004f098: str r4, [r2]
8004f09c: cmp ip, #12               ; 0..12，13 路
8004f0a0: ldrls pc, [pc, ip, lsl #2] ; 跳表 → 0x8005007C..0x8005013C
8004f0a4: b 0x8004DE30              ; 越界 → 默认
```

**13 路 case 全展开（实测）**——输出 `0x0014000v`（cat=0x14, sub=v）：

| 输入（0xF0000+枚举E） | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 输出（0x0014_000v 的 v） | C | B | A | 9 | 7 | 6 | 5 | 4 | 3 | 2 | 1 | 8 | 0 |

⇒ **p7 确实「认识」PWB 风格编码**，并将其翻译为内部统一编码 **`0x0014000v`（cat=0x14 家族）**。这是「0xF00xx 与 p7 的对应」的**直接实证**（此前该对应无证据）。

### 9.2 写槽系统（调用图，全量反汇编复核）✅

- **写槽原语 `0x64F0C`**：全镜像 **227 个调用点**，集中在 profile 装载族（`0x65260-0x66834` 等）——槽写入是 p7 参数系统的通用底层。
- **PW 应用写槽链（唯一路径复核）**：
  `0xD26B8`（PW 应用例程）**唯一引用 = `0x4CA00` 的 `b`**（类别消息 0x0107000E 跳表支）→ `0x56C40` → `0x65D6C` → **`0x6F2FC`（写槽 0xd5/0xd9/0xda/0xdc..0xe2）**。
  ⇒ 与 `PW_APPLY_TRIGGER_CHAIN` 结论一致；**「预览调节」通道 = 类别消息链（不变）**。

### 9.3 `0x201` handler 的 p7 侧形态（初勘）🔶

- 命令表所指 `leaf 0x51618 / str 0xa3530`：
  - `0x51618` = 函数 `0x5153C`（「拍摄启动门禁」：读状态区 `0x85180348/350/35C`、读槽 24、日志）内的一个 case 尾。
  - `0xa3530` = `0xa35xx` 区函数（含「6 字节 → 3×16-bit」解析段与初始化序列）内的点。
- **初勘未见**这两处直接调用写槽族（0x65xxx）——「48B 载荷（含 3 个 PWB 值）的 p7 消费路径」**未完全定案** ❓（但 §9.1 已证 p7 有 PWB 域转换器——消费端应经它）。验证法（下一步候选）：反汇编 `0x5153C`/`0xa35xx` 完整体 + 追 `0x14` 家族（`0x0014000v`）的下游消费者；或上机对比拍摄前后槽值。

### 9.4 双通道并存模型（修正/细化 `PW_APPLY` 的图景）

| 通道 | 数据 | p7 落点 | 用途（推断） |
|---|---|---|---|
| **A 预览调节**（既有） | 类别消息 `0x0107000E` | 写槽链（0xd26b8→…→0x6f2fc）→ 槽变更通知 → 全 8 项下发 | 界面选择即生效 |
| **B 拍摄启动**（本日新增） | `STILL_START_CAPTURE(0x201)` 48B 块（3×`0xF0000+枚举`） | **`0x4F09C` 转换器 → `0x0014000v`** →（下游待续） | 拍摄时携带 PWB 状态 |

两通道不冲突；**A1/A2 的「写槽」正路结论不变**（「外部驱动全 7 维」仍需 A1）。

---
*§9 追加：2026-10-15 · 全离线（p7 固件全量反汇编 + 调用图）；零写机。命令：`arm-linux-gnueabi-objdump -D -b binary -m arm --adjust-vma=0x80000000 /mnt/e/NXWA/fw/v1.12/parts/chunk-05.bin`（**路径须写死，勿用 shell 变量**——WSL 参数层会吞）。*

---
*生成：2026-10-15 · 分支工作树（Codex 克隆）· 全离线（反编译 + 转储 + WSL 全盘搜索）；零写机。*
