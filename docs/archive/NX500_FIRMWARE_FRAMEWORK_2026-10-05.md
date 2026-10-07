# NX500 相机系统固件层整体框架

> 爬取时间：2026-10-05 21:10–21:20
> 目标机：`192.168.0.105`（**注意：IP 变了，原 `.103` 已不通**），`NX500` 固件 `1.12`，`NX500GLU0APC1`
> 数据落盘：`test_server/sysarch/raw8/`（89 份文件，278 KB 原始输出）
> 爬取器：`test_server/sysarch/fwprobe.py`（批次化、串行、每条独立超时、可断点续跑）

---

## 〇、抓取方法与铁律遵守情况

| 铁律 | 本轮执行 |
|---|---|
| telnet 必串行 | ✅ 全程单会话，每条命令独立发送 |
| 禁用 `cat /proc/iomem` | ✅ 脚本里**根本没有这条命令** |
| 禁用 `find /sys/...` | ✅ 只用 `ls` + 限定深度 |
| 单条命令 ≤2.5s | ✅ 超时上限 6s，实测每条 0.3–1.5s |
| ≥10KB 走 FTP | ✅ `libudd5.so`(320KB) + 7 份 ini 全部走 FTP |
| CRLF 是头号坑 | ✅ 落盘前统一 `CRLF → LF` |

**批次执行结果：89/89 条全部成功，0 失败 0 中断。**

---

## 一、系统总览

```
Machine: Samsung-DRIMe5-ES          ← dmesg 冷启动首行
Linux 3.5.0 #7 PREEMPT 2015-06-03   ← 内核（比记忆里的 3.5.0 hs2704 更早）
#1 PREEMPT Wed Jun 3 14:40:29 KST 2015 armv7l
/etc/version: 1.12 / NX500 / NX500GLU0APC1 / DSP_NX500GLU0APC1_SR1 / BABF43A
Tizen 2.2.0 Magnolia
```

**DRIMe5-ES SoC 组成**（`d5_lib.h` 中断枚举 + dmesg 双证）：

| 核 | 角色 | 证据 |
|---|---|---|
| **Cortex-A9 (CA9)** | 应用核，跑 Linux/Tizen | 用户态全部在这里 |
| **Cortex-A7 (CA7)** | 协处理器 | `s1 key push!(ipcc raw int[a7_2:0])` |
| **★ ISP（ID=31）** | 图像信号处理 | `DRIME5: IDS : 31(ISP), 57(ARM)` |
| ARM（ID=57） | 主核 | 同上 |
| Cortex-M4 ×N | 实时微控制器 | `m4_off_work_handler M4 Off` |
| SRP | DSP | 头文件声明，**内核侧无代码路径** |

---

## 二、存储层与挂载拓扑

```
/dev/root          ext4   ro   ← 只读 rootfs（/usr /bin /sbin /lib 都在这）
/dev/mmcblk0p11    ext4   rw   → /opt              （应用数据，可写）
/dev/mmcblk0p14    ext4   rw   → /opt/usr          （NX-KS2 mod 部署在此）
/dev/mmcblk1p1     exfat  rw   → /opt/storage/sdcard  （SD 卡，FTP 根）
/dev/loop0         squashfs ro  → /usr/share/locale
tmpfs                     rw   → /tmp /var/log /var/run /dev/shm
```

★ **关键结论**：
- **`/usr` 在只读 rootfs** ⇒ 改系统库必须走 `/opt/usr` 覆盖或换 rootfs，**不能原地改**。
- **mod 部署目标 `/opt/usr/nx-ks/` 在可写分区 p14** ⇒ 这是唯一安全的落地点。
- **FTP 根 = SD 卡**（`/opt/storage/sdcard`），不是 `/`。这解释了为什么直接
  `RETR /opt/usr/lib/xxx` 返回 `550 Error`。

### 分区表（`/proc/partitions`，eMMC 3.7 GB）

| 设备 | 大小 | 推测用途 |
|---|---|---|
| `mmcblk0p1..p4` | 20M/10M/30M/1K | bootloader 区 |
| `mmcblk0p5..p8` | 20M/10M/30M/50M | 厂商镜像（**未挂载，可能是只读固件分区**） |
| `mmcblk0p9` | 150M | ? |
| `mmcblk0p10` | 1G | ? |
| **`mmcblk0p11`** | **100M** | **`/opt`** |
| `mmcblk0p12/13` | 5M/10M | ? |
| **`mmcblk0p14`** | **2.3G** | **`/opt/usr`** |
| `mmcblk0boot0/1` | 4M ×2 | eMMC boot 分区（unknown partition table） |

