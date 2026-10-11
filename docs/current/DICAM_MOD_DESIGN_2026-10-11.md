# di-camera-app 修改设计（面向功能矩阵 X05 / G-6 / 滚轮交互）（2026-10-11）

> 依据：`FEATURE_MATRIX_MOD_FULL_2026-10-11.md`（X05 / G-6 / 滚 95 条）· `FILMLAB_WHEEL_PREVIEW_FEASIBILITY_2026-10-11.md` · `CAMERA_MENU_ARCHITECTURE_2026-10-07.md`
> 目标样本：NX500 v1.12 `di-camera-app`（4,773,516 B｜md5 `ae44293e969101d1cf0a93cbe9b99f75`｜sha256 `55dcc7814372…`）
> 方法：全离线 —— WSL 反汇编（objdump + ARM binutils）＋ 与既有 Ghidra 全量反编译交叉核对（`E:/ghidra_out/di-camera-app.arm_dump/04_decompiled.c`，11.6 MB，逐条吻合）＋ **QEMU chroot 实跑 `st help`**（相机 rootfs）+ QEMU 实跑 `st app/*`（崩溃路径确认）
> 口径：✅ = 离线已证 ｜ 🔶 = 待上机验证 ｜ ⛔ = 明确不做

---

## 0. 十秒结论

**"改 di-camera-app" 的正确姿势不是"重编/加页面"，而是分五档（0/A/B/C/D）。其中两件事改变全局判断：**

1. ★★ **`st app` 是 App 的官方命令通道**（SysV 消息队列 `0x8828`；~30 条命令，覆盖换模式/驱动/滤镜/显示/计时器/变焦…）。**零补丁、今天可用**，且 mod 的 `install.sh` 里**早已在用它**（`st app disp lcd`，生产验证）。
2. ★★ **投递侧三件套全部现成**：`mount -o remount,rw /`（install.sh 先例）＋ `bluetoothd` 开机钩子 → `/opt/usr/nx-ks/init.sh`（install.sh 先例）＋ systemd 管理（`systemctl restart di-camera-app`，**启动链无签名校验**）。⇒ **"改 App" ≠ "重刷固件"**。

对功能矩阵三条目的的结论：

| 条目 | 原判定 | 本次修正 | 走哪条路 |
|---|---|---|---|
| **X05 原生菜单加滤镜入口** | "技术上能、成本极高（需重编）" | ★ 拆成 3 档；推荐 **C-2「给命令表加一个 `film` 命令」**：补丁仅 **2 处、合计 13 字节**（§5-C2） | 路线 C-2 |
| **G-6 画面向导 3 槽** | "slot 12 在 prefman 存在但 UI 不显示" | ★ **修正：App 里根本没有第 4 个自定义槽**（PW 枚举 1–13 全表 + 两副本查尽，CUSTOM4 零引用）。「加槽」= 真补丁且收益极小 ⇒ **不加**；"想多条配方位"改走 prefman slot 0–8（与 App 无关） | ⛔ 不改 |
| **滚 95 条（长列表）** | 链路 C ⛔（成本/收益倒挂） | 维持"不建长列表"；**但路线 0 打开新玩法**：`st app` 当驱动层 + 键位脚本 = 逐格换配方（零 App 改动） | 路线 0 |

---

## 1. 功能矩阵 → App 修改目标全映射

| 矩阵条目 | 需要改 App 吗 | 改什么 / 走什么 | 备注 |
|---|---|---|---|
| X05 原生菜单加滤镜入口 | ✅ 值得（小额） | C-2：命令表加 `film` → `st app film <cmd>` 直达 mod | §5 |
| G-6 槽 3→12 | ⛔ 不划算 | 加第 4 槽要动 6+ 张表；改走 prefman 0–8（wheel 文档 E2） | §4 |
| 滚 95 条长列表 | ⛔ 不做 | 长列表=重写 View；替代 = 路线 0 + 键位 | §3 |
| 波轮换配方（手机滤镜轮体验） | 🔶 可选后续 | C-3：波轮事件钩子（在 C-2 成功后评估） | §5-C3 |
| F09/F11 全 7 维 | ❌ 不靠 App | 走 A1 p7 patch（主线） | 其他文档 |
| F23 键位映射 | ❌ 不改 App | 现有 EV_*.sh 体系 | 其他文档 |
| F18 主菜单显示 IP | ❌ 不改 App | mod_gui 已做 | 其他文档 |
| F12 Web 遥控 | ❌ 不改 App | 原生菜单本有 checkbox | — |

