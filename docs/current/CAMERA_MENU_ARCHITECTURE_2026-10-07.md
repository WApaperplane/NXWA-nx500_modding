# 相机系统菜单渲染档案（★ 与 NX-KS mod 菜单彻底区分）

> 2026-10-07 起草 · 证据来源：`p7_full.bin`（12,845,056 B）+ `test_server/appprobe/di-camera-app`（4,773,516 B）
> ★★ **本文档纠正一项长期误判**：此前把 NX-KS mod 的 `gui_*.NX500` 菜单当成了"相机系统菜单"。
> 两者**完全不同层、不同实现、不同入口**。见 §1 对照表。

---

## 0. 结论前置

| 问题 | 答案 |
|---|---|
| 相机系统菜单（MENU 键）由谁渲染？ | ★★★ **`di-camera-app`**（Linux 侧 Tizen app，4.7MB，EFL/Edje） |
| p7 固件里有菜单吗？ | ★★★ **没有。p7 显示层只做「取景器叠加层」（FD 框 / 目标框 / 过曝区）** |
| 菜单外观从哪来？ | ★★ **Edje 主题文件** `slp_edc_menu.edj`（可用 `edje_decc` 解开） |
| 菜单项数据从哪来？ | ★★ **代码里的 C++ 结构体数组**：`CAPPGUIMenuView::menu_depth1/2_list`（`menu_item` 结构） |
| 能加新菜单项吗？ | ★ **能，但必须改 `di-camera-app` 的 `.data` 或重编**；p7 侧改不了（那边没菜单） |

---

## 1. ★★★ 两种"菜单"对照表（别再混）

| 维度 | **NX-KS mod 菜单** | **相机系统菜单** |
|---|---|---|
| 载体 | `mod_gui`（14KB 第三方 ELF） | `di-camera-app`（4.7MB 官方 Tizen app） |
| 入口按键 | **EV 键**（`EV_EV.sh` → `loadgui.sh`） | ★ **MENU 键**（系统级，内核直接分发） |
| 数据源 | 文本文件 `gui_*.NX500`（`button|标签|命令`） | ★ **C++ 结构体数组**（编译进二进制） |
| 界面技术 | EFL 直构（elm_win/table/button） | ★ **EFL + Edje**（`slp_edc_menu.edj` 渲染） |
| 层级 | 2 列固定网格，单页 | ★ **1~3 级多层**（depth1/2/3 + expand + DCM + DateTime + License + MicLevel…） |
| 与相机关系 | **覆盖层**（起来盖住，退出回系统 UI） | ★ **就是系统 UI 本身** |
| 能力 | 点击即退，动作只能 `system("cmd &")` | ★ 完整状态机 + 事件分发 + IPCC 报文给 ISP |
| 可否扩展 | ✅ 改文本文件即可（但能力极弱） | ⚠️ **必须改二进制或重编** |

★★ **一句话**：mod 菜单是"贴纸"，系统菜单是"本体"。

---

## 2. ★★★ p7 里没有菜单 —— 三条独立证据

### 2.1 源码树：266 个 `.cpp`，零个 UI/菜单文件

```
p7 全二进制 .cpp 路径 266 个，分类：
  product/...        211 个 → ISP/Liveview/Backend/CaptureController/Lens/AF
  IQ_Common/ Lens/ AF/ core/ libif/ src/ ...  其余
★ 唯一沾"显示"的：DPIF/Src/DisplayLCD.cpp + DPIF/Src/DisplayTV.cpp
★ 无任何 Menu / GUI / OSD / Draw / Font / Dialog 源文件
```

### 2.2 `CDisplayLCD` 的职能 = 画框，不是画菜单

```
CDisplayLCD 区（file 0x63e7e8 附近）的实际符号：
  waitVSync / isr_displayer_lcd_vsync   ← 垂直同步中断
  dp_box_get_flip_info
  dp_box_lcd_fd_draw      ← Face Detection 框
  dp_box_lcd_obj_draw     ← 目标跟踪框
  dp_box_tv_fd_draw / dp_box_tv_obj_draw
  RTTI: CDisplayLCD / ~CDisplayLCD / CDisplayTV / ~CDisplayTV
```
⇒ p7 显示层**只把 ISP 算出的 FD/obj 框叠加到 LCD/TV 输出**，这就是全部"UI"。

### 2.3 菜单的 24 个核心概念，23 个全零

