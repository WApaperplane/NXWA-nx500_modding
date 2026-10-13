# 相机上线核查 + restart 卡死事件（2026-10-13 晚）

> **范围**：执行 `UI0_HOST_FEASIBILITY_2026-10-13.md` §7 的「8 项开机核查清单」，并据此裁定 UI-1 的注入与恢复路径。
> **性质**：7 项只读 + 1 项写机（无害 drop-in 实测）——**写机项触发整机卡死事件**，用户物理重启恢复。
> **口径**：✅ 本机实测 ｜ 🔶 推断 ｜ ❌ 实测证伪 ｜ ❓ 未知（附探查法）
> **上游**：`UI0_HOST_FEASIBILITY_2026-10-13.md`；**下游**：UI-1a 实验设计（须按本文 §5 修订）

---

## 0. 结论先行

1. ★★ **`systemctl restart di-camera-app` = 整机卡死**（实测 1 次，须物理重启恢复）。
   ⇒ UI0 §2 的「首次注入靠 restart 兜底」与「单命令回滚 `… && systemctl restart di-camera-app`」**全部作废**；
   ⇒ UI0 §4 的「在同一 drop-in 内启用 `Restart=always` 作为自愈」**反成杀手**——App 一旦异常，
   systemd 就去 restart，而 restart 即卡死，**比不自愈更糟**。
2. ✅ **P1 drop-in 通道的静态面成立**：systemd 208 **认** `/run/systemd/system/<unit>.d/*.conf`
   （`systemctl show -p DropInPaths` 已登记该文件），`Environment=` 被 systemd 采纳。
   这条静待裁决的 🔶（UI0 §2 末）**裁决完毕 = 支持**。
3. ✅ **P1 的 tmpfs 性质实测成立**：整机重启后 drop-in **自动消失**、App 回到**原厂环境**（environ 无注入变量）
   ⇒ 「重启即清、免刷机、免清理」这一核心卖点**得到实证**（虽是意外取得）。
4. ★ **仓内存在「往 di-camera-app 进程内注入」的既有先例**：`/opt/usr/nx-ks/auto/a_init.sh` 以
   `poker $(pgrep di-camera-app) <addr:value> …` 对**运行中**的 App 打内存补丁（9 组）。UI0 §0 结论 3
   「仓内无任何往 di-camera-app 注入 .so 的先例」——**.so 注入确无先例，但内存补丁有先例**，须区分。
5. ⏳ **注入时序仍无解**：App 于 **boot+12.2 s** 启动；唯一已确认的开机钩子（bluetoothd wrapper → init.sh）
   在 **boot+37.8 s** ⇒ **drop-in 永远慢 25 s**。「boot+12.2 s 之前的执行点」❓ **未找到**，是 UI-1 的头号阻塞。

---

## 1. 八项链路核查结果（全部有结论）

| # | 核查项 | 结果 | 依据 |
|---|---|---|---|
| 1 | `systemctl --version` | ✅ **208** | 与 WSL rootfs-112 一致 ⇒ drop-in 机制（≥v207）成立 |
| 2 | 启动时序裁决 | ✅ App **boot+12.2 s**／init.sh **boot+37.8 s** | `/proc/<pid>/stat` 第 22 字段（HZ=100）：di-camera-app=1224 tick，keyscan=3783 tick |
| 3 | 真机 `res/edje/` | ✅ **4 个 .edj** | `nx_style.edj` / `nx_style_hdmi.edj` / `nx_style_hdmi_720.edj` / `tizen-hd.edj`；**无 slp_edc** |
| 4 | `slp_edc*.edj` 全盘 | ✅ **非本 App 资源** | 仅存在于 `ap-setting-app/res/edje/com.samsung.ap-setting-app/`(19) 与 `smart-wifi-app/res/edje/`(6)；`/opt`、`/opt/usr` 下**零命中** |
| 5 | 无害 drop-in 实测 | ✅ 静态面成立 ／ 🔴 **激活动作卡死整机** | 见 §2 |
| 6 | App 真实环境 | ✅ 与 UI0 §1 表**逐条一致**，**无 LD_PRELOAD** | `/proc/247/environ`（PID 247=di-camera-app）⇒ 当前**零注入**、干净基线 |
| 7 | mount 拓扑 | ✅ rootfs **ro**（507 M，**96 % 用满**，剩 23 M）／`/opt`=p11 rw 45 %／`/opt/usr`=p14 rw（2.3 G 用 **6 %**）／SD=exfat rw | `mount` + `df -h` |
| 8 | `/opt/usr/nx-ks/dicam/` | ✅ **不存在**（`ls` RC=2）⇒ T2 投递目录待建 | C-2 波次共用 |

