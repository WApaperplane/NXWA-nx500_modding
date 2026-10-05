# NX500 Camera System Firmware-Layer Framework

> Crawl window: 2026-10-05 21:10–21:20
> Target: `192.168.0.105` (**note: the IP changed — the old `.103` is no longer reachable**),
> firmware `NX500GLU0APC1` v`1.12`
> Raw data: `test_server/sysarch/raw8/` (89 files, 278 KB of raw output)
> Crawler: `test_server/sysarch/fwprobe.py` (batched, serial, per-command timeout, resumable)

---

## 0. Crawl Method & Discipline Compliance

| Rule | This run |
|---|---|
| telnet must be serial | ✅ single session throughout, each command sent independently |
| Never `cat /proc/iomem` | ✅ the script **does not contain this command at all** |
| Never `find /sys/...` | ✅ only `ls` with bounded depth |
| Single command ≤2.5 s | ✅ 6 s cap in code, observed 0.3–1.5 s per command |
| ≥10 KB via FTP | ✅ `libudd5.so` (320 KB) + 7 ini files, all via FTP |
| CRLF is the #1 trap | ✅ normalized `CRLF → LF` before writing to disk |

**Batch result: 89/89 commands succeeded. 0 failures, 0 interruptions.**

---

## 1. System Overview

```
Machine: Samsung-DRIMe5-ES          ← first line of the cold-boot dmesg
Linux 3.5.0 #7 PREEMPT 2015-06-03   ← kernel (earlier than the hs2704 build we had on record)
#1 PREEMPT Wed Jun 3 14:40:29 KST 2015 armv7l
/etc/version: 1.12 / NX500 / NX500GLU0APC1 / DSP_NX500GLU0APC1_SR1 / BABF43A
Tizen 2.2.0 Magnolia
```

**DRIMe5-ES SoC composition** (two independent sources: `d5_lib.h` interrupt enum + dmesg):

| Core | Role | Evidence |
|---|---|---|
| **Cortex-A9 (CA9)** | Application core, runs Linux/Tizen | all user space lives here |
| **Cortex-A7 (CA7)** | Co-processor | `s1 key push!(ipcc raw int[a7_2:0])` |
| **★ ISP (ID=31)** | Image signal processing | `DRIME5: IDS : 31(ISP), 57(ARM)` |
| ARM (ID=57) | Main core | same line |
| Cortex-M4 ×N | Real-time micro-controllers | `m4_off_work_handler M4 Off` |
| SRP | DSP | declared in headers, **no code path on the kernel side** |

---

## 2. Storage Layout & Mount Topology

```
/dev/root          ext4   ro   ← read-only rootfs (/usr /bin /sbin /lib live here)
/dev/mmcblk0p11    ext4   rw   → /opt              (application data, writable)
/dev/mmcblk0p14    ext4   rw   → /opt/usr          (NX-KS2 mod deployment target)
/dev/mmcblk1p1     exfat  rw   → /opt/storage/sdcard  (SD card, FTP root)
/dev/loop0         squashfs ro  → /usr/share/locale
tmpfs                     rw   → /tmp /var/log /var/run /dev/shm
```

★ **Key consequences**:
- **`/usr` sits on the read-only rootfs** ⇒ replacing a system library requires an
  `/opt/usr` overlay or a rootfs replacement. **In-place edits are impossible.**
- **The mod target `/opt/usr/nx-ks/` is on the writable p14 partition**
  ⇒ the only safe drop location.
- **The FTP root is the SD card** (`/opt/storage/sdcard`), not `/`.
  This is why a direct `RETR /opt/usr/lib/xxx` returns `550 Error`.

### Partition table (`/proc/partitions`, 3.7 GB eMMC)

| Device | Size | Inferred purpose |
|---|---|---|
| `mmcblk0p1..p4` | 20M/10M/30M/1K | bootloader area |
| `mmcblk0p5..p8` | 20M/10M/30M/50M | vendor images (**unmounted — possibly read-only firmware partitions**) |
| `mmcblk0p9` | 150M | ? |
| `mmcblk0p10` | 1G | ? |
| **`mmcblk0p11`** | **100M** | **`/opt`** |
| `mmcblk0p12/13` | 5M/10M | ? |
| **`mmcblk0p14`** | **2.3G** | **`/opt/usr`** |
| `mmcblk0boot0/1` | 4M ×2 | eMMC boot partitions (unknown partition table) |

★ **`mmcblk0p5..p8` being unmounted makes them the prime candidates for the ISP firmware image.**

---