```
menuIndex     0    MenuItem      0    selectedItem  0    cursor   0
scroll        0    submenu       0    SubMenu       0    hierarchy 0
navigate      0    TabControl    0    CTab          0    ListCtrl  0
CMenu         0    MenuForm      0    MenuScreen    0    CMenuItem 0
RootMenu      0    MenuTitle     0    m_pMenu       0    menuItem  0
```
> 唯一"命中"的 `selection` 6 处全是 `SetSelectionAfArea` / `SetSelectionArea`（对焦区，功能不是界面）。

**判据提炼（可推广）**：UI 工具包必有**字体 / 文字绘制 / 控件类**。p7 里 `Font`、`DrawStr`、`DrawText`、`Dialog`、`Popup`(控件义)、`Widget` **全部 0 命中** ⇒ 不可能有菜单。
★ **新铁律候选**：`判某固件有没有 UI，先搜 Font/DrawText/Dialog/Widget 四件套；四件全无 ⇒ 该固件无界面，别再找菜单。`

---

## 3. ★★★★★ 相机系统菜单的完整架构（di-camera-app）

### 3.1 源文件全貌（`GUI/src/...`，共 84 个）

```
GUI/src/GUI_Main.cpp                  ← 入口
GUI/src/CAPPGUIEtc.cpp  gui_data_converter.cpp  gui_util_menu.cpp
GUI/src/view/CAPPGUIMenuView.cpp      ★ 菜单视图（核心）
GUI/src/view/gui_view_menu.cpp        ← 菜单视图工具
GUI/src/view/CAPPGUIHdmiMenuView.cpp  ← HDMI 输出的菜单视图（独立一套）
GUI/src/state/CAPPGUIMenuTopState.cpp        ★ 菜单顶层
GUI/src/state/CAPPGUIMenuDepth1State.cpp     ★ 一级
GUI/src/state/CAPPGUIMenuDepth1ExpandState.cpp
GUI/src/state/CAPPGUIMenuDepth2State.cpp     ★ 二级
GUI/src/state/CAPPGUIMenuDepth3State.cpp     ★ 三级
GUI/src/state/CAPPGUIMenuDCMState.cpp
GUI/src/state/CAPPGUIMenuDateTimeState.cpp
GUI/src/state/CAPPGUIMenuLicenseState.cpp
GUI/src/state/CAPPGUIMenuMicLevelState.cpp
GUI/src/state/CAPPGUIMenuState.cpp
GUI/src/state/CAPPGUITopState.cpp            ← 应用顶层状态机
GUI/src/state/CAPPGUIApplication.cpp
… 其余 70 个（Preview / Playback / ThumbNail / Hotkey / I-Fn / SmartPanel / PhotoEdit / Popup / Custom / Mode / RemoteViewfinder / TVLink / SmartLink / GroupShare / QuickPanel …）
```

### 3.2 菜单视图 API（`CAPPGUIMenuView`，已 demangle）

| 分类 | 成员/方法 | 作用 |
|---|---|---|
| **数据** | `menu_depth1_list` / `menu_depth2_list` / `menu_depth1_expand_list` | ★ 菜单项数组（三级） |
| | `mode_item_list` | 模式专属菜单项 |
| | `rotate_list_` / `rotate_id_` | 转盘菜单 |
| | `layout` / `position` / `depth` / `current_event` | 运行态 |
| **构建** | `setMenuList(void)` | ★ 构建/刷新菜单表 |
| | `SetMenuListStyle(int, const char*, int&, int&, bool&)` | 样式 |
| | `SetMenuTitle(int, const char*)` | 标题 |
| **取用** | `getMenuItem(DEPTH, E)` | ★ 按深度取项 |
| | `GetInfoList()` / `GetInfoData()` | 取菜单信息 |
| | `getDepth2UiValue` / `getDepth2Positon` / `GetGui2UiValue` | 取值/定位 |
| | `getMenuHelpTitle` / `getMenuHelpDesc` | 帮助文案 |
| **绘制** | `displayTop()` / `displaySub1()` / `displaySub2()` | ★ 分深度绘制 |
| | `SetDrawInfo(DEPTH, menu_item*, int)` | 设置绘制信息 |
| | `DrawMenuSmart(menu_item*, int, int)` | 智能菜单绘制 |
| | `DrawUpInfo(...)` / `drawTopIcon(bool)` / `DrawKeyMapBg(int)` | 顶栏/图标/按键图 |
| | `setFocusCursor(int,int)` / `setPosition(DEPTH,int)` / `setDepth(DEPTH)` | 焦点/位置/层级 |
| **常量** | `MENU_TOP_NUM` / `MENU_REFRESH` / `MENU_FIRST_ENTER` / `FLAG_FP_MODE` | 枚举 |
| **结构** | `menu_item`（嵌套类型）、`DEPTH`（嵌套枚举） | ★ 数据模型 |