**额外基线（G1-3「上机前负载基线」）**：单核，loadavg `1.06/0.82/0.38`；
**di-camera-app 单进程 CPU 61 %、累计 2 m 18 s**；`MemFree` 仅 **≈9.7 MB**（`MemTotal` 500 MB）；
rootfs 96 % 满、`/run` tmpfs 250 M 充裕、`/opt/usr` 空间充裕。

---

## 2. restart 卡死事件（★ 本文最重要的一条）

### 2.1 动作序列

```sh
# 1) 建 drop-in（只读语义，无副作用）
D=/run/systemd/system/di-camera-app.service.d
mkdir -p $D
printf '[Service]\nEnvironment=NXWA_TEST=1\n' > $D/nxwa-test.conf
systemctl daemon-reload
# 2) 激活动作 ← 出事点
systemctl restart di-camera-app
```

### 2.2 观测结果

| 阶段 | 观测 | 判读 |
|---|---|---|
| drop-in 建立后 | `systemctl show -p DropInPaths` = `/run/systemd/system/di-camera-app.service.d/nxwa-test.conf`；`-p Environment` = `NXWA_TEST=1` | ✅ **通道成立** |
| `daemon-reload` | `RELOAD_RC=0` | ✅ 无报错 |
| **`restart` 后** | **整机卡死**（用户现场确认「相机卡死了」）；telnet 会话失去 prompt 同步，FTP 取回超时 | 🔴 **卡死** |
| 用户物理重启后 | `/proc/uptime` = 127 s（先前 364 s）；journal 首条 `Oct 13 21:16:47`；**SD 卡无新 crash 日志** | ✅ **干净重启**，非崩溃 |
| 重启后复查 | drop-in 目录**为空**（`/run` tmpfs 被清）；App environ **无 NXWA_TEST**（回到原厂环境） | ✅ **P1 tmpfs 性质实证** |

### 2.3 机制推测（❓ 待证）

- `regpmon.sh`（`rc3.d/S99regpmon` 等）用 `set_pmon` 注册监控，**名单中无 `di-camera-app`**
  ⇒ **不是**「进程监控发现 App 死了就 reboot」这条路径。❌ 排除。
- `regpmon.sh` 头部写着 `# Don't regist processes on hibernation capturing sequence`，并检查
  `/opt/etc/.hib_capturing`、`/opt/etc/.hib_capturing_firstboot`；`HIB=a` 贯穿 App 与 init.sh 的环境
  ⇒ **整机存在 hibernation / 快照式快速启动机制**，`di-camera-app` 很可能与之绑定。
- 最可能：**App 的退出（SIGTERM）被系统级联锁放大**——系统判定「主应用退出」而进入
  hibernation 捕获/恢复序列，该序列在无显示/无前端时挂死。**这是推断，不是结论。**
- 与 **U2 v9 同型**（「第二套全屏 GL 窗口拖死整机，需物理重启」）——但本次**连窗口都没建**，
  仅 restart 一个既有进程即可致死 ⇒ 说明该机型对 App 生命周期的扰动极其敏感。

### 2.4 对 UI-1 的硬修正（必须落到实验设计）

| UI0 原设计 | 修正后 |
|---|---|
| §2 回滚 = `rm -rf … && daemon-reload && restart` | **禁用 restart**。回滚只做「删 drop-in + daemon-reload」，**再走自然重启**（用户正常关机/开机） |
| §2 首次注入靠 `systemctl restart` 兜底 | **作废**。注入必须**在 App 首次 exec 之前**就绪 ⇒ 见 §5 |
| §4 启用 `Restart=always` + `RestartSec=3` | **禁用/重新评估**。若 App 异常，systemd 会 restart ⇒ **自动卡死**。自愈须换机制（watchdog 拉活、或接受物理重启兜底） |
| §5 判据 4「可逆：删 drop-in + reload + restart ⇒ 心跳不再出现」 | 改为「删 drop-in + reload ⇒ **自然重启一次** ⇒ 心跳不再出现」 |
| §0 结论 3「无注入先例」 | 修正为「**.so 注入无先例；内存补丁有先例（poker）**」 |

