# NX500 Film Simulation Module + ISP Internals — Progress Report

> Ready-to-post text for international communities (HN, Reddit, Discord, GitHub Issues).
> The Chinese versions live in `DEVELOPMENT_REPORT_2026-10-05.md` and `FORUM_POST.md`.

---

## Long version (GitHub Issues, technical forums)

### NX500 FilmLab + System-Level RE Report

**TL;DR**
- Shipped **FilmLab**, a working film-simulation module: 9 recipes, one-tap switching, body-button UI — all verified on real hardware
- Extracted key NX500 ISP internals: a physical→virtual address formula and the complete userspace control chain for **3D LUT** and **hardware grain (NOG)**
- Debugged a "camera freezes when entering playback" fault — **it's a defect in Samsung's own 1.12 firmware**, unrelated to the module
- Included a **pitfall list** (7 refuted paths + 6 measured hardware constraints) that may save others days

---

### 1. FilmLab (complete)

**Architecture**
```
SD card recipes.json  →  mkgui generates dynamic menu  →  mod_gui one tap
  →  filmlab.sh apply  →  prefman set ×7 + setusr 20  →  ISP updates live (~2 s)
```

**Key design decisions**

1. **Always write slot 9 (UI "Custom 1").** The original version rotated across slots — but then users couldn't tell which slot held the recipe, which defeats the point of one-tap switching. Pinning to a single slot means the camera UI always shows "Custom 1"; one press changes the viewfinder instantly.
2. **Recipes live on the SD card, not in the camera.** Adding one = editing a JSON file. Zero menu changes, no reflash, unbounded count.
3. **Recipe cycling bound to the S1 body key**, hooking into the community's existing `EV_*.sh` mechanism (original saved as `.orig`).

**The 9 recipes**: `portra400` `velvia50` `trix400` `ektachrome` `hp5` `superia400` `monowarm` `ektachrome_cyan` `cine_teal`

`monowarm` is unique to the camera's own pipeline: `SAT=0` (true monochrome) while retaining an R/B gain differential — a warm-toned black-and-white. A PC-side matrix engine cannot produce this.

**★ Explicit capability boundary**: the 7 PW dimensions are a *global vector applied identically to every pixel* (R/G/B gain + HUE/SAT/SHARP/CONTRAST). This achieves film-style colour rendition, colour casts, and contrast shaping. It does **not** achieve true tone curves, brightness-zone separation, or film grain. For reference, `voxivoid/recipe-lab-sony-pmca` (a comparable Sony-era project) produces 77 recipes from 26 one-byte slots, so this module reaches comparable control granularity.

---

### 2. System-level findings (directly usable)

**① Physical → virtual address mapping**
```c
virt_of_phys(p) = p - 0xB7FC000;
```
Two independent samples agree exactly, and the second result lands inside the ISP register window from `/proc/<pid>/maps`. With this, any hardware register address can be computed.

**② Complete userspace control chain for 3D LUT and hardware grain**

`libudd5.so` ships **fully unstripped** — 388 symbols with real names:
```c
d5_ep_3dl_load_lut(handle, mode, table, data)   // dual table: Cb / Cr select independently
_udd_ep_3dl_reg_SetReg / SetAddress / rw_Start / SelLUT / SelCbCr_ch
_udd_ep_nog_set_std_sigma  /  _udd_ep_nog_set_gamma  /  _udd_ep_nog_select_rv_type
```
**Measured:** `d5_ep_open()` allocates all 9 EP register groups from an independent process, yielding *real* page-aligned virtual addresses. The library opens its own device node and mmaps the hardware — a legitimate channel around the `/dev/mem` `CONFIG_STRICT_DEVMEM` restriction.

**③ A dead-code elimination (saved hours)**

`libcapture-fw-prod.so` has 1,835 unstripped symbols, and its `CAttributeHandler` class exposes 324 methods — including the most enticing find of the project: `setPWBracket(char, char)`, a genuine shadow/highlight curve control. A full heap scan returned **zero hits**. The runtime never calls it.

> ★ **The most transferable methodology lesson here:** a library showing up in `/proc/<pid>/maps` proves it was *loaded*, not that it is *called*. The correct test is to scan the target process's memory for the library's key function addresses and check whether anything references them. **Do this before deep analysis** — skipping it cost hours here. I wrote `heapscan` (reads `/proc/pid/mem` directly, 3.4 MB in seconds) to make this cheap.

