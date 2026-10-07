# USB 有线安全通道 —— 社区方案调研与定案

> 2026-10-06 · 目的：**为 p7 固件刷写建立一条独立于 WiFi 的安全通道**
> 结论前置：**社区不存在"USB 有线 root shell"方案，但存在 3 条可用的 USB 相关路径**；
> 其中真正能提供"刷固件安全性"的是 **Dropbear SSH（加密认证）** + **`info.tgw` PTP/dev 模式（免WiFi 触发）** 的组合。

---

## 0. 一句话结论

| 问题 | 答案 |
|---|---|
| 社区有过"有线 root 模式"吗？| ★ **有 SSH（Dropbear），但是 WiFi 上的；有 USB 触发 dev 模式，但不是 root shell** |
| 社区做过 USB 网卡（rndis/usb0）吗？| ★★ **没有。10 年前就有人判过"走不通"，至今零进展** |
| 对刷固件的安全价值 | ★★★ **SSH = 加密 + 密钥认证 + 不开广播服务**；PTP 模式 = 免 WiFi 的第二条触发链 |
| 能否完全脱离 WiFi | ★★ **不能**。USB 网卡不可行，UART 无信号 ⇒ **刷固件的"最后一根线"只能是 WiFi telnet** |

---

## 1. 三条 USB 路径的完整定性

### 路径 A：★ Dropbear SSH（社区 `ssh-server/`，v2.88 集成）—— **这是你要的那个方案**

| 项 | 内容 |
|---|---|
| 仓库 | `ottokiksmaler/nx500_nx1_modding/ssh-server/`（README + `dropbear-2020.81-nx-path.patch` + `files/`）|
| 原理 | 把 **Dropbear SSH server + OpenSSH 的 `scp`/`sftp-server`** 装到相机 |
| 体积| dropbear ~240KB，**常驻仅 ~2MB RAM** |
| 路径 | 二进制 → `/opt/ssh/`；authorized_keys → `/opt/home/root/.ssh/`；host key → `/opt/ssh/`（首次连接自动生成，`-R`）|
| 启动 | 由 NX-KS 的 `/opt/usr/nx-ks/init.sh` 拉起：`/opt/ssh/dropbear -R &` |
| 安装 | SD 卡放 `files/` 内容 + `authorized_keys` → 开机自动装 |
| 前置| ★ **依赖 NX-KS mod ≥ v2.88**（我们需要装 `/opt/usr/nx-ks/` ⇒ 已满足）|
| 交叉编译 | `arm-linux-gnueabi` + `./configure --disable-{lastlog,utmp,wtmp,utmpx,wtmpx,zlib,syslog} --prefix=/opt/ssh` |

★ **对我们刷固件的安全价值（3 条，条条是刚需）**：
1. **加密 + 密钥认证** ⇒ 局域网里 telnet 空密码 = 任何设备可连；改p7 期间这是致命风险。
2. **SFTP/SCP 双向** ⇒ 11.52MB 的 p7 镜像、SLP 整包、备份包都能安全搬运，不用 FTP（FTP 是明文 + 我们已踩过 CRLF 坑）。
3. **可关掉 telnet/ftp** ⇒ 刷固件期间把广播面缩到只剩一个密钥端口。

⚠️ **patch 只有 5 处路径改写**（`default_options.h`），无代码逻辑改动 ⇒ 移植风险极低：
```
/etc/dropbear/dropbear_*_host_key  →  /opt/ssh/dropbear_*_host_key
/usr/libexec/sftp-server           →  /opt/ssh/sftp-server
/usr/bin/dbclient                  →  /opt/ssh/dbclient
DEFAULT_PATH 加 /opt/ssh:/opt/usr/nx-ks:/usr/sbin:/sbin
```
⚠️社区用 **Samsung `sbs` 工具链**编译。我们有 zig 0.13.0 ⇒ 需验证能否直接编（dropbear 依赖 `libtomcrypt`/`libz`，patch 已 `--disable-zlib`）。
⚠️ **`-B` = 允许 root 无密码登录 = 绝对不要加**（社区 README 自己标了 DANGER ZONE）。

### 路径 B：★ `info.tgw` → USB 线触发 dev/PTP 模式（社区 `Enable-PTP-on-NX500-NX1.md`）

