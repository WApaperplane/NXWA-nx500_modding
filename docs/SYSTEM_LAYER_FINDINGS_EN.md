# NX500 System-Level Findings — ISP Internals & Toolchain

> Companion to [`DEVELOPMENT_REPORT_EN.md`](DEVELOPMENT_REPORT_EN.md).
> **Only empirically verified conclusions are recorded here.** Every refuted hypothesis is listed in §10, because knowing which paths are dead ends saves more time than the findings themselves.

**Platform**: Samsung NX500, Tizen / DRIMe5, firmware 1.12
**Date**: 2026-10-04 → 10-05

---

## 1. Physical → Virtual Address Mapping

```c
virt_of_phys(p) = p - 0xB7FC000
```

**Two independent samples agree exactly:**

| Physical | Virtual | Delta | Source |
|---|---|---|---|
| `0x94000000` | `0x88804000` | `-0xB7FC000` | CMA 288 MiB region |
| `0x85400000` | `0x79c04000` | `-0xB7FC000` | ISP segment |

**Cross-check**: `0x79c04000` falls inside the `71d74000-79d74000 rw-s /dev/mem` mapping in `/proc/252/maps` (offset `0x99600000`, 8 MB) — the ISP register window.

**This is a uniform linear mapping, not a segmented table.** With it, any hardware register address can be computed.

### 1.1 Known segment translations

| Physical (maps `offset` column) | Virtual | Size | Suspected use |
|---|---|---|---|
| `0x99600000` | `0x79c04000` | 8 MB | **ISP register window** |
| `0x98200000` | `0x78204000` | 8 MB | ISP-related |
| `0x97800000` | `0x77804000` | 8 MB | — |
| `0x94000000` | `0x88804000` | 32 MB | CMA (part of the 288 MiB) |
| `0x84c00000` | `0x78c04000` | ~5 MB | — |
| `0x854e0000` | `0x79504000` | 44 KB | — |
| `0x85600000` | `0x79604000` | 4 KB | — |
| `0x85500000` | `0x79524000` | 4 KB | — |

---

## 2. 3D LUT and NOG (Hardware Grain) Control Chain

`libudd5.so` — 320,216 bytes, **fully unstripped**, 388 symbols.

### 2.1 Register-group base globals

All at `.bss`, static offsets:

| Address | Name | Value in a fresh probe (after `d5_ep_open()`) |
|---|---|---|
| `0x57720` | `ep_top_reg_base` | `0xb6f7f000` |
| `0x57724` | `ep_nog_reg_base` | `0xffffffff` (uninitialised) |
| `0x57728` | `ep_ldc_reg_base` | `0xb6f7e000` |
| `0x5772c` | `ep_bblt_reg_base` | `0xb6f79000` |
| `0x57730` | **`ep_3dlut_reg_base`** | `0xb6f76000` |
| `0x57734` | `ep_fd_reg_base` | `0xb6f78000` |
| `0x57738` | `ep_jpeg_reg_base` | `0xb6f77000` |
| `0x5773c` | `ep_rsz_reg_base` | `0xb6f7b000` |
| `0x57740` | `ep_mc_reg_base` | `0xb6f7c000` |
| `0x57744` | `ep_lvr_reg_base` | `0xb6f7a000` |

**These are real, page-aligned virtual addresses — the library opens its own device node and mmaps the hardware.** This is a legitimate channel around the `/dev/mem` `CONFIG_STRICT_DEVMEM` restriction.

Caveat: these are the *probe process's own* mappings. `di-camera-app` holds a separate set.

### 2.2 3D LUT symbols

