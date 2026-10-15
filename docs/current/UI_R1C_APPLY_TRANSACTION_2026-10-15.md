# UI-R1c：原厂「选择自定义槽→应用→返回取景」App 事务图（2026-10-15）

> **任务来源**：`NATIVE_UI_ROADMAP_2026-10-15.md` §4 UI-R1c。
> **完成标准**：跟踪原厂「选择自定义槽→应用→返回取景」的 App 事务——调用顺序、原始/编码值域、通知与锁；区分 App 状态更新与仅写变量；形成可观测点清单；与 A2 研究相邻。
> **口径**：✅ = 本轮实测 ｜ 🔶 = 推断 ｜ ❓ = 未决（附验证法）
> **地址**：file < 0x4384AC ⇒ VA = file+0x8000；≥ ⇒ +0x10000。转储：`E:/tmp/ui_r1a/`。

---

## 0. 结论（先读这段）

1. **原生「画面向导」UI 本体 = `CAPPGUIGadgetPWState`**（PW Gadget 状态类）：**5 组列表**（`pos_list_` 0..4）+ **7 个滑块**（滑块描述表 `DAT_0046e52c`，7 项 × 7 词）。
2. ★★ **7 维的 UI 值项 id 已锁定**（滑块表词 1 实测）：
   `0xDC=R、0xDD=G、0xDE=B`（彩色三滑块，值域 **0..199**，与 p7 色彩编码 `v*0xff/200` 吻合）；
   `0xDF=HUE`、`0xE0/0xE1/0xE2`=其余三个双向标量（值域 **0..20**，显示值 = 内部值−10，即 ±10）。
3. **「调节」事务的最小动作 = `GUI_Set_System_Value(4, 4, value_id, value)`**（写值系统；触摸变体 `GUI_Touch_Set_System_Value` 先置 `0x7f7` 触摸标志）。⇒ **这是「最小可复用事务」的头号候选**（7 维各自独立、不依赖 UI 状态机）。
4. **「应用下发」事务在拍摄启动链**：`__ui_start_capture` → `UI_Operate_Start_Capture(8)` → `__ui_set_pwb_capture_param`（读掩码 `0x100` → 3 个位号 → `0xF00xx` 编码 → 暂存）→ `UI_Mm_Camera_Start_Capture()` → **`mm_camera_capture_still(18 参数)`**（capfw 出口）。
5. **与 p7 的接口跨侧未闭合**（⚪ 已知边界）：App 经 capfw/MCB 下发，p7 侧接收端（class 无静态引用）属 `PW_APPLY_TRIGGER_CHAIN` 的研究域——「外部可驱动全 7 维」的结论不变（需 A1 路径）。

---

## 1. UI 结构：5 组 × 7 滑块（实测 ✅）

### 1.1 滑块描述表 `DAT_0046e52c`（VA；.data；转储复现：`dicam_dump.py 0x45e52c 0x45e600`）

每项 7 词（28 B）；`GetList_num(i) = &DAT_0046e52c + i*7`（VA `0x2B4588`）：

| i | 词0（OSD slider 句柄） | **词1 = value_id ★** | 词2 min | 词3 max | 词4（值文本句柄） | 词5 | 词6 |
|---|---|---|---|---|---|---|---|
| 0 | 0x560 | **`0xDC` R** | 0 | **199** | 0x561 | 0x559 | — |
| 1 | 0x562 | **`0xDD` G** | 0 | **199** | 0x563 | 0x55A | — |
| 2 | 0x564 | **`0xDE` B** | 0 | **199** | 0x565 | 0x55B | — |
| 3 | 0x566 | **`0xE0`** | 0 | **20** | 0x567 | — | 1 |
| 4 | 0x568 | **`0xE1`** | 0 | **20** | 0x569 | — | 2 |
| 5 | 0x56A | **`0xE2`** | 0 | **20** | 0x56B | — | 3 |
| 6 | 0x56C | **`0xDF` HUE** | 0 | **20** | 0x56D | — | 4 |

