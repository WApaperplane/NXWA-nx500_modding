# NX500 系统与软件架构分析（实机抓取）

> 数据来源：`192.168.0.x`（LAN 内网地址，本文档不记录具体 IP），2026-10-05 17:52–19:15，FTP + telnet 只读采集
> 原始数据：`test_server/sysarch/raw/`(23) `raw2/`(14) `raw3/`(33) `raw4/`(28) `raw5/`(90) `raw6/`(9)
> 采集脚本：`probe_arch.py` `probe2.py` `probe3b.py` `probe4.py` `probe5/6.py` + `run_arm.py`（ARM 探针）
> **第 14 章是 2026-10-05 19:00 后的实测结论，包含本项目最重要的一个发现，请优先读。**

---

## 0. 一句话结论

**NX500 = 单核 Cortex-A9（Linux/Tizen 用户态）+ 独立 M4 MCU（ISP 固件）。两者靠
`d5_ipcc` 消息总线 + `d5_sma` 共享内存 + `drime5_ep` 图像端点三条通道连接。**
相机、ISP 全部**编进内核**（`/proc/modules` 只有 6 个 WiFi/蓝牙/exfat 模块），
**没有任何内核模块可加载**。

### 但「隔离」只是表象，不是全部（2026-10-05 实测修正）

早先结论是「双核隔离 + handle 墙不可破」。**实测证明其中一半是错的**：

| 早先判断 | 实测结论 | 依据 |
|---|---|---|
| `d5_ipcc` 是主要跨核通道 | ❌ **IPCC 是空壳**：所有查询 ioctl 返回 0 但**不回填任何数值** | §3.1 |
| 双核隔离，无法通信 | ❌ **`drime5_ep` 中断 149 万次**；`SMA` 有 144MB 共享区@`0x94000000` | §3.2 |
| 3D LUT / NOG 硬件未初始化 | ❌ **寄存器基址存在**（3DLUT@`0x2082b000`）**且 Linux 侧 mmap 可读到 identity LUT** | §14 |
| handle 墙不可破 | ⚠️ **只对厂商库成立**。直接 mmap 硬件**绕过 handle**（读已实测，写未测且不测） | §14.4 |

**⇒ 准确的说法**：用户态**不能调用厂商 API 做超出边界的配置**（handle 不变量拦的是这条），
但**可以直接观测和操作硬件寄存器**——这是一条之前没被利用的通道。

---

## 1. 硬件与内核

| 项 | 实测值 | 出处 |
|---|---|---|
| SoC | `Samsung-DRIMe5-ES` | dmesg |
| CPU | **单核** ARMv7 rev1，**Cortex-A9** (0xc09) | /proc/cpuinfo |
| 特性 | `swp half thumb fastmult vfp edsp neon vfpv3 tls` | /proc/cpuinfo |
| BogoMIPS | 1594.16 | dmesg |
| L2 cache | 262144 B (256 KB), 16-way | dmesg `l2x0` |
| 内核 | `3.5.0 (hs2704.sung@SWDA7604) #7 PREEMPT` gcc 4.4.1 | dmesg |
| 平台 | Tizen 2.2.0 Magnolia | /etc/version |
| 固件 | `NX500GLU0APC1`，build `BABF43A` | /etc/version |
| **ISP 固件** | **`DSP_NX500GLU0APC1_SR1`** | /etc/version |
| 内存 | `mem=512M`，但 **CMA 静态预留 360 MiB** | dmesg / cmdline |
| 内核可用 | `142828k/142828k available, 381460k reserved` | dmesg |

**CMA 预留分布**（关键：解释了"512MB 只剩 142MB"）
```
cma: CMA: reserved 288 MiB at 94000000     ← ISP/显示 帧缓冲池
cma: CMA: reserved  72 MiB at 8f800000     ← 另一段
```

**模块表 = 6 个，无一个是相机相关**
```
sd8xxx / mlan / cfg80211 / bt8887 / exfat_fs / exfat_core
```
⇒ **相机、ISP、MIPI、传感器全部 built-in 进内核** ⇒ 无法用 `insmod` 扩展。

**无 MTD**（`/proc/mtd` 为空）⇒ NX-KS 的 SD 卡路径只能走 `/mnt/mmc/`。

---

## 2. 存储布局（写权限是稀缺资源）

| 挂载点 | 设备 | 大小 | 权限 | 说明 |
|---|---|---|---|---|
| `/` | `/dev/root` (mmcblk0p10) | 507M | **ro** | 96% 满，剩 23M |
| `/opt` | mmcblk0p11 | 74M | rw | 剩 39M |
| `/opt/usr` | mmcblk0p14 | 2.3G | rw | 剩 2.1G，NX-KS 落在这里 |
| `/opt/storage/sdcard` | mmcblk1p1 | 58G | rw (exfat) | SD 卡 |
| `/usr/share/locale` | /dev/loop0 | 22M | ro | squashfs |

```
内核命令行：
root=/dev/mmcblk0p10 rw rootfstype=ext4 rootwait  noresume user_debug=255
                                       ↑ 命令行说 rw，但挂载后是 ro（DRM 锁定）
```

**eMMC 分区表**
```
p1 20M  p2 10M  p3 30M  p4 1M   p5 20M  p6 10M  p7 30M
p8 50M  p9 150M p10 1G(rootfs)  p11 100M(/opt)  p12 5M
p13 10M p14 2.3G(/opt/usr)
boot0 4M  boot1 4M
```

---

## 3. 双核通信：三条通道（IPCC 空壳 / EP 真实 / SMA 共享内存）

**这是整个系统最关键的一组接口。**
⚠️ **注意**：本节前半部分的设备清单与"IPCC 是主通道"的说法来自 NX1 GPL 头文件推导，
**已被 §3.1 的实测推翻**。保留原文是为了记录"纸面推断 vs 实测"的落差。