```c
d5_ep_3dlut_op_init                 0x13c2c   ★ init
d5_ep_3dl_load_lut                   0x13d10   ★★ load LUT
d5_ep_3dl_save_lut                   0x13e14   ★  save LUT

_udd_ep_3dl_reg_GetReg               0x17508
_udd_ep_3dl_reg_SetReg               0x17530   ★ direct register write
_udd_ep_3dl_reg_OnOff                0x1755c
_udd_ep_3dl_reg_SelCbCr_ch           0x175e4   ★ select Cb / Cr channel
_udd_ep_3dl_reg_SelLUT               0x17668   ★ select table
_udd_ep_3dl_reg_SetColorFormat_LUT0  0x176ec
_udd_ep_3dl_reg_SetColorFormat_LUT1  0x17770
_udd_ep_3dl_reg_Acc_OnOff            0x177f4
_udd_ep_3dl_reg_rw_Start             0x17884   ★ start read/write
_udd_ep_3dl_reg_SetAddress           0x1798c   ★ set address

_udd_ep_3dl_ctrl_ConfigBypassMode    0x1863c
_udd_ep_3dl_ctrl_ConfigAccessMode    0x18664
_udd_ep_3dl_ctrl_ConfigProcessMode   0x186b8
```

### 2.3 NOG (hardware grain) symbols

```c
_udd_ep_nog_reg_struct_init  0x20070   ★ must be called first
_udd_ep_nog_set_random_seed  0x20168
_udd_ep_nog_seed_load_switch 0x20250
_udd_ep_nog_select_rv_type   0x20300   ★ grain type
_udd_ep_nog_set_std_sigma    0x203b0   ★ grain intensity
_udd_ep_nog_set_gamma        0x20560   ★ grain distribution
_udd_ep_nog_set_bypass       0x2080c
d5_ep_nog_set_noisegen       0x105f0
d5_ep_nog_set_bypass         0x105cc
_udd_ep_nog_regset0          0x57768
_udd_ep_nog_regset1          0x57748
```

### 2.4 `d5_ep_3dl_load_lut` semantics (from disassembly)

```
prototype: d5_ep_3dl_load_lut(handle, mode, table, data)
validation:
    handle != NULL
    mode <= 2
    table ∈ {0, 1}        ← dual table: Cb and Cr select independently
returns: -1 on failure, 0 on success

internal flow:
    bl 0x8b60   → _udd_ep_set_timeout_rdma_start_fsm   (PLT 0x8b64)
    builds a 60-byte structure on the stack
    bl 0x86f8   → _udd_ep_demux_path_input             (PLT 0x86fc)
```

**Important correction to an earlier assumption**: `d5_ep_3dl_load_lut` does **not** write registers itself. It constructs a descriptor and configures the demux path. The actual register writes happen in the `_udd_ep_3dl_reg_*` group.

### 2.5 `d5_ep_3dlut_op_init` hard constraint

```
0x13c44: ldr r3, [handle]        ; r0 = handle (a POINTER, not an integer)
0x13c48: cmp r3, #0
0x13c4c: bne ...
0x13c50: mvn r3, #0              ; NULL → return -1
0x13c58: ldr r3, [handle, #0x0c] ; ★ read handle+0x0c
0x13c60: cmp r3, #1               ; ★ must equal 1
0x13c64: bne ...
```

**The handle is a pointer whose field at offset `0x0c` must equal 1.** It is created and initialised by the camera framework. An independent probe process has no way to construct it.

**Consequence**: writing a 3D LUT from a standalone probe is blocked. Calling into the camera framework from outside the process (e.g. `GetCameraIfHandle()`) segfaults, because that path requires an initialised camera context.

### 2.6 3D LUT is initialised on demand

```
libudd5.so is mapped in 4 processes:
    pid 193  deviced
    pid 197  enlightenment
    pid 252  di-camera-app
    pid 290  ap-setting-app

yet in di-camera-app:
    ep_3dlut_reg_base = 0x0000
    ep_mc_reg_base    = 0x0000
    ep_top_reg_base   = 0x0000
```

**In the default camera state the 3D LUT register groups are not allocated at all.** A value of `0x0103b7f` was observed in an earlier session — that was post-use state, not initial state. This is the key unknown to investigate next.