**维序与文本证据**（`SetSlideValueText`，VA `0x2B4CFC`）：
- `value_id − 0xDC < 3` ⇒ `Set_Color_Value_text`（彩色文本）⇒ **0xDC/0xDD/0xDE = R/G/B**（且滑块 0/1/2 的样式为 `hotkey_slider_r/g/b`，见 `SetPWSlide`）✅
- `value_id == 0xDF` ⇒ `Set_Hue_Value_text`（HUE 专用文本）⇒ **0xDF = HUE** ✅
- 其余（0xE0/0xE1/0xE2）⇒ `Set_Value_text(v − 10)` ⇒ **显示 = 内部−10（双向 ±10）** ✅

### 1.2 5 组列表 ↔ 7 滑块的映射（`GetSlideIndex`，VA `0x2B4C60`）

| `pos_list_`（列表组） | 滑索引 | 内容 |
|---|---|---|
| 0 | `pos_slide_` ∈ {0,1,2}（焦点轮换） | **RGB 组**（3 滑块） |
| 1 | 3 | 0xE0 维 |
| 2 | 4 | 0xE1 维 |
| 3 | 5 | 0xE2 维 |
| 4 | 6 | HUE |

- `SetPWNaviFocus`：`pos_slide_ = clamp(pos_slide_ + d, 0, 2)`（VA `0x2B4C28`）✅
- 列表 UI（5 项）由 `SetPWList`（VA `0x2B4708`）用 `pw_list_item` 数组构建（每项 0x10 B：{+4=?, +8=text_id, +0xC=item 句柄}），挂到 OSD hotkey list `0x553`；列表文本经 `osd_get_text` 渲染。**`pw_list_item` 5 项文本内容的初始化点未定位 ❓**（验证法：搜 `pw_list_item` 写入点/构造器；推论 = 组名「COLOR/SAT/…/HUE」，不影响事务结构）。

---

## 2. 调节事务（拖动/滚轮 → 写值）✅

```
用户操作（触摸拖动 / 滚轮 / 导航滑动）
  ├─ SetSlideDrag（VA 0x2B4F38）：osd_get_slider_value → SetSlideValueText
  │     └─ GUI_Touch_Set_System_Value(4, 4, pw_slide_[1], iVar1)        ← 触摸版写值
  │          ├─ UI_Set_Value(0x7f7, 1, ...)   （「触摸中」标志，UI_Touch_Event 用）
  │          └─ GUI_Set_System_Value(4, 4, pw_slide_[1], iVar1)
  └─ SetPWNaviSlide（VA 0x2B4D7C）：±1 增量 → clamp(min,max) → SetSlideValue
        └─ GUI_Set_System_Value(4, 4, pw_slide_[1], iVar1)                ← 导航版写值
```

- `SetSlideValue`（VA `0x2B4D50`）= `osd_set_slider_position` + `SetSlideValueText`（纯显示）。
- **写值核心：`GUI_Set_System_Value(4, 4, value_id, value)`**（VA `0x303508`，size=548）；
  触摸包装 `GUI_Touch_Set_System_Value`（VA `0x303850`）另置 `0x7f7` 标志。
- 另有 `GUI_Touch_Set`（VA `0x303888`）：四元组 `(type,list,data,value)` 经 `UI_Touch_Event_Manager_To_GUI` 转发（GUI 事件管理通道）——两条写值路径并存 🔶。
- ❓ **`GUI_Set_System_Value` 的深层路径未细读**（548 B 函数体）：它到 `UI_Set_Value`/User_Spec 的哪一层、是否即时推 mm_camera（预览生效链）——**验证法**：读 VA `0x303508` 函数体；上机 hook 观察调它后 `st cap capdtm getusr` 是否立即变化。

---

## 3. 「应用下发」事务（PWB；拍摄启动链）✅ 主干

