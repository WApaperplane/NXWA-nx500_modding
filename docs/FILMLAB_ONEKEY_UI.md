# FilmLab 一键 UI —— 设计文档（2026-10-05）

> 需求：mod_gui 三层嵌套不够"一键"。希望挂在一个弃用按键（WiFi）上直接触发，
> 单击打开 Film UI，**波轮切换**，**同时支持触屏**。

---

## 零、先说结论：三个需求，两个撞硬墙

| 需求 | 可行性 | 依据 |
|---|---|---|
| ① 挂 WiFi 键 | **可行** | keyscan.c 规则 B：同键 1 秒内连按两次 → `MOBILE_MOBILE.sh`，不需改 keyscan、不需重编译 |
| ② 波轮切换 | **mod_gui 层无解，必须自写 UI** | mod_gui.c 的 `key_down_callback` 只认 13 个键，方向键与 JOG 全落进 `else → quit_app()` |
| ③ 触屏 | **可行** | mod_gui 走 elm_button 的 `clicked` smart callback，触摸是 EFL 原生路径 |

**「三层」的真正根因不是层级多，是 mod_gui 每次只能开一屏、且开完即关**：
`run_command()` 里 `system()` 后立刻 `quit_app()`。所以点完一个配方窗口就没了，
想再选一个必须重新走一遍菜单树。

---

## 一、WiFi 键：为什么这个槽位现在是空的

社区原版 `EV_MOBILE.sh` = 开 telnetd + FTP。但本项目里 **telnet 已改成主菜单按钮**
（`gui_tpl.NX500` 里的「IP: x.x.x.x [Telnet开/关]」，`telnet_toggle.sh`），
README 明确写了「替代 EV+WiFi 组合键」——**组合键通道已弃用，槽位真空着**。

### keyscan.c 的三条触发分支（源码实测，不是猜）

```c
/* 规则 B：同键双击 —— 这是 WiFi 键唯一可用的钩子 */
if (NXKEY_EV1 != code && msec_elapsed < 1000
    && code == previous_ev.code && value == previous_ev.value) {
    sprintf(shell_name, "%s_%s", nxkeyname[code], nxkeyname[code]);
}
/* 规则 C：只有 MODE_SAS 转盘「松开」时触发 */
if (NXKEY_SAS == code && 0 == value) { sprintf(shell_name, "%s", ...); }
/* 规则 A：EV 按住 + 任意键 */
if (ev_pressed == 1 && code != NXKEY_EV && value == 1) {
    sprintf(shell_name, "EV_%s", nxkeyname[code]);
}
```

**★ 关键事实：单击 MOBILE 键在 keyscan 层不存在任何钩子**，
它走的是相机原生 WiFi 开关。所以 FilmLab 能挂的是：

| 槽位 | 文件名 | 触发 | 体验 |
|---|---|---|---|
| `MOBILE_MOBILE` | `MOBILE_MOBILE.sh` | 双击 WiFi（1 秒内） | **单手一次动作**，零 UI 轮换 |
| `EV_MOBILE` | `EV_MOBILE.sh` | 按住 EV + WiFi | 两只手，但打开即配方列表 |

门槛 `strlen(shell_name) > 4`：`MOBILE_MOBILE`（13 字符）通过。

> **`EV_REC.sh` / `EV_MENU.sh` 不存在**：`NXKEY_REC 171` / `NXKEY_MENU 127`
> 只有 `#define` 没有 `nxkeyname[]` 表项，名字是空串 → 触发条件失败。
> 转盘 JOG1/JOG2/JOG3 同样无表项。

---

## 二、突破：mod_gui 可以指定任意菜单为顶层

从 `mod_gui` 二进制（14,130B，未 strip）里挖出的路径解析逻辑：

```
字符串：'Usage: %s [path_to_scripts_directory] [debug]'
        '%s/%s%s'  +  'mod_gui.cfg.'  +  '/etc/version.info'
源码语义：
  if (strlen(basename) < 1)  →  <dir>/mod_gui.cfg.<MODEL>  或  <dir>/mod_gui.cfg
  else                        →  <path>.<MODEL>  不可读再试  <path>
```

`loadgui.sh` 传的是 `gui_ini`（无扩展名），实际读 `gui_ini.NX500` —— 机制就是这个。