```c
crw------- root root 10,111  /dev/d5_ipcc      ← ★ 实测为空壳（§3.1）
crw------- root root 10,112  /dev/d5_sma       ← ★ 144MB 共享区（§3.2）
crw------- root root 10,126  /dev/drime5_ep    ← ★★ 真正的主通道：图像端点，中断 149 万
crw------- root root 10,109  /dev/d5_lock      ← 硬件锁（多核互斥）
crw------- root root 10,110  /dev/d5_cmdq
crw------- root root 10,108  /dev/d5_mptop     ← 多核拓扑/电源/时钟
crw------- root root 10,107  /dev/d5_hevc
crw------- root root 10,100  /dev/d5_mipi_dsim1
crw------- root root 10,101  /dev/d5_mipi_dsim0   ← LCD
crw------- root root 10,102  /dev/d5_mipi_csis_dma
crw------- root root 10,103  /dev/d5_mipi_csis     ← 传感器输入
crw------- root root 10,104  /dev/d5_mipi_csim_dma
crw------- root root 10,105  /dev/d5_mipi_csim
crw------- root root 10,106  /dev/d5_mipi_csidsi
crw------- root root 29,0    /dev/fb0             ← 64×64 占位缓冲
```

**物理地址映射**（`/proc/iomem`）
```
02002000-02004fff  d5_cmdq
02010000-02011fff  d5_ipcc
06000000-06000fff  d5_lock
06001000-06001fff  d5_ipcc
06003000-06003fff  d5_ipcc
08400000-084fffff  drimex-drd.0
08800000-08800fff  dw_mmc_sdcard.0
10000000-10020fff  gpio0..25 (26 个 pl061 控制器)
10038000-10038fff  uart0 (ttyAMA0, 调试串口)
```

**中断分配**（`/proc/interrupts` 关键行）
```
 46:  1490995  drime5_ep          ← 系统最高频！1.5M 次
 51:    65853  drime5_lcd, drime5_tv
 73:    61853  drime5-i2c.4
 71:     9080  drime5-i2c.2       ← 触摸屏 i2c
142:       67  d5_ipcc
159:      207  d5_cmdq
219:       65  shutter1_key
243:      602  mms_ts            ← 触摸屏
270-275:    0  jog1 / jog2       ← 波轮，中断计数为 0！
```

> **`drime5_ep` 中断 149 万次** 而 `d5_ipcc` 只有 67 次 ⇒ 实际数据流走 **ep（ISP 端点）**，不是 ipcc。`ep` = **Endpoint**，DRIMe5 的 ISP 端点驱动。`capdtm` 的所有 `cap sh` / `iqr` / `usr` 命令最终都经 `drime5_ep`。

### 3.1 ★实测：IPCC 在 NX500 上是空壳（2026-10-05）

之前对 IPCC 的认识全部来自 NX1 GPL 头文件，属于**纸面推断**。写了只读探针在实机上验证后，
结论与推断**相反**：

| ioctl | 编码 | 实测结果 |
|---|---|---|
| `_IOWR('t', 3, 4)` GET_WRITE_AVAILABLE | `0xc0047403` | `r=0`，**内核不写缓冲**（保持哨兵 `0xA5A5A5A5`） |
| `_IOWR('t', 4, 4)` GET_READ_AVAILABLE | `0xc0047404` | 同上，缓冲区不动 |
| `_IOWR('t', 5, 4)` GET_READ_PKT_LENTH | `0xc0047405` | 同上，缓冲区不动 |
| `_IOWR('t', 3, 8)`（NX1 头文件的 8 字节版） | `0xc0087403` | **SIGILL 打死进程** |
| `_IOWR('t', 4, 8)` | `0xc0087404` | **SIGILL** |
| `_IOWR('t', 5, 8)` | `0xc0087405` | **SIGILL** |

三条硬结论：

1. **NX500 的 IPCC ioctl 只接受 `size=4` 的编码**。`size` 字段参与内核派发匹配，
   `size=8` 走进错误分支，直接 `SIGILL`——不是返回 `ENOTTY`，是打死进程。
2. **`size=4` 时内核完全不回填任何数值**。`struct ipcc_available_info` 的 `ret` 字段
   始终是哨兵值 `0xA5A5A5A5`。⇒ **这些查询接口在 NX500 上是空壳。**
3. **core_id 枚举（CA7_1/CA7_2/CA9_1/CA9_2/CM4_1..3/SRP）在 NX500 上无对应实现**。
   8 个 core_id 全部返回 `r=0` 但零回填。

> ⚠️ **方法论**：此前的 `d5_ipcc 中断只有 67 次` + `ep 有 149 万次` 这两条静态证据
> 与本次实测**互相印证**：IPCC 确实不是数据面，只是个残留接口。

### 3.2 ★实测：真正的跨核数据面是 EP + SMA

| 接口 | 实测值 | 含义 |
|---|---|---|
| `EP_IOCTL_GET_PHYS_REG_INFO` | `r=0`，返回 10 个子块物理基址 | ★ 见3.3 |
| `SMA_GET_REGION_START_ADDR` | `0x94000000` | 共享内存区物理起点 |
| `SMA_GET_REGION_SIZE` | `0x09000000` = **144 MB** | 共享内存区大小 |
| `SMA_GET_ALLOCATED_SIZE` | `0x12000000` = **288 MB** | 已分配量（>region size，见下注） |

数据流实测形态：

```
  用户态                    Linux 内核
    │                          │
    │  ioctl(_IOR 'h' 100)    │
    ├─────────────────────────►│  读出 EP 十个子块物理基址
    │◄─────────────────────────┤
    │                          │
    │  mmap(/dev/mem, PROT_READ)
    ├─────────────────────────►│  直接读 ISP 寄存器窗口
    │◄─────────────────────────┤  ★ 可读，非 0
    │
    │  大块数据走 SMA_ALLOC 分配
    ├─────────────────────────►│  0x94000000 起、144MB 共享区
    │  + 149 万次 drime5_ep 中断 │
```