## 3. User-Space Framework

### 3.1 Key processes (`/proc/*/comm`)

| PID | Process | Notes |
|---|---|---|
| 1 | `systemd` | Tizen 2.2 style init |
| 139 | `Xorg` | **X11 graphics (a full-screen 720×480 saturates the single core)** |
| 175 | **`launchpad_prelo`** | ★ **respawns `di-camera-app`; cannot be killed** |
| 197 | `enlightenment` | EFL window manager |
| **252** | **`di-camera-app`** | ★ main camera application (CPU time 00:25:29) |
| 259 | `isf-panel-efl` | viewfinder panel |
| — | `dfmsd` (7.3 MB) | Tizen application-management daemon |
| — | `MOAL_*` | Marvell wireless driver |
| 154 | `nx-on-wake` | ★ **our own NX-KS2 wake-up script** |

### 3.2 Key libraries (`/usr/lib`)

| Library | Size | Role |
|---|---|---|
| **`libudd5.so`** | **320216** | ★ **DRIMe5 user-space hardware driver master library** (`-ludd5`) |
| `libtint-util.so` | 254252 | ★ Samsung internal image toolkit (yccMixer / yccToRgb) |
| `libevas.so.1.7.99` | 739008 | EFL canvas |
| `libsoup-2.4.so` | 327244 | HTTP client (used by the port-80 web album) |
| `libpulsecore-4.0.so` | 421960 | audio |
| `libsensor.so.1.1.0` | 83716 | ★ sensor abstraction layer |
| `libdrm_drime5.so.1` | 5840 | DRM display |
| `libmm-displayer.so` | 28844 | display abstraction |
| `libmm-type.so` | 19296 | `CYcc` type system |

### 3.3 Notable `libudd5.so` exports (503 symbols total)

- **EP (image engine)**: `d5_ep_open/close`, `d5_ep_top_update_sreg`,
  `d5_ep_3dl_load_lut/save_lut`, **`d5_ep_nog_set_noisegen`** ★,
  `d5_ep_mc_*`, `d5_ep_srsz_*`, `d5_ep_lvr_*`, `d5_ep_jpeg_*`, `d5_ep_bitb_*`
- **Base-address variables (.bss)**: `ep_top_reg_base@…`, `ep_3dlut_reg_base`,
  `ep_nog_reg_base`, … 11 in total
- **IPCC**: `ipcc_open/close/read_pkt/write_pkt/raw_send_interrupt`
- **GPIO / SPI / PWM**: the full `ugpio` family
- **SMA**: `d5_ep_sma_virt_to_phys` (virtual→physical translation, mandatory for EP DMA)

### 3.4 Device nodes (`/dev`)

| Node | major:minor | Maps to |
|---|---|---|
| **`/dev/drime5_ep`** | **10:126** | ★ **EP image engine (NOG and 3D LUT both live here)** |
| `/dev/d5_sma` | 10:112 | shared-memory allocator |
| `/dev/d5_ipcc` | 10:111 | inter-core IPC |
| `/dev/d5_mptop` | 10:108 | multi-processor topology |
| `/dev/d5_cmdq` | 10:110 | command queue |
| `/dev/d5_hevc` | 10:107 | hardware H.265 |
| `/dev/d5_lock` | 10:109 | hardware lock |
| `/dev/mipi_csis*` | 10:101–106 | MIPI CSI receive (sensor) |
| `/dev/mipi_dsim0/1` | 10:100/101 | MIPI DSI transmit (panel) |
| `/dev/kmem`, `/dev/mem` | 1:2, 1:1 | ★ kernel memory (EP dumps depend on these) |
| `/dev/fb0` | 29:0 | framebuffer |

★ **`d5_promise` has sysfs entries but no device node** ⇒ a pure kernel-internal
component (multi-core voltage domains), unreachable from user space.
Its `tmcb` node exposes 9 sets of min/max/mean statistics.

---

## 4. Kernel Layer

### 4.1 Platform devices (`/sys/bus/platform/devices/`, 52 entries)

**DRIMe5-specific**: `d5_cmdq` `d5_hevc` `d5_ipcc` `d5_lock` `d5_mipi_csis*`
`d5_mipi_csim*` `d5_mipi_dsim*` `d5_mptop` `d5_promise` `d5_sma` `d5_tsu`
`drime5_ep.0` `d5-keys` `drime5-adc` `drime5-clock` `drime5-ddrfreq` `drime5-drm.0`
`drime5-drm-hdmi.0` `drime5-fault-handler` `drime5-i2c.0..5` `drime5-i2s.0`
`drime5-ispfreq` `drime5-pmu.1` `drime5-pwm.4/5/10` `drime5-rmu.0` `drime5-rtc`
`drime5-thermister` `drime5_cec.0` `drime5_dp_ctrl.0` `drime5_lcd` `drime5_spi.0`
`drime5_wdt` `drimex-drd.0` `d5-adc-battery`

