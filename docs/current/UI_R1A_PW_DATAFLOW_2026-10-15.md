# UI-R1a：PW 菜单数据流地址图（2026-10-15）

> **任务来源**：`NATIVE_UI_ROADMAP_2026-10-15.md` §4 UI-R1a / §9 首批执行包。
> **完成标准**：从现有反编译提取 PW 菜单数据流、两份描述表、名称解析和刷新入口；输出「表→View→State→handler→状态写入」带地址图；结构字段有读写证据，未知项明列。
> **口径**：✅ = 本轮实测（反编译/转储/引用扫描）｜🔶 = 推断 ｜ ❓ = 未决（附验证法）
> **地址体系**：file < 0x4384AC ⇒ VA = file+0x8000；≥ ⇒ VA = file+0x10000（UI-R0 §5）。下列地址均注 file/VA。

---

## 0. 结论（先读这段）

**PW 的「值 → 显示」存在三条独立消费链**（全部经本轮实测定位）：

| # | 消费链 | 入口函数 | 数据 | 用途 |
|---|---|---|---|---|
| **A** | **OSD 图标链** ✅完整 | `CAPPGUICustomView::Draw_pw`（VA `0x33B074`） | **表①**（file `0x40C6A8`，14 条） | 拍摄画面 OSD 上 PW 指示图标 |
| **B** | **Smart Panel 装载链** 🔶部分 | `CAPPGUISmartPanelView::GetButtonInfo`（VA `0x340F78`，param_1==**0xda** 分支） | **表②**（file `0x41754C`，14 条）→ `memcpy` 到 .bss `0x596EE4` | 智能面板（FN 面板）按钮列表数据 |
| **C** | **名称解析链** ✅主体 | `GetDescriptionByTitle`（VA `0x3049C4`，size=13784，巨型 `strcmp` 链） | 记录的 name 字段（内部名，如 `CAP_FN_PW`） | 内部名 → **MSG 名**（如 `MSG_MENU_PW`）→ （消息系统）文案 |

**值来源（A 链的上游）**：`Draw_pw` 读 `UI_Get_Value(0xda)` → 分派至 `UI_Get_Value_Capture_Menu(0xda)` → `0xda ≤ 0x22d` ⇒ **`User_Spec_Get_Value()`**（用户设置值系统）。✅

**两条消费链的语义差异**：表①（OSD 用）保持原始顺序（含显示序特征）；表②（Smart Panel 用）为 **id 升序**。两表内容字段逐条相同、顺序不同、消费方不同——**不是简单的「同一表两副本」**。

---

## 1. 两表结构与字段布局（实测 ✅）

### 1.1 记录布局（步长 0x114 = 276 B）

| 偏移 | 字段 | 类型 | 证据 |
|---|---|---|---|
| `+0x00` | icon 路径字符串指针 | VA ptr | 转储注解（如 `"list icon/picture_wizard/icon_pw_off.png"`） |
| `+0x04` | 槽位 id | int（OFF=0，STANDARD=1…PRO=13） | 转储逐条 + `Draw_pw` 比较 `puVar3[0x46]`（=下一条 +0x04） |
| `+0x08` | 名称字符串指针 | VA ptr（内部名） | 转储注解（如 `"CAP_MENU_CUSTOM_MODE_1"`） |
| `+0x0C..0x113` | 零填充（264 B） | — | 转储「66 zero words skipped」 |

- 遍历步进证据 ✅：`Draw_pw` 内 `puVar3 += 0x45`（0x45 词 ×4 = 0x114 B）；`GetButtonInfo` 内 `memcpy(..., 0x114 × N)`。
- 转储全文：`E:/tmp/ui_r1a/table1_dump.txt` / `table2_dump.txt`（复现：`python test_server/isp/dicam/dicam_dump.py 0x40c6a8 0x40d800`）。

### 1.2 两表条目对照