---

## 3. Kernel EP Driver Surface

`/proc/kallsyms` is fully readable — **43,181 lines**.

```
ep_set_top_reg_info    c02cc40c      ep_set_ldc_reg_info  c02cc420
ep_set_mc_reg_info     c02cc434      ep_set_rsz_reg_info  c02cc448
ep_set_jpeg_reg_info   c02cc45c      ep_set_fd_reg_info   c02cc470
ep_set_bblt_reg_info   c02cc484      ep_set_lvr_reg_info  c02cc498
ep_set_3dlut_reg_info  c02cc4ac  ★   ep_set_nog_reg_info  c02cc4c0  ★
ep_get_reg_info        c02cc4d4  ★   ep_set_device_info   c02cc4f0
ep_dd_set_top_reg      c02cc504      ep_dma_reset         c02cc514
ep_pmu_requeset        c02cc530      ep_pmu_clear         c02cc538
ep_pmu_on_off          c02cc550      ep_set_clk_rate      c02cc554

c07551c8 B reg_info     ← bss global holding all register-group configuration
```

Module abbreviations: `top` = top level, `ldc` = lens distortion, `mc` = motion compensation (owns yccmixer), `rsz` = resize, `fd` = face detection, `bblt` = BB LT, `3dlut`, `nog` = noise generator.

**★ This corrects a dead end.** An earlier attempt built register-group pointers manually and segfaulted because they read as zero. The missing step was calling `ep_set_*_reg_info` first — those functions *are* the kernel-side "allocate and populate" entry points.

---

## 4. `CCapVirtualAddrIf` — Verified Working

`SingletonI<T>::getInstance()` is a **static** function (no `this` parameter), so it is safe to call from a standalone probe.

```c
SingletonI<CCapVirtualAddrIf>::getInstance()   // static address 0x626e4
```

**Measured instance state:**

```
instance = 0x0006f230
vtable   = base + 0xb0010   (matches _ZTV17CCapVirtualAddrIf ✓)
+0x04 = 0x94000000    ← dmesg: "cma: reserved 288 MiB at 94000000"
+0x08 = 0xbfffffff    ← 4 GB minus 1, address-space ceiling
+0x0c = VirtTopAddr   ← GetVirtTopAddr() returned 0x887f8000 when called
```

**This avoids the `GetCameraIfHandle()` crash**, which segfaults in a standalone probe because the camera framework is not initialised there. Hard constraint: framework functions must be called from inside `di-camera-app`.

### 4.1 Full singleton table

| Singleton | `getInstance()` |
|---|---|
| **`CCapVirtualAddrIf`** | **`0x626e4`** ← address mapping layer |
| `CCaptureController` | `0x3d1d4` |
| `CTraceLog` | `0x3e178` |
| `CCapturePublisher` | `0x80f14` |
| `CMCBAdapter` | `0x871f0` |

---

## 5. Confirmed Dead Code

`libcapture-fw-prod.so` — 1,835 unstripped symbols. `CAttributeHandler` has **324 methods**.

### 5.1 The tempting ones

| Static address | Method | Attribute ID |
|---|---|---|
| `0x94e84` | `setPWColor` | `0x10E` (read from a `movw r0, #0x10E` instruction) |
| `0x94d10` | `setPWSaturation` | `0x111` |
| `0x94d8c` | `setPWSharpness` | `0x112` |
| `0x94e08` | `setPWContrast` | `0x113` |
| **`0x965f4`** | **`setPWBracket(char, char)`** | ★ genuine shadow/highlight curve control |
| `0x92fb8` | `getPWBracketParam` | read current curve params |

### 5.2 But a heap scan returns zero

`heapscan` over `[heap]` (3.4 MB) + `.data`/`.bss` (352 KB):