**Loaded modules** (`/proc/modules`): `sd8xxx` (459 K) `mlan` (391 K) `cfg80211`
`bt8887` (722 K) `exfat_fs` `exfat_core`
⇒ **All of DRIMe5 is built into the kernel** (no separate `.ko`); only WLAN/BT/filesystems
are modular.

### 4.2 Key cold-boot dmesg lines (first time we captured the `[ 0: 0.000000]` epoch)

```
[ 0: 0.000000] Booting Linux on physical CPU 0
[ 0: 0.000000] Machine: Samsung-DRIMe5-ES
[ 0: 1.243065] drime5_es_init()
[ 0: 1.245633] DRIME5: IDS : 31(ISP), 57(ARM) PROMISE : 97 RESULT : 8
[ 0: 1.245640] DRIME5 ASV : 8 Group
[ 0: 1.278069] VDD_ISP: 770 <--> 1400 mV at 860 mV      ← ★ ISP voltage domain
[ 0: 1.285031] Switching to clocksource drime5_clocksource_timer
[ 0: 1.294795] dma-pl330.0: Loaded driver for PL330 DMAC
[ 0: 1.308053] Mali: Mali device driver loaded
[ 0: 1.308212] UMP: UMP device driver 1 loaded
[ 0: 1.339544] input: Melfas MMS100s Touchscreen
[ 0: 2.305072] drime5_wdt: Watchdog Timer enabled (5 seconds)
[ 0: 2.421656] mmcblk0boot0: H4G2a partition 1 4.00 MiB
```

★★ **Established this run: the entire cold-boot log contains no ISP firmware load record.**
A search for `request_firmware` / `uImage` / `rom.bin` / `devicem4.bin` / `srp`
returns **zero hits**. Only BT (`BT: FW download over, size 653112 bytes`) and WLAN
log firmware downloads.

⇒ **The ISP firmware is loaded by the bootloader before Linux starts; the Linux side
is completely unaware of it.** This corroborates the zero-ISP-reference finding across
all 503 `libudd5.so` symbols.

---

## 4.2 ★★★ eMMC Unmounted-Partition Scan (done opportunistically while crawling — highest-value result)

Raw data: `raw8/uimage_scan.txt`. **Read-only probing** (`dd if=… | od`; no write
operation of any kind was issued against a partition).

| Partition | Header | Interpretation |
|---|---|---|
| p5 | `33 00 33 00 09 84 df 56` | not a uImage; sparse ⇒ data/idle |
| **p6** | **`27 05 19 56`** + `Linux-3.5.0` | ★ **uImage (kernel)** |
| **p7** | `4e 00 00 ea 18 00 00 ea` | ★ **bare ARM image (no uImage header)** |
| p8/p9/p10/p12 | all zeros | idle |
| **p13** | **`27 05 19 56`** + `Linux-3.5.0` | ★ **uImage (kernel)** |

### Full uImage header decode

| Field | `mmcblk0p6` | `mmcblk0p13` |
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

★★ **Critical reading: both uImages share `load_addr == entry_point == 0x86008000`,
both are `type = kernel`, both uncompressed.** ⇒ These are **two copies of the same
kernel** (primary/backup), *not* "kernel + ISP firmware".

⇒ **The ISP firmware (`DSP_NX500GLU0APC1_SR1`) is not inside either uImage.**
   The two most likely locations are:
   - **`p1..p4` (the bootloader area)** — the bootloader loads it before Linux,
     consistent with "zero awareness on the Linux side".
   - **`p7`, the bare image** — no uImage header, starts with ARM instructions
     (`4e/18/1e/2c/38 00 00 ea` = a run of `b .`, i.e. a typical ARM relocation table;
     the trailing `12 05 6d f9` = `ldr r1,[pc,#0x512]` jumps to a data table).

### ARM disassembly of the first 64 bytes of `p7`

```
4e 00 00 ea   b  .            ← 5 consecutive = ARM relocation table
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
12 05 6d f9   ldr  r1, [pc, #0x512]   ← jump to data table
08 10 2d e9   push {r3, r8}
```