---

## 3. mod 注入架构发现（同批取得，改写 UI0 部分结论）

1. ★★ **`/opt/usr/nx-ks/auto/a_init.sh`（645 B，mtime 10-11 21:07）—— 既有「进程内注入」工具链**：

   ```bash
   renice -n -15 -p $$
   [[ $(echo $(st cap capdtm getusr MONITOROUT) | grep LCD) > "" ]] && $( /opt/usr/nx-ks/onscreen_ks & ) &
   /opt/usr/nx-ks/poker $(pgrep di-camera-app) 0xb4095a08:c0f68910 0xb40959fe:c0f6ba20 \
       0xb4095a68:c0f6ba20 0xb409596a:c0f25d53 0xb40958f8:c0f25d53 0xb4095a58:c0f25d53 \
       0xb4095928:c0f25d53 0xb40959aa:c0f6ba23 0xb40959b2:c0f6ba23
   systemctl set-environment Pro4K=160 ProHD=180 Hq4K=90 HqHD=90 HqVGA=180 fps=4 &
   ```

   - **`poker`**（472,702 B，2016-04-27）= 往**运行中**进程写内存的补丁器，用法 `<pid> <addr:value>…`
     ⇒ **这是「App 启动之后再动手」的成熟先例**（与 LD_PRELOAD 的「必须早于 exec」形成两条互补通道）。
   - `pgrep di-camera-app` 取 PID ⇒ 证明 mod **已有**在 App 运行时定位并改写其内存的能力。

2. **`a_init.sh` 是生成物**：`/opt/usr/nx-ks/br_up.sh` 用 `pokemonche <key> <val>` 逐项拼参，
   再 `sed` 渲染模板 `/opt/usr/nx-ks/init_auto.tp` → `auto/a_init.sh`（同名工具族：`poker` / `pokemonche`）。

3. 其他既有件：`bt.sh` 手动切蓝牙（调 `bluetoothd.orig` + restart `bluetooth-frwk`）；
   `uninstall*.sh` **含 `reboot`**；`install.sh` 是「二象性」脚本（`bluetoothd.orig` 已存在即走卸载分支）。

---

## 4. 开机钩子链（实测 + 残留未知）

```
kernel → systemd(PID 1)
  ├─ boot+ 9.7s  enlightenment
  ├─ boot+12.2s  di-camera-app          ← ★ 目标进程，唯一窗口在此之后
  ├─ boot+37.8s  keyscan                 ← init.sh 第 40 行启动
  ├─ boot+38.6s  onscreen_ks             ← ★ 启动者未知 ❓
  └─ boot+42.5s  FTP(busybox tcpsvd) / telnetd
```

- ✅ **`/usr/sbin/bluetoothd` = mod 的开机钩子**：79 B wrapper（原厂二进制改名 `bluetoothd.orig`，332,440 B），
  内容 `if [ -x /opt/usr/nx-ks/init.sh ]; then /opt/usr/nx-ks/init.sh; fi`。
  `init.sh` 全文 = 纯 `export` 环境变量 + `nice -n +15 keyscan … &`（**无任何 drop-in / 注入逻辑**）。
- ✅ **`init.sh` 本次开机确实执行过**：keyscan（PID 333/334）参数与 init.sh 第 40 行**逐字一致**。
- ❓ **`onscreen_ks`(boot+38.6 s) 的启动者未确认**；`a_init.sh`（其唯一已知启动者之一）**不在**开机自启链中。
  **探查法**：在 `/opt/usr/nx-ks/*` 与所有被替换二进制中 grep `onscreen_ks`/`a_init`；
  或下次开机前给 `init.sh` 加一行 `date >> /mnt/mmc/boot.log`，逐脚本插桩。