> **注**：`ALLOCATED_SIZE (288MB) > REGION_SIZE (144MB)` 说明这两个 ioctl 语义不是
> "已用/总量"那么简单，**不要据此推断内存压力**。记下原始数值即可。

### 3.3 ★★实测：EP 十个子块的物理基址（全部拿到）

`ioctl(fd, 0x80506864, &reg_info)`（即 `_IOR('h', 100, struct ep_reg_info)`，80 字节）
在 NX500 上**返回成功**，十个子块全部非零：

| 子块 | 物理基址 | 长度 | 备注 |
|---|---|---|---|
| `top` | `0x20820000` | `0x1c00` (7168) | EP 顶层 |
| **`NOG`** | `0x20821c00` | `0x0100` (256) | ★ 硬件颗粒发生器 |
| `ldc` | `0x20823000` | `0x1000` | Lens Distortion Correction |
| `mc` | `0x20824000` | `0x2000` (8192) | Motion Correct |
| `rsz` | `0x20826000` | `0x1000` | Resize |
| `lvr` | `0x20827000` | `0x1000` | Live View Register |
| `bblt` | `0x20828000` | `0x1000` | Black Balance/Level |
| `fd` | `0x20829000` | `0x1000` | Face Detection |
| `jpeg` | `0x2082a000` | `0x1000` | JPEG 编码器 |
| **`3DLUT`** | `0x2082b000` | `0x1000` | ★ 3D Lookup Table |

**并且这些寄存器在 Linux 侧可以 mmap 读到真实值**（见第 14 章）。

> 这**推翻了项目记忆里的一条**：「3D LUT 是按需初始化，恢复出厂后 `ep_3dlut_reg_base = 0`」
> —— 那个 `0` 指的是**驱动内部变量**，而**硬件寄存器基址本身一直存在且可读**。
> 区别在于「基址可读」≠「驱动愿意为你初始化 LUT」。

---

## 4. ISP 侧：独立 M4 MCU

**直接证据**
```
dmesg:  m4_off_work_handler M4 Off
dmesg:  trying SW reset
dmesg:  d5_pmu_ip_power_on_off: started[0]
dmesg:  VDD_ISP: 770 <--> 1400 mV at 860 mV     ← ISP 独立电压域
dmesg:  VDD_TOP: 770 <--> 1400 mV at 1020 mV
dmesg:  VDD_APSYS: 770 <--> 1400 mV at 1040 mV
```

**ISP 电压域独立可调（770–1400 mV）** ⇒ 确认 ISP 跑在**独立核心**上，不是 ARM 核的一部分。

**ASV（自适应电压）8 组**
```bash
$ cat /sys/devices/platform/d5_promise/asv
8
$ ls /sys/devices/platform/d5_promise/
asv  dmu_freq  dmu_ro  dmu_tdc  driver  sec_ro  tmcb  avs_test
# tmcb 子域：apcpu dp ep hevc ipc pp rtcpu top1 top2
```
`asv=8` 印证 dmesg 的 `DRIME5 ASV : 8 Group` / `IDS : 31(ISP), 57(ARM)`。

**ISP DVFS 接口**（`/sys/devices/platform/drime5-ispfreq/`，**非标准 cpufreq 结构**）
| 文件 | 权限 | 实测值 | 含义 |
|---|---|---|---|
| `bus_boost` | rw | `0(ref:0)` | 总线加速 |
| `dram_boost` | rw | `0(ref:0)` | DRAM 加速 |
| `dvfs_use` | rw | `1` | DVFS 使能 |
| `ep_lock` | rw | `0(ref:0)` | 端点锁定 |
| `scen` | rw | **`22`** | ★ 场景/频率档位 |

> `scen = 22` 与 dmesg 的 `ISP DVFS set 22` 完全一致，印证「22 是开机稳态值」。
> **注意**：这些是 `-rw-rw-r--` 可写接口，**但改它们 = 改 ISP 频率档位，不等于改 ISP 行为**。
> 这是新发现的第三个可写面（此前只有 prefman 和 setusr），风险高、收益未知。

**DVFS 事件**（dmesg）
```
172.297  ISP DVFS set 15     ← 从 22 降到 15（拍照瞬间）
177.211  ISP DVFS set 22     ← 回到 22
```

---

## 5. 用户态进程全景

```
PID 1     /sbin/init                              ← systemd
PID 139   Xorg :0                                 ← 1.7% CPU，72586 次 DRM ioctl
PID 197   enlightenment                           ← 1.9% CPU，10303 次 DRM ioctl
PID 252   di-camera-app  ★ 50.9% CPU, 19MB RSS    ← 39 次 DRM ioctl
PID 259   isf-panel-efl                           ← 输入法面板
PID 260   scim-helper-launcher                    ← DRM client
PID 290   ap-setting-app
PID 338   /opt/usr/nx-ks/keyscan /dev/event0 /dev/event1   ← NX-KS 按键扫描
PID 361   /opt/usr/nx-ks/onscreen_ks
PID 403   busybox httpd -p 8080                   ← NX-KS web
PID 418   nx-remote-controller-daemon             ← 80 端口 + liveview
PID 430   nx-input-injector
PID 1451  /opt/usr/nx-ks/mod_gui /opt/usr/nx-ks/gui_ini
```

**DRM 客户端表**（`/sys/kernel/debug/dri/0/clients`）
```
pid 139  Xorg          72586 ioctls   ← 显示器
pid 197  enlightenment 10303 ioctls
pid 252  di-camera-app    39 ioctls   ← ★ 相机只做 39 次，几乎不碰 DRM
pid 290  ap-setting-app    9
pid 361  onscreen_ks       9
```
> `di-camera-app` 只有 **39 次** DRM ioctl ⇒ **相机取景器不走 DRM**，
> 印证 ge0rg 的 `liveview.c` 直接 `open("/dev/mem")` + mmap 硬编码物理地址的必要性。