**This is not Linux code** (no `Linux-3.5.0` header, no `__boot_`-style layout).
It looks much more like an **M4/CM4 or ISP co-processor firmware image header**.
⇒ ★ **This is the strongest candidate yet for the `DSP_NX500GLU` firmware body.**

### Next step (targeting p7 / p1-p4)

```sh
# read-only: first 1 KB of p7, hunting for a uImage header or a signature
dd if=/dev/mmcblk0p7 bs=1024 count=1 2>/dev/null | od -A x -t x1z -v | head -70
# read-only: sweep p1-p4 for 0x27051956 or a 0x4e00 lead-in
for p in 1 2 3 4; do echo "== p$p =="; dd if=/dev/mmcblk0p$p bs=4k count=64 2>/dev/null | od -A x -t x1z | head -8; done
```
⚠️ **Read-only. Never `dd` *to* a partition device, never mount it writable.**

---

## 5. `/opt/etc` — the Camera's System Configuration Core (new this run)

This directory had never been explored before. **It is where camera behaviour
actually lives.**

```
/opt/etc/
├── .debugmode                    27 B    ← debug-mode switch ★
├── .mac.info                     17 B
├── mmfw_camcorder.ini            3.9 K   ← Camera/Camcorder master config
├── mmfw_camcorder_dev_video_pri.ini  6.5 K  ← primary video pipeline
├── mmfw_camcorder_dev_video_sec.ini  5.8 K  ← secondary video pipeline
├── mmfw_player.ini               2.4 K   ← player
├── gst-openmax.conf              2.8 K   ← ★ GStreamer OpenMAX plugin
├── dlog.conf / dlog_logger.conf  2.9 K   ← logging
├── dnsmasq.leases, p2p_supp.conf, wl-regdom.conf
├── smack/ smack-app/ smack-app-early/    ← SELinux policy
├── ssl/certs, allshare/config, dump.d/module.d
```

### 5.1 Key facts in `mmfw_camcorder.ini`

```ini
ModelName = DRIMeIV-NX300      ← ★ the config declares NX300; the hardware is an NX500
DisplayDevice = 0 || 0
ImageProfile = 2
```

### 5.2 Resolution table in `mmfw_camcorder_dev_video_pri.ini`