---

## 2. 新证据：App 的运行时骨架（投递与注入的基础）

### 2.1 systemd 单元（rootfs 原文）

```ini
# /usr/lib/systemd/system/di-camera-app.service
[Unit]
Description=Start di-camera-app
After=hib_ready.service xorg.service default.target wm_ready.service deviced.service
[Service]
ExecStart=/usr/apps/com.samsung.di-camera-app/bin/di-camera-app
StandardOutput=tty
EnvironmentFile=/run/tizen-mobile-env
#Restart=always          ← 被注释：App 崩了 systemd 不会拉起来（需手动 start）
#RestartSec=3
[Install]
WantedBy=default.target
```

三个要点：
- **启动=裸 exec**（systemd 直接拉起 ELF）⇒ **没有 Tizen 包管理器、没有签名校验环节**（签名文件 `signature1.xml`/`author-signature.xml` 只在包安装语境有意义）✅
- `EnvironmentFile=/run/tizen-mobile-env` —— **tmpfs 上的环境文件**；systemd 启动服务时读取 ⇒ **改这个文件 + restart = 给 App 注入环境变量（含 LD_PRELOAD）的现成口子** 🔶（写入者待上机确认）
- 控制方式：`systemctl restart/start/stop di-camera-app` 🔶（上机验一次）

### 2.2 投递先例（全部在 mod 现有生产代码里）

| 能力 | 先例（仓库内） | 状态 |
|---|---|---|
| rootfs 可写回 | `install.sh`：`mount -o remount,rw /` + `mv /usr/sbin/bluetoothd /usr/sbin/bluetoothd.orig` + 写脚本 | ✅ 装机时已执行 |
| 开机钩子 | 同上：替换后的 `bluetoothd` 先跑 `/opt/usr/nx-ks/init.sh` | ✅ 已装 |
| App 命令通道 | `install.sh`：`st app disp lcd`（切显示输出） | ✅ 生产使用 |
| 服务重启 | `systemctl restart bluetooth-frwk.service`（bt.sh 内） | ✅ 已用 |

> ⇒ **"把补丁放到相机上"这件事**，没有任何新机制需要发明：rootfs 写回 + 开机脚本 + 服务重启，三件都是已上机跑通的。

---

## 3. 路线 0（★ 零补丁）：`st app` —— App 的官方命令通道

### 3.1 全链（离线已证 ✅，与 10-08 `MCB_PROTOCOL_AND_ST_TABLE` 的队列结论衔接）

```
mod 脚本 / telnet
  │  st app <cmd> [args...]
  ▼
st（usr/bin/st，4.6KB 瘦客户端；process_option 标记 mode=1 的命令走队列）
  │  shell_sndmsg(argc, argv, key=0x8828)
  ▼
SysV 消息队列 0x8828        ← 消息格式：{mtype; argc; 20B/槽 × N}（槽=定长 20 字节，19 字符上限）
  ▼
di-camera-app 内的 shell 线程（线程名 "shell_di_app"；sem = /sem_app_res）
  │  msgrcv → shell_exec(argc, argv, top_cmd_list)      [lib 内置表]
  │  命中 "app" 条目 → shell_application → 调 App 注册的回调
  ▼
App 注册的 ui_shell_command(argc, argv)   （vaddr 0xc91a0，20B thunk）
  │  shell_exec(argc, argv, &App命令表@0x449d28)        [App 私表]
  ▼
App 内 handler 执行（换模式/驱动/显示/…），结果 int 写 /tmp/app_result + sem_post
```

- 端点核对：`st` 里 `movw r2,#34856`(=0x8828) 直连 `shell_sndmsg`；App 侧 `start_shellthread(0x8828)` + `prctl(0xF,"shell_di_app")` + `"Message queue for shell command was created…"` ✅
- 回执：`sem_wait(/sem_app_res)` → 读 `/tmp/app_result`（`fscanf "%d"`）⇒ **命令有返回值可做判据** ✅（离线链路）/🔶（上机实读）