| Search target | Hits |
|---|---|
| `CAttributeHandler` vtable | **0** |
| capture-fw base address | **0** |
| `setPWColor` / `setPWSaturation` / `setPWContrast` | **0** |
| `setPWBracket` / `getPWBracketParam` | **0** |
| `writeUserAttr` | **0** |

**The NX500 runtime never references any of these.** The camera actually uses the `st` / `capdtm` / `libudd5.so` path (`prefman` + `setusr` + ipcc).

### 5.3 The correct dead-code test

```
✗  Wrong:   it appears in /proc/<pid>/maps → assume it is used
✓  Correct: scan the target process's memory for the library's key
            function addresses and check whether anything references them
```

`maps` proves *loaded*, not *called*. This is the single highest-value lesson from the whole investigation.

---

## 6. Measured Hardware Constraints

| Constraint | Observed | Implication |
|---|---|---|
| `/dev/mem` read | `pread` returns -1 | `CONFIG_STRICT_DEVMEM` — registers not directly readable |
| `/proc/<pid>/mem` read of device mapping | `read` returns -1 | Kernel forbids cross-process reads of device mappings |
| `poker` write to `.text` | `Buffers not the same: ERROR` | Code pages kernel-protected — call-site hijacking impossible |
| `poker` write to `.data` | ✓ succeeds | Data pages freely read/write |
| **CPU NX bit** | **absent** (`Features: swp half thumb fastmult vfp edsp neon vfpv3 tls`) | ARMv7; code placed in `.data` is likely executable |
| Root filesystem | `/dev/root` ext4 **ro** | Cannot replace any `.so` |
| `LD_LIBRARY_PATH` | `:/usr/lib:/usr/lib/driver` | Leading empty entry = cwd, but cwd is `/` → unusable |
| `LD_PRELOAD` | not present | Cannot inject |
| `/proc/softirqs`, `/proc/interrupts`, `/proc/PID/io` | unavailable | 3.5 kernel exports none of them; standard perf tooling fails |

**The only remaining register-access channel is `libudd5.so`'s wrapper functions**, which use `ioctl` internally (the kernel proxies register access).

**The only remaining code-injection channel** is `poker` writing `.data` (no NX). GOT slots in `di-camera-app` live at `0x448adc` (4,384 bytes, `rw-p`, verified writable).

---

## 7. Platform Baseline

| Property | Value |
|---|---|
| CPU | ARMv7 rev 1 (v7l), Exynos, NEON, **no NX** |
| Memory | CMA statically reserved 288 + 72 MiB at `0x94000000` → ~142 MB actually usable |
| Root FS | `/dev/root` ext4 **ro**; `/usr/share/locale` mounted from `/dev/loop0` squashfs (loop mounting is supported) |
| `di-camera-app` | pid 252, loaded at `0x00008000-0x00441000` (**no PIE, not relocated**) |
| Library path | `LD_LIBRARY_PATH=:/usr/lib:/usr/lib/driver`, cwd `/` |

### 7.1 Unstripped libraries

| Library | Size | Symbols | Role | Actually called? |
|---|---|---|---|---|
| **`libudd5.so`** | 320 KB | unstripped | **3D LUT / NOG / ipcc wrappers** | ✅ **yes** |
| `libsif.so` | 657 KB | 654 / 81 classes | SIF image framework | ✅ yes |
| `libcapture-fw-prod.so` | — | 1,835 | property bus | ❌ **dead code** |
| `libSLP-db-util.so` | 10 KB | — | (not the 3D LUT host, contrary to earlier assumption) | — |

### 7.2 `libsif.so` key addresses (verified via `poker`)

| Runtime | Static | Method |
|---|---|---|
| `0xb0c943c4` | `0x2c3c4` | `DscFileHandler::taskMain` (thread entry) |
| `0xb0c95590` | `0x2d590` | **`DscFileHandler::writeChunks`** |
| `0xb0c99c44` | `0x31c44` | `DscFileHandler::operate(tImage_buffer*)` |
| `0xb0c9b8e0` | `0x338e0` | **`DscFileHandler::storageException(bool)`** |
| `0xb0c9c4d4` | `0x344d4` | `pauseOrResume(FileHandlerState)` |