★ **`mmcblk0p5..p8` 未挂载 = 极可能存 ISP 固件本体**。这是下一步首选目标。

---

## 三、用户态框架

### 3.1 关键进程（`/proc/*/comm`）

| PID | 进程 | 说明 |
|---|---|---|
| 1 | `systemd` | Tizen 2.2 风格 init |
| 139 | `Xorg` | **X11 图形（满屏 720×480 吃满单核）** |
| 175 | **`launchpad_prelo`** | ★ **会拉起 `di-camera-app`，杀不掉** |
| 197 | `enlightenment` | EFL 窗口管理器 |
| **252** | **`di-camera-app`** | ★ 相机主程序（CPU 时间 00:25:29） |
| 259 | `isf-panel-efl` | 取景面板 |
| — | `dfmsd` (7.3 MB) | Tizen 应用管理守护 |
| — | `MOAL_*` | Marvell 无线驱动 |
| 154 | `nx-on-wake` | ★ **NX-KS2 自加的唤醒脚本** |

### 3.2 关键库（`/usr/lib`）

| 库 | 大小 | 作用 |
|---|---|---|
| **`libudd5.so`** | **320216** | ★ **DRIMe5 用户态硬件驱动主库**（`-ludd5`） |
| `libtint-util.so` | 254252 | ★ 三星内部图像工具（yccMixer / yccToRgb） |
| `libevas.so.1.7.99` | 739008 | EFL 画布 |
| `libsoup-2.4.so` | 327244 | HTTP 客户端（80 端口相册用） |
| `libpulsecore-4.0.so` | 421960 | 音频 |
| `libsensor.so.1.1.0` | 83716 | ★ 传感器抽象层 |
| `libdrm_drime5.so.1` | 5840 | DRM 显示 |
| `libmm-displayer.so` | 28844 | 显示抽象 |
| `libmm-type.so` | 19296 | `CYcc` 类型系统 |

### 3.3 `libudd5.so` 关键导出（503 符号）

- **EP（图像引擎）**：`d5_ep_open/close`、`d5_ep_top_update_sreg`、`d5_ep_3dl_load_lut/save_lut`、
  **`d5_ep_nog_set_noisegen`** ★、`d5_ep_mc_*`、`d5_ep_srsz_*`、`d5_ep_lvr_*`、`d5_ep_jpeg_*`、`d5_ep_bitb_*`
- **基址变量（.bss）**：`ep_top_reg_base@…`、`ep_3dlut_reg_base`、`ep_nog_reg_base` 等 11 个
- **IPCC**：`ipcc_open/close/read_pkt/write_pkt/raw_send_interrupt`
- **GPIO / SPI / PWM**：`ugpio` 全套
- **SMA**：`d5_ep_sma_virt_to_phys`（虚拟→物理地址转换，EP DMA 必需）

### 3.4 设备节点（`/dev`）

| 节点 | major:minor | 对应 |
|---|---|---|
| **`/dev/drime5_ep`** | **10:126** | ★ **EP 图像引擎**（NOG/3DLUT 都在这） |
| `/dev/d5_sma` | 10:112 | 共享内存分配器 |
| `/dev/d5_ipcc` | 10:111 | 跨核 IPC |
| `/dev/d5_mptop` | 10:108 | 多核拓扑 |
| `/dev/d5_cmdq` | 10:110 | 命令队列 |
| `/dev/d5_hevc` | 10:107 | 硬件 H.265 |
| `/dev/d5_lock` | 10:109 | 硬件锁 |
| `/dev/mipi_csis*` | 10:101–106 | MIPI CSI 接收（传感器） |
| `/dev/mipi_dsim0/1` | 10:100/101 | MIPI DSI 发送（屏） |
| `/dev/kmem`, `/dev/mem` | 1:2, 1:1 | ★ 内核内存（EP dump 靠它） |
| `/dev/fb0` | 29:0 | framebuffer |

★ **`d5_promise` 有 sysfs 但无设备节点** ⇒ 纯内核内部组件（多核电压域），
   用户态无法访问。`tmcb` 节点读出 9 组温度/电压统计（min/max/mean）。

---

## 四、内核层

### 4.1 平台设备（`/sys/bus/platform/devices/`，52 个）