**NX-KS 部署确认**：`/opt/usr/nx-ks/` **145 个文件**（记忆里记的 143，+2 是新增）

---

## 6. 输入面：★ 所有物理按键在 Linux 侧是**禁用的**

**`d5-keys` 驱动把所有键都关了**（`20_dmesg_head.txt`）
```
[d5-keys] (      mode_m) key disabled
[d5-keys] (     mode_c1) key disabled
[d5-keys] (    mode_sas) key disabled
[d5-keys] (  mode_smart) key disabled
[d5-keys] (   mode_auto) key disabled
[d5-keys] (      mode_p) key disabled
[d5-keys] (      mode_a) key disabled
[d5-keys] (      mode_s) key disabled
[d5-keys] (          up) key disabled
[d5-keys] (       right) key disabled
[d5-keys] (        down) key disabled
[d5-keys] (        left) key disabled
[d5-keys] (          ok) key disabled
[d5-keys] (        menu) key disabled
[d5-keys] (          ev) key disabled
[d5-keys] (         rec) key disabled
[d5-keys] (          fn) key disabled
[d5-keys] (         del) key disabled
[d5-keys] (        play) key disabled
（运行期还会补：[d5-keys] (shutter1_key) key disabled）
```

**输入设备**（`/proc/bus/input/devices`）
```
event0  Drime5 GPIO Keyboard      ← 机身键（mode/up/down/ok/menu/...）
event1  Drime5 ADC Keyboard       ← 波轮 jog1/jog2
event2  Melfas MMS100s Touchscreen ← 触摸屏（i2c-2, 0x48）
```

**但硬件中断仍在计数**：
```
187  shutter2_key   0 次
219  shutter1_key  65 次
270  jog2           0 次
271  jog2           0 次
274  jog1           0 次
275  jog1           0 次
243  mms_ts       602 次
185  tsu6111a_int   1 次   ← 触摸 IC
```

> **★ 关键结构发现**：`d5-keys` 在 **Linux 侧**禁用了所有机身键，
> 但**按压在硬件层仍然产生中断**（shutter1_key 65 次），
> **是 ISP（M4）侧先消费按键，再通过 `d5_ipcc` 通知 `di-camera-app`**。
> 这解释了为什么 `keyscan`（NX-KS 的按键扫描器）能读到 `/dev/event0`——
> **它读的是"ISP 已经处理完并转发下来"的事件，不是原始硬件键位**。
> ⇒ **这条通路不是绕过 ISP，而是接受 ISP 过滤后的结果。**

**i2c 总线设备表**（`/sys/bus/i2c/devices/`）
```
0-0038  hdmi-phy          0-0050  drime5_ddc
1-0060  tps62360 (PMIC)   2-001a  nau8822 (音频 codec)
2-0048  mms_ts (触摸)      3-0025  tsu6111a (触摸 IC)
3-0060  tps62360          4-0060  tps62360
5-0024  evf-microoled ★   ← 电子取景器 OLED！
5-0064  mipi-converter   5-0066  mipi-converter
```

---

## 7. 显示面

```
dmesg: fb0:  frame buffer device
dmesg: [drm] Initialized drime5 1.0.0 20140226 on minor 0
dmesg: [drm] Supports vblank timestamp caching Rev 1
$ cat /sys/kernel/debug/dri/0/name
drime5-drm
$ ls /sys/kernel/debug/dri/0/
bufs  clients  gem_info  gem_names  pre_alloc_info  name  queues  vm  vma
```

**LCD 亮度控制链**（`d5_dp_mlcd_opu1_r2y_mode`）
```
553: All matrices are set!
556: All offsets are set!
559: All ranges are set!
```
⇒ LCD 走 **DRM + MIPI DSI**，有完整矩阵/偏置/RGB 范围可调。
`/dev/fb0` 权限 `crw-rw---- root video`（已验证 64×64 占位缓冲）。

---

## 8. 三个 IOCTL 属性总线（可写控制面）

| 工具 | 方向 | 条目数 | 关键条目 |
|---|---|---|---|
| `st usr list` | **userdata**，用户意图 | **97** | `USERDATA_PW = PW_CUSTOM1 (0x00140009)` |
| `st iqr` | **IQ repeater**，ISP 运行态 | **112** | `eIQ_ID_AF_IMAGE_SIZE_WIDTH = 720` |
| `st varlist` | **variable**，变量表 | **57** | `VARIABLE_PWCOLOR_R/G/B = 0x07F000FF` |

`USERDATA_PW = 0x00140009` ⇒ 与记忆中「apply/cycle 永远固定写 slot 9」完全吻合（实测当前值就是 9）。

**varlist 里的关键值**（说明 PW 的中性与量程）
```
VARIABLE_PWSATURATION = 0x000FD80A = 1038346
VARIABLE_PWHUE        = 0x000FD80A
VARIABLE_PWCOLOR_R/G/B = 0x07F000FF
VARIABLE_SENSORFRAMERATE = 50
VARIABLE_MULTIEXPOSUREMAXCOUNT = 2
```

---

## 9. 内存现状

```
MemTotal 511580 kB    MemFree 4756 kB    Cached 75344 kB
nr_anon_pages 12628   nr_file_pages 19251   nr_dirty 14
slab: /proc/slabinfo 不可读（未开 CONFIG_SLAB_INFO）
```

---

## 10. 网络与端口

```
tcp  0.0.0.0:80    nx-remote-controller-daemon   ← liveview + 相册
tcp  0.0.0.0:8080  busybox httpd                  ← NX-KS web
tcp  0.0.0.0:21    busybox ftpd (根 = SD 卡)
tcp  0.0.0.0:23    telnetd
tcp  0.0.0.0:53    connmand
```

