# 相机上线核查 + restart 卡死事件（2026-10-13 晚）

> **范围**：执行 `UI0_HOST_FEASIBILITY_2026-10-13.md` §7 的「8 项开机核查清单」，并据此裁定 UI-1 的注入与恢复路径。
> **性质**：7 项只读 + 1 项写机（无害 drop-in 实测）——**写机项触发整机卡死事件**，用户物理重启恢复。
> **口径**：✅ 本机实测 ｜ 🔶 推断 ｜ ❌ 实测证伪 ｜ ❓ 未知（附探查法）
> **上游**：`UI0_HOST_FEASIBILITY_2026-10-13.md`；**下游**：UI-1a 实验设计（须按本文 §5 修订）
> ★ **10-14 深夜修订**：附 D 整体重写（U5 终审）——「刷机重置 /opt/usr」旧结论**推翻**；另破案「刷机后 mod 自动恢复链」（D.5）。

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
- ✅ **`onscreen_ks` / `a_init.sh` 的开机触发者 —— 已定位（10-13 晚 22:0x 补测）**，见 §5「U1 已解」。
- ✅ **`bluetooth-frwk.service` 之谜已解**：它**是** `Type=forking`，其 ExecStart 脚本 `/etc/rc.d/init.d/bluetooth-frwk-service`
  执行 `/usr/bin/bt-service &` 后**立即退出** ⇒ systemd 判定 forking 服务启动失败 ⇒ **journal 不记 `Started Bluetooth service`**。
  而 `bluetooth.target` 无任何 unit 引用却被 reached（`StopWhenUnneeded=yes`）⇒ 早先据「`graphical.target.wants/` 为空」推断
  「该服务从未启动」是**误导**。⚠️ 注：rootfs 是**只读挂载**，`atime` **不可用**（内核在 ro fs 上不更新 atime；`/opt` 又是 `noatime`）。
- 系统 unit 实况：`hib_ready.service` / `wm_ready.service` 均为 **not-found**（但被 `di-camera-app.service` 的 `After=` 引用）；
  `hib_tmp.service` / `hibernation.service` = **active (exited)**，描述均为 "Preparing snapshot image…"。

---

## 5. 残留未知与下一步

| # | 事项 | 状态 | 说明 |
|---|---|---|---|
| U1 | **boot+12.2 s 之前的执行点** | ✅ **已结：不存在** | 见下「U1 结论」 |
| U2 | `restart` 卡死的精确机理 | 🔶 **已收敛为 hibernation 联锁** | 见 **附 C**；❌ 不得再贸然 restart |
| U3 | `onscreen_ks` / `a_init.sh` 的触发者 | ✅ **已定位**（与 U1 同链） | 见下 |
| U4 | G4-0 缺 `.uploads/fw/nx500_v1.12.bin` | ⚠️ **实为克隆差异，非真缺失** | Codex 克隆缺 `.uploads/` 与 `raw8/emmcbak/p7_orig.bin` ⇒ 门控须在**小A克隆**跑（小A克隆 G4 = PASS） |
| **U5** | **SLP 是否含 `/opt/usr/`** | ✅ **10-14 终审：不写 p14**（见附 D） | **`parttab` `opt-usr=image:none` + 十段↔分区映射全锁定 ⇒ 刷 A1 不抹 `/opt/usr/nx-ks`**；旧「会重置 /opt/usr」已推翻；另见附 D.5（自动恢复链） |

### U1 结论：调用链定位完成（10-13 晚补测，纯只读）

**完整链（journal + 进程时间线互证）**：

```
21:16:31 kernel: BT: Loading driver          ← insmod（= /var/log/8887_bt.log 的作者）
21:16:32 kernel: BT: FW download over, size 653112 bytes
21:16:33 kernel: BT: Driver loaded successfully
21:16:33 systemd[1]: Reached target Bluetooth.
    ↓ 3.4 s
boot+37.83 s  keyscan     启动（starttick 3783）
boot+38.57 s  onscreen_ks 启动（starttick 3857）
```

⇒ **`bt-service`（boot+35 s 加载 BT 驱动）→ `/usr/sbin/bluetoothd`（79B wrapper）→ `init.sh`（boot+37.8 s）→ `keyscan`**。

