# NX-KS2 Development Report — FilmLab & NX500 Internals

**Date**: 2026-10-04 → 2026-10-05
**Branch**: `nx-ks2`
**Author**: WApaperplane
**Scope**: NX500 film-simulation module (FilmLab) + ISP system-level reverse engineering

---

## Abstract

This report covers two parallel tracks:

1. **FilmLab** — a working film-simulation module with 9 recipes, one-tap switching, and camera-button-driven UI, all verified on real hardware.
2. **System-level RE** — extraction of the NX500's ISP control surface, including a physical→virtual address mapping formula, the complete userspace control chain for 3D LUT and hardware grain (NOG), and the elimination of a large dead-code path.

Along the way we debugged a "camera freezes when entering playback" fault and traced it to a **defect in Samsung's own 1.12 firmware**, unrelated to this module.

---

## 1. FilmLab — Film Simulation Module (complete)

### 1.1 Architecture

```
SD card: /mnt/mmc/filmlab/recipes.json   ← single source of truth, unbounded
        ↓ mkgui
mod_gui dynamic menu (≤22 buttons)
        ↓ one tap
filmlab.sh apply
        ↓
prefman set ×7  +  st cap capdtm setusr 20
        ↓
ISP live update (~2 seconds)
```

### 1.2 Key design decisions

| Decision | Rationale |
|---|---|
| **Always write slot 9 (UI "Custom 1")** | The original version rotated across slots. Users could not tell which slot held the recipe — that is not "one tap". Pinning to a single slot means the camera UI always reads "Custom 1"; one press changes the viewfinder instantly. |
| Recipes live on SD, not in camera | Adding a recipe = editing one JSON file. Zero menu changes. No reflash. |
| `mkgui` generates the menu at runtime | Menu size stays bounded regardless of recipe count. |
| Recipe cycling bound to the S1 body key | Hooks into the community's existing `EV_*.sh` body-button mechanism (original saved as `.orig`). |

### 1.3 The 9 recipes

`portra400` · `velvia50` · `trix400` · `ektachrome` · `hp5` · `superia400` · `monowarm` · `ektachrome_cyan` · `cine_teal`

**`monowarm` is unique to the camera's own pipeline**: `SAT=0` (true monochrome) while retaining an R/B gain differential — a warm-toned black-and-white. A PC-side matrix engine cannot produce this.

### 1.4 Capability boundary (stated explicitly)

The 7 PW dimensions are a **global vector applied identically to every pixel** (R/G/B gain + HUE/SAT/SHARP/CONTRAST).

- ✅ Achievable: film-style colour rendition, colour casts, contrast shaping
- ❌ Not achievable: true tone curves, brightness-zone separation, film grain

For reference, `voxivoid/recipe-lab-sony-pmca` (a comparable Sony-era project) produces 77 recipes from 26 one-byte slots — this module reaches comparable control granularity.

---

## 2. System-Level Reverse Engineering

Full detail: **[`SYSTEM_LAYER_FINDINGS_EN.md`](SYSTEM_LAYER_FINDINGS_EN.md)**.

### 2.1 Physical → virtual address mapping (directly usable)

```c
virt_of_phys(p) = p - 0xB7FC000;
```

Two independent samples agree exactly: `0x94000000 → 0x88804000` (CMA region) and `0x85400000 → 0x79c04000` (ISP segment). The second result falls inside the `71d74000-79d74000 rw-s /dev/mem` mapping from `/proc/<pid>/maps` — the ISP register window.

### 2.2 Complete userspace control chain for 3D LUT / NOG

`libudd5.so` (320 KB) ships with a **fully unstripped** symbol table (388 symbols):

```c
d5_ep_3dl_load_lut(handle, mode, table, data)   // load LUT (dual table: Cb / Cr)
_udd_ep_3dl_reg_SetReg      0x17530   _udd_ep_3dl_reg_SetAddress  0x1798c
_udd_ep_3dl_reg_rw_Start    0x17884   _udd_ep_3dl_reg_SelLUT      0x17668
_udd_ep_nog_reg_struct_init 0x20070   _udd_ep_nog_set_std_sigma  0x203b0
_udd_ep_nog_set_gamma       0x20560   _udd_ep_nog_select_rv_type 0x20300
```

**Measured**: `d5_ep_open()` successfully allocates all 9 EP register groups from an independent process, yielding **real virtual addresses** (page-aligned). The library opens its own device node and mmaps the hardware registers — this is a legitimate channel that bypasses the `/dev/mem` `CONFIG_STRICT_DEVMEM` restriction.

### 2.3 Kernel EP driver control surface

`/proc/kallsyms` is fully readable (43,181 lines):

```c
ep_set_3dlut_reg_info   c02cc4ac   ep_set_nog_reg_info  c02cc4c0
ep_get_reg_info         c02cc4d4   c07551c8 B reg_info
```

**This corrects a dead end**: an earlier attempt failed because the register-group pointers were all zero and hand-built pointers segfaulted. The missing step was calling `ep_set_*_reg_info` first — those functions *are* the kernel's "allocate and populate a register group" entry points.