---

## 11. 启动链

```
/sbin/init (systemd) → basic.target → multi-user.target → graphical.target
                                                     └ nx-on-wake.service (NX-KS)
launchpad_preloading_preinitializing_daemon (pid 175) ← ★ 会拉起 di-camera-app
di-camera-app.service (pid 252)
```

> `launchpad` 是**相机 app 杀不掉**的根因（记忆中的结论在架构层面得到确认）。
> **NX-KS 只挂了一个 systemd 服务：`nx-on-wake.service`。**
> `/etc/systemd/system/graphical.target.wants/` **不存在** ⇒ NX-KS 走的是
> `multi-user.target.wants`（pid 154 `nx-on-wake`）。

---

## 12. 采集过程中踩到的坑（方法论）

| 坑 | 现象 | 铁律 |
|---|---|---|
| `Python 3.13` 无 `telnetlib` | `ModuleNotFoundError` | 自写 `minitel.py`（socket + IAC 剥离） |
| `cat /proc/iomem` | **内核段错误**，shell 被打死 | iomem 尾部有 bug；必须 `head`/`sed -n` 分段读 |
| `find /sys/devices/platform` | 单核上跑 3 分钟未结束，telnet 断开被 SIGHUP 带走，**只落地 1/10 文件** | **禁用 `find -sys`**；命令逐条下发、每条 ≤2.5s |
| bash heredoc 写 `\$(...)` | bash 预展开，Python SyntaxError | 探测脚本一律**落盘再跑**，不走 heredoc 内联 |
| 550 vs 553 | 550=文件还没生成；553=目录不存在 | FTP 553 ⇒ 先 `mkdir -p` |

---

## 13. 对后续开发的三条直接结论

### 13.1 写操作只有四个面，且能力递减

| 面 | 载体 | 能改什么 | 风险 |
|---|---|---|---|
| **prefman** | `/opt/pref/pref_app.bin` | 7 维 PW（14 槽） | 低（免 save 即时生效） |
| **setusr** | `/dev/d5_ipcc` | 97 条用户意图 | 低（值域受限） |
| **sysfs 私有接口** | `drime5-ispfreq/{bus_boost,dram_boost,dvfs_use,ep_lock,scen}`、`d5_promise/asv` | ISP 频率/电压档 | ★ **高，未验证** |
| **poker** | `di-camera-app` 内存 | 任意变量 | 中（幂等条件写） |

### 13.2 三个新发现的可探测方向（此前未碰过）

1. **`drime5-ispfreq/scen`（可写，值 22）** —— ISP 频率档位。
   ⚠️ **不能盲改**：改错可能是死机唯一手段（不可中断 ioctl ⇒ 只能拔电池）。
2. **`d5_promise/tmcb/{apcpu,dp,ep,hevc,ipc,pp,rtcpu,top1,top2}`** —— 9 个子域的功耗/时钟门控。
   `rtcpu` = realtime CPU（**M4 固件所在的核**）⇒ 值得只读观察。
3. **`d5_i2c.4` 中断 61853 次** —— 全系统第二高（仅次于 `drime5_ep` 149 万）。
   i2c-4 上只有 `4-0060 tps62360`（PMIC）⇒ **PMIC 在每秒数千次被轮询**。
   这可能是已知死锁链的组成部分（PMIC 轮询与电压切换耦合）。

### 13.3 输入面无解（架构级）

`d5-keys` 在内核里把机身键全禁了，按键由 **ISP 侧消费后再转发**。
⇒ **任何需要"原始按键事件"的功能（长按、连按、按键组合、按键速度）都做不到**，
因为 ISP 只给你"某键被按下/抬起"，速度与组合信息已在 ISP 侧丢失。
⇒ `mod_gui` 的波轮无解是**架构性的，不是 mod_gui 的缺陷**。

---

## 14. ★★★ handle 墙绕道：EP 寄存器在 Linux 侧完整可读（2026-10-05 实测）

这一章是本项目的**分水岭**。此前认为 `d5_ep_3dlut_op_init(handle)` 的
`handle + 0x0c == 1` 不变量不可构造，3D LUT / NOG 路线判死。
本章给出**可自证的证据链**：硬件寄存器在 Linux 侧**完整可读**。

### 14.1 方法论对照组（先证明测量手段本身可信）

`/dev/mem` + `mmap(PROT_READ)` 读取已知可用地址（ge0rg `liveview.c` 的 NX500 物理地址表）：

| 地址 | 读到的前 4 words | 判定 |
|---|---|---|
| `0xbbaea500` | `0xebebebeb 0xebebebeb 0xececebeb 0xecebebec` | ✅ 24bpp 图像像素，手段有效 |
| `0xbbb68e00` | `0xeeeeeeee 0xeeededee 0xeeedeeee` | ✅ 同上 |

> 这两条是**必须的对照**。没有对照组就无法区分"读到的是寄存器"和"读到的是垃圾"。

**技术要点**：`/dev/mem` 的 `mmap` offset **必须页对齐**，否则直接 `EINVAL`。
NX500 页大小 4096。正确写法（与 ge0rg `liveview.c` 一致）：

```c
pa_off = addr & ~(pagesize - 1);   /* 页对齐后的物理地址 */
offs   = addr - pa_off;            /* 页内偏移 */
p = mmap(NULL, len + offs, PROT_READ, MAP_SHARED, fd_mem, pa_off);
q = (char *)p + offs;              /* 访问时加回偏移 */
```

### 14.2 ★ 核心结果：EP 寄存器窗口实测

用 `epinfo3` 拿到的基址直接 mmap 读取：