**④ Measured hardware constraints (kernel 3.5)**

| Item | Result |
|---|---|
| `/dev/mem` register access | ✗ `CONFIG_STRICT_DEVMEM` |
| `poker` write to `.text` | ✗ kernel read-only memory protection |
| `poker` write to `.data` | ✓ works |
| **CPU NX bit** | **absent** (ARMv7 → code in `.data` is executable) |
| Root filesystem | ext4 **read-only** |
| CPU | ARMv7 rev 1 (v7l), Exynos, NEON |
| Memory | CMA statically reserved 360 MiB → only ~142 MB actually usable |

---

### 3. Fault investigation: "freezes when entering playback"

**Symptom**: after entering playback, *only the delete key hangs*. All other keys respond, the shutter works, the display is normal. The power dial cannot shut down; only pulling the battery recovers.

**Conclusion: a defect in Samsung's 1.12 firmware — independent of the module, the SD card, and file state.**

| Experiment | Result |
|---|---|
| Roll the module back to its earliest version | Still reproduces |
| Format the SD card | Still reproduces |
| Brand-new empty card (zero files, zero module) | Still reproduces |
| **Factory reset** | **Gone** |

**Mechanism**: corrupted state under `.thumbcache` → the `ImageGenerator` thread enters an invalid state on entering playback → the whole system wedges (even SD-card log writes stop) → uninterruptible wait.

**Why formatting didn't help**: formatting clears `DCIM/` and the root, but **not** `/mnt/mmc/.thumbcache/` — a hidden directory the camera manages itself. Only a factory reset truly resets internal state.

**★ If you hit something similar: do a factory reset first, not mod surgery or an SD card swap.**

---

### 4. Ten refuted hypotheses (the real lesson of that day)

All ten shared one root error: **treating co-occurring phenomena as causation**.

| # | Hypothesis | What refuted it |
|---|---|---|
| 1 | Dirty data in slot 12 | Still froze after resetting all slots to neutral |
| 2 | `iqr` hi16 is the live PW value | Wrote 0 — unchanged (it is an ISP constant table) |
| 3 | Zero-byte thumbnails | Deleted all 31 — still froze |
| 4 | `ipcc_ioctl` deadlock chain | Also blocked in the **healthy** state → normal condition |
| 5 | Applying a recipe triggers it | Froze with `PW_TYPE=STANDARD` (recipe inactive) |
| 6 | Photo accumulation / memory leak | `MemFree` stable at 27 MB |
| 7 | A thread spinning in a busy loop | After fixing two measurement bugs, delta = **0** |
| 8 | `CAttributeHandler` is usable | Heap scan: zero hits → dead code |
| 9 | An `iqr` hang precedes the freeze | Watchdog logged `ok` throughout; criterion never fired |
| 10 | `400x82` is the size playback uses | After clearing the cache, zero were generated |

**Two rules:**
1. **Causality requires both** "A always implies B" **and** "removing A removes B". "A reboot clears it" only proves the state lives in memory, not what that state is.
2. **When reproducing a symptom, decompose it orthogonally** — same action, different context. The decisive split (playback vs. not) should have happened at 19:00; it happened at 22:10. Cost: six hours mining dead code.

**Three technical mistakes worth avoiding:**
- **jiffies ÷ 100, not ÷ 4** — `utime` in `/proc/PID/stat` is clock ticks (HZ=100). Getting this wrong caused a false accusation.
- `awk '{print $14}'` **misaligns fields** on `/proc/PID/task/TID/stat` when `comm` contains spaces or parens (`SIF Main)`) → strip with `sed 's/.*) //'` first.
- **C++ inheritance: `dlsym` needs the base-class name** (no `C` suffix).

---

### 5. Pitfall list

**Refuted paths — don't repeat these:**

| Path | Wall |
|---|---|
| 3D LUT register write | `/dev/mem` blocked by `CONFIG_STRICT_DEVMEM` |
| `capdtm setvar` direct PW write | `varlist` and `getvar/setvar` use **two different index spaces** |
| `iqr` direct write | It is the ISP firmware's **constant table**, independent of user settings |
| `adj_*` segments (6–10) write | **Read-only constants** (confirmed by 5 write experiments) |
| Hijacking `CAttributeHandler` | **Dead code** (zero heap references) |
| Hijacking a GOT slot to reach 3D LUT | `di-camera-app` imports **zero** 3D LUT functions → no slot exists |
| `poker` write to `.text` | Kernel read-only memory protection |