### 2.4 Dead-code identification (saved hours)

`libcapture-fw-prod.so` has **1,835 unstripped symbols**. Its `CAttributeHandler` class exposes **324 methods**, including the most enticing find of the whole project:

```c
setPWBracket(char, char)   // genuine shadow/highlight curve control
setPWColor / setPWSaturation / setPWSharpness / setPWContrast
mm_camera_set_usr_attributes   // property-bus entry point
```

A full heap scan returned **zero hits** — these methods are never invoked at runtime on NX500.

> **★ Methodology lesson (the single most transferable item here)**
> A library appearing in `/proc/<pid>/maps` proves it was **loaded**, not that it is **called**.
> The correct test: scan the target process's memory for the library's key function addresses and check whether anything references them.
> Run this check *before* deep analysis. Skipping it cost several hours here.

### 2.5 Measured hardware constraints

| Constraint | Result |
|---|---|
| Read registers via `/dev/mem` | ✗ `CONFIG_STRICT_DEVMEM` |
| Write `.text` via `poker` | ✗ kernel read-only memory protection |
| Write `.data` via `poker` | ✓ works |
| **CPU NX bit** | **absent** (ARMv7 → code in `.data` is executable) |
| Root filesystem | ext4 **read-only** |
| CPU | ARMv7 rev 1 (v7l), Exynos, NEON |
| Memory | CMA statically reserved 288+72 MiB → ~142 MB actually usable |

---

## 3. Fault Investigation: "freezes when entering playback"

### 3.1 Symptom

After entering playback, **only the delete key hangs**. All other keys respond, the shutter works, the display is normal. The power dial cannot shut the camera down; only pulling the battery recovers it.

### 3.2 Conclusion

**A defect in Samsung's 1.12 firmware itself — independent of this module, the SD card, or file state.**

Elimination sequence:

| Experiment | Result |
|---|---|
| Roll the module back to its earliest version (9/6) | Still reproduces |
| Format the SD card | Still reproduces |
| Use a brand-new empty card (zero files, zero module) | Still reproduces |
| **Factory reset** | **Gone** |

### 3.3 Mechanism

```
Corrupted state under SD-card .thumbcache
  → the ImageGenerator thread enters an invalid state on entering playback
  → the entire system wedges (even SD-card log writes stop)
  → uninterruptible wait → power dial cannot complete shutdown
```

**Why formatting did not help**: formatting only clears `DCIM/` and the root directory. It does **not** clear `/mnt/mmc/.thumbcache/` (a hidden directory managed by the camera itself). Only a factory reset truly resets the internal state.

### 3.4 ★ Investigation methodology (10 refuted hypotheses)

Ten hypotheses were tested and refuted on this single day. **All ten shared one root error: treating co-occurring phenomena as causation.**