★ 关键自由函数：`UI_Get_Item_Addr(int)`（按索引取项地址）、`get_select_menu_string()`（取选中项文本）。

### 3.3 菜单项结构体

```
tag_MENU_INFO            ← 菜单信息结构体（17 处引用）
  └─ .list[]             ← 项列表；越界报 "invalid case, tag_MENU_INFO.list:[%d]"
menu_item                ← CAPPGUIMenuView 内部结构
curr_menu_item[i].text   ← ★ 每项有 .text 字段（调试打印）
```
管理函数签名（mangled 还原）：
```c
UI_Manage_PB_Menu_Info_By_GUI(tag_MENU_INFO, bool)       // 播放
UI_Manage_Capture_Menu_Info_By_GUI(tag_MENU_INFO*, ...)  // 拍摄
UI_Manage_Common_Menu_Info_By_GUI(tag_MENU_INFO*, ...)
UI_Set_Menu_Info_By_GUI(tag_MENU_INFO*, ...)
UI_Manage_HDMI_Menu_Info_By_GUI(...)
UI_Manage_Development_Menu_Info_By_GUI(...)
UI_Set_Capture_Menu_Info_By_GUI(tag_MENU_INFO, ...)
… 共 17 个同族管理函数（按场景分：拍摄/播放/HDMI/开发/缩略图/照片编辑/WiFi…）
```

### 3.4 状态机与事件（MENU 键的落点）

```
每个菜单状态类都有标准接口：
  onEnter() / onExit() / handle(ISAFEvent*)          ← ISAFEvent = 统一事件对象
  onEventMenu / onEventOK / onEventUpDown / onEventLeft / onEventRight
  onEventWheelDialCW / onEventWheelDialCCW           ← ★ 机身转盘
  onEventTouchMenu / onEventTouchUp / onEventTouchDown
  onEventS1 / onEventDel / onEventFn / onEventCheck
  onEventResolutionChanged / onEventNewMode / onEventDragEnd …

★ MENU 键 ⇒ ISAFEvent 的 onEventMenu ⇒ 由【当前活跃 State】处理
  ⇒ 状态栈：CAPPGUITopState → MenuTopState → MenuDepth1State → MenuDepth2State → MenuDepth3State
```

★★ **重要推论**：菜单树深度是**编译期决定的**（每级一个 State 类）。加一级菜单 = 加一个 State 类 + 注册到状态机 + 加菜单项到 `tag_MENU_INFO` ⇒ **必须改二进制**。

### 3.5 外观 = Edje 主题（可解）

```
/usr/apps/com.samsung.di-camera-app/res/edje/slp_edc_menu.edj      ★ 主菜单
                                        slp_edc_hdmi_menu.edj      HDMI 菜单
                                        slp_edc_hdmi_menu_720.edj
                                        slp_edc_custom.edj        自定义菜单
                                        slp_edc_datetime.edj      日期时间
                                        slp_edc_gadget.edj
                                        slp_edc_hotkey.edj
                                        slp_edc_liveview.edj
                                        slp_edc_modedial.edj
                                        slp_edc_photoedit.edj
                                        slp_edc_playback.edj
                                        slp_edc_quick_panel.edj
                                        slp_edc_remote_viewfinder.edj
                                        slp_edc_sensor_cleaning.edj
                                        slp_edc_smart_panel.edj
                                        slp_edc_smartlink.edj
                                        nx_style.edj / nx_style_hdmi[_720].edj
```
★ **Edje 部件名**（代码通过 part 名操纵界面）：
```
menu_dep1_e_shutter       menu_flash            menu_dep1_focus_mode_1
menu_dep1_photo_size      menu_dep1_slide_show_option
depth2_language  depth2_filter  depth2_help_display
depth2_external_wireless_flash  depth1_list_item_info
depth1_list_get_menu_item_info  depth2_1row  depth2_2row
menu render  i:%d  count:%d _position[ MENU_DEPTH_1 ]:%d     ← 绘制调试打印
```
★★ **这是最有价值的可操作点**：`.edj` 是**独立资源文件**，可用 `edje_decc` 解开 → 改布局/图/字体 → 重编回。**改外观不需要动二进制。**