```bash
# SD 卡根目录放一个只含 CRLF 的空文件
printf '\r\n' > /path/to/SD/info.tgw
# 插卡 → 插 USB 线 → 开机
```
| 项 | 结论 |
|---|---|
| 效果 | 机身左侧亮**一串绿点** = factory/development/custom 模式已激活；`dfmsd` 在后台等 PTP/MTP 命令 |
| 收益 | ★ **相机可继续操作**（JPG/RAW/视频/模式都行），同时 PC 能实时读 DCIM（~18MB/s）|
| 兼容 | 社区验证：NX500 ✓ / NX1 ✓ / NX30 ✓ / NX2000(fw1.15) ✓；**Windows 下是 MTP** |
| 代价 | ★ **照片尺寸菜单变灰**（28MP 锁定）|
| ★ 与我们的关系 | ★★★ **`info.tg`（无 w）我们已经在用**（触发 dfmsd 跑 install.sh）。**`info.tgw` 是它的 USB 变体** |
| ⚠️ 关键线索 | 社区原话：**"dfmsd daemon expects textual commands from the computer"** ⇒ 有文本协议入口，**但至今无人逆完** |
| 已验证失败 | `gphoto2 --summary` → `PTP I/O error` / `vendor or product id (0x0,0x0) is not valid` ⇒ **PTP 响应不完整** |

⇒ ★★ **这条线的真实价值不是"root over USB"，而是"免WiFi 的第二条触发链 + 高速文件通道"。**
★ 而且它和我们的 SD 卡触发链**是同一套机制**，改一个字（`tg`→`tgw`）就能复用。

### 路径 C：UART 串口（`console=ttyAMA0,115200n8`）—— **硬件存在，但社区已判死**

| 证据 | 内容 |
|---|---|
| ★ 实机内核 cmdline | `console=ttyAMA0,115200n8` ⇒ **UART0 就是内核 debug console**（NX1 GPIO map: UART0 = pin 9:4,5）|
| ★ 社区尝试结果 | issue #44（Vasile）：**"brick resurrect attempt failed, no UART signals coming out on the microUSB connector"** |
| 判定 | ★★★ **microUSB 口上没有 UART 桥**。UART0 是**机身内部测试点**（GPIO 9:4/5），要飞线才能用 |
| gphoto 佐证 | `Serial port support : no` |

⇒ **对刷固固件的价值 = 0（现状下）**，但记录在案：
★ 未来若做"终极救援通道"，飞线 UART0（2 根线，GPIO 9:4/5）+ USB-TTL 适配器
⇒ 能拿到 **bootloader 阶段的完整 console**，这是 p7 改坏时**唯一**能救砖的手段（SLP 官方退路只覆盖 p7 本身）。
⚠️ **绝不能因此拆机**—— 只在"p7 改坏 + 官方 bin 也救不回"这个极端场景才考虑。

---

## 2. ★★ USB 网卡（RNDIS/ECM/g_ether）：**判定为不可行**

你问的"有线 root 模式"如果指USB 网卡，答案是**社区零进展，且有10 年前的明确负面结论**：

| 判据 | 证据 |
|---|---|
| 社区无人做过 | 100 条 issues 全扫：USB 相关仅 5 条（#115 webcam/#63 screen off/#51 rsync to USB HDD/#42 USB 远控快门/#37 PTP）**零条涉及 USB 网络** |
| 串口被明确排除 | gphoto `Serial port support : no` |
| PTP 不完整 | `--summary` 直接 `PTP I/O error` + `VID/PID = 0x0,0x0` ⇒ USB 栈只是半通|
| 内核侧 | 实机 `/proc/modules` 只有 6 个模块（sd8xxx/mlan/cfg80211/bt8887/exfat×2）⇒ ★ **无 USB gadget 模块**；`/dev` 无 `usb0`/`rndis0` 痕迹 |
| 硬件 | microUSB 2.0，NX1 GPIO map 有 `USB_DET`(pin 25:4)⇒ 有物理检测脚，**但 DRD（双角色）能力未证实** |
| ★ 结论 | ⇒ 要做 USB 网卡得**重编内核加 `g_ether`/`g_multi` gadget + 确认 DRD 硬件**。<br>★ 而刷固件只需要"一条可靠通道"，**不需要 USB 网卡** ⇒ **投入产出比极差，不做** |

---

## 3. ★ 刷固件的安全通道设计（结论性方案）

### 3.1 通道矩阵