**★ 3D LUT is initialised on demand.** `libudd5.so` is mapped in four processes, yet `ep_3dlut_reg_base` / `ep_mc_reg_base` / `ep_top_reg_base` are all `0`. The camera does not use its 3D LUT by default — which is both why it's hard to reach and the first thing worth investigating.

**NX500-wide quirk**: indexes printed by any "list" command cannot be assumed valid for read/write commands. Always align in three steps — *read list → verify with the read command → verify with the write command*. I hit this three times in one day.

**`prefman` specifics**:
- `set` takes effect immediately without `save` (milliseconds, zero eMMC writes)
- **Never add `load -a 0`** — it reloads from eMMC and overwrites your value
- **`fetch` corrupts `/opt/pref/pref_app.bin`** (it ignores the path you give it) — use `save_file`

**Operational trap**: `killall -q busybox` **kills your own telnet/ftp**, because `telnetd`, `ftpd`, and `httpd` are all busybox symlinks. Enumerate `/proc/*/cmdline` and match precisely.

---

### 6. Tooling (open-sourced in the repo)

| Tool | Purpose |
|---|---|
| **`heapscan`** | Batch-reads `/proc/pid/mem` — **the dead-code tool** |
| **`symref.py`** | eip → which `.so` + symbol name |
| **`pltscan.py`** | PLT/GOT mapping + call-site location |
| **`arm2.py`** | ARM32 disassembler (proper bitfield decoding) |
| `elfmap.py` / `libscan.py` / `cxx.py` / `rodump.py` | ELF analysis suite |

**Build rule for camera-side probes**: `-target arm-linux-gnueabi.2.15 -O0 -mfloat-abi=soft` (`-O1`+ segfaults on this toolchain).

---

### Full documentation

- [`DEVELOPMENT_REPORT_EN.md`](DEVELOPMENT_REPORT_EN.md) — full report
- [`SYSTEM_LAYER_FINDINGS_EN.md`](SYSTEM_LAYER_FINDINGS_EN.md) — all technical details, 12 sections

**Questions especially welcome:**
1. What camera setting or mode causes NX500 to initialise its 3D LUT?
2. What is the message format for `/dev/d5_ipcc` when driving the EP framework?

Either answer would unlock a large amount of capability.

---
---

## Short version (Twitter / Mastodon / Bluesky)

**NX500 film-simulation module + ISP reverse engineering**

✅ FilmLab shipped: 9 recipes, one-tap switching, body-button UI — verified on hardware
🔍 Extracted ISP internals: `virt = phys - 0xB7FC000`, full 3D LUT + hardware-grain control chain
🐛 Debugged "freezes on entering playback" — **a defect in Samsung's 1.12 firmware**, not the module

**The most valuable takeaway:** `maps` listing a library ≠ it's being called. To find dead code, scan the target process memory for the library's key function addresses. I wrote `heapscan` (3.4 MB in seconds) and it saved hours.

Pitfall list included: 7 refuted paths, 6 hardware constraints, 3 technical traps (jiffies ÷ 100 not ÷ 4; `/proc/PID/task/*/stat` field misalignment; `dlsym` needs base-class names on C++ inheritance).

Docs: https://github.com/WApaperplane/nx500_nx1_modding/tree/nx-ks2/docs

---
---

## Two-paragraph version (Discord / Slack intro)

Been doing a film-simulation mod for the NX500. The module (**FilmLab**) is working — 9 recipes, one-tap switching via the body buttons, ~2 s to apply. It's built on the camera's 7-dimensional Picture-Width parameters (RGB gain + HUE/SAT/SHARP/CONTRAST), which is enough for film-style colour rendition but not for true tone curves or grain.

Along the way I dug into the ISP layer and pulled out a few things that seem generally useful: a physical→virtual address formula (`virt = phys - 0xB7FC000`, verified on two samples), the complete userspace control chain for 3D LUT and hardware grain (the library ships unstripped), and a hard constraint set (`/dev/mem` is blocked, `.text` is kernel-protected, but there's no NX bit so `.data` is executable). I also spent a day chasing a "freezes in playback" bug that turned out to be **Samsung's own firmware** — format the card and it persists, factory reset and it's gone.

Worth knowing if you touch this platform: `maps` showing a library doesn't mean it's called. Scan process memory for the library's function addresses first — I lost hours to a 324-method class that was entirely dead code.
