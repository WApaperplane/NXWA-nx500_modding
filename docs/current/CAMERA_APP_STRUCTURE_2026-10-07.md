# 相机 App 结构盘查（di-camera-app）— 面向我们的 App 开发

> 日期：2026-10-07 ｜ 样本：`test_server/appprobe/di-camera-app`（4,773,516 B，从实机拉取）
> 配套：`docs/current/CAMERA_MENU_ARCHITECTURE_2026-10-07.md`（菜单专项）、`docs/current/NATIVE_UI_DESIGN_2026-10-07.md`（我们自己的 UI 设计）
> 目的：把相机**官方主 App** 的骨架摸清，回答「我们要做 App，该学它的哪一层、能复用什么、哪些是墙」。

---

## 0. 十秒结论

| 项 | 结论 |
|---|---|
| 这是什么 | 三星官方 Tizen 相机主程序，**EFL + Edje** 写的（elementary/evas/edje 全套） |
| 代码规模 | 244 个源文件，4 大模块：**UI 153 / GUI 83 / Service 6 / libgui 1** |
| 架构范式 | **Manager 总线 + State 状态机 + View 视图**（三层分离得很干净） |
| 依赖规模 | ~111 个 `.so`（EFL 栈 25 + Tizen 框架 20+ + 三星私有 30+ + 媒体栈 15+） |
| 入口 | 标准 EFL `elm_init → elm_run`，Tizen `appcore-efl` 生命周期 |
| ★ 我们能直接复用什么 | **架构范式**（Manager/State/View 分层）；**EFL API 用法**（`libelementary.so.1` 我们已有）；**`libdi-elementary.so` 这个三星相机专用控件库** |
| ★ 我们碰不了什么 | 整个 App 是**编译期骨架**（State 枚举 + Edje 主题打包），**改不了**；只能用「外挂/覆盖」法 |
| ★ 最值钱的一条 | **`ui_event_key_*.cpp` 有 35 个** —— 官方按下每个键的完整处理链，是我们的**键位行为权威参考** |

---

## 1. 这个 App 是什么 / 不是什么

### 1.1 是什么
- 三星 **NX 系列相机的出厂主程序**，包名 `com.samsung.di-camera-app`（"di" = Digital Imaging）
- 技术栈：**Tizen 2.2.0 "Magnolia" + EFL（Enlightenment Foundation Libraries）+ Edje 主题**
- 二进制：32 位 ARM **EXEC（非 PIE）**，`e_type=2`，`e_machine=0x28`，小端，interp `/lib/ld-linux.so.3`
- 它是**本体**：MENU 键弹出的菜单、liveview 叠加、回放、缩略图……全是它画的

### 1.2 ★ 不是我们改的 mod 菜单
```
[相机系统菜单]  MENU 键 → di-camera-app (4.7MB, 三星官方)   ← 本体，改不动
[mod 菜单]      EV  键 → mod_gui (14KB, 我们) → /opt/usr/nx-ks/gui_*.NX500  ← 贴纸，可替换
```
参见 `CAMERA_MENU_ARCHITECTURE_2026-10-07.md`。**别再把两者搞混。**

---

## 2. 源码模块结构（244 文件）

从 ELF 中残留的 `__FILE__` 路径还原出的原始工程结构：

| 模块 | 文件数 | 职责 | 典型文件 |
|---|---|---|---|
| **UI/src** | 153 | 业务逻辑：事件、回调、显示、操作、命令 | `ui_event_key_*.cpp`(35)、`ui_operate_*.cpp`(15)、`ui_mm_*.cpp`(7) |
| **GUI/src** | 83 | 界面渲染：State / View / Edje 绑定 | `CAPPGUIMenuView.cpp`、`CAPPGUITopState.cpp` |
| **Service** | 6 | 菜单数据层 + 产线模式 | `Service/Menu/ui_menu_*.cpp`(4)、`Service/Production/*`(2) |
| **libgui** | 1 | gui 公共库 | `gui_view_menu.cpp` 等 |

### 2.1 UI/src 详解（★ 最重要的一层）

UI 层有极清晰的 **Manager 模式**：