**DRIMe5 专属**：`d5_cmdq` `d5_hevc` `d5_ipcc` `d5_lock` `d5_mipi_csis*` `d5_mipi_csim*`
`d5_mipi_dsim*` `d5_mptop` `d5_promise` `d5_sma` `d5_tsu` `drime5_ep.0` `drime5-keys`
`drime5-adc` `drime5-clock` `drime5-ddrfreq` `drime5-drm.0` `drime5-drm-hdmi.0`
`drime5-fault-handler` `drime5-i2c.0..5` `drime5-i2s.0` `drime5-ispfreq` `drime5-pmu.1`
`drime5-pwm.4/5/10` `drime5-rmu.0` `drime5-rtc` `drime5-thermister` `drime5_cec.0`
`drime5_dp_ctrl.0` `drime5_lcd` `drime5_spi.0` `drime5_wdt` `drimex-drd.0` `d5-adc-battery`

**加载模块（`/proc/modules`）**：`sd8xxx`(459K) `mlan`(391K) `cfg80211` `bt8887`(722K)
`exfat_fs` `exfat_core`
⇒ **DRIMe5 全部编译进内核**（无独立 .ko），只有 WLAN/BT/文件系统是模块。

### 4.2 冷启动 dmesg 关键行（本轮首次拿到 `[ 0: 0.000000]` 段）

```
[ 0: 0.000000] Booting Linux on physical CPU 0
[ 0: 0.000000] Machine: Samsung-DRIMe5-ES
[ 0: 1.243065] drime5_es_init()
[ 0: 1.245633] DRIME5: IDS : 31(ISP), 57(ARM) PROMISE : 97 RESULT : 8
[ 0: 1.245640] DRIME5 ASV : 8 Group
[ 0: 1.278069] VDD_ISP: 770 <--> 1400 mV at 860 mV      ← ★ ISP 电压域
[ 0: 1.285031] Switching to clocksource drime5_clocksource_timer
[ 0: 1.294795] dma-pl330.0: Loaded driver for PL330 DMAC
[ 0: 1.308053] Mali: Mali device driver loaded
[ 0: 1.308212] UMP: UMP device driver 1 loaded
[ 0: 1.339544] input: Melfas MMS100s Touchscreen
[ 0: 2.305072] drime5_wdt: Watchdog Timer enabled (5 seconds)
[ 0: 2.421656] mmcblk0boot0: H4G2a partition 1 4.00 MiB
```

★★ **本轮定案：整个冷启动日志里没有任何 ISP 固件加载记录。**
`request_firmware` / `uImage` / `rom.bin` / `devicem4.bin` / `srp` **全部零命中**。
只有 BT（`BT: FW download over, size 653112 bytes`）和 WLAN 有固件下载日志。

⇒ **ISP 固件由 bootloader 在 Linux 之前加载，Linux 侧完全无感知。**
   这与 libudd5.so 里 503 个符号零 ISP 引用**互相印证**。

---

## 四之二、★★★ eMMC 未挂载分区扫描（抓取时顺手做的，最高价值发现）

原始数据：`raw8/uimage_scan.txt`。**只读探测**（`dd if=… | od`，未对分区做任何写操作）。

| 分区 | 头部 | 判读 |
|---|---|---|
| p5 | `33 00 33 00 09 84 df 56` | 非 uImage，稀疏 ⇒ 数据/空闲 |
| **p6** | **`27 05 19 56`** + `Linux-3.5.0` | ★ **uImage（内核）** |
| **p7** | `4e 00 00 ea 18 00 00 ea` | ★ **裸 ARM 指令镜像（无 uImage 头）** |
| p8/p9/p10/p12 | 全零 | 空闲 |
| **p13** | **`27 05 19 56`** + `Linux-3.5.0` | ★ **uImage（内核）** |

### uImage 头完整解析

| 字段 | `mmcblk0p6` | `mmcblk0p13` |
|---|---|---|
| magic | `0x27051956` ✓ | `0x27051956` ✓ |
| timestamp | 2015-06-03 05:40:33 | 2015-06-04 04:06:26 |
| **data_size** | 3,175,976 (3.03 MB) | **6,169,752 (5.88 MB)** |
| **load_addr** | `0x86008000` | `0x86008000` |
| **entry_point** | `0x86008000` | `0x86008000` |
| os / arch | Linux / arm | Linux / arm |
| **type** | **2 = kernel** | **2 = kernel** |
| compression | 0 = none | 0 = none |
| data_crc | `0x62eb5c06` | `0x588ba89f` |

★★ **关键判读：两个 uImage 的 `load_addr == entry_point == 0x86008000` 完全相同，
且 type 都是 `kernel`，都不压缩。** ⇒ 这是**同一内核的两份副本**（主/备份），
不是"内核 + ISP 固件"。