- ⚠️ `bluetooth-frwk.service` 实测 **disabled + inactive(dead)**（`ps` 无 bluetoothd）⇒ **init.sh 的实际调用者并非它**，
  另有一处调用 `bluetoothd`（候选：开机早期某个 unit）❓。
- 系统 unit 实况：`hib_ready.service` / `wm_ready.service` 均为 **not-found**（但被 `di-camera-app.service` 的 `After=` 引用）；
  `hib_tmp.service` / `hibernation.service` = **active (exited)**，描述均为 "Preparing snapshot image…"。

---

## 5. 残留未知与下一步

| # | 事项 | 影响 | 探查/解决法 |
|---|---|---|---|
| U1 | **boot+12.2 s 之前的执行点** | ★ **UI-1 头号阻塞** | 逐脚本插桩 `/mnt/mmc/boot.log`；查 rc3/rc5.d 全链、被替换二进制清单 |
| U2 | `systemctl restart di-camera-app` 卡死的**精确机理** | 决定能否有安全重启路径 | 查 `amd` / `launchpad*` 守护逻辑；`st cap` 观察；❌ **不得再贸然 restart** |
| U3 | `onscreen_ks` / `a_init.sh` 的开机触发者 | 决定能否复用该时机做注入驱动 | 见 §4 |
| U4 | G4-0 缺 `.uploads/fw/nx500_v1.12.bin` | 门控 G4 **FAIL**，挡 L4（改 p7） | 补备份（工作区已有 `NX500_FW_v1.12.zip`，需解压就位） |

**对 UI-1 的路线建议（本轮实测后）**：

- **通道 A｜内存补丁（poker 式）**：App 启动后可用，**零新机制、有先例**；但只能写内存数据（改参数/跳转），
  **不能加载 .so**。适合「改参数/打小补丁」类需求。
- **通道 B｜LD_PRELOAD（P1 drop-in）**：静态面已成立，但**受时序死锁**——除非找到 boot+12.2 s 前的执行点，
  或改 unit 本体（rootfs 写，破坏「零 rootfs 写入」）。**U1 不清则此路不通。**
- **通道 C｜改 unit 本体加 `ExecStartPre`（P5）**：时机天然正确，但需 `mount -o remount,rw /` ⇒
  **放弃零写入**，且刷机重置。可作为「U1 长期无解时」的降级选项。
- 另有 **P2（`EnvironmentFile=-/opt/usr/nx-ks/dicam/nxwa.env`）**：把环境值与代码分离，
  **但仍需 drop-in 承载，时序问题同上**。

---

## 附 A：本次新建工具（`E:/NXWA/tools/`，不入库）

| 工具 | 用途 |
|---|---|
| `nx-telnet.py` | 纯 socket 批量 telnet 执行（无 `telnetlib` 依赖），`-c`/`-f` 传命令 |
| `nx-probe.py` | ★ **telnet 发一条复合命令 → 落 SD 卡 → FTP 取回**；遵门控 **G1-4「不信回显」**；文件名带 pid 防并发覆盖 |

**环境事实（工具相关）**：telnet 登录名 `drime5`，root 空密码；FTP 服务 =
`busybox tcpsvd/ftpd -w /opt/storage/sdcard`；**`/mnt/mmc` 是 `/opt/storage/sdcard` 的 symlink**；
**busybox 无 `pidof`**（用 `grep /proc/*/comm` 或 `pgrep`）；SD 卡 exFAT。

## 附 B：本次执行纪律复盘

- ✅ 遵守门控 **G1-4**（会话只发一条命令、结果走 FTP）——首次违规（批量 telnet + 读回显）已自查纠正。
- ✅ 遵守 **G1-7**（探测用单条复合语句，无长驻进程）。
- ❌ **教训**：写机项（§7-5）**未先评估「restart 该 unit 的副作用」**即执行。UI0 把它标为「无害」，
  实测并非无害。⇒ **凡涉及重启系统服务的动作，执行前须先查该服务的依赖/联锁（本机型尤其：hibernation 联锁）。**

---
*生成：2026-10-13 晚 · 分支 `nxwa` · 证据源：相机 192.168.0.105 实机探测（telnet/FTP）+ 现场确认*
*本文含 1 项写机记录（§2），已如实记载其后果；其余全部为只读探测。*