### 3.2 App 命令表（@vaddr 0x449d28，~30 项，8B/项 {name, handler}，"end" 哨兵）

文档化命令（App 自身 `help` 输出原文，全部 `st app <…>` 前缀）：

| 命令 | 参数 | 作用 |
|---|---|---|
| `mode` | `smart-pro\|auto\|p\|a\|s\|m\|custom2\|custom1` | ★ 换拍摄模式 |
| `drive` | `single\|conti_n\|conti_h\|timer\|bracket` | 驱动模式 |
| `set sf` | `off/vig/min/war/neg/red/gr/bl/yel` | ★ Smart Filter 切换 |
| `set izoom` | `1.0\|1.2\|1.4\|1.7\|2.0` | 数码变焦 |
| `set efs` | `on\|off` | EFS 开关 |
| `set disp_timer / power_timer` | `off/0.5/1/3/5/10(/30)` | 计时器 |
| `show` | `liveview\|lock3a\|pro_shift` | 屏上信息 |
| `volum` | `off\|low\|mid\|high` | 音量 |
| `bb` / `video` | `lcd\|evf\|tv` + `on/off/osd` | 黑屏/视频输出控制 |
| `disp` | `lcd\|evf\|auto` | ★ 显示输出（install.sh 已用） |
| `lens` | `info\|pzoom` + `tele\|wide\|stop` | 镜头 |
| `data save` | — | 菜单值保存 |
| `isfull` / `wifidirect start\|stop` / `power on` / `rtc set\|get` / `led` / `ptp` / `lang` | … | 杂项 |
| `test` | `a\|b\|finit\|flash\|tt\|ps\|oor\|vconf\|f\|bodyfw\|nolens\|affail\|logo\|spanel` | 单动作测试（慎用） |

未文档化（静态解出，handler 均在 App 内）：`cmode`（自定义模式/预载文件机务，子命令 `pre/pref/upload/make` + 信息打印；见 §4.4）、`changemode`、`uscom/uscap/usetc`（UserSpec 表 dump——可当 USER 参数勘察工具）、`softap/strobe`（重复项）、`nx`。

### 3.3 立即价值（今天就能做的三件事）

1. **远程换模式/驱动/显示**：脚本里直接 `st app mode m` / `st app drive bracket` / `st app disp lcd`——不需要任何补丁。
2. **勘察工具**：`st app uscom` / `st app uscap` 打印 UserSpec 全表（name/value/db-value）——做 prefman 类工作的顺手工具。
3. **为键位脚本提供"动作库"**：EV_*.sh 里调 `st app …`，等于把原生 App 当"动作执行器"。

### 3.4 局限（诚实边界）

- **不新增 UI**：命令是"驱动层"，不是界面层；画面向导列表、菜单项本身不受影响。
- **命令集固定**：想加新命令 ⇒ 路线 C-2。
- **单参数 19 字符**：消息槽定长 20B（含 NUL）——长命令要拆分或靠 C-2 的 v2 桩拼接。
- 🔶 App 必须在运行（队列存在）；App 没跑时 `st app` 会失败（install.sh 的时序已容忍这一点）。

---

## 4. 新证据：PW / custom 槽位结构（G-6 结案）

### 4.1 PW 槽位描述表（.rodata，两副本）

| 副本 | 位置（file 偏移，记录步长 0x114） | 内容 |
|---|---|---|
| ① | 0x40c6a8 起 | OFF、STANDARD(1)、CLASSIC(2)、VIVID(3)、PORTRAIT(4)、LANDSCAPE(5)、FOREST(6)、RETRO(7)、COOL(8)、CALM(9)、CUSTOM1(10)、CUSTOM2(11)、CUSTOM3(12)、PRO(13) |
| ② | 0x41754c 起 | 同上（另一 UI 面副本） |

每记录 = {icon 路径指针, 槽位 id, 名称指针, …0 填充}。**两副本都只到 13（PRO），没有任何 CUSTOM4/id14 条目** ✅

### 4.2 名字 → 消息 ID 的解析机制