| 序 | 表①（file 基址 `0x40C6A8` / VA `0x4146A8`） | 表②（file 基址 `0x41754C` / VA `0x41F54C`） |
|---|---|---|
| 0 | OFF (id=0) | OFF (id=0) |
| 1 | STANDARD(1) | STANDARD(1) |
| 2 | VIVID(3) | CLASSIC(2) |
| 3 | PORTRAIT(4) | VIVID(3) |
| 4 | LANDSCAPE(5) | PORTRAIT(4) |
| 5 | FOREST(6) | LANDSCAPE(5) |
| 6 | RETRO(7) | FOREST(6) |
| 7 | COOL(8) | RETRO(7) |
| 8 | CALM(9) | COOL(8) |
| 9 | CLASSIC(2) | CALM(9) |
| 10–13 | CUSTOM1/2/3、PRO（(10)(11)(12)(13)） | 同左（id 序） |

- 表② = **id 升序**；表① = 另一排列（顺序对 `Draw_pw` 无影响——它按 id 精确匹配）。
- 记录内容逐条相同（icon/name 相同，仅顺序不同）✅。
- **两表都只到 13（PRO）**，无 CUSTOM4/14 条目 ✅（与 G-6 结案一致）。

### 1.3 相邻家族表（同名同构，勿混淆）

`0x40D5C0` 起为 **smart_filter 表**（icon `icon_sf_*`），由 `Draw_sf`（VA `0x33B0FC`）消费；同族还有一批表（`0x41C2A0` / `0x41CE7C` / `0x41DB6C` / `0x41E520` / `0x41E634` / `0x41E970` / `0x420464` 等）由 `GetButtonInfo` 各分支使用——**均为「0x114 记录 × N 条」同一格式**（N 由域 id 决定，见 §2.2）。

---

## 2. 表 → 消费方 地址图

### 2.1 A 链：表① → `Draw_pw`（OSD 图标）✅ 完整

```
拍摄状态变化 / OSD 刷新
   └─ CAPPGUICustomView::Draw_pw(this, param_1=osd元素, param_2)
        │                 [VA 0x33B074, file 0x333074]
        ├─ param_2 == 1000 → iVar1 = UI_Get_Value(0xda)          ← 【全局路径】当前 PW 值
        └─ 否则            → iVar1 = *(this + param_2*0x334 + 0xa0) ← 【视图缓存路径】
        │
        ├─ iVar1 == 0 → 取记录0.icon（OFF）
        └─ 否则：遍历表① 记录1..13，比较每条的 id 字段（puVar3[0x46]）
               命中 → uVar2 = 记录.icon
               未命中(14 条走完) → uVar2 = 0
        │
        └─ osd_set_image(param_1, icon_ptr)                       ← 设置 OSD 图标
```

**值来源分派链**（`UI_Get_Value`，VA `0x1FF988` size=140）：

```
UI_Get_Value(param_1)                       [VA 0x1FF988]
  ├─ 200..776        → UI_Get_Value_Capture_Menu()   ★ 0xda=218 落此域
  ├─ 1000..1186      → UI_Get_Value_PB_Menu()
  ├─ 1..99           → UI_Get_Value_Common_Menu()
  ├─ 2000..2107      → UI_Get_Value_Control()
  ├─ 2500..2560      → UI_Get_Value_Development_Menu()
  └─ 3100..3176      → UI_Get_Value_WiFi_Info()

UI_Get_Value_Capture_Menu(param_1)          [VA 0x281F80 size=44]
  ├─ param_1 > 0x22d → __ui_get_value_pointer_ui_capture_menu() 解引用
  └─ 否则            → User_Spec_Get_Value()      ★ 0xda=218 落此
```

- `Draw_sf`（VA `0x33B0FC`）与 `Draw_pw` **同模板**：读 `UI_Get_Value(0xd9)` → 查 smart_filter 表（VA `0x4155C0`）。
- `Draw_pw` 的调用者（OSD 刷新循环）❓ 未定位（验证法：xref VA `0x33B074`）。