**三项穷举否定**（说明此前为何找不到调用者）：

1. **WSL rootfs-112 全盘 `grep -rF`**：无任何文件引用 `init.sh` / `keyscan` / `/opt/usr/nx-ks/init.sh`
   （`enlightenment`、`license.txt` 两处命中均为 `. ` 正则通配符误报，用 `-F` 复核后消失）
2. **`/opt/usr/nx-ks/` 全部顶层脚本 + `auto/` + `nx-rc/`**：**无一处**调用 `init.sh`
3. **SD 卡 `scripts/`（= `/opt/usr/nx-ks/` 的部署源镜像）与 SD 根目录**：**无 `info.tg` / `nx_cs.adj`**
   （已被 `uninstall_direct.sh` 删除）⇒ SD 触发链当前未激活

⇒ **`boot+12.2 s` 之前不存在任何执行点**（rootfs 上 mod 仅 1 个改动点 = `bluetoothd`；App 的 25 s 初始化结束后才轮到 init.sh）。

**对 UI-1 的路线建议（U1 已结后，据实修订）**：

- **通道 B｜LD_PRELOAD（P1 `/run` drop-in）**：❌ **在「每次开机」场景下判死**——drop-in 由 init.sh 建立（boot+37.8 s），
  永远晚于 App（boot+12.2 s）；且 `/run` 是 tmpfs，**重启即清**，无法跨重启携带；唯一激活手段 `restart` 又会卡死整机。
- **通道 C｜改 unit 本体（P5）**：★ **唯一能保证「早于 App exec」的路径**——直接给
  `/usr/lib/systemd/system/di-camera-app.service` 加 `Environment=LD_PRELOAD=…`，由 `init.sh` 幂等重建。
  需 `mount -o remount,rw /`。**关键认识：mod 早已在 rootfs 写文件（`bluetoothd` wrapper + `bluetoothd.orig`），
  「零 rootfs 写入」本就不是现状** ⇒ P5 与项目既有做法一致，**不是新增违例**。
- **通道 A｜内存补丁（poker 式）**：App 启动后可用、**有先例、零新机制**；但只能写内存（改参数/跳转），
  **不能加载 .so**。适合「改参数/打小补丁」类需求。
- **P2（`EnvironmentFile=`）**：仍需 drop-in 承载 ⇒ 时序问题同通道 B。

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

## 附 C：本机启动为「hibernation 快照式」（U2 的机理落点）

| 证据 | 内容 |
|---|---|
| kernel cmdline | `mem=512M hibernate=nocompress root=/dev/mmcblk0p10 rw rootfstype=ext4 rootwait noresume user_debug=255` |
| `/var/log/hib.txt` | `Mar 30 17:08:48 : echo reboot > /sys/power/disk` ／ `: > open done [/sys/power/state].` |
| systemd units | `hib_tmp.service` / `hibernation.service` 均 `active (exited)`，描述 "Preparing snapshot image…"；`hib_post.path` 监控 `/tmp/.hib_post`；`hib_post.service` = `After=… di-camera-app.service` + `ExecStart=swapoff -a` |
| dmesg 时间戳 | 形如 **`[代: 秒]`**：`[0: 1.22]`（冷启动）→ `[1: 23.06]`（**恢复代**，WiFi 此时才初始化） |
| `/opt/usr/nx-ks/hibernate.sh` | `st cap iq af pos` → `st cap lens power off` → `systemctl hybrid-sleep` |

⇒ 冷启动 → 存休眠快照 → **reboot 恢复**（`/sys/power/disk=reboot` 即此义）。
**这很可能就是 `systemctl restart di-camera-app` 卡死整机的土壤**：App 的生命周期被卷进快照/恢复序列。
🔶 仍属推断，**不得再以 restart 复现验证**（代价是整机卡死 + 物理重启）。

## 附 D：SLP 分区结构与「刷机会不会抹掉 /opt/usr」（U5 核查 · ★ 10-14 终审修订）