App 内有一张 **{内部名 → MSG id} 的 8B 对表**（.text 常量区，file 0x2fde00–0x306580 区段散列），例如：
```
{"CAP_FN_PW" → "MSG_MENU_PW"} … {"CAP_MENU_CUSTOM_MODE_3" → "MSG_MENU_PW_CUSTOM03"} …
```
⇒ 菜单文案 = 内部名 → MSG id → （消息系统）本地化文本。**改菜单文字 = 改对表里的 id 或改 MSG 库**（路线 B 的关键机制）。

### 4.3 G-6 结案

- `CAP_MENU_CUSTOM_MODE_1/2/3` 存在；**`_4` 不存在**（全二进制零命中）✅
- `MSG_MENU_PW_CUSTOM03` 存在；CUSTOM01/02/04 的 MSG id 不存在 ✅
- 图标 `icon_pw_custom04[_b]` 在主题里有素材但**无任何表引用**（= 跨机型/遗留素材）✅
- ⇒ **"3 个可见自定义槽"是 App 编译期事实**；把第 4 槽接出来要改：槽位表 + 名→msg 表 + 至少一处 handler/计数逻辑 + 资源接线。**评估：为"+1 格"做真补丁，性价比不合格 ⇒ ⛔**
- ⇒ **想要"更多条配方位"：走 prefman slot 0–8**（wheel 文档路 3 / 实验 E2），那条线完全不经 App。

### 4.4 附带发现：cmode 通道与 preload 文件（🔶 待上机，先记录）

- `st app cmode pre <a> <b>` → `Ui_Cmode_Make_Preload_Film(a,b)`；`pref`/`upload`/`make` 子命令 → 预载文件读写 + `User_Spec_Save_Pref` + 启动加载
- 预载文件路径：**`/opt/apps/preload.bin`**（`Ui_Cmode_Make_Preload_File`，4000B 缓冲）
- 含义：**厂测的"自定义模式预载"文件通道**——如果格式解开且路径可写，或可成为"文件 → 相机状态"的第三条官方通路（前两条 = prefman / 画面向导）。**未解，仅记录**。

---

## 5. 修改路线设计（0 / A / B / C / D）

### 路线 0 —— `st app`（零补丁）✅ 可用
见 §3。成本 ★；风险 ✩（生产已在用）。

### 路线 A —— `.edj` 主题（外观层）
- 能改：菜单观感（颜色/图标/布局/字体）。不能改：菜单项结构/动作。
- 载体：`/usr/apps/com.samsung.di-camera-app/res/edje/*.edj`（可解包重编）＋ icons。
- 用途：如果将来 C-2 的 `film` 入口想要"像原生一样"的图标/文案，A 是配套项。
- 成本 ★★；风险 ✩（资源文件，可回滚）。

### 路线 B —— `.data`/`.rodata` 表改（"改名/换图标"级）
- B-1: 改**名→msg 对表**里的 id（让某菜单项显示我们的文案）——只改显示，不改行为。
- B-2: 改**槽位描述表**（icon 路径/名称指针）——同上，只改外观。
- 定位方法已备（本文件附录工具：xref + 表 dump）。
- 成本 ★★；风险 ✩✩（写错=菜单显示乱/崩，可回滚）。
- **单独用价值低**（改皮不改骨），通常作为 C 的配套。

### 路线 C —— 代码小补丁（★ 本设计核心）

#### C-1 动作重定向（备选，先不动）
把某个弃用菜单项的 handler 指针改到我们的代码。需要先定位"菜单动作 dispatch"的确切落点（GUI State 的 onSelect → UI_Manage_* → 动作函数）。**保留为备选**：C-2 成功后，若"必须出现在原生菜单里"（而不是命令通道），再评估 C-1。

#### C-2 ★ 推荐：给 App 命令表加一个 `film` 命令（补丁 = 13 字节）

目标：`st app film <短命令>` ⇒ App 内 `system()` 执行 ⇒ 直达 mod 脚本。

**为什么选它**：入口是"官方风格、可脚本化、持久"的；补丁量极小；失败可回滚；不动 UI 状态机。

**补丁规格（NX500 v1.12 偏移，全部 file offset）**：