---

## 4. ★★★ 可扩展性评估（三条路，按成本排序）

| 路 | 手段 | 能做什么 | 成本 | 风险 |
|---|---|---|---|---|
| **A** | 改 `.edj` 主题 | 改菜单**外观**（颜色/图标/布局/字体） | ★ 低（解包→改→回编） | 低（资源文件，可回滚） |
| **B** | 改 `di-camera-app` 的 `.data` | 改**已有菜单项的文本/数值**（如把某项改名） | ★★ 中（定位结构体偏移 + 写入） | 中（要精确偏移，错了崩） |
| **C** | 重编 `di-camera-app` | **加新菜单项/新层级页** | ★★★★ 极高（无源码，要重建 GUI 状态机） | 高 |

★★ **与铁律的接口**：
- 铁律 86（固件层准入门槛）**不适用于此** —— 这不是固件，是 Linux 用户态 ELF，**可观测、可回滚**。
- 但路 C 撞上 **铁律 88（单核相机资源边界）**：新增一个 State 类会增加常驻内存与事件分发开销，**必须按"单次连续段小"原则设计**。
- 铁律 104（进程活着 ≠ 系统没被拖垮）：菜单是**前台交互**，肉眼即可判定 ⇒ **天然满足判据要求**。

### ★ 我的建议：先做 A，验证 B，C 不做

```
① 上机 dump /usr/apps/com.samsung.di-camera-app/res/edje/  （只读，看有哪些 .edj + 大小）
② 拉 slp_edc_menu.edj 回 PC，用 edje_decc 解开 → 看菜单布局定义
③ 若能改 → 做「配方名显示在菜单里」这类低风险改动（路 A）
④ 路 B 需要先在 PC 侧定位 menu_depth1_list 的 .data 偏移 → 定准了再动
★ 路 C（加菜单页）成本与「自研 UI」相当，已有 NATIVE_UI_DESIGN 的 EFL 方案可替代 ⇒ 不做
```

---

## 5. 与 NATIVE_UI_DESIGN 的关系

`docs/current/NATIVE_UI_DESIGN_2026-10-07.md` 的结论**依然有效且更划算**：

| 方案 | 本质 | 与系统菜单关系 |
|---|---|---|
| 自研 EFL 视图（nxfilmui） | 独立 EFL 窗口，覆盖层 | ★ 与系统菜单**同层但不侵入**（都是 EFL app） |
| 改 `di-camera-app` 菜单 | 侵入系统本体 | ★ 真正"融进系统菜单"，但成本高、风险高 |

⇒ ★★ **定案不变**：**自研 EFL 视图为主（可控、可回滚、不碰系统二进制），改 Edje 主题为辅（低成本改观感），改 di-camera-app 本体不做。**

---

## 6. 待验证（上机只读清单）

```
① ls -la /usr/apps/com.samsung.di-camera-app/res/edje/   → 确认 .edj 清单与大小
② ls -la /usr/apps/com.samsung.di-camera-app/bin/        → 确认 di-camera-app 本体与大小
③ 是否有 edje_decc / edje_cc 在相机上（busybox 未必有）
④ /usr/apps/com.samsung.di-camera-app/ 下有无 manifest / app.cfg（Tizen app 描述）
★ 全部 O_RDONLY，按铁律 90：一次一步，段间留 60~120 秒
★ 探端口先于一切：21 不通 = 整机离线，绝不盲发
```

---

## 7. 证据脚本（可复跑）

| 脚本 | 作用 |
|---|---|
| `test_server/isp/p7_menu_final.py` | 证明 p7 无菜单（24 概念 × 引用数） |
| `test_server/isp/ui_menu_hunt.py` | p7 UI 原语存在性（Font/DrawText/Dialog/Widget） |
| `test_server/isp/camapp_menu_arch.py` | ★ 解 `di-camera-app` 菜单架构（demangle + 源文件 + edj + 部件名） |
| `test_server/isp/st_table_hunt.py` | p7 `st` shell 命令表（另一件事：shell 接口，非 UI） |