```
__ui_start_capture（ui_state_capture_still.cpp，反编译 L37640+ 区）
  └─ UI_Operate_Start_Capture(8, ...)   ← 操作码 8（触发点：反编译 L37763，位于驱动模式分派内）
       └─ __ui_set_pwb_capture_param（内联于 case 8；L151724-151768）
            ├─ uVar4 = UI_Get_Value(0x100)          ← ★「pw_value」掩码（14 位）
            ├─ 解出置位位号 local_3c[0..2]（最多 3 个）
            ├─ local_50/4c/48 = UI_Get_Mm_Camera_Picture_Wizards(位号+1)   ← 编码器
            │      （VA 0x1E6F6C：枚举 1..12 → 0xF0000/0xF0008/0xF0001…0xF000B）
            └─ UI_Mm_Camera_Set_Capture_Pwb_Param(local_50, local_4c, local_48, 0, …)
                   （VA 0x1E6E78：仅暂存 → DAT_004aa4e8/EC/F0/F4）
  …
  └─ UI_Mm_Camera_Start_Capture()（VA 0x1E63E0）
       └─ mm_camera_capture_still(DAT_004aa2f0, …, DAT_004aa4e8..f4, …)   ← ★ capfw 出口（18 参数）
```

**掩码约束**（`UI_Check_PW_BRK_Setting`，VA `0xD72FC`）：数 `0x100` 置位数，
**恰好 3 返回**；否则强制 `UI_Set_Value(0x100, 7)`（回退 bit0/1/2）✅。
（⇒「3」的语义 = 画面向导组合的合法位数；触发时机 ❓ 待查调用者。）

**编码器**（`UI_Get_Mm_Camera_Picture_Wizards`，VA `0x1E6F6C`）：`case n → 0xF00xx` 静态表；
`位号+1` 的 +1 偏移为必须（case 从 1 起步）。**0xF00xx 编码语义已解 ✅**（= `0xF0000`+置换序 σ(位号)；capfw 侧经 `FUN_35FB0` 反置换为标准枚举，随 `STILL_START_CAPTURE(0x0201)` 的 48B 载荷下发——全链见 `UI_R1_SUPPLEMENT_MENU_CHAIN_2026-10-15.md` §8）。

---

## 4. 值域 / 编码 / 通知与锁（汇总）

| 项 | 值 | 出处 |
|---|---|---|
| RGB 值域 | 0..199 | 滑块表 min/max；与 p7 `v*0xff/200` 吻合 ✅ |
| 标量/HUE 值域 | 0..20（显示 −10..+10） | 滑块表 + `Set_Value_text(v−10)` ✅ |
| 7 值项 id | 0xDC/DD/DE/DF/E0/E1/E2 | 滑块表 ✅ |
| pw_value 掩码 | `0x100`（14 位、恰 3 位） | `UI_Check_PW_BRK_Setting` + case8 ✅ |
| PWB 编码 | `0xF00xx`（3 个）| `UI_Get_Mm_Camera_Picture_Wizards` ✅ |
| 触摸标志 | `0x7f7` | `GUI_Touch_Set_System_Value` ✅ |
| 值系统 | `UI_Get_Value/UI_Set_Value`（顶层分派 VA `0x1FF988`；Capture 域 ≤0x22D 走 `User_Spec_Get_Value`） | UI-R1A §2.1 ✅ |
| 通知/锁 | **未发现显式锁或队列**（同步调用链）；触摸通道有 `0x7f7` 标志保护 🔶 | 本轮 ✅ |
| 线程 | UI 线程（同 R1B 结论）；`UI_Touch_Event_Manager_To_GUI` 为事件转发 🔶 ❓ | — |

---

## 5. 与 p7 侧的接口（跨侧，⚪ 已知边界）