### 2.2 B 链：表② → `GetButtonInfo`（Smart Panel 装载）🔶 部分

```
CAPPGUISmartPanelView::GetButtonInfo(this, param_1=面板域id, param_2=_sp_list_*)
    [VA 0x340F78, file 0x330F78, size=1568]
  ├─ uVar1 = UI_Get_Default_Enable_Flag(param_1, ...)   ← 域默认启用标志
  ├─ uVar2 = UI_Get_Enable_Flag(param_1)                ← 域当前启用标志
  └─ 巨型分派（按 param_1）：
       param_1 == 0xda  ⇒  memcpy(&DAT_00596EE4, &表②(0x41F54C), 0xF18); iVar6 = 0xE
                                          └ .bss 0x596EE4，0xF18 = 0x114×14（恰 14 条）✅
       （同族：0xd9→0x99164×9条 / 0xd2→0x9F158×27条 / 0xd3→0x96308×11条 / 0xe3→0x98360×4条 …）
  └─ （iVar6 = 条目数，随返回值/引用传出）
```

- **0xda 域 = PW 面板**（14 条）；`memcpy` 长度 0xF18 = 0x114×14 与表②完全自洽 ✅。
- 调用 `GetButtonInfo` 的「UpdateXXX」族（已定位 3 处）：
  - `SetAccordingOfUI`（VA `0x341688` size=40，纯转调 wrapper）
  - `UpdateDisk`（VA `0x3433D8` size=1336）内一处
  - `UpdateButton`（VA `0x3439A8` size=76）内一处：`GetButtonInfo(this, *(this + (param_1+0x918A)*4 + 4), ...)` ← 面板 id 经对象内索引表取
- **.bss 副本（0x596EE4）的具体消费方** ❓ 未决——拷贝后由 `param_2`（`_sp_list_*` 列表结构）承载；列表→渲染段的细节未解（验证法：搜 0x596EE4 的所有运行期读取；或上机 hook `SmartPanel` 渲染）。
- 语义推断 🔶：`GetButtonInfo` = 面板「按域装载按钮表」；表② 即 **PW 面板的按钮列表数据源**。

### 2.3 记录 name 字段 → `GetDescriptionByTitle`（名称链）见 §3。

---

## 3. 名称解析链（内部名 → MSG 名 → 文案）

### 3.1 解析器：`GetDescriptionByTitle` ✅（结构实证）

- **VA `0x3049C4`，file `0x2FC9C4`，size=13784**（巨型函数）。签名形态：`pcVar2 = GetDescriptionByTitle(param_1 /*内部名字符串*/)`。
- **实现 = 巨型 `strcmp` 链**（非数据表）：逐条 `strcmp(param_1, "内部名")` → 命中则 `pcVar2 = "MSG 名"`。
- ⚠️ 修正既有表述：`DICAM_MOD_DESIGN §4.2` 所称「名→MSG id 的 8B 对表（file 0x2fde00–0x306580）」——**实测就是本函数的函数体+常量池**（该 file 区段 ↔ 本函数 VA 区间吻合：file `0x2FDE00`→VA `0x305E00` 落在 `0x3049C4..0x307F9C` 内）✅。

### 3.2 PW 相关映射样例（实测摘录）

| 内部名（输入） | MSG 名（输出） | 出处（反编译行） |
|---|---|---|
| `CAP_FN_PW` | `MSG_MENU_PW` | L305906-305908 |
| `CAP_MENU_CUSTOM_MODE_3` | `MSG_MENU_PW_CUSTOM03` | L306075-306078 |
| `CAP_MENU_CUSTOM_MODE_PRO` | `CAP_MSG_CUSTOM_MODE_PRO` | L306081-306084 |
| `CAP_FN_QUALITY` | `MSG_MENU_QUALITY` | L305911-305913 |
| （表①/② 的其它 name 字段同理在链内） | — | — |