---

## 8. `st cap` Command Tree

```sh
st cap capdtm usrlist# userdata indexes 0-86 (full table)
st cap capdtm getvar <id>  # ★ different index space from varlist
st cap capdtm setvar <id> <data> <len>
st cap capdtm varlist
st cap iqr                # 183 IQ nodes (read-only; ISP constant table)
st devman get/set [dev] [prop] [val]   # all nodes read back 0 — no usable properties
st firmware up            # only accepts uImage / rom.bin / devicem4.bin
```

**★ NX500-wide quirk**: indexes printed by any "list" command cannot be assumed valid for read/write commands. Align in three steps: *read list → verify with the read command → verify with the write command*. This was hit three times in one day (`setusr`, `getvar`, `varlist`).

---

## 9. `adj_*` Segments Are Read-Only Constants

| Segment | Size | Non-zero | Verdict |
|---|---|---|---|
| 6 `adj_iq` | 3.5 KB | 1.6% | empty |
| 7 `adj_vfpn` | 24 KB | 90.6% | fixed-pattern-noise correction |
| 8 `adj_cs` | 64 KB | 49.5% | colour space (contains ASCII `"0100"` / `"Drim"` — structured, not random) |
| 9 `adj_dpc` | 5.2 MB | — | demosaic |
| 10 `adj_dpc2` | 1 MB | 10.5% | demosaic tables |

Each segment exposes exactly **one** named entry covering the whole blob; there is no field-level semantic annotation.

**Five write experiments** (`IQPREF_DATA` header, the ASCII strings, the segment header, data at `0x280`) all wrote and read back correctly, but `iqr[88] COLOR_SPACE` never changed. **Conclusion: the ISP reads this memory directly and never writes it back through the prefman path.**

`/opt/pref/default/` holds a clean factory copy of every segment — preferable to `/opt/pref/*.bin`, which `prefman fetch` will corrupt.

---

## 10. Ten Refuted Hypotheses

**All ten shared one root error: treating co-occurring phenomena as causation.**

| # | Hypothesis | What refuted it |
|---|---|---|
| 1 | Dirty data in slot 12 | Still froze after resetting all 14 slots to neutral |
| 2 | `iqr` hi16 is the live PW value | Wrote 0 — completely unchanged (it is an ISP constant table) |
| 3 | Zero-byte thumbnails in `.thumbcache` | Deleted all 31 — still froze |
| 4 | `ipcc_ioctl` deadlock chain | Also blocked in the **healthy** state → that is its normal condition |
| 5 | Applying a recipe is the trigger | Froze with `PW_TYPE=STANDARD` (recipe inactive) |
| 6 | Photo accumulation / memory leak | `MemFree` stable at 27 MB across 20 s |
| 7 | A thread spinning in a busy loop | After fixing two measurement bugs, its CPU delta was **0** |
| 8 | `CAttributeHandler` property bus is usable | Heap scan: zero hits → dead code |
| 9 | An `iqr` hang precedes the freeze | Watchdog logged `iqr: ok` throughout; criterion never fired |
| 10 | `400x82` is the size playback uses | After clearing the cache, the camera generated **zero** of them |

### 10.1 Two rules

1. **Causality requires both** "A always implies B" **and** "removing A removes B". "A reboot clears it" only proves the state lives in memory.
2. **When reproducing a symptom, decompose it orthogonally** — same action, different context. The decisive split (playback vs. not) should have happened at 19:00; it actually happened at 22:10. Cost: six hours mining dead code.

### 10.2 Three recurring technical errors