| # | 位置 | 原内容 | 改为 | 说明 |
|---|---|---|---|---|
| 1 | 0x3656dc | `"uscom"`（UserSpec dump 命令名，**全镜像唯一引用**=表项①） | `"film"`（5 字节，余下保留） | 命令名就地改名 |
| 2 | 0xc23a8（=vaddr 0xca3a8，`FUN_000ca3a8` 头部，原 656B dumper 已弃用） | dumper 前导字节 | **桩 v1（16B）**：`cmp r0,#2; bxlo lr; ldr r0,[r1,#4]; b <system@plt=0xadd08>` | handler(argc,argv)，argv[1]=参数 |

- 表项本身**不需要动**（0x439e00 的名字指针仍指向那串、handler 指针仍指向 FUN 头部）——只改 8+8 字节内容。✅（引用唯一性已验：`uscom` 串仅 1 处引用；FUN_000ca3a8 仅 1 处引用=该表项）
- 调用样例：`st app film "…"`（参数 ≤19 字符）
- **v1 的短路径问题**：`system(argv[1])` 里 argv[1] 是裸命令串，若想跑 mod 脚本需要短路径。两种解法（择一，开发期定）：
  - (a) rootfs 加一个短符号链接（如 `/f` → `/opt/usr/nx-ks/f.sh`）⇒ `st app film "/f apply 23"`（13 字符 ✓）
  - (b) **桩 v2（推荐）**：利用 FUN 遗体的 ~600 字节空间，写 60–100B 汇编：`"sh /opt/usr/nx-ks/f.sh " + argv[1..n]` 拼接入静态缓冲 → `system(buf)` ⇒ `st app film apply 23` 自然可用，零 PATH 依赖。
- 补充：`system` 已在 PLT（0xadd08）✅；App 自身多处调用 `system`（28xxxx 区已见此模式），不引入新依赖。
- 成本 ★★★（一次小补丁 + 一次交叉验证）；风险 ★（13 字节、无结构改动；错=该命令崩、可回滚）。

#### C-3 波轮事件钩子（🔶 后续，不在本期）
在 C-2 成立之后评估：把某 State 的 `onEventWheelDialCW/CCW` 补丁为"先调我们的命令再走原逻辑"。"滚轮换配方"的正统实现。规模中等，本期不做。

### 路线 D —— 注入层（不改二进制；做实验 / 过渡期用）

| 子路线 | 机制 | 用途 | 状态 |
|---|---|---|---|
| D-1 LD_PRELOAD | 写 `/run/tizen-mobile-env`（追加 `LD_PRELOAD=/opt/usr/nx-ks/libhook.so`）→ `systemctl restart di-camera-app` | 拦截 libc/菜单回调做**不改字节**的行为实验 | 🔶 两处待验：env 文件写入者、restart 可行性 |
| D-2 bind-mount | `mount --bind /opt/usr/nx-ks/dicam/di-camera-app /usr/apps/com.samsung.di-camera-app/bin/di-camera-app` + restart | 整只替换（免 rootfs 写入），开机由 init.sh 复挂 | 🔶 待上机（mount 能力已具备） |

### 明确不做

| 项 | 原因 |
|---|---|
| 长列表（95 条滚轮） | 等于重写 View/State，撞单核红线（铁律 88） |
| 加第 4 个自定义槽 | 见 §4.3 |
| 全量重编 | 无源码，等价重写 |
| 改 State 状态机加页 | 同上；需求已被路线 0/C-2 覆盖 |

---

## 6. 投递 / 持久化 / 回滚（全部有生产先例）

### 6.1 三条投递路对比

| 路 | 操作 | 持久性 | 回滚 | 前置 |
|---|---|---|---|---|
| **T1 rootfs 原地补丁**（推荐给 C-2 正式版） | `mount -o remount,rw /` → 按 §5-C2 写 13 字节 → `sync` → `remount,ro` | 永久（到下次固件重刷） | 还原备份字节（备份存 /opt/usr） | 备份文件放 **/opt/usr**（不在 rootfs，不占空间） |
| **T2 bind-mount 替换** | 补丁二进制放 /opt/usr/nx-ks/dicam/；init.sh 里 bind + restart | 每次开机由 init.sh 复挂 | 卸载 mount + restart | 开机钩子（已有） |
| **T3 env 注入**（D-1） | 追加 env + restart | 每次开机重写 /run（tmpfs） | 去掉 env 行 + restart | env 写入者确认 |