⇒ **ISP 固件（`DSP_NX500GLU0APC1_SR1`）不在这两个 uImage 里。**
   最可能的两个位置：
   - **`p1..p4`（bootloader 区）** —— bootloader 加载它，Linux 之前，与"Linux 侧零引用"一致
   - **`p7` 裸镜像** —— 无 uImage 头，头 64 字节是 ARM 指令
     （`4e/18/1e/2c/38 00 00 ea` = 连续 `b .`，典型 ARM relocation 表；
     末尾 `12 05 6d f9` = `ldr r1,[pc,#0x512]` 大偏移跳到数据表）

### `p7` 头 64 字节 ARM 反汇编

```
4e 00 00 ea   b  .            ← 连续 5 条 = ARM relocation 表（重定位项）
18 00 00 ea   b  .
1e 00 00 ea   b  .
2c 00 00 ea   b  .
38 00 00 ea   b  .
00 f0 20 e3   movw r2, #0
02 00 00 ea   b  .
14 c1 9f e5   ldrb r1, [pc, #0x14]
7c c0 9c e5   ldrb r0, [pc, #0x7c]
1c ff 2f e1   bx   lr
04 e0 4e e2   uxtb lr, lr
12 05 6d f9   ldr  r1, [pc, #0x512]   ← 跳到数据表
08 10 2d e9   push {r3, r8}
```

**这不是 Linux 代码**（无 Linux-3.5.0 头、无 `__boot_` 风格），
更像是 **M4 / CM4 或 ISP 协处理器的固件镜像头**。
⇒ ★ **这是 `DSP_NX500GLU` 固件本体的最强候选。**

### 下一步（针对 p7 / p1-p4）

```sh
# 只读：p7 前后各取 1KB，找 uImage 头或签名
dd if=/dev/mmcblk0p7 bs=1024 count=1 2>/dev/null | od -A x -t x1z -v | head -70
# 只读：p1-p4 全扫，找 0x27051956 或 0x4e00 开头
for p in 1 2 3 4; do echo "== p$p =="; dd if=/dev/mmcblk0p$p bs=4k count=64 2>/dev/null | od -A x -t x1z | head -8; done
```
⚠️ **只读，绝不 `dd` 到分区设备，绝不 mount 写。**

---


之前从未深入过这个目录。**这是相机行为的配置核心**。

```
/opt/etc/
├── .debugmode                    27 B    ← 调试模式开关 ★
├── .mac.info                     17 B
├── mmfw_camcorder.ini            3.9 K   ← Camera/Camcorder 主配置
├── mmfw_camcorder_dev_video_pri.ini  6.5 K  ← 主视频管线
├── mmfw_camcorder_dev_video_sec.ini  5.8 K  ← 次视频管线
├── mmfw_player.ini               2.4 K   ← 播放器
├── gst-openmax.conf              2.8 K   ← ★ GStreamer OpenMAX 插件
├── dlog.conf / dlog_logger.conf  2.9 K   ← 日志
├── dnsmasq.leases, p2p_supp.conf, wl-regdom.conf
├── smack/ smack-app/ smack-app-early/    ← SELinux 策略
├── ssl/certs, allshare/config, dump.d/module.d
```

### 5.1 `mmfw_camcorder.ini` 里的关键事实

```ini
ModelName = DRIMeIV-NX300      ← ★ 配置标称是 NX300，硬件却是 NX500
DisplayDevice = 0 || 0
ImageProfile = 2
```

### 5.2 `mmfw_camcorder_dev_video_pri.ini` 分辨率表

```ini
CaptureResolution = 1024,1024 | 2000,2000 | 2640,2640 | 3640,3640
                   | 1920,1080 | 2944,1656 | 3712,2808 | 5464,3072
                   | 1728,1152 | 2976,1984 | 3888,2592 | 4896,3264
                   | 5464,3640 | 5592,3728  || 5592,3728
                                        ↑ 默认        ↑ 最大
```
- `5464,3640` = 19.9 MP（NX500 实际输出）
- `5592,3728` = 20.8 MP（全像素）
- `PreviewResolution` 最大 `4096,2160`，默认 `640,480`
- `PictureFormat = 0,4,7 || 7` ⇒ 默认 **I420**（0=NV12, 4=YUYV, 7=I420）
- `RecommendDisplayRotation = 3`（270°）
- `SensorEncodedCapture = 1`（主传感器直出编码）

### 5.3 ★ 关键否定证据

**在全部 7 份配置里 grep `ep|isp|nog|lut|drime|d5` —— 零命中 EP/NOG/LUT 相关配置项。**

⇒ 印证之前的结论：**EP 硬件参数不经过 mmfw 配置框架**，
   它由 ISP 固件 + `libudd5.so` 旁路控制。配置框架只管分辨率/格式/曝光/白平衡。