### 3.3 未决点 ❓

1. **`CAP_MENU_CUSTOM_MODE_1` 在代码中零引用**（grep 全反编译 0 命中；`MSG_MENU_PW_CUSTOM01/02` 亦不存在 ✅ 与 G-6 一致）——CUSTOM1 的「名→文案」路径未证实。
   - 可能的旁路：CUSTOM1 的显示名来自**运行时动态数据**（如当前配方名——正好是本项目要接的接口点 🔶）；
   - 验证法：上机时观察 CUSTOM1 槽 UI 实际渲染文本与读取源；或对 `MsgExport`/消息系统侧继续静态。
2. **MSG 名 → 本地化文案**的最后一环未解（消息系统内部；`res/locale/*/LC_MESSAGES/*.mo` 是否参与待证）。
   - 验证法：搜 `MSG_MENU_PW` 字符串的运行时消费者（消息库 API）；对照 .mo 内容。
3. `CAPPGUIModeView` 构造（VA `0x30E918`）把 `CAP_MENU_CUSTOM_MODE_2` 装入 `data_list._72_4_`（L312079）——**模式视图的列表数据**；它与 PW 面板的关系为旁证（同一套「内部名」体系），未详追。

---

## 4. 可覆盖性分析（为 R2b 标签替换设计）

| 可动面 | 内容 | 直接效果 | 风险 |
|---|---|---|---|
| ① 表① icon 指针（`+0x00`） | 改 OSD PW 图标 | 拍摄画面指示图标变化 | 低（仅显示） |
| ② 表①/② name 指针（`+0x08`） | 改内部名 → 走向**另一条 MSG 文案** | 标题/描述文案变化（若该名在链内） | 低-中（须目标名在链内） |
| ③ 字符串内容（等长原地替换） | 直接改 icon 路径 / 内部名文本 | 图标加载变化 / 链查找失败（名字必须匹配链） | 中（长度受限，禁截断） |
| ④ `GetDescriptionByTitle` 链（改 MSG 名输出） | 让某内部名指向别的 MSG 文案 | 文案变化 | 中（代码补丁，等长 or 桩） |
| ⑤ id 字段（`+0x04`） | ⚠️ 动它会改变「值↔条目」匹配 | 一般**不建议**动 | 高（破坏匹配） |
| ⑥ .bss 副本（`0x596EE4`） | 运行时改副本 | 影响 Smart Panel 渲染（若副本被读） | ❓（消费者未解，先不动） |

**R2b 候选（供后续设计）**：若目标是「让 CUSTOM1 显示我们的名称」——优先候选 = ② 改表记录 name 指针 或 ③ 改链输出（④），具体待 3.3-1 未决点解开后定。

---

## 5. 未决项清单（附验证法）

| # | 未决项 | 验证法 |
|---|---|---|
| U1 | `Draw_pw` 的调用者（OSD 刷新时机/线程） | xref VA `0x33B074`；或反编译搜调用点 |
| U2 | .bss 副本 `0x596EE4` 的消费方 | 搜运行期读取点；上机 hook SmartPanel 渲染 |
| U3 | `CAP_MENU_CUSTOM_MODE_1` 的名→文案路径 | 见 §3.3-1 |
| U4 | MSG 名 → 文案的最终环节（.mo 参与？） | 见 §3.3-2 |
| U5 | `_sp_list_*` 结构定义与所有权 | 追 `param_2` 的构造点（`UpdateDisk`/`UpdateButton` 侧） |
| U6 | `this + param_2*0x334 + 0xa0`（视图缓存路径）的写入方 | 搜 0x334 步进访问 / view 类字段 |

---
*生成：2026-10-15 · 分支工作树（Codex 克隆）· 证据：`E:/tmp/ui_r1a/*.txt` 转储 + `04_decompiled.c` 引用（行号注明）；全部结论可复现。*