- **首次安装模式**（仿 bluetoothd 钩子）：一次性动作 + 有备份 + 有回滚脚本 + 写"已装标记"防重复执行。
- 存量 mod 的增量同步链（info.tg→install.sh）**不碰 rootfs**；所以 App 补丁要做成**独立的"App 补丁器"**（一次性、显式触发），不塞进日常同步。

### 6.2 备份 / 回滚纪律

```
备份：/opt/usr/nx-ks/dicam/backup/di-camera-app.v1.12.orig  （md5 ae44293e… 对拍）
       /opt/usr/nx-ks/dicam/backup/patch_NXO.bytepatch.json（记录改了哪几个字节：位置/原值/新值）
回滚：按 bytepatch.json 逆写 → remount → restart di-camera-app
```
- 遵守 `HANDOVER` 备份纪律：**备份必须标注"对应哪个固件态"**（= v1.12 官方 + U5 之后）。
- rootfs 96% 满 ⇒ 只做**原地字节改写**（不复制整文件进 rootfs）。

---

## 7. 判据（每条路线写死）

| 路线 | 判据 |
|---|---|
| 路线 0 | `st app help` 回显用法表；`st app disp lcd` 切换输出可见；`/tmp/app_result` 有返回值 🔶 |
| C-2 | `st app film "<短命令>"` ⇒ 目标脚本执行（落盘时间戳/log 一行）；`st app uscom` 不再输出 dump 表（改名生效的反证） |
| T1/T2 | App 正常起（画面恢复=失败即崩场景）；`systemctl status di-camera-app` 无异常退出 🔶 |
| D-1 | `cat /proc/<app pid>/environ` 含 LD_PRELOAD 🔶；hook 库的日志出现 |
| D-2 | `mount | grep di-camera-app`；App 起后行为 = 新二进制行为 |

失败模式与处置：App 崩（画面黑）→ telnet 仍活 → 还原备份 + `systemctl restart di-camera-app`（注意：unit 里 Restart=always **被注释**！崩了不会自愈，必须手动拉）。

---

## 8. 风险清单

| # | 风险 | 级别 | 缓解 |
|---|---|---|---|
| 1 | 补丁错字节 ⇒ App 崩 | 中 | 只改 13 字节 + bytepatch.json + 备份；失败 5 分钟内可还原 |
| 2 | 单核资源（铁律 88） | 低 | C-2 不增加常驻逻辑；v2 桩仅执行期开销 |
| 3 | 时机：App 重启影响 | 低 | 装补丁选"用户可接受屏幕闪一下"的时机；重启次数=1 |
| 4 | 签名/安全层 | 低（静态判"无校验"，🔶 上机复核） | 首次实验用 T2（bind-mount，零落盘）先证伪签名问题 |
| 5 | smack/`device-sec-policy` | 低 | 策略文件里 di-camera-app 只是包名条目；行为影响待观察 |
| 6 | rootfs 空间 | 低 | 原地改写；备份进 /opt/usr |
| 7 | 未来固件升级覆盖 | 中 | 补丁器可重放（bytepatch 是针对 v1.12 的；升级后需重新对偏移） |

---

## 9. 实验计划

### 9.1 离线（现在就能做）

| # | 项 | 产物 |
|---|---|---|
| O-1 | 本设计 + 分析脚本入库（`test_server/isp/dicam/`） | 本文件 + 4 个脚本 |
| O-2 | 桩 v1/v2 的 ARM 汇编 + 字节编码自测（objdump 反查） | `test_server/dicam/` 下 stub.s / stub.bin + bytepatch 生成器 |
| O-3 | bytepatch 生成/校验器（改前/改后 md5、字节 diff 打印） | 同目录 `mkbytepatch.py` |

### 9.2 上机（合并一批，铁律 87：一次上机做完）