| 通道 | 加密 | 认证 | 带宽 | 刷固件用途 | 现状 |
|---|---|---|---|---|---|
| telnet | ✗ 明文 | ✗ 空密码 | 高 | **兜底救援**（唯一不可被自己锁死的）| ★ 已在用，**永不删** |
| FTP | ✗ 明文 | ✗ 空密码 | ~18MB/s | 快速搬运镜像（SD 卡已够用）| 已在用 |
| ★ **SSH/SFTP** | ✓✓ | ✓✓ 密钥 | 高 | ★★★ **刷固件主通道** | ★ **待装（社区现成方案）** |
| ★ USB PTP | — | — | ~18MB/s | ★ 免 WiFi 触发 + 高速导图 | 待试（`info.tgw`）|
| USB 网卡 | — | — | — | ❌ **不可行** | 不做 |
| UART | — | — | 115200 | 仅终极救援 | 需飞线，不做 |

### 3.2 ★★ 刷固件时的分层策略

```
第0 层（改前）：★ 10 个分区备份已全部校验 PASS（9-9）← 这是最后一道防线
第 1 层（改时）：SSH/SFTP 为主通道（加密+密钥）+ telnet 保留为兜底
第 2 层（改后）：★ p7 专用退路 = SLP 整包刷机身菜单（官方 .bin 改名 nx500.bin）
第 3 层（终极）：UART0 飞线（只在 p7 + 官方 bin 都救不回时）
```

★ **关键安全动作（改 p7 前后必做）**：
1. **只开SSH，关 telnet/ftp**（`init.sh` 注释掉 telnet 启动行）⇒ 缩到单个密钥端口
2. ★ **host key 预生成**（先连一次生成 `/opt/ssh/dropbear_*_host_key`）⇒ 避免首次连接时相机在写 flash
3. ★ **p7 镜像走 SFTP 传输**，不用 FTP ⇒ 避免明文传输被中途改动（★ 这是"刷固件安全性"的实质）
4. ★ **回读校验**：刷完立刻 `md5sum` 校验 p7，与 PC 侧比对
5. ★ **`boot0` 仍无备份** ⇒ 动手前必须补（唯一未备份分区）

---

## 4. 行动项（按优先级）

| # | 任务 | 风险 | 收益 |
|---|---|---|---|
| **U1** | ★ **补 `boot0` 备份**（10→11 分区）| 零（只读）| ★★★ 补上唯一缺口 |
| **U2** | **装 Dropbear SSH**（社区 `ssh-server/files`）| 低（纯新增，不覆盖）| ★★★ 刷固件主通道 |
| **U3** | **zig 0.13 能否编 dropbear**（替代 Samsung `sbs`）| 低（编不过就用社区二进制）| 中 |
| **U4** | 试 `info.tgw` → USB PTP 模式 | 零（SD 卡放个文件）| ★★ 免 WiFi 第二触发链 |
| **U5** | 逆 `dfmsd` 的 USB 文本协议 | 中 | ★ 可能拿到 USB 控制通道 |
| **U6** | 验证 `SelCbCr_ch` / 4 档切换（**回到 A 线主任务**）| 低 | ★ 零风险可交付 |
| ✗ | USB 网卡 RNDIS | — | ❌ **不做** |

---

## 5. 明确不做

| 项 | 理由 |
|---|---|
| USB 网卡 / RNDIS | 内核无 gadget 模块，硬件 DRD 未证实，收益仅"更快的 telnet"，而SSH 已解决同一问题 |
| 拆机飞线 UART | 现阶段完全不需要；只在"p7 + 官方 bin 双双失效"时才是唯一手段 |
| 逆 dfmsd USB 文本协议（现在做）| U5 有价值但**不阻塞任何交付** ⇒ 排在 A 线之后 |

---

## 6. 一句话答复

**你要找的方案社区确实有，叫 Dropbear SSH（`ssh-server/`，v2.88 集成，~240KB + 2MB RAM），但它跑在 WiFi 上，不在 USB 上。**
**"有线 root" 社区从未做出来** —— USB 网卡 10 年前就判死（内核无 gadget 模块 + PTP 栈半通 + gphoto `Serial port:no`），
唯一能上"有线"的是 `info.tgw` 触发的 PTP/dev 模式，但它是文件通道不是 shell。
⇒ **要刷固件的安全性，答案是装 SSH 把 telnet 收窄，而不是折腾 USB 网卡。**