> **10-14 深夜整体修订**：10-13 的初判「`idx6/7/9 ↔ p10/p11/p14` ⇒ 刷机将重置 `/opt` 与 `/opt/usr`」**已推翻**。
> 终审手段（全程只读）：① rootfs 内升级器**权威配置** `/etc/parttab` + `/etc/imagetab`（10-14 提取，存档 `rea-tmp/fwbin/`）；
> ② SLP 十段逐段与真机分区/备份**逐字节或指纹比对**（脚本 `rea-tmp/verify_idx8_p12.py`、`verify_idx7_idx9.sh`）；
> ③ 真机 `/proc/partitions` 分区几何对照；④ 离线包级比对（A1 vs 官方）。
> **另：本次一并破案「刷机后 mod 自动恢复链」（见 D.5）——直接决定 A1 的新前置。**

### D.1 十段 ↔ 分区 终审映射表（全部锁定）

| idx | imagetab 名 | 目标分区 | 证据（级别） |
|---:|---|---|---|
| 0 | vImage | **无（跳过）** | parttab 无 vImage 条目（升级器报 "no vImage partition" 跳过）；p6 尾部残段（2.98 MB）与 idx0 尾部逐字节同 ⇒「vImage 曾写 p6、后被 uImage 覆盖前段」的历史遗留 |
| 1 | bootloader.bin | boot0（**@512 B 偏移**） | 与真机 boot0 备份全量逐字节一致（跳过 512 B 设备自带头） |
| 2 | uImage | p6 | 与真机 p6 备份前缀全量逐字节一致 |
| 3 | rImage | p13 | 与真机 p13 备份全量逐字节一致 |
| 4 | devicem4.bin | boot1 | 与真机 boot1 备份全量逐字节一致 |
| 5 | **rom.bin** | **p7**（rtos） | 与真机 p7 头部一致；★ **A1 包唯一改动段**（见 D.3） |
| 6 | rootfs.img | p10（platform） | LZOP→ext4（≈507 MiB = 真机 rootfs fs 尺寸）；cmdline `root=/dev/mmcblk0p10` |
| 7 | opt.img | p11（opt） | LZOP→ext4，解压 104,857,088 B；ext4 superblock @0x438=`53EF`；顶层结构与真机 /opt 一致 |
| 8 | pcache.list | p12（pcache） | ★ **铁证三重**：A1 包 idx8 ≡ 真机 p12 纯净回读（`p12_pristine.bin`）前 28,672 B，**逐字节 diff=0**（md5 `11f6a32f…`，与 U5 文档记录的「相机回读 28672B md5」三方一致）；p12 有效内容恰为前 28,672 B（"PAGECACHE"+"ELIST"，非零最大偏移 28,663）；U5 实刷「改 img8[0] → p12[0] 变」闭环 |
| 9 | **snapshot.img** | **p9（snapshot）** | ★ **Samsung 休眠换出内存镜像**：0x400 处 swap 头 `last_page=38,398 页`×4K = **153,592 KiB = dmesg「Adding 153592k swap on /dev/mmcblk0p9」精确互洽**；0xFEC 处 `SWAPSPACE2`+`S1SUSPEND`（Samsung suspend 签名）⇒ **10-13「App 资源镜像」定性系误判**（见 D.4） |

**十段之外**：`#extended (p4)` 在 parttab 中被注释禁用（order 4 空缺之因）。
**真机几何对照**（`/proc/partitions`，KiB）：p9=153,599 ／ p10=1,048,575 ／ p11=102,399 ／ p12=5,119 ／ p14=2,372,607
——parttab `size(M)` 列 15/17 项精确吻合（含 p12=5、p11=100、p10=1024）；唯二差异见 D.6。

### D.2 升级器权威配置原文（为什么可以断言 p14 不被写）

`/etc/parttab`（rootfs 内，升级器读它决定「写哪些分区」）关键行（全文 17 行见 `rea-tmp/fwbin/parttab`）：

```
# <vol>       <dev>       <size(M)>  <image>          <order> <compress> <fs>  <mount-point>
platform      /dev/mmcblk0p10  1024   rootfs.img         5   LZO   ext4
opt           /dev/mmcblk0p11   100   opt.img            6   LZO   ext4  -j   /opt
opt-usr       /dev/mmcblk0p14     0   none              10   None  ext4  -j   /opt/usr   ← ★ image=none
adj / rtos_data / pref / pref_recovery  (image=none，一律不写)
snapshot      /dev/mmcblk0p9    100   snapshot.img      14   LZO   raw
```