```ini
CaptureResolution = 1024,1024 | 2000,2000 | 2640,2640 | 3640,3640
                   | 1920,1080 | 2944,1656 | 3712,2808 | 5464,3072
                   | 1728,1152 | 2976,1984 | 3888,2592 | 4896,3264
                   | 5464,3640 | 5592,3728  || 5592,3728
                                        ↑ default     ↑ maximum
```
- `5464,3640` = 19.9 MP (the NX500's actual output)
- `5592,3728` = 20.8 MP (full pixel count)
- `PreviewResolution` maxes at `4096,2160`, defaults to `640,480`
- `PictureFormat = 0,4,7 || 7` ⇒ default **I420** (0=NV12, 4=YUYV, 7=I420)
- `RecommendDisplayRotation = 3` (270°)
- `SensorEncodedCapture = 1` (primary sensor encodes directly)

### 5.3 ★ A Key Negative Result

**Grepping all 7 config files for `ep|isp|nog|lut|drime|d5` yields zero hits on
EP/NOG/LUT configuration items.**

⇒ This corroborates the earlier conclusion: **EP hardware parameters do not flow
through the mmfw configuration framework.** They are controlled out-of-band by the
ISP firmware plus `libudd5.so`. The config framework only handles resolution, format,
exposure and white balance.

---

## 6. ★ Most Important Validation This Run: On-Device Library vs GPL Package

| | NX1 GPL package | **On-device NX500** |
|---|---|---|
| file | `.uploads/nx1_open/.../libudd5.so` | **`raw8/real_libudd5.so`** (pulled via FTP) |
| size | 279036 | **320216** |
| `.text` | `@0x8f70` size 227224 | `@0x91c0` size **264768** |
| symbol count | 503 | 503 (identical names) |

### Offset re-decoding on the on-device library: exact agreement

| Item | GPL build | **On-device build** | Verdict |
|---|---|---|---|
| `ADD 0x30` (NOG block) | 5/5 functions | **5/5 functions** | ✅ match |
| `ADD 0x65/0x66/0x67` | ✓ | ✓ | ✅ match |
| `SUB 0x1f` (mask) | ✓ | ✓ | ✅ match |
| `set_bypass` size | 240 | **240** | ✅ |
| `set_std_sigma` size | 432 | **432** | ✅ |
| `set_gamma` size | 684 | 684 | ✅ |
| `reg_struct_init` size | 248 | 248 | ✅ |

★★ **Conclusion: every NOG/3D-LUT register-offset conclusion holds on the real device.**
The two builds differ only in base addresses; the instruction encodings are identical
⇒ **compiled from the same source.**

> On-device `.bss` locations:
> `ep_nog_reg_base@0x57724`, `nog_regset0@0x57768`, `nog_regset1@0x57748`

---

## 7. Next Steps (by value)

| Priority | Action | Rationale |
|---|---|---|
| **1** | **Dig into `mmcblk0p7` (bare ARM image)** | ★ new finding, **strongest ISP-firmware candidate**. First 64 B already disassembled: relocation table + data-table layout, no Linux signatures |
| **2** | Sweep `mmcblk0p1..p4` (bootloader area) for `0x27051956` | The bootloader loads the ISP firmware before Linux; most likely hiding here |
| **3** | NOG probe (`d5_ep_nog_set_noisegen`) + pixel-variance statistics before/after liveview | Single decisive test for the FilmLab hardware-grain path |
| 4 | Verify whether `d5_ep_top_update_sreg(3DLUT_SHADOW_UPDATE)` is required for 3D-LUT changes to take effect | Determines whether `.cube` LUTs can be pushed down into the body |
| 5 | FTP-pull `di-camera-app` (the main camera program) and disassemble to find its ISP calls | It is the only user-space program that calls libudd5 |

⚠️ **Risk note for reading unmounted partitions**: `mmcblk0p5..p8` may hold
vendor read-only images. **Read only, never write**:
```sh
dd if=/dev/mmcblk0p5 of=/dev/null bs=1M count=1     # confirm readability first
```
⚠️ **Never `dd` into a partition device. Never mount it writable.**

---

## 8. New Tools Added This Run

| File | Purpose |
|---|---|
| **`test_server/sysarch/fwprobe.py`** | ★ Batched crawler: 89 commands in 5 batches, serial, per-command timeout, auto-reconnect, LF normalization, resumable (skips files that already exist) |
| **`test_server/sysarch/ftpx.py`** | FTP get/put wrapper (stdlib `ftplib`, no third-party dependency); returns `None` on failure instead of raising |

### Traps hit this run (4 new ones)

1. **The camera's IP changes** (`.103` → `.105`)
   ⇒ ping neighbouring IPs before doing anything; never trust a remembered address.
2. **FTP refuses symlinks**: a chain created with `ln -sf` makes `RETR` return
   `550 Error` (vsftpd anti-escape) ⇒ you must make a real `cp`.
3. **The FTP root is the SD card, not `/`**: `RETR /opt/usr/lib/x.so` fails because the
   real path is `/usr/lib/x.so` (**`/usr` is on the read-only rootfs, not under `/opt/usr`**).
   Standard flow: `cp` to `/opt/storage/sdcard/` over telnet, then pull via FTP.
4. **telnet echo pollution**: the command is echoed back and long commands wrap into
   fragments that look like garbage
   ⇒ **never read results from the echo; read only what follows the prompt.**

---

## 9. Cross-Reference: Where the Details Live

| Topic | Document |
|---|---|
| EP register map, NOG offsets, 3D LUT entry chain | `docs/ISP_NOG_ENTRY_2026-10-05.md` |
| Full system architecture, key sequence, PF/SRSZ | `docs/NX500_ARCHITECTURE.md` |
| 10-04 + 10-05 consolidated bilingual results | `docs/CONSOLIDATED_REPORT_2026-10-05.md` |
| Raw crawl output (89 files) | `test_server/sysarch/raw8/` |

---

## 10. Terminology

| Term | Meaning |
|---|---|
| **UDD** | Userspace Device Driver — Samsung's model where the *user-space* library talks to hardware registers directly via `ioctl` + `mmap`, with the kernel only providing the device node |
| **EP** | Image Engine — a hardware block handling colour/lens/scaler/JPEG sub-pipelines, exposed as `/dev/drime5_ep` |
| **NOG** | Noise Generator — the hardware grain generator inside EP |
| **3D LUT** | 3-dimensional colour lookup table, also inside EP |
| **SMA** | Shared Memory Allocator — the `d5_sma` driver providing virtual→physical translation |
| **IPCC** | Inter-Processor Communication Channel — nominally the cross-core path, but measured to be a shell |
| **uImage** | The standard U-Boot bootable-image container; magic `0x27051956` |
| **bx / bl** | ARM branch-exchange / branch-with-link instructions |