- App 出口 = `mm_camera_capture_still(...)`（capfw 高层 API）→ capfw 内部再编 MCB（`SetUserDataMCB`/`SetVariableDataMCB` 两门或其它 CID——capfw 侧属既有研究，`PW_APPLY_TRIGGER_CHAIN` §7）。
- p7 侧接收：**9 类消息无静态引用**（p7 = 运行时派发表）——「外部驱动全 7 维」结构上不通 ⇒ 仍需 A1（改 p7）。★ **App→p7 的 PWB 通道已解**（2026-10-15 晚）：`0xF00xx` → capfw `FUN_35FB0` 反置换 → **`STILL_START_CAPTURE(0x0201)` 的 48B 载荷** → p7 handler（0x51618 区）。p7 handler 内的「参数→写槽 `0xda..0xe2`」段为下一深挖点（全链见 `UI_R1_SUPPLEMENT_MENU_CHAIN_2026-10-15.md` §8）。
- p7 侧既有事实（引用）：**写参数槽 0xda..0xe2 ⇒ 槽变更通知 ⇒ 全 8 内部 id 下发 ISP**（`PW_APPLY_TRIGGER_CHAIN_2026-10-10.md` 铁律三）。

---

## 6. 可观测点清单（供 UI-R5a / 验收判据）

| 层 | 观测点 | 判据 |
|---|---|---|
| App 值系统 | 7 值项（0xDC..0xE2）、掩码 0x100 | 🔶 需在 App 内打印（或经 C-2 桥扩展）|
| OSD | 滑块位置/值文本（渲染） | 目视 |
| capfw/MCB | `mm_camera_capture_still` 调用（18 参数含 PWB） | 🔶 hook 打印 |
| p7 | `st cap capdtm getusr` / `iqr`(184 ID) / `varlist` | 既有工具 ✅ |
| p7 行为 | 画面色彩变化（端到端） | 目视 + A/B |

**负结论判据**：值变了但画面未动 ⇒ 卡在 p7 消费侧（与 A1 的已知边界一致，勿误判为 App 侧失败）。

---

## 7. 最小可复用事务候选（→ UI-R5a 输入）

| # | 候选 | 内容 | 前置 | 副作用 |
|---|---|---|---|---|
| **1 ★** | **写值** | `GUI_Set_System_Value(4, 4, value_id, value)`（value_id ∈ 0xDC..0xE2） | App 运行；值域合规 | 写值系统（预览是否即时生效 ❓） |
| 2 | 触发 PWB 下发 | `UI_Operate_Start_Capture(8, …)` | 掩码 0x100 合法（3 位） | 暂存 PWB → 随下次 capture_still 下发 |
| 3 | 端到端 | 候选 1 + 拍摄动作（正常快门） | — | 全链（capfw→p7） |

- ❗ 候选 1/2 均为 **App 内函数**——外部复用需要进程内通道（C-2 命令桥扩展 / 桩），不是 shell 可达（与 C-2 的「命令桥」定位一致）。
- ❗ 写值 ≠ 画面生效：生效条件三重（值系统 → PWB/capture 链 → p7 消费），逐层可观测（§6）。

---

## 8. 未决项清单（❓ 附验证法）

| # | 项 | 验证法 |
|---|---|---|
| U1 | `GUI_Set_System_Value`(0x303508, 548B) 深层路径（到 User_Spec / mm_camera 的哪层；预览即时性） | 读函数体；上机 hook |
| U2 | `pw_list_item` 5 项文本的初始化者 | 搜写入点/构造器 |
| U3 | `UI_Check_PW_BRK_Setting` 的调用时机 | 搜调用点 |
| U4 | `0xF00xx` 编码语义 + 与 p7 参数槽的对应 | ✅ **已解**（2026-10-15 晚）：= `0xF0000+枚举` 双向置换（capfw `FUN_35FB0` 反置换）；经 `CaptureStillImage` → `CMCBAdapter::SendCommand(0x0201=STILL_START_CAPTURE, 48B)` 下发——全链详见 `UI_R1_SUPPLEMENT_MENU_CHAIN_2026-10-15.md` §8 | ✅ 解 |
| U5 | 「返回取景」退出动作（`SetReset`/退出回调的完整链） | 读 `SetReset`(0x2B4F7C) 及退出点 |
| U6 | `UI_Operate_Start_Capture` 操作码 8 的完整触发条件 | 读 `__ui_start_capture` 全链（2204B） |

---
*生成：2026-10-15 · 分支工作树（Codex 克隆）· 证据：04_decompiled.c（行号/VA 注明）+ `dicam_dump.py` 转储；全部可复现。*