| # | Hypothesis | What refuted it |
|---|---|---|
| 1 | slot 12 contains bad data | Still froze after resetting to neutral |
| 2 | `iqr` hi16 is the live PW value | Wrote 0 — completely unchanged (it's an ISP constant table) |
| 3 | Zero-byte thumbnails cause it | Deleted all 31 — still froze |
| 4 | `ipcc_ioctl` deadlock chain | Also blocked in the *healthy* state → it's normal |
| 5 | Applying a recipe triggers it | Froze with `PW_TYPE=STANDARD` (recipe not active) |
| 6 | Photo accumulation / memory leak | `MemFree` stable at 27 MB |
| 7 | A thread spinning in a busy loop | After fixing the measurement method, delta = **0** |
| 8 | `CAttributeHandler` is usable | Heap scan: zero hits → dead code |
| 9 | `iqr` hang is an early warning | The watchdog logged `ok` throughout; the criterion never fired |
| 10 | `400x82` is the size playback uses | After clearing the cache it generated **zero** of them |

**Two rules that would have prevented this:**

1. **Causality requires both** "A always implies B" **and** "removing A removes B". "A reboot clears it" only proves the state lives in memory — it says nothing about what that state is.
2. **When reproducing a symptom, decompose it orthogonally** — same action, different context. The decisive split (playback vs. non-playback) should have happened at 19:00; it actually happened at 22:10. The cost was six hours spent mining dead code inside the ISP layer.

### 3.5 Three recurring technical mistakes

1. **jiffies ÷ 100, not ÷ 4.** `utime` in `/proc/PID/stat` is in clock ticks (HZ=100). Getting this wrong caused a false positive on a thread wrongly identified as the culprit.
2. **`awk '{print $14}'` misaligns fields on `/proc/PID/task/TID/stat`** when `comm` contains spaces or parentheses (e.g. `SIF Main)`, `FileHandler)`). Strip first: `sed 's/.*) //' | awk '{print $11}'`.
3. **`dlsym` on an inherited C++ method needs the base-class name** (no `C` suffix): `_ZN17CCapVirtualAddrIf14GetVirtTopAddrEv` works, `...IfC14GetVirtTopAddrEv` returns NULL.

---

## 4. Tooling

All in `test_server/pwfilter/`.

### 4.1 PC-side analysers

| Tool | Purpose |
|---|---|
| **`symref.py <maps> <eip...>`** | Core: eip → which `.so` + offset within it + **symbol name** |
| **`pltscan.py <elf> [kw]`** | PLT/GOT mapping + call-site location (used to prove dead code) |
| `elfmap.py <elf> [eip...]` | ELF32 section layout + eip→file offset |
| `libscan.py <so> [kw]` | Section table + symbol filtering |
| `cxx.py <so> [kw]` | C++ class structure + demangling |
| **`arm2.py <so> <va> [n] [label]`** | ARM32 disassembler (proper bitfield decoding) |
| `enumscan.py` / `rodump.py` | `E_*` enum / `.rodata` string extraction |

### 4.2 Camera-side probes (`b1/src/`)

| Probe | Purpose |
|---|---|
| **`heapscan`** | Batch-reads `/proc/pid/mem` (3.4 MB in seconds) — the core dead-code tool |
| **`ispprobe`** | `dlopen` + `dlsym` to resolve runtime addresses; `SingletonI::getInstance()` verified working |
| **`lut3d_probe`** | 3D LUT / NOG control-chain probe (38 symbols + 9 register groups) |
| `memread` / `regscan` | `/dev/mem` access (blocked by `STRICT_DEVMEM` in practice) |

**Build rule**: `-target arm-linux-gnueabi.2.15 -O0 -mfloat-abi=soft` (`-O1` and above segfault on this toolchain); add `-ldl` when using `dlopen`.

### 4.3 Transport / remote execution

| Script | Note |
|---|---|
| `ftp_put.py` / `ftp_get.py` | Remote paths **must be prefixed with `/mnt/mmc/...`** (FTP root = SD card) |
| `telnet_run.py <ip> <cmd>` | **Must be run serially** (parallel connections wedge the single core). Never `killall busybox` — `telnetd`/`ftpd`/`httpd` are all busybox symlinks |

---

## 5. Paths Ruled Out

Shared to save the community from repeating them.

| Path | Wall encountered |
|---|---|
| 3D LUT register write | `/dev/mem` blocked by `CONFIG_STRICT_DEVMEM` |
| `capdtm setvar` direct PW write | `varlist` and `getvar/setvar` use **two different index spaces** |
| `iqr` direct write | It is the ISP firmware's **constant table**, independent of user settings |
| `adj_*` segments (6–10) write | **Read-only constants** — 5 write experiments confirmed write/read-back works but the ISP ignores them |
| Hijacking `CAttributeHandler` | **Dead code** (zero heap references) |
| Hijacking a GOT slot to reach 3D LUT | `di-camera-app` imports **zero** 3D LUT functions → no slot to patch |
| `poker` write to `.text` | Kernel read-only memory protection |

### One finding worth calling out separately

**3D LUT is initialised on demand:**

```
libudd5.so is loaded in 4 processes (deviced / enlightenment / di-camera-app / ap-setting-app)
but ep_3dlut_reg_base / ep_mc_reg_base / ep_top_reg_base are all 0
```

The camera does not use its 3D LUT by default. This is why the path is hard — and it is the first thing to investigate further.

---

## 6. `prefman` Control Surface (fully mapped)

```sh
prefman set                     # ★ live effect without save (milliseconds, zero eMMC writes)
prefman load -a 0               # ★★ NEVER add this — reloads from eMMC and OVERWRITES your value
prefman save_file {ID} <path>   # ★ actually writes to the given path (safe)
prefman fetch {ID} <path># ★★ ignores the path, writes into /opt/pref/pref_app.bin (corrupts it)
prefman info 0                  # 672 named entries
```

**PW block layout**: `addr(param i, style s) = 41964 + i*52 + s*4`, where `i=0..6` = R/G/B/HUE/SAT/SHARP/CONTRAST
**Neutral values**: R/G/B = 100, HUE/SAT/SHARP/CONTRAST = 10

**★ NX500-wide quirk**: indexes printed by any "list" command cannot be assumed valid for read/write commands. Always align in three steps: *read list → verify with read command → verify with write command*. (This was hit three separate times on `setusr`, `getvar`, and `varlist`.)

---

## 7. Next Steps

1. **Reinstall and verify FilmLab** — restore the 9 recipes to a working state
2. **Automate thumbnail cache filling** — `convert -resize 320x213!` on both required sizes, which removes the trigger for the firmware defect
3. **Probe 3D LUT activation conditions** — determine which camera settings cause `ep_3dlut_reg_base` to become non-zero (zero-risk, read-only)
4. **Register-level LUT write** — use the verified mmap channel to drive the LUT within the camera process context

---

## Acknowledgements

Thanks to the NX-KS community for `poker` (process memory read/write), `nx-remote-controller-daemon`, the `mod_gui` framework, and extensive documentation. None of the system-level findings above would have been possible without these tools.

---

## Licence

Scripts and documentation in this repository follow the original licence. **Please do not redistribute the reverse-engineering findings here for commercial firmware distribution.**