```
┌─ Manager 总线（15 个，事件驱动的中枢）─────────────────────┐
│  ui_event_manager.cpp              总事件泵               │
│  ui_event_key_manager.cpp          按键总分发  ★★★        │
│  ui_event_callback_manager.cpp     回调登记                │
│  ui_event_drivedial_manager.cpp    拨盘（DRIVE DIAL）      │
│  ui_event_modedial_manager.cpp     模式转盘                │
│  ui_event_battery_manager.cpp      电池                   │
│  ui_event_flash_manager.cpp        闪光灯                 │
│  ui_event_flip_manager.cpp         翻转屏                 │
│  ui_event_degree_manager.cpp       姿态/重力              │
│  ui_event_timer_manager.cpp        定时器                 │
│  ui_event_gui_manager.cpp          GUI 桥接               │
│  ui_event_hdmi_connect_manager.cpp HDMI 接入              │
│  ui_event_usb_connect_manager.cpp  USB 接入  ★            │
│  ui_display_manager.cpp / ui_display_playback.cpp  显示    │
│  ui_filelist_manager.cpp           文件列表               │
└───────────────────────────────────────────────────────────┘

┌─ ★★★ 按键处理：35 个 ui_event_key_*.cpp ───────────────────┐
│  拍照模式：cap_capture / cap_cwb / cap_iFn / cap_liveview  │
│            cap_lock3a / cap_menu / cap_modechange          │
│            cap_movie_rec / cap_selection_af / cap_tracking_af
│            cap_pano_capture / cap_focus_custom_setting     │
│  回放模式：pb_menu / pb_movie / pb_movie_trim / pb_photo_edit│
│            pb_single / pb_slideshow / pb_thumbnail         │
│            pb_folderview / pb_dzoom / pb_panorama          │
│  HDMI：hdmi_menu / hdmi_single / hdmi_movie / hdmi_thumbnail│
│        hdmi_slideshow / hdmi_folderview / hdmi_dzoom / hdmi_panorama
│  其他：capture_mode / development_mode / wifi_stl / my_film_thumb
└───────────────────────────────────────────────────────────┘

┌─ 操作层（Operate，15 个）──────────────────────────────────┐
│  ui_operate_capture / capture_common / video / zoom        │
│  ui_operate_playback（+ boost / memory / common）           │
│  ui_operate_thumbnail / media / dcm / panorama / sound      │
│  ui_operate_system / user_spec                             │
└───────────────────────────────────────────────────────────┘

┌─ 摄像头/媒体适配（mm_*，7 个）─────────────────────────────┐
│  ui_mm_camera / ui_mm_camcorder / ui_mm_photo              │
│  ui_mm_slideshow / ui_mm_sound / ui_mm_fileinfo            │
│  ui_mm_util_movie                                          │
└───────────────────────────────────────────────────────────┘

┌─ 回调层（6 个，对接底层 SDK）─────────────────────────────┐
│  ui_callback_capture / camcorder / lens / media / playback │
│  ui_event_callback_manager                                 │
└───────────────────────────────────────────────────────────┘

┌─ 命令层（nx_cmd_*，5 个）──────────────────────────────────┐
│  nx_cmd.cpp / nx_cmd_capture.cpp / nx_cmd_capture_basic.cpp│
│  nx_cmd_key.cpp  ★ / nx_cmd_record.cpp                     │
└───────────────────────────────────────────────────────────┘

其它：ui_camera_main.cpp（入口）、ui_hibernation.cpp（休眠）、
     ui_devman.cpp / ui_di_sensor.cpp（设备/传感器）、
     ui_folderview.cpp、ui_alg_prosuggest.cpp（算法）、
     ui_asl_interface.cpp、ui_debug.cpp、Inc/cmd/KTMutex.h
```

### 2.2 GUI/src 详解（State / View 分离）

GUI 层是教科书式的 **MVC 变体**：每个功能 = 一对 `XxxState.cpp` + `XxxView.cpp`。

```
主模式：CAPPGUITopState / ModeState / ModeView / ModeTagState
菜单：  CAPPGUIMenuTopState / MenuState / MenuView
        MenuDepth1State / MenuDepth1ExpandState / MenuDepth2State / MenuDepth3State
        MenuDCMState / MenuDateTimeState / LicenseState / MicLevelState
        MultilangMenuView（多语言）
回放：  PlaybackState / PlaybackView / PlaybackVolumeState / PlaybackZoomState
        PlaybackMovieTrimState / ThumbNailState / ThumbNailView
        QuickViewZoomState / PreviewState / PreviewView
显示：  Gadget 系列（CWB/FTMF/Timer/VariableSlide/WBBRK/WBSub/DisSub）
        IFn 系列（IFnState/IFnCustomState/IInUnit/IInCustomView）
弹出：  PopupState / PopupView / QuickPanelState / QuickPanelView
编辑：  PhotoEditState / PhotoEditView、Hotkey 系列
其它：  SelectionAFState / MultiAFState / SmartPro / SmartPanel 系列
        TVLink / SmartLink / RemoteViewfinder（无线）
        GroupShare / Mobile 系列（MobileConnection/MobilePBFileTrans/MobileSelectPhone）
        Custom / EV / DevMenuView / InstructionView / PowerOffView / SensorCleaningView
框架：  CAPPGUIApplication.cpp（应用对象）、CAPPGUIEtc.cpp（杂项）
```

### 2.3 Service 层（菜单数据层）