###⇒ 可以直接跳过三层

```sh
mod_gui /opt/usr/nx-ks/gui_filmlab1b      # 打开【就是】配方列表
```

**这不是绕过限制，是这个能力本来就有、之前没用过。**

---

## 三、波轮撞墙：mod_gui 源码级证据

```c
static Eina_Bool key_down_callback(void *data, int type, void *ev)
{
    Ecore_Event_Key *event = ev;
    if (0 == strcmp("F6", event->key)) asprintf(&key, "%s","smart");
    ... /* F7~F10, KP_Home, Scroll_Lock, XF86PowerOff,
           Hiragana, Muhenkan, Control_R, Alt_R, Katakana */
    if (0 == strcmp("XF86Reload",event->key) || 0 == strcmp("XF86WWW",event->key)
        || 0 == strcmp("KP_Enter", event->key))
        return ECORE_CALLBACK_PASS_ON;
    else
        quit_app();              /* ← 方向键 / JOG 全走这里 */
}
```

- 源码里**没有** `Up` / `Down` / `Left` / `Right` 任何一个字符串
- 源码里**没有** `JOG1_CW` / `JOG1_CCW`
- 也没有 switch，也没有按键表 —— 就是一串 `if strcmp`，默认 `else quit_app()`

JOG 在 X11 层是独立 keycode（社区实测 `xinput test 8`）：
`JOG1_CW=185  JOG1_CCW=186  JOG2_CW=171  JOG2_CCW=173`，
**没有映射为方向键**。

⇒ **波轮切换必须在 mod_gui 之外实现。**

---

## 四、为什么自写 UI 用 EFL 而不是 X11

| 方案 | 单核表现 | 结论 |
|---|---|---|
| X11 全屏 720×480 | **吃满单核，连 `echo` 都执行不完**（已实测） | 淘汰 |
| EFL / elementary | 与 `di-camera-app`、`mod_gui` 同一套栈，evas 合成 | 采用 |

2026-08 的 `nxflab.c`（X11 版）已实机验证是死路，这次不重复。

### 编译可行性（2026-10-03 已验证过的路）

- EFL **头文件** 相机和 sysroot 都没有 → 全部手写 ABI 声明
- EFL **库** 真机上有，10-03 已 dump 到 `test_server/appprobe/`：
  `libelementary.so.1`（导出 2402 符号）、`libevas.so.1`（885）、`libecore_evas.so.1`（280）

### ★ 踩到的真坑：链接期 stub 会让波轮静默失效

第一版用 stub 库占 `ecore_event_handler_add`，编译通过、导入表里却**已经没有这个符号**了
—— 意味着真机上会调用**空函数**：窗口能开、能触摸，**波轮完全无反应且不报错**。

改用 `dlsym(RTLD_DEFAULT, ...)` 运行时解析，符号留在导入表里，
由真机 `ld-linux` 按 `libelementary → libecore` 链解析到真函数。

**编译通过 ≠ 功能可用** —— 这是本项目最贵的一类教训。

产物自检三项（`build_filmui.sh` 会提醒）：
1. `NEEDED` 里不能出现 `libecore.so.1`（本地没这库）
2. 导入表里不能有 `ecore_event_handler_add`（必须靠 dlsym）
3. 导入表里必须有 `dlsym` / `dlerror`

---

## 五、交付物

| 文件 | 位置 | 作用 |
|---|---|---|
| `nxfilmui.c` | `test_server/filmlab/src/` | EFL UI 源码（波轮+触摸） |
| `nxfilmui.arm` | `test_server/filmlab/` | 编译产物，834,688B |
| `flab_ui.sh` | `scripts/nx-rc/` | 启动器（`ui` / `cycle` / `stop`） |
| `EV_MOBILE.sh` | `scripts/nx-rc/` | EV+WiFi → 直达配方页（零改动路径） |
| `MOBILE_MOBILE.sh` | `scripts/nx-rc/` | 双击 WiFi → 零 UI 轮换 |
| `build_filmui.sh` | `test_server/filmlab/` | 构建脚本 |
| `deploy/filmlab/` | 仓库 | 部署包 + `INSTALL.txt` |
| `filmlab-apply.sh` | `test_server/filmsim/` | 新增 `export` 子命令 |

### `export` 为什么是必需的