1. **jiffies ÷ 100, not ÷ 4** — `utime` in `/proc/PID/stat` is in clock ticks (HZ = 100). This error caused a false accusation against a thread.
2. **`awk '{print $14}'` misaligns fields on `/proc/PID/task/TID/stat`** when `comm` contains spaces or parentheses (`SIF Main)`, `FileHandler)`) → must use `sed 's/.*) //' | awk '{print $11}'`.
3. **`dlsym` on an inherited C++ method needs the base-class name** (no `C` suffix) — `_ZN17CCapVirtualAddrIf14GetVirtTopAddrEv` resolves; `...IfC14GetVirtTopAddrEv` returns NULL.

### 10.3 An operational trap

**`killall -q busybox` is suicidal on this device.** `telnetd`, `ftpd`, and `httpd` are all busybox symlinks. Killing busybox kills your own remote access. Always enumerate `/proc/*/cmdline`, match precisely, then `kill -9 <pid>`.

---

## 11. Toolchain

All tools are in `test_server/pwfilter/`.

| Tool | Purpose |
|---|---|
| **`symref.py <maps> <eip...>`** | Core: eip → which `.so` + offset + **symbol name** |
| **`heapscan`** (camera-side) | Batch `read()` of `/proc/pid/mem` — 3.4 MB in seconds; the dead-code tool |
| **`pltscan.py <elf> [kw]`** | PLT/GOT mapping + call-site location |
| **`arm2.py <so> <va> [n] [label]`** | ARM32 disassembler (proper bitfield decoding) |
| `elfmap.py` | ELF32 sections + eip→file offset |
| `libscan.py` | Section table + symbol filtering |
| `cxx.py` | C++ class structure + demangling |
| `rodump.py` / `enumscan.py` | `.rodata` strings / `E_*` enums |
| `ispprobe` (camera-side) | `dlopen` + `dlsym` + `SingletonI::getInstance()` |
| `lut3d_probe` (camera-side) | 3D LUT / NOG control-chain probe |
| `ftp_put.py` / `ftp_get.py` | Transfer — **remote paths must be prefixed `/mnt/mmc/...`** |
| `telnet_run.py <ip> <cmd>` | Remote execution — **serial only** (parallel wedges the single core) |

**Build rule for camera-side probes**: `-target arm-linux-gnueabi.2.15 -O0 -mfloat-abi=soft` (`-O1` and above segfault); add `-ldl` for `dlopen`.

**A note on writing disassemblers**: guessing instruction encodings by pattern will mis-decode `LDR`/`STR`/`STM`/`LDM`. Decode by bitfield rules (cond / op / sub-op) instead. The first version of `arm2.py` failed exactly this way; the rewrite decodes correctly.

---

## 12. Where to Go Next

| Priority | Direction | Rationale |
|---|---|---|
| **1** | **Find what initialises 3D LUT** | It is initialised on demand. Probe `ep_3dlut_reg_base` while cycling through camera settings until it becomes non-zero. Zero-risk. |
| **2** | Locate the real 3D LUT caller | Not in `di-camera-app` (zero imports). Candidates: `deviced`, or the EP framework driven by ipcc messages. |
| 3 | Write a LUT via the verified mmap channel | Requires a valid `handle` (§2.5). |
| — | ~~Register write via `/dev/mem`~~ | Blocked by `CONFIG_STRICT_DEVMEM` |
| — | ~~`CAttributeHandler` property bus~~ | Dead code (§5) |
| — | ~~Call-site hijacking~~ | `.text` is kernel-protected (§6) |
| — | ~~GOT slot hijack in `di-camera-app`~~ | No 3D LUT imports exist → no slots |

**Open questions for anyone with deeper knowledge of this platform:**

1. What camera setting or mode causes NX500 to initialise its 3D LUT?
2. What is the message format for `/dev/d5_ipcc` when driving the EP framework? (`libudd5.so` contains 793 strings and no message-type enum.)
