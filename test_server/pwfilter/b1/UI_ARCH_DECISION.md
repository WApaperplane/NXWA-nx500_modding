# FilmLab UI 架构决策（2026-10-04 16:30 定案）

## 一、问题：X11 满屏窗口在单核相机上不可用

### 实测数据

| 现象 | 证据 |
|---|---|
| X11 存活 | `SURVIVED (PASS)` —— setsid + sigaction 修复后能活过 shell 退出 |
| **但系统卡死** | X11 运行时，连 `echo hello > /tmp/x` + `date` 都执行不完，输出文件为空 |
| CPU 被吃满 | 单核 ARM，X11 每轮 select 1 秒 + 有事件时全屏重绘（720×480 = 345600 像素） |

**根因**：不是轮询频率的问题（降到 1 秒也卡），是**X11 满屏窗口本身就占满单核**。
相机上还有 `di-camera-app` / `Xorg` / `enlightenment` / ISP 固件全在跑。

**→ X11 满屏 GUI 在这台相机上只能"短时间看一眼"，不能交互。**

## 二、★★★ 决策：mod_gui 为主，X11 降级为可选

### 为什么 mod_gui 是正解

| | mod_gui（EFL） | 自写 X11 |
|---|---|---|
| CPU 开销 | **低**（EFL 为相机 UI 而生，原生优化） | **极高**（吃满单核） |
| 触屏支持 | ✅ 原生（`button`/`checkbox` 就是屏幕按钮） | ❌ 收不到按键事件 |
| 按键支持 | ✅ 走 `EV_*.sh` 机制 | ❌ 无输入焦点 |
| 社区生态 | ✅ `EV_OK.sh` / `loadgui.sh` 全套现成 | 无 |
| 能显示图片 | ❌ | ✅（但代价是卡死） |
| 能显示参数细节 | ❌ 只有文字 | ✅（但代价是卡死） |

**mod_gui 缺的只有"图形"，而它换来的是"能用"。**

### 相机上的 mod_gui 架构（实机查清）

```
/opt/usr/nx-ks/
  mod_gui              ← ARM ELF，链接 libelementary（EFL）
  gui_ini.NX500        ← 主菜单
  gui_func.NX500       ← 实用功能子菜单
  ... 8 个 .NX500 子菜单
  loadgui.sh           ← 启动 mod_gui
  gui_exit.sh          ← 退出（killall -q mod_gui）
  EV_OK.sh             ← 机身 OK 键 → 启/停 onscreen_235（触屏 UI）
  EV_UP.sh EV_DOWN.sh EV_LEFT.sh EV_RIGHT.sh   ← 方向键
  EV_S1.sh             ← S1 键（★ 可自定义）
  EV_EV.sh             ← ★ 打开 mod_gui 的入口
  onscreen_235         ← ARM ELF + EFL，触屏 UI 框架
```

**★ 关键发现：`EV_*.sh` 是社区现成的机身按键 → shell 绑定机制。**
用户按机身键 → 对应脚本执行 → 脚本可以写 prefman / 起进程 / killall。
**这正是木一要的"绑一个机身按键"——机制已经存在，只要写脚本挂上去。**

### 已部署的 FilmLab 组件

| 路径 | 作用 |
|---|---|
| `/opt/usr/nx-ks/filmlab.sh` | 配方引擎（12 子命令） |
| `/opt/usr/nx-ks/flab_ui.sh` | 触屏/按键驱动（写控制文件） |
| `/opt/usr/nx-ks/gui_filmlab.NX500` | FilmLab 主菜单（已挂进 `gui_ini.NX500`） |
| `/opt/usr/nx-ks/gui_filmlab1b.NX500` | 8 个一键配方 |
| `/opt/usr/nx-ks/gui_filmlab2.NX500` | 预设槽管理 |
| `/opt/usr/nx-ks/gui_filmlab3.NX500` | 诊断页 |
| `/opt/usr/nx-ks/filmlab/nxflab.arm` | X11 选择器（**可选，卡顿**） |
| `/mnt/mmc/filmlab/recipes.json` | 配方库 v2（8 个，只含 PW 7 维） |