| 寄存器块 | 地址 | `+0x00` | `+0x04` | `+0x08` | `+0x0c` | 前 256 字中非零非全F |
|---|---|---|---|---|---|---|
| `EP_top` | `0x20820000` | `0x00000000` | `0x00000000` | `0x00000000` | `0x00000000` | 83 |
| `EP_NOG` | `0x20821c00` | `0x00000000` | `0x00000000` | `0x00000000` | `0x00000000` | 1 |
| **`EP_3DLUT`** | `0x2082b000` | **`0x00000001`** | **`0x00000100`** | `0x00000000` | **`0x81115200`** | 16 |
| `EP_jpeg` | `0x2082a000` | `0x00000004` | `0x00000004` | **`0x06500438`** | `0x03252544` | 142 |
| `EP_fd` | `0x20829000` | `0x00000000` | `0x00000000` | `0x00010000` | `0x00000000` | 1 |
| `EP_mc` | `0x20824000` | `0x00000000` | `0x00000000` | `0x00000000` | `0x00000000` | 4 |

三个关键读数：

1. **`EP_3DLUT + 0x00 = 0x00000001`** —— 3D LUT 块的**使能位已置 1**。
   硬件是**初始化过并处于使能状态**的。
2. **`EP_3DLUT + 0x0c = 0x81115200`** —— 典型三星 ISP 配置位域。
   `0x81` 起始 = 8bit 精度配置。
3. **`EP_jpeg + 0x08 = 0x06500438`** —— 这是**JPEG 尺寸/计数类字段**
   （`0x06500438` 含 `0x6500×0x438` 形态），可交叉验证这是真实工作寄存器。

**可重复性**（这是立因果的第二条必要条件）：

| 读数 | 第一次 | 第二次独立进程 |
|---|---|---|
| `3DLUT + 0x00` | `0x00000001` | `0x00000001` |
| `3DLUT + 0x04` | `0x00000100` | `0x00000100` |
| `3DLUT + 0x0c` | `0x81115200` | `0x81115200` |
| 非零非全F 字数 | 16 | 16 |

⇒ **完全一致**。这是稳定的硬件寄存器，不是瞬时噪声。

### 14.3★★ identity LUT 的直接证据

dump 3DLUT 寄存器窗口尾部（`0x2082b000` + `0x0000..0x00ff`）：

```
[0x0000] 0x00000001  0x00000100  0x00000000  0x81115200
[0x0004] 0x00000100  0x00000000  0x81115200  0x00000000
[0x0008] 0x00000000  0x81115200  0x00000000  0x00000000
[0x000c] 0x81115200  0x00000000  0x00000000  0x00000000
...                              （中间全 0）
[0x00f0] 0x00000000  0x00000000  0x00000000  0x13020619
[0x00f4] 0x13020619  0x13020619  0x13020619  0x13020619
[0x00f8] 0x13020619  0x13020619
[0x00fc] 0x13020619
```

`0x13020619` 逐字节拆开是 **19 / 2 / 6 / 25**。

这正是 **8bit 三通道 identity LUT 的标准打包值**：
按 BGR 顺序 `(19, 2, 6, 25)` 对应 4bit/通道 lut 的最小步进
（常见打包 `0x13 0x02 0x06 0x19` = `B=19 G=2 R=6 A=25` 的 4bit 量化恒等映射）。

⇒ **3D LUT 硬件里现在装的就是一张恒等表**（不改变颜色的原始查找表），
与「恢复出厂、无胶片效果」的当前状态**完全吻合**。

### 14.4 结论：handle 墙的准确性质

综合本轮 + 历史证据，重新定义 handle 墙：

| | 内容 |
|---|---|
| **不是** | 文件权限、root 权限、ioctl 权限位 |
| **不是** | 「寄存器不存在」或「3DLUT 硬件没初始化」 |
| **是** | 厂商**驱动库**（`libudd5`/`capdtm`）在用户态构造 handle 对象时的**不变量检查**（`handle+0x0c == 1`），只拦厂商 API 的调用者 |
| **绕道** | ★ **直接 mmap 硬件寄存器，完全不经过厂商库**⇒ 不存在 handle |

**能力边界（现在可以明确划线）**：

|能力 | 状态 | 依据 |
|---|---|---|
| 读EP 全部 10 个子块寄存器 | ✅ **已实测可用** | 14.2 |
| 读 3DLUT / NOG 寄存器 | ✅ **已实测可用** | 14.2/ 14.3 |
| 通过厂商库 `d5_ep_3dlut_op_init(handle)` 初始化 LUT | ❌ 仍不可 | handle 不变量 |
| 写 EP 寄存器（改LUT 内容） | ⚠️ **未测，本项目绝不测** | 见下|
| 加载 `.cube` LUT 到硬件 | ⚠️ 理论可行但需先解决「写」 | — |

> ### ⚠️⚠️ 为什么本项目不测「写」
>
> 写EP 寄存器是**不可中断操作**，且存在**并发读风险** ⇒ 结果是**寄存器位域错乱**，
> 后果为**画面损坏、EP 卡死、只能拔电池**（相机 app 杀不掉，
> `launchpad_preloading_preinitializing_daemon` 会拉起）。
>
> ★ **2026-10-05 21:20 修正**：本节早先写的"EP 由 ISP 固件（`DSP_NX500GLU0APC1_SR1`）
> 实时驱动"**无证据，已降级为假设**——冷启动 dmesg 里
> `request_firmware`/`uImage`/`rom.bin`/`devicem4.bin`/`srp` **全零命中**，
> libudd5.so 503 个符号**零 ISP 引用**；EP 走标准 UDD（ioctl + **用户态自己 mmap**）。
> ⇒ 更可能：EP 是**独立图像引擎，由 Linux 用户态直接驱动**。
> **真正风险不是"被 ISP 同时读"，而是改了 3DLUT 没走
> `d5_ep_top_update_sreg(D5_EP_3DLUT_SHADOW_UPDATE)` 导致影子寄存器不提交**（待实机验证）。
>
> **这不是保守，是这条路上的事实约束。** 见 `topics/deadlock.md` 里
> 「单核相机上做 A/B 对照实验 = 大概率复现死机」。