`/etc/imagetab`（10 项 = SLP 十段次序）：
`vImage / bootloader.bin / uImage / rImage / devicem4.bin / rom.bin / rootfs.img / opt.img / pcache.list / snapshot.img`

**规则**：升级器按 imagetab 逐段找分区写镜像；`image=none` 的卷（adj/rtos_data/pref/pref_recovery/**opt-usr**）**不在写入面**；
ext4 卷遵循「挂载成功不格式化」（mkfs_skip）——重写 rootfs/opt 只写镜像内容，不额外破坏。

### D.3 A1 包改动面（字节级实证）

**A1 `slp_a1_p7_g_v116.bin` vs 官方 `NX500_v1.12.bin`：十段逐段比对 ⇒ 九段逐字节相同，唯 idx5（p7）不同**：

| idx | 名称 | A1 md5（前 12) | 官方 md5（前 12） | 同? |
|---:|---|---|---|---|
| 0–4、6–9 | vImage…snapshot（九段） | 全同 | 全同 | ✅ |
| **5** | rom.bin（p7） | `2ee98811a600…` | `5fc4824f5b6a…` | ❌ |

⇒「**A1 = 官方 v1.12 + 仅改 p7**」字节级实锤；执行链/目标范围与官方升级完全一致。

### D.4 旧结论推翻 & 刷 A1 的真实损失面（终版）

**推翻对照**：

| 10-13 初判 | 10-14 终审 |
|---|---|
| `idx9` =「App 资源镜像」（≈150 MiB） | ❌ 实为 `snapshot.img`（Samsung 休眠换出内存镜像）；其中 `di-camera-app`/`slp_edc`/cpio 串 = **换出内存残页** |
| `idx6/7/9 ↔ p10/p11/`**`p14`** | ✅ idx6→p10 ✓、idx7→p11 ✓；❌ **idx9→p9**（与 p14 无关） |
| 刷 A1 会重置 `/opt/usr/nx-ks` | ❌ **不会**：parttab `opt-usr=image:none` + 十段无一段指向 p14 |
| 「解压尺寸与真机分区不吻合，待复核」 | ✅ 已对照：p10=1024 MiB（df 显示的 507M 是 **fs** 而非分区）、p11=100 MiB、p12=5 MiB 全吻合 |

**损失面（终版）**：

| 分区 | 会被写？ | 写入内容 | 影响 | 恢复路径 |
|---|---|---|---|---|
| **p14** `/opt/usr` | **否** | — | ✅ `/opt/usr/nx-ks/` 全部 mod 文件安全（T2 投递物同理——**T2 方案获终审支持**） | 无需处置（撤销 10-13 旧硬前置「刷前备份 nx-ks」） |
| p10 rootfs | 是 | rootfs.img（官方同内容） | mod rootfs 改动被抹：`/usr/sbin/bluetoothd` hook（`.orig`+wrapper） | ★ **自动**：刷后 SD 全量安装装回（见 D.5） |
| p11 `/opt` | 是 | opt.img（官方同内容） | p11 上唯一非固件物 = `/opt/etc/{.mac.info,btmac.info,wl-regdom.conf,auto_check.txt}`；**mtime=开机时刻实证为「开机自动维护的派生物」** | 开机自动重写（值已存档 `rea-tmp/probe_optetc_2026-10-14.txt`）；未恢复可手工写回 |
| p7 | 是 | A1 补丁 rom.bin | ← 本刷机唯一目的 | 按 A1 runbook |
| boot0/boot1/p6/p13 | 是（同内容） | 官方件 | 写入 = 无变化（U4/U5 同型链已安全实证） | — |
| p9/p12 | 是（同内容） | 官方件（休眠快照/pcache） | 无变化 | — |
| NVD（p1/2/3/5）、p8、p4 | 否 | — | MAC/pref 标定不受影响 | — |

### D.5 ★ 刷机后 mod 自动恢复链（10-14 破案，直接决定 A1 前置）

**问题**：完整刷机（如 U5）会把 rootfs 恢复为官方（hook 必被抹）——那 U5 之后的 mod 是怎么活的？

**证据链（全部实测）**：

1. **SYNC.md（主包文档，SD 根）**：相机固件内置触发链 **`info.tg → nx_cs.adj → dfmsd → 自动执行 /mnt/mmc/install.sh`（无需按键）**。
   `install.sh` = **安全分发器**：`bluetoothd.orig` 不存在（=未装）⇒ **全量安装**（含 bluetoothd hook）；已存在 ⇒ 增量同步（`cp -ar scripts/* → /opt/usr/nx-ks/`，不碰 hook）。
   **安装/同步完成后自动删除 3 个触发文件**（防重复触发/防误卸载）。
2. **U5 实测时间线（10-11 晚，多源互证）**：
   - 20:5x R 包刷入 → 自动重启，**21:05:19** 系统启动（由 21:10 时 uptime=281 s 反推）
   - **21:06:51**：hook 安装落盘（wrapper mtime；`.orig` mtime=**2015-04-02** = `mv` 保留原厂时间戳 ⇒ 「安装分支」特征）
   - **21:07**：`find -cnewer` 计 **317 个条目** ctime 落定（`cp -ar` 全量同步指纹：保 mtime、改 ctime）+ `auto/a_init.sh` 生成
   - **21:07:04**：`onboard.log` 落盘（install.sh 完成后调 `onboard.sh` **拉起 telnetd/ftpd**）
   - **~21:10**：此前记录的「telnet 自行恢复」= 上述链跑完的自然结果
3. ⇒ **「刷机后 telnet ~4 min 窗口」机理解闭**：等 dfmsd→install.sh→onboard 链跑完（≈boot+105 s）。
4. ⇒ 反向实证：**U5 刷机确实把 rootfs 恢复为官方**（否则 hook 不会被重装；`.orig` 走的是「不存在→安装」分支）。

**A1 刷机的新前置（正式）**：

1. **SD 卡备好「主包引导器」**：仓库根 3 件套 `info.tg` + `nx_cs.adj` + `install.sh`（**必须最新版**——SYNC.md 警告旧「二象性」版会把「装过再跑」执行成卸载）——素材在本地工作副本 `E:/NXWA/NX-WA-2.88.0-nxwa.1/`；`scripts/` 母本 SD 上已有。
2. 刷机流程照旧（`nx500.bin` 改名 → 机身 UI 升级）。
3. **刷后预期**：重启后 ~2 分钟内 dfmsd 自动触发全量安装（屏幕弹窗）→ 完成后自动重启 → **telnet 由 onboard 拉起**。⇒「别急判砖」纪律的制度化。
4. 若未触发（引导器未放成/已被消费）：走人工路径（机身侧或备用部署）。

### D.6 勘误与遗留

- parttab `size(M)` 列唯一不符：`snapshot=100` vs 真机 p9 ≈150 MiB（产线扩容/历史值，待考；无实践影响——snapshot 只毁休眠快照，开机重建）。
- `opt-usr=0` 系「不参与写入」占位（与 `image=none` 同义），非尺寸不符。
- 10-13「App 资源镜像」证据归因：换出内存残页；「slp_edc 之谜」（= Samsung Link Platform 中间件主题，真机 `/opt`、`/opt/usr` 零命中）两案合并结案。
- 证据文件：`rea-tmp/fwbin/`（parttab/imagetab/升级器全套字符串）、`rea-tmp/verify_idx8_p12.py`、`rea-tmp/sdcard_peek/`（SD 根小文件）、`raw8/emmcbak/`（分区备份 + md5s.txt）。

---
*生成：2026-10-13 晚 · 分支 `nxwa` · 证据源：相机 192.168.0.105 实机探测（telnet/FTP）+ 现场确认*
*★ 10-14 深夜修订：附 D 整体重写（U5 终审）——证据源追加：`/etc/parttab`+`/etc/imagetab` 提取、十段逐字节比对、`/proc/partitions`、SD 触发链实测（317 条 ctime 指纹）*
*本文含 1 项写机记录（§2），已如实记载其后果；其余全部为只读探测。*