```
Service/Menu/
  ui_menu_capture.cpp          ← 拍照菜单定义
  ui_menu_capture_enable.cpp   ← 菜单项启用/禁用逻辑
  ui_menu_common.cpp           ← 公共菜单
  ui_menu_development.cpp      ← 开发/产线菜单
Service/Production/
  ui_production_mode_callback.cpp
  ui_production_mode_cmd_handler.cpp   ← ★ 产线模式命令（可能有用！）
```

★ **`ui_menu_common.cpp` / `ui_menu_capture.cpp` 是菜单数据的真源头** —— 比 GUI 层的 State 更接近「菜单项到底是哪些」。

---

## 3. 依赖剖析（111 个 .so，分五族）

| 族 | 数量 | 库 | 说明 |
|---|---|---|---|
| **EFL 栈** | ~25 | `libelementary` `libevas` `libecore*` `libedje` `libeet` `libefreet*` `libeina` `libethumb_client` `libedbus` | ★ 界面框架；`libelementary.so.1` 我们本地已有 |
| **Tizen 框架** | ~20 | `libcapi-appfw-application.so.0` `libappcore-efl.so.1` `libappcore-common.so.1` `libbundle.so.0` `libvconf.so.0` `libdlog.so.0` `libsystem-tools.so` | 应用生命周期、配置、日志 |
| **★ 三星相机私有** | ~30 | **`libdi-elementary.so`**（相机专用控件）**`libgui.so`** `libdcm.so` `libdiosal.so` `libcapture-fw-prod.so` `libfirmware-upgrade.so` `libprefman.so` `libshell-command.so` `libmulticore-bridge.so` `libdi-sensor.so` `libdi-alg-prosuggest.so` `libfilelist-manager.so` `libhibernation.so` `libfactory-mode.so` `libuser-spec.so` `libversion-info.so` | ★★ 这是「相机能力」的来源 |
| **媒体栈** | ~15 | `libmmf-*` `libmm-*` `libmmfsession` `libmmffile` `libasound` `libpulse*` `libavsysaudio` | 音视频 |
| **系统基础** | ~20 | `libcrypto/libssl.so.1.0.0` `libsqlite3` `libdbus-1` `libicu*52` `libglib-2.0` `libexif` `libdrm` `libtbm` `libX11` `libXDGmime` | 通用 |

★★ **对我们最有价值的三个库**：
1. **`libdi-elementary.so`** — 三星在 elementary 之上做的相机专用控件（滑块、参数条、图标栅格…）。我们做原生 UI 时**优先用它**，比自己画省事且风格一致。
2. **`libgui.so`** — 本 App 自己的公共 GUI 库（`gui_view_menu.cpp` 在这）。
3. **`libshell-command.so`** — 执行 shell！我们的 mod 就是靠它开的后门。

---

## 4. 运行框架与入口

```
Tizen 应用启动
   ↓  libcapi-appfw-application.so.0（应用框架）
   ↓  libappcore-efl.so.1（EFL 生命周期：create/terminate/pause/resume）
   ↓  elm_init() → CAPPGUIApplication（应用对象）
   ↓  State 状态机注册（TopState → ModeState → …）
   ↓  elm_run()  ← ★ 主循环（单核 100% 就在这里）
   ↓  退出时 elm_shutdown()
```

**证据**：二进制内 `elm_` 出现 238 次、`Evas` 107 次、`edje` 43 次 —— EFL/Edje 是绝对主体。

### 4.1 与我们 nxfilmui 的对照（★ 关键）

| 维度 | 官方 di-camera-app | 我们的 nxfilmui |
|---|---|---|
| 框架 | EFL 1.7 (`libelementary.so.1`) | 同 |
| 入口 | `elm_init → elm_run` | 同（已验证 108 万次事件循环） |
| UI 描述 | **Edje 主题**（25 个 `.edj` 编译产物） | 纯 C 代码建控件 |
| 状态管理 | 100+ State 类 | 无（简单 8 按钮） |
| 事件模型 | Manager 总线 + `ISAFEvent` 统一事件 | 直接回调 |
| 依赖 | 111 个 .so | 只依赖经 ABI 白名单验证的几个 |

⇒ **结论**：我们的 nxfilmui **架构上比官方简单一个数量级**，但**用的是同一套 EFL**。
⇒ **不能**复用官方的 State/Edje（编译期固化）；**可以**复用它的 EFL 用法和 `libdi-elementary`。

---

## 5. ★ 开发启示：我们能怎么做

### 5.1 三条可行路线（按推荐度）