**主菜单已插入**（`gui_ini.NX500` 末尾）：
```
button|胶片配方 FilmLab|@/opt/usr/nx-ks/gui_filmlab.NX500
```

## 三、交互设计（用户在外面拍摄时）

### 路径 A：mod_gui 触屏（主路径，推荐）

```
按 EV_EV 键（或触屏）→ mod_gui 打开
  → 「胶片配方 FilmLab」
     → 「一键配方」→ 8 个配方按钮，点一下 1 秒生效
     → 「预设槽」→ 预写 3 个可见槽，之后机身 UI 零延迟选
     → 「诊断」→ 只读状态
     → 「返回」→ 回主菜单
```
**全程触屏可点，不需要 telnet。** 这是能带到外面用的形态。

### 路径 B：机身按键（待做，机制已存在）

**方案 B1：把 EV_S1 键改成"配方轮换键"**
```sh
# /opt/usr/nx-ks/EV_S1.sh 里加：
/opt/usr/nx-ks/filmlab.sh cycle   # 切换到下一个配方
```
需要在 `filmlab.sh` 加 `cycle` 子命令：记住当前槽位，读 SD 卡配方列表，
写下一个配方到当前槽 + 切 enum。**一次按键换一个配方，零界面。**

**方案 B2：EV_LEFT / EV_RIGHT 做配方上下翻**
社区已经在 `EV_RIGHT.sh` 里用 prefman 改设置了，说明这条路可行。

**方案 B3：触屏 overlay（`onscreen_235`）**
用 EFL 写一个 FilmLab 触屏层，浮在取景器上。
`onscreen_235` 是 ARM ELF + EFL，可以仿写。**这是唯一能"边拍边切"的形态。**

### 路径 C：X11 图形选择器（降级为可选）

- 通过 telnet 启动，短时间查看配方参数
- **不适合交互**（会卡死系统）
- 保留它的价值：7 维可视化，PC 上截图用

## 四、下一步（按可行性排序）

| # | 内容 | 依据 | 价值 |
|---|---|---|---|
| **1** | **验证 mod_gui 触屏实机可用** | 已部署，只需按 EV_EV 键点一遍 | ★★★ |
| **2** | **`filmlab.sh` 加 `cycle` 子命令 + 绑 EV_S1** | 社区按键机制已存在 | ★★★ 边拍边切 |
| **3** | 配方扩到 20–30 个 | JSON 加行 | ★★ |
| **4** | EFL 触屏 overlay（仿 `onscreen_235`） | 框架现成 | ★★ 但工作量大 |
| **5** | X11 加缩略图预览 | 需要 X11 不卡 | ★ 现在不做 |

## 五、教训

### ★★ 性能判断必须前置

我先写了 700 行 X11 代码才测出"吃满单核"。
**正确顺序：先用最小程序测"X11 满屏窗口 + 常驻进程"的 CPU 占用，
确认可行再写界面。** 这个顺序我搞反了。

### ★ FTP 是默认传输方式（我这次退化了）

这一轮我大量用 telnet 传文件、写命令、读结果，慢三个数量级且容易超时。
**记忆里的铁律被我自己忘了：≥10KB 走 FTP，telnet 只用于"必须看回显"的诊断。**
正确做法：脚本用 `ftp_put` 传，结果用 `ftp_get` 拉，一次 telnet 都不需要。

### ★★ 社区框架要先摸清再动手

相机上已经有一整套 `EV_*.sh` + `mod_gui` + `onscreen_235` 的按键/触屏框架，
社区作者已经把"机身按键 → shell"这条路走通了。
**我在写700 行 X11 之前应该先读这些脚本。**
EOF_MARKER_NOT_USED