| # | 实验 | 步骤（合并执行） | 判据 | 风险 |
|---|---|---|---|---|
| E-D1 | 路线 0 验证 | `st app help`；`st app uscom`（先看表）；`st app mode p→a`；`st app disp lcd`；看 `/tmp/app_result` | 回显/画面/文件 | ✩ 只读/低危（mode 切换会动拍摄状态，用前记录） |
| E-D2 | 服务控制演练 | `systemctl status/restart di-camera-app` | App 恢复显示 | ✩✩（一次 restart） |
| E-D3 | env 文件与 D-1 通道 | `cat /run/tizen-mobile-env`；尝试追加一行无害变量 → restart → `cat /proc/<pid>/environ` | 变量生效 | ✩✩ |
| E-D4 | T2 演练 | bind-mount **原文件到自己**（无实际变更）→ restart 验证机制可用 → 卸载 | mount 表 + App 正常 | ✩✩ |
| E-D5 | C-2 灰度（E-D1~D4 全绿后） | T2 方式挂"打了 C-2 的副本" → `st app film "…"` 试验 | §7 判据 | ✩✩✩（首个真补丁；全链路回滚预案就位后做） |

> 纪律照旧：一份 telnet 会话一条命令；结果走 FTP 拉；批次留散热间隔；E-D5 前先跑 `gate_flow.py`。

---

## 10. 与既有文档的衔接与修正

| 文档 | 关系 |
|---|---|
| `CAMERA_MENU_ARCHITECTURE_2026-10-07.md` §4 「路 C 不做」 | ★ **修正**：路 C 拆档后，**C-2（13 字节级）可做且推荐**；"全量加页/重编"仍不做 |
| `MCB_PROTOCOL_AND_ST_TABLE_2026-10-08.md` §2（st/队列/key 0x8828） | 本文补全**队列之后的一半**（App 内命令表 + 回执 + 投递侧）；两文合并后通道全链闭环 |
| `FILMLAB_WHEEL_PREVIEW_FEASIBILITY_2026-10-11.md` | 「滚 95 条 ⛔」不变；新增"路线 0 驱动层"作为滚轮交互的新备选 |
| `FW_NATIVE_UI_ONEKEY_FEASIBILITY_2026-10-10.md` | "重刷 rootfs 才能动 di-camera-app"→ 修正为 **remount rw 就地改 / bind-mount** 两条更轻的路 |
| `FEATURE_MATRIX_MOD_FULL_2026-10-11.md` X05/G-6 | §0 结论表回填这两行 |

---

## 11. 附录

### A. 关键地址速查（NX500 v1.12，file offset = vaddr−0x8000（<0x4384ac）/ −0x10000）

| 对象 | vaddr | file | 说明 |
|---|---|---|---|
| `system@plt` | 0xadd08 | — | 桩尾巴 |
| App 命令表 | 0x449d28 | 0x439d28 | ~30 项 {name,handler}，end@0x449e28 |
| `ui_shell_command` | 0xc91a0 | 0xc11a0 | 注册回调 |
| `cmode` handler | 0xc91b4 | 0xc11b4 | pre/pref/upload/make |
| `disp` handler | 0xcaf74 | 0xc2f74 | 参数索引=argv[1] |
| `uscom` 名串 | 0x36d6dc | 0x3656dc | 改 `film` 的目标 |
| `FUN_000ca3a8` | 0xca3a8 | 0xc23a8 | 桩宿主（原 uscom dumper） |
| PW 槽位表①/② | — | 0x40c6a8 / 0x41754c | 步长 0x114 |
| 名→msg 对表区 | — | 0x2fde00–0x306580 | → 解析链 |
| systemd unit | — | rootfs `/usr/lib/systemd/system/di-camera-app.service` | |
| env 文件 | — | `/run/tizen-mobile-env` | tmpfs |

### B. 证据与复跑

- 二进制：`E:/NXWA/fw/v1.12/extract/di-camera-app/…/bin/di-camera-app`（md5 `ae44293e…`，与 rootfs 内文件 md5 一致 ✅）
- Ghidra 全量反编译：`E:/ghidra_out/di-camera-app.arm_dump/04_decompiled.c`、`libshell-command.so_dump/04_decompiled.c`
- chroot 复跑：`chroot /opt/nxks2/rootfs-112 /usr/bin/st help`（WSL）
- 分析脚本（可复跑）：`test_server/isp/dicam/`（README 见该目录）

### C. 变更记录

- 2026-10-11 夜：初版（离线）。新增：systemd 骨架 / st app 全链与命令表 / PW 表结构（G-6 结案）/ C-2 补丁规格 / 投递三路 / 实验 E-D1–E-D5。

---

*生成：2026-10-11 · 分支 `nxwa` · 全程离线（未新增上机动作）*