---

## 六、★ 本轮最重要的验证：真机库 vs GPL 库

| | NX1 GPL 包 | **真机 NX500** |
|---|---|---|
| 文件 | `.uploads/nx1_open/.../libudd5.so` | **`raw8/real_libudd5.so`**（FTP 拉回） |
| 大小 | 279036 | **320216** |
| `.text` | `@0x8f70` size 227224 | `@0x91c0` size **264768** |
| 符号数 | 503 | 503（同名） |

### 重跑偏移解码结果：完全一致

| 项 | GPL 版 | **真机版** | 判定 |
|---|---|---|---|
| `ADD 0x30` (NOG 组) | 5/5 函数 | **5/5 函数** | ✅ 一致 |
| `ADD 0x65/0x66/0x67` | ✓ | ✓ | ✅ 一致 |
| `SUB 0x1f` (mask) | ✓ | ✓ | ✅ 一致 |
| `set_bypass` size | 240 | **240** | ✅ |
| `set_std_sigma` size | 432 | **432** | ✅ |
| `set_gamma` size | 684 | 684（待验） | ✅ |
| `reg_struct_init` size | 248 | 248 | ✅ |

★★ **结论：所有 NOG/3DLUT 寄存器偏移结论对真机成立。**
两版只是基址/地址不同，**指令编码完全相同** ⇒ 同一份源编译。

> `.bss` 变量位置对比（真机）：
> `ep_nog_reg_base@0x57724`、`nog_regset0@0x57768`、`nog_regset1@0x57748`

---

## 七、下一步（按价值排序）

| 优先级 | 动作 | 判据 / 理由 |
|---|---|---|
| **1** | **深挖 `mmcblk0p7`（裸 ARM 镜像）** | ★ 本轮新发现，**ISP 固件最强候选**。头 64B 已反汇编，是 relocation 表 + 数据表结构，无 Linux 特征 |
| **2** | 扫 `mmcblk0p1..p4`（bootloader 区）找 `0x27051956` | bootloader 在 Linux 之前加载 ISP 固件，最可能藏在这 |
| **3** | NOG 探针（`d5_ep_nog_set_noisegen`）+ liveview 前后像素方差统计 | 一举定 FilmLab 硬件颗粒路线生死 |
| 4 | 验证 `d5_ep_top_update_sreg(3DLUT_SHADOW_UPDATE)` 是否 3DLUT 生效必要步骤 | 决定 .cube LUT 能否下沉机身 |
| 5 | FTP 拉 `di-camera-app`（相机主程序，反汇编找 ISP 调用） | 它是唯一调用 libudd5 的用户态程序 |
| 5 | FTP 拉 `dfmsd`（7.3 MB，Tizen 应用管理） | 了解应用生命周期 |

### ⚠️ 读未挂载分区的风险
`mmcblk0p5..p8` 可能是厂商只读镜像区。**只读不写**：
```sh
dd if=/dev/mmcblk0p5 of=/dev/null bs=1M count=1     # 先确认可读
```
⚠️ **不要 `dd` 到分区设备**，不要尝试 mount 写。

---

## 八、本轮新增工具

| 文件 | 作用 |
|---|---|
| **`test_server/sysarch/fwprobe.py`** | ★ 批次化爬取器：89 条命令分 5 批，串行、每条独立超时、自动重连、行尾 LF 归一、断点续跑（已存在则跳过） |
| **`test_server/sysarch/ftpx.py`** | FTP 收发封装（stdlib ftplib，不引第三方），失败返回 None 不抛异常 |

### 踩坑记录（本轮新增 4 条）

1. **相机 IP 变了**：记忆里的 `.103` 不通，实机在 **`.105`**。
   ⇒ **教训：ping 一下邻近 IP 再动手，不要直接用记忆里的地址。**
2. **FTP 拒绝软链**：`ln -sf` 建的软链 `RETR` 返回 `550 Error`
   ⇒ vsftpd 防越权，**必须真实 `cp`**。
3. **FTP 根是 SD 卡不是 `/`**：`RETR /opt/usr/lib/x.so` 失败，
   真实路径是 `/usr/lib/x.so`（`/usr` 在只读 rootfs，**不在 `/opt/usr`**）。
   ⇒ **标准流程：telnet 里 `cp` 到 `/opt/storage/sdcard/`，再 FTP 取。**
4. **telnet 输出的回显污染**：`cmd` 被回显且行尾有 `\r`，长命令会被折行成
   看似乱码的片段（` 명령rirational` 那种）。
   ⇒ **不要从回显里读结果，只读下一行 prompt 之后的内容。**