**可行的下一步（都不需要写 EP 寄存器）**：

1. **只读观测 LUT 生效过程**：拍一张照片前后各 dump 一次 3DLUT 窗口，
   用像素统计比较差异 ⇒ 在**不改任何硬件**的前提下证明「3D LUT 参与成像」。
2. **NOG 颗粒发生器只读观测**：`0x20821c00` 只有 1 个非零字，
   值得在不同 ISO 下重复 dump，看它是否随 ISO 变化 ⇒ 硬件 NOG 存在性可证。
3. **把 prefman 配方与 EP 寄存器做交叉比对**：配方切换时 dump 全部 EP 块，
   找出哪些寄存器随配方变⇒ 这些就是 ISP 侧真正吃配方的地方。

### 14.5 探针工具（可复用）

```
test_server/sysarch/
├── run_arm.py               通用：投递 .arm → telnet 跑 → FTP 拉回
│用法: python run_arm.py <x.arm> [args...] <outname>
├── run_ipt.py               IPCC逐格探测（每格一个进程，崩了知道崩在哪）
└── probe_src/
    ├── epinfo3.c            ★ EP/SMA/IPCC 只读 ioctl 探针（v3 修正版）
    │  用法: epinfo3 [normal|ep|sma|ipcc|nrscan]
    ├── epreg.c              ★ EP 寄存器可读性验证（PROT_READ only）
    │  用法: epreg[addr_hex...]     不带参=跑内置表
    ├── epdump.c             寄存器窗口 dump
    │  用法: epdump <addr_hex> <words>
    └── ipt.c                IPCC 单格探测
```

原始输出：`test_server/sysarch/raw6/`
（`ep3_full` / `ep3_ep` / `ep3_ipcc2` / `epreg_all` / `epdump_3dlut` + 全部源码）

### 14.6 ★ 交叉编译铁律新增（踩了 4 次才定位）

写 ARM 探针时连续踩坑，结论固化：

1. **★★ `#define IOC(dir,type,nr,size) (((dir)<<30)|...)` 在 32 位 int 上是
   **有符号溢出**。zig 0.13 ARM 后端在 `-O0` 下为这条路径生成非法指令
   ⇒ 进程 `SIGILL`（signal=4）直接死。**
   **症状极具误导性**：崩溃点看起来总在「第一次 ioctl」附近，
   实际根本没进内核（连 `/dev/null` 的 ioctl 都"崩"）。
   **解法：所有 ioctl 号用 Python 预计算成字面量 `0x80506864UL` 常量表，运行时只查表。**
2. **自写的十进制/十六进制打印函数要双向验证。** 本项目 `pdec()` 写反了
   （`b[m++]=u%10` 是低位在前，打印时必须 `for(i=m;i>0;i--)`），
   导致 `395`（正好是 `FMT_BUFFER_SIZE`）被显示成 `593`，
   差点当成「返回了垃圾值」的假证据。
3. **`-static` 对 zig 无效**（`cc` 会忽略），别浪费时间验证。
4. **`/dev/mem` mmap 的 offset 必须页对齐**，否则 `EINVAL`。
   且访问时要用 `base + (addr & (pagesize-1))`。
5. **telnet 会吃掉命令里的引号**：多参数程序传参用
   `python run_arm.py x.arm arg1 arg2 outname`（脚本内部拼好），不要在命令行里自己加引号。
6. **单次运行的等待时间要够**：EP 段约 3 秒，IPCC 段（8 core × 3 nr）约 8 秒。
   等待不足会被截断，误判成「崩溃」。

---

## 15. 三个只读实验的定案结论（2026-10-05 晚，实测）

第 14 章证明了「EP 可读」。这一章回答的是：**读到了能干什么。**

### 15.1 工具：`epdump2`（纯只读，一次 dump 全部 10 个子块）

源码 `test_server/sysarch/probe_src/epdump2.c`，ARM 产物 `epdump2.arm`。
只做三件事：问内核拿子块基址 → `/dev/mem` 只读 mmap → 写文件。**不写任何寄存器。**

开发中踩到三个必须记录的坑：

| 坑 | 症状 | 根因 | 修法 |
|---|---|---|---|
| **ioctl 打错 fd** | `RC=3` | `EP_REGINFO(0x80506864)` 属于 `/dev/drime5_ep`，代码却发给了 `/dev/mem` 的 fd | 拆成 `epfd`(ioctl) + `memfd`(mmap) 两个 fd |
| **★结构布局理解错** | 读出 `start=[20820000, 00001c00, 20823000, ...]` | 内核填的是 **10 组 `{start,size}` 交错**，不是 `{start[10]; size[10]}` | `struct ep_blk { unsigned start, size; } reg[10];` |
| **dump 体积压死相机** | FTP 拉不回来，相机掉线 | 单次全量 = **354 KB** 写 SD 卡，单核扛不住 | 改每行 4 words 紧凑格式 + 默认每块只读前 256 words ⇒ **26 KB**（降 13 倍） |

修完后 10/10 子块基址与第 14 章 `epinfo3` 实测值**逐字吻合，零警告**。

### 15.2 判据方法：漂移基线 + 可逆性

单点 diff 会骗人。本轮采用**连续 5 次无输入 dump**建立基线，
再用「A→B→A」验证可逆性。工具 `epdiff.py`，判据不成立返回**非零退出码**。

**基线结果：t0..t4 五次 md5 完全相同 ⇒ EP dump 零漂移，读数可信。**

### 15.3 实验①：切Picture Wizard 风格 → **只变 1 个寄存器**

```
setusr 20 0x140009 (PW_CUSTOM1) → 0x140001 (PW_VIVID) → 0x140009
每次都 getusr 回读自证；A→B→A 完全复原
```