UI 读不了 JSON —— 相机上没有 `jq`。所以引擎要能把 JSON 拍平成纯文本：

```
key|label|R|G|B|HUE|SAT|SHARP|CON
portra400|Portra 400|106|100|93|11|9|9|8
trix400|TriX 400|100|100|100|10|0|13|12
```

`→ /mnt/mmc/filmlab/recipes.txt`（LF 行尾，竖线/换行已过滤）

### UI 交互

| 通道 | 行为 |
|---|---|
| **波轮** | 上下滚 = 上一个/下一个，**滚动即实时应用**（可来回对比） |
| **触摸** | 点配方块 = 立即应用，**★ 不关窗**（可连点多个对比） |
| 退出 | `Left` / `Esc` |

★ 「滚动即应用 + 不关窗」是相对 mod_gui 的核心改进：
mod_gui 是点一下就关，无法对比。

---

## 六、★ 已实机验证 vs 必须实机确认（严格分开）

### 已在本地/既有实机数据上验证

| 项 | 验证方式 | 结果 |
|---|---|---|
| mod_gui 可指定任意菜单为顶层 | 二进制字符串 + 源码语义 | ✅ 逻辑确定 |
| mod_gui 不认方向键/JOG | 源码 `key_down_callback` 逐行读 | ✅ 铁壁 |
| WiFi 键双击 → `MOBILE_MOBILE.sh` | keyscan.c 源码 | ✅ 规则确定 |
| EFL 符号齐全 | 用 Python 解析 ELF `.dynsym`，逐符号定位所属库 | ✅ 全部命中 |
| UI 配方解析 | 拿真实 export 输出喂 `parse_line` 离线回归 | ✅ 9/9 解析正确 |
| prefman 地址公式 | 离线反解 `41964 + k*52 + 9*4` = `0xa410/0xa444/...` | ✅ 与引擎一致 |
| 编译产物 ABI | Python 读 `.dynamic` / `.dynsym` | ✅ ARM ELF、动态链接、5 个 NEEDED |
| 三个 shell 脚本 | `sh -n` | ✅ |
| 所有文件行尾 | Python 统计 CRLF | ✅ 全 0 |

### ★ 必须实机确认（不能靠推断）

| # | 待确认 | 怎么测 | 失败时怎么办 |
|---|---|---|---|
| 1 | **NX500 实体 WiFi 键是否发 code 215** | `keyscan /dev/event0 /dev/event1 /opt/usr/nx-ks/ debug` 后按 WiFi，看 `/tmp/key_code` | 不发 215 → WiFi 键方案整个作废，改挂 `EV_S1`（已有槽位） |
| 2 | **ecore 给的 keysym 名是 `JOG1_CW` 还是别的** | 起 UI 后看 `filmui.log` 有没有 `sel -> N`（波轮触发过） | 都不匹配 → 加 `st key jog` 探测，或改用上下方向键 |
| 3 | `elm_gengrid` 在这个 EFL 1.7.99 上布局是否正常 | 看窗口是否出配方块 | 崩 → 退化成 `elm_table`（mod_gui 用的就是它） |
| 4 | EFL 窗口是否真不吃满单核 | 起 UI 后 `echo` 是否还能及时执行 | 吃满 → 立刻关，退回零 UI `cycle` 方案 |
| 5 | 触摸坐标是否落在按钮上 | 点一下看 `filmui.log` 有没有 `applied sel=N` | 不准 → 改大按钮尺寸（当前 340×54） |

**相机当前不在线**（`192.168.0.100–.107` 80 端口全无响应），以上 5 项全部未测。

---

## 七、零改动方案（今天就能用，不依赖 UI 编译）

即使波轮那条路全部失败，这两条**已经确定可用**：

```sh
# EV+WiFi → 直接打开 FilmLab 配方页（跳过主菜单三层）
sh /opt/usr/nx-ks/nx-rc/EV_MOBILE.sh

# 双击 WiFi → 零 UI 轮换配方 + 弹配方名
sh /opt/usr/nx-ks/nx-rc/MOBILE_MOBILE.sh
```

依赖 `mod_gui` 与 `popup_timeout`（都是社区现成 ELF），不需要新编译任何东西。
唯一前置：`filmlab.sh mkgui` 能生成菜单（已实现）。