| # | 路线 | 机制 | 可行性 | 说明 |
|---|---|---|---|---|
| **A** | **独立 EFL App（当前 nxfilmui）** | 自己写 ELF，靠 key slot 触发 | ★★★★★ 已在跑 | 不碰官方，最安全；瓶颈是**按键槽位** |
| **B** | **复用 `libdi-elementary.so`** | 在 A 的基础上链接三星控件库 | ★★★★ 待验证 | 省掉自己画控件；需确认 ABI/符号可用 |
| **C** | **改官方 App**（打补丁 `di-camera-app`） | 二进制 patch / 加菜单页 | ⛔ 极难 | State 是编译期枚举 + Edje 主题打包，等价重写 |

### 5.2 ★★★ 最值钱的复用点：35 个 `ui_event_key_*.cpp`

这些文件是**官方对每个键在每种模式下怎么响应的完整权威记录**。
我们可以据此：
1. **知道哪些键空闲** —— 直接反证我们的新键位是否冲突（对应 `topics/keyscan` 的键名表）
2. **学官方的事件处理套路** —— 比如 `ui_event_key_cap_menu.cpp` 就是 MENU 键的完整链路
3. **抄它的参数操作方式** —— 官方怎么改 ISO/快门/WB，我们可以照做（对应我们的 `prefman` 通路）

### 5.3 ★ 值得注意的两个库

- **`libfirmware-upgrade.so`** —— 相机端固件升级逻辑在这里（呼应 iLauncher 报告 §4.3：**升级是相机自己做**）
- **`ui_production_mode_cmd_handler.cpp`** —— 产线模式命令处理器，可能含调试/测试入口

---

## 6. ★ 实机安装布局（已从二进制路径字符串还原）

```
/usr/apps/com.samsung.di-camera-app/
├── di-camera-app                    ← 主 ELF（本文件的样本）
├── lib/                             ← App 私有 .so
└── res/
    ├── edje/
    │   ├── images/
    │   │   ├── lcd/                 ← LCD 版素材
    │   │   └── hdmi/                ← HDMI 版素材
    │   └── *.edj                    ← ★ 25 个主题（见下）
    └── sounds/camera/
        ├── 01_The_Flea_Waltz.aac  ... 20_Four_Seasons.aac      ← BGM（曲目列表）
        └── 01_N_Move.wav 02_N_DepthMove.wav 03_N_Select.wav
            05_N_Cancel.wav 06_N_SButton.wav 07_N_AF.wav
            08_N_Shutter_10f_3sec.wav 09_N_Shutter_15f_2sec.wav
            10_N_Shutter_30f_1sec.wav …                          ← 操作音效
```

### 6.1 ★ 25 个 Edje 主题（完整名单）

```
nx_style.edj                    nx_style_hdmi.edj
nx_style_hdmi_720.edj
slp_edc_menu.edj                ★ 菜单
slp_edc_hdmi_menu.edj           slp_edc_hdmi_menu_720.edj
slp_edc_liveview.edj            ★ 取景
slp_edc_playback.edj            slp_edc_photoedit.edj
slp_edc_gadget.edj              slp_edc_hotkey.edj
slp_edc_iFunction.edj           ★ iFn
slp_edc_modedial.edj            ★ 模式转盘
slp_edc_quick_panel.edj         slp_edc_custom.edj
slp_edc_datetime.edj            slp_edc_power_off.edj
slp_edc_sensor_cleaning.edj     slp_edc_smart_panel.edj
slp_edc_smartlink.edj           slp_edc_remote_viewfinder.edj
slp_edc_hdmi.edj                slp_edc_hdmi_480.edj / _576.edj / _720.edj
```

★ **看到 `menu` 主题是 `.edj`（编译后的 Edje 包）就明白**：改菜单外观 = 改 `.edj` 并重新编译 EDC。
这比改 C++ 容易，但**加新菜单项**仍需改 `ui_menu_*.cpp` 的数据（编译期）。

## 7. 上机只读清单（可选，进一步取证）

```
① ls -la /usr/apps/com.samsung.di-camera-app/        验证 §6 布局
② ls -la /usr/apps/com.samsung.di-camera-app/res/edje/   拿 25 个 .edj 实测名单
③ ls -la /usr/lib/libdi-elementary.so                确认控件库在（路线 B 前提）
④ nm -D /usr/lib/libdi-elementary.so | head -50      看导出符号（能否复用）
⑤ cat /usr/apps/com.samsung.di-camera-app/*.xml      拿 Tizen 应用描述（权限、入口）
```

---

## 8. 与既有文档的关系

| 文档 | 关系 |
|---|---|
| `CAMERA_MENU_ARCHITECTURE_2026-10-07.md` | 菜单专项（本文件 §2.2 的展开） |
| `NATIVE_UI_DESIGN_2026-10-07.md` | 我们 UI 的设计（本文件 §4.1 的对照组） |
| `docs/HANDOVER_*` | 项目总纲；本文件补上「官方 App 骨架」这一块 |
| `topics/keyscan`（记忆） | 键名表；本文件 §5.2 的 35 个文件是它的行为侧对照 |