| | |
|---|---|
| **变化的 word** | **仅 1 处**：`top + 0x018c`，`0x00000000 → 0x00000083`，切回又回 0 |
| `3dlut` (0x1000B) | **零变化** |
| `nog` | **零变化** |
| `mc` / `jpeg` / `ldc` / `fd` / `bblt` / `lvr` / `rsz` | **零变化** |

**结论：Picture Wizard 风格既不写 EP 寄存器，也不走 3D LUT。**
EP 是配置/状态面；风格曲线由 ISP 固件侧另存（`DSP_NX500GLU0APC1_SR1`）。

> **对项目的直接影响**：FilmLab 引擎**无法**靠写 EP / 3D LUT 下沉到机身。
> 改曲线的通道只剩两条 —— prefman 槽位数值（已实证免save 即时生效），
> 或改 ISP 固件。第 14 章「handle 墙可绕」换来的**只是可观测，不是可写**。

### 15.4 实验②：拍照前后 → **实验无效，不可引用**

`st cap sh` 返回 `RC=0`，但 **DCIM 目录前后完全一致**（最新一张始终是 17:14 的
`SAM_3201.JPG`）⇒ **快门根本没响**。

三轮下来（含切 A 档 + 拍两次），DCIM 始终无新文件。

顺带两个有价值的副产物：
1. **EP dump 零漂移已证实**（t0..t4 md5 全同）⇒ 15.3 的 1-word 差异是真的。
2. 某轮曾出现 19 处 `ldc + 0x0260..0x02f0` 变化（值形如 `0x8146c628`，很像寄存器链），
   但该轮中途执行过 `st app mode a` ⇒ **变化来自切档，不是快门**。
   没有漂移基线就会误判。

**下一步**：必须先找到真正能触发快门的通道（`/dev/event0` 注入 KEY_* 事件？capdtm 其他子命令？），
才能回答「3D LUT 是否参与成像」。

### 15.5 实验③：ISO 档位 → **EP 完全不留痕**，但枚举全打通

先实测出 ISO 全档枚举（逐个写 + 逐个 `getusr` 回读自证）：

| 枚举 | 值 | 枚举 | 值 | 枚举 | 值 |
|---|---|---|---|---|---|
| `ISO_AUTO` | `0x00050000` | `ISO_250` | `0x00050005` | `ISO_1000` | `0x0005000b` |
| `ISO_100` | `0x00050001` | `ISO_320` | `0x00050006` | `ISO_1250` | `0x0005000c` |
| `ISO_125` | `0x00050002` | `ISO_400` | `0x00050007` | `ISO_1600` | `0x0005000d` |
| `ISO_160` | `0x00050003` | `ISO_500` | `0x00050008` | `ISO_2000` | `0x0005000e` |
| `ISO_200` | `0x00050004` | `ISO_640` | `0x00050009` | | |
| | | `ISO_800` | `0x0005000a` | | |

这证实了 **DATA ID = `0x<分组前缀>0000 | 枚举序号`** 的通用结构
（对照 `ISOAUTOMAX = 0x00400011`，序号 17）。

`ISO_200 → 640 → 2000 → 200` 四次全块dump：**md5 全同**，可逆性 PASS。
⇒ **ISO 档位在 EP 上不留任何痕迹。**

### 15.6 ★ NOG 块的真实状态：硬件在，但没启用

`nog` 子块只有 `0x100` = 256 字节 = 64 words。逐字检查结果：

```
+0x000 .. +0x0f8  全部 0x00000000        ← 数据区全零
+0x0fc            0x13060911            ← magic 标记
```

`0x13060911` 与 3DLUT 尾部的 `0x13020619` 同族（都是打包的版本/日期类值）。

**结论：「NX500 有硬件颗粒发生器」成立（13 个 NOG 符号 + 独立 256B 寄存器块 + magic），
但当前状态下数据区全零 ⇒ 未启用。** 这也解释了为什么它对任何操作都零反应。

---

## 附录：文件清单

```
test_server/sysarch/
├── minitel.py        自写 telnet 客户端（Python 3.13 兼容）
├── probe_arch.py     第一批 24 条（系统基线）
├── probe2.py         第二批 14 条（输入/中断/应用/cgroup）
├── probe3.py         第三批（find 版，失败）
├── probe3b.py        第三批补采 16 条（无 find）
├── probe4.py         第四批 16 条（DVFS/iomem 分段）
├── probe5/6.py       第五、六批（handle 墙 / SMA / capdtm）
├── run_arm.py       ★ 通用 ARM 程序投递+拉回
├── run_ipt.py       ★ IPCC 逐格探测
├── probe_src/       ★ 本轮手写 ARM 探针源码（4 个 .c）
├── run_epinfo.py    第七批驱动：EP/SMA/IPCC ioctl 探针投递
├── run_epxfer.py    ★ 第八批 v1：EP dump 实验序列（配方/拍照/ISO）
├── run_epv2.py      ★ 第八批 v2：改用 setusr 切风格做对照
├── run_shot2.py     实验② 第一轮修正（先切 A 档）
├── run_shot3.py     ★ 实验② 决定性版（漂移基线 t0..t4）
├── run_iso.py       ★ 实验③：ISO 档位对照
├── iso_enum.py      ★ ISO 枚举逐个试写 + 回读自证
├── ep_smoke.py      ★ 单发验证（抓到 ioctl 打错 fd）
├── epdiff.py        ★ 差分 + 可逆性判定（判据不成立返回非零）
├── epdump2.arm      ★ 只读全块 dump 器（ARM32）
├── raw/   23 文件    第一批原始输出
├── raw2/  14 文件    第二批
├── raw3/  33 文件    第三、四批
├── raw4/  28 文件    第五批
├── raw5/  90 文件    第六批及深挖
├── raw6/   9 文件    第七批：ioctl 探针实测（第 14 章）
└── raw7/  30+ 文件   ★ 第八批：三个只读 EP 实验（本文第 15 章）
```
