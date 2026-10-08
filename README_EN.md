# NX-WA

An enhancement mod for the **Samsung NX500 / NX1** (Tizen / DRIMe5), built on the
community [`nx500_nx1_modding`](https://github.com/SamsungNX500/nx500_nx1_modding) upstream.

**This fork**: **[WApaperplane/nxwa](https://github.com/WApaperplane/nxwa)**
(renamed from the `nx500_nx1_modding` fork to **`nxwa`** on 2026-10-08 and authoritative from now on; the on-camera install path `/opt/usr/nx-ks/` is unchanged).

> 这是一个三星 NX500 / NX1 相机的增强 mod，基于社区上游工程改造与扩展。中文版见 [README.md](README.md)。

**Branches**: `master` = untouched upstream history (do not touch); **`nxwa` = this project's source (the branch this document lives on)**.

**License & attribution**: **AGPL-3.0** (derived from the community `nx500_nx1_modding` upstream, verified to be AGPL-3.0 itself) — upstream lineage table and the pre-release checklist live in [ATTRIBUTION.md](ATTRIBUTION.md).

## Highlights

- **FilmLab film recipes** — 18 film looks (negative / slide / B&W / cinema). On the camera: **`EV+AEL` → tap a recipe → pick "自定义1" in the Picture Wizard UI (3 steps)**; no Fn menu digging needed. The recipe library lives on the SD card (editable, extensible); the menu is generated automatically.  
  ★ Measured on-camera (2026-10-08): the previously documented "tap a recipe and it applies immediately (2 steps)" is **not reproducible**. Applying a recipe is three independent channels — **① storage (`prefman`) and ② selection (`setusr 20`)** only change *which* style is selected and **never reach the ISP's PW engine**; **③ parameters** are pushed by the app over its internal **attribute bus** (`CAttributeHandler::setPWColor… → set_attribute(0x10e/0x110/0x111/0x112)`), which the `st` command surface does **not** expose — so "one tap applies it" is architecturally impossible from a shell script.
  ★ You can now **verify objectively**: `sh /opt/usr/nx-ks/filmlab.sh check` reads the 7 values the ISP is actually using and compares them with the recipe slot (read-only, zero risk). Details: `docs/current/PW_PARAM_CHANNEL_2026-10-08.md`.
- **Web remote (`nx-rc`) photo gallery** — *collapsed directory model*: directories in reverse order, only the newest expanded by default, lazy loading + thumbnail cache. Fixes the first-paint stall on a single-core CPU when the SD card holds many directories.
- **Live directory source for the gallery** — the `dirlist` CGI on port 8080 does a real `readdir` on every request, so brand-new photos appear instantly (the port-80 daemon's list is a boot-time snapshot; new photos never show up there).
- **Thumbnail pre-warm** — enabling the remote spawns a background warmer (grid 320 px × newest 300 + lightbox 1024 px × newest 60, under `nice -n 19`, never disturbing shooting). The frontend shows progress; failed loads retry automatically.
- **IP + one-tap Telnet/FTP in the main menu** — regenerated on every open; the last row shows the current IP and Telnet state, one tap toggles it (replaces the `EV+WiFi` combo). No more repeated IP popups.
- **On-camera thumbnail CGI** — ImageMagick DCT resize + SD-card cache + `nice`-deprioritised, with frontend heartbeat debounce and concurrency limiting. Spurious "WiFi disconnected" states eliminated.
- **Port-8080 service cluster** (busybox httpd) — `thumb` (thumbnails) / `dirlist` (live directory) / `prewarm` (progress) / `push` (push the frontend over WiFi, no card pulling).
- **Shooting-parameter Web API** (`capdtm`); key-remap / bitrate / blackout and other original NX-KS modules preserved.
- **Brand-new sync pipeline** — the SD-card "smart installer" does an incremental sync on insertion (it never uninstalls by accident), plus over-the-air `push` over WiFi.

## Camera menu cheat-sheet

| Menu item                       | What it does                                                                          |
| ------------------------------- | ------------------------------------------------------------------------------------- |
| `IP: x.x.x.x [Telnet关]`        | Shows the current WiFi IP; **tap = toggle Telnet(23) + FTP(21)**, with popup feedback  |
| `远程控制` (checkbox)              | Toggles the web remote (port 80); also starts the port-8080 cluster and thumbnail warm-up |
| **`EV + AEL`** (key combo)      | ★ **FilmLab recipe menu**: tap a recipe to apply it instantly; press again = close. 【NX500 only】 |

The menu is regenerated every time it opens (`gen_menu.sh`), so the IP / Telnet state is always current.
PC-side troubleshooting: `test_server/telnet_run.py <camera-ip> 'command'` (non-interactive telnet, root, empty password).

## FilmLab recipes

> **Two steps to a look**: `EV + AEL` opens the recipe menu → tap a recipe → the image takes on that film look immediately.
> (No Fn menu detour; the old "pick PW → Slot9 → confirm" flow is completely gone.)

### The 18 built-in recipes

| Family         | Recipes (= menu order)                                                |
| -------------- | --------------------------------------------------------------------- |
| Colour negative | Portra 400 / Portra 800 / Gold 200 / UltraMax 400 / Superia 400 / Fuji 400H |
| Slide          | Velvia 50 / Provia 100F / Ektachrome / EK Cyan 冷调 / Kodachrome        |
| Black & white  | TriX 400 / HP5 Plus / Delta 3200 / MonoWarm 暖调 / MonoCool 冷调        |
| Cinema · FX    | Cine Teal / X-Pro 交叉                                                 |

- B&W recipes use `SAT=0` (true monochrome); **MonoWarm / MonoCool are the camera-unique warm / cool monochromes** (they keep a R/B gain difference).
- A recipe = a Picture-Wizard 7-dimensional vector (R/G/B gain + HUE / SAT / SHARP / CONTRAST), written to the UI's "Custom 1" slot — a fixed, predictable location.
- Colour recipes achieve their film cast via relative R/G/B gain differences plus saturation/contrast (more controllable than HUE).

### Adding / editing recipes (no code changes, no re-flash)

```
The recipe library lives on the SD card: /mnt/mmc/filmlab/recipes.json   <- the engine reads this
To add one: edit that JSON -> copy back to the SD card -> reopen the menu (it regenerates itself)
```

- Authoritative source table in the repo: `test_server/filmsim/recipes/nx500_recipes.txt`
  → `python test_server/filmsim/mk_recipes_json.py` generates `recipes.json`.
- One-shot deploy / menu refresh: `python test_server/filmsim/deploy_recipes.py a` → `… b <idx>`.

### Known limits (honest notes)

- `mod_gui` inherently exits on click: you cannot scroll-compare; to compare, tap two recipes in a row and watch the change.
- White balance is not part of a recipe: adjust WB in the camera UI (recipes only carry the colour look).
- A recipe is a **global colour vector** — no highlight roll-off, no zone-based exposure (same class as Recipe Lab).
- Recipes are **NX500-only** (the prefman offsets were only measured on NX500 1.12); on NX1, `EV+AEL` automatically falls back to the community long-recording script (`EV_AEL.community.sh`).
- Advanced (telnet): `filmlab.sh list` lists recipes / `dump` reads all slots / `reset` restores neutral / `cycle` advances to the next.

## Quick start

Put the following on the root of an SD card, insert it into the camera and it runs automatically
(the camera firmware trigger chain: `info.tg` → `nx_cs.adj` → runs `install.sh`).
After installation, enable Bluetooth in the settings to start initialisation:

```
info.tg  nx_cs.adj  install.sh   <- repo root (smart installer: not installed = full install, installed = incremental sync)
scripts/                          <- the whole directory (module masters, synced into the camera)
```

- Supported firmware: NX500 **1.12** / NX1 **1.41** (other versions are refused).
- **Re-inserting the card when already installed = incremental sync** — overwrite only, never delete, never uninstall; the SD `scripts/` masters are kept.
- To uninstall, use `uninstall.sh` from the camera menu.

## Daily updates: two paths

| Method                | Command / action                                                                 | When                              |
| --------------------- | -------------------------------------------------------------------------------- | --------------------------------- |
| SD smart installer    | Copy the latest `scripts/` + `info.tg`/`nx_cs.adj`/`install.sh` to the SD → insert | Big releases / new modules        |
| WiFi push             | `scripts/nx-rc/push/push.sh <camera-ip>`                                          | Web-frontend-only changes, no card pulling |

See [SYNC.md](SYNC.md) (bilingual install / sync / rollback guide).

## Layout

| Path                                | Description                                                                 |
| ----------------------------------- | --------------------------------------------------------------------------- |
| `install.sh` `info.tg` `nx_cs.adj`  | SD-root trigger trio (install / sync entry points)                          |
| `scripts/`                          | All module masters; sync target = the camera's `/opt/usr/nx-ks/`            |
| `scripts/filmlab.sh`                | ★ **FilmLab engine** (camera-side): recipe load / apply / menu generation    |
| `scripts/filmlab/recipes.json`      | Recipe-library seed: copied to the SD card `/mnt/mmc/filmlab/` on first install |
| `scripts/EV_AEL.sh`                 | FilmLab entry (`EV+AEL`); on NX1 it falls back to `EV_AEL.community.sh`      |
| `scripts/gui_filmlab*.NX500`        | FilmLab menus: `1b` = recipe main menu (default); `2/3/4` = preset slots / WB / diagnostics pages |
| `scripts/nx-rc/`                    | Web remote: `web_root/` (frontend), `thumb/` (thumbnails), `capdtm/` (parameter API), `push/` (WiFi sync) |
| `scripts/update_nxrc.sh`            | Camera-side incremental updater for the nx-rc module                        |
| `test_server/`                      | PC-side dev/verification environment (camera API mocks + Playwright cases)   |
| `test_server/filmsim/`              | FilmLab dev side: recipe source table `recipes/nx500_recipes.txt` + generators / deployers |
| `deploy/filmlab/`                   | Early FilmLab deployment artifacts (the `nxfilmui` native-UI experiments, kept for reference) |
| `backup_original/`                  | Factory backups (not committed)                                             |

## Docs

> ★ **Docs are partitioned by freshness**: `docs/current/` (authoritative) / `docs/archive/` (historical) / `docs/evidence/` (reverse-engineering evidence).
> Full index in [`docs/README.md`](docs/README.md). **2026-10-07 full cleanup**: outdated / wrong documents moved to `archive/` and 3 historical errors corrected.

**Current (★ start here)**

- [`docs/current/HANDOVER_2026-10-07.md`](docs/current/HANDOVER_2026-10-07.md) — ★★★ project handover: state / dead ends / verified / blocked / discipline / TODO
- [`docs/current/ERROR_CORRECTIONS_2026-10-07.md`](docs/current/ERROR_CORRECTIONS_2026-10-07.md) — ★★★★★ error-correction report: 9 corrections across mod / firmware / system (C1–C9)
- [`docs/current/FIRMWARE_BREAKTHROUGH_2026-10-07.md`](docs/current/FIRMWARE_BREAKTHROUGH_2026-10-07.md) — firmware-layer breakthrough: ISP parameter blocks solved / Magic-Lantern three paths assessed
- [`docs/current/P7_DISPATCH_AND_LSC_2026-10-07.md`](docs/current/P7_DISPATCH_AND_LSC_2026-10-07.md) — jump-table mechanism correction + lens-shading descriptor solved
- [`docs/current/STRATEGY_2026-10-07.md`](docs/current/STRATEGY_2026-10-07.md) — development strategy (final)
- [`docs/current/FEATURE_MATRIX_2026-10-07.md`](docs/current/FEATURE_MATRIX_2026-10-07.md) — feature matrix (final)
- [`docs/current/3DLUT_API_GUIDE.md`](docs/current/3DLUT_API_GUIDE.md) / [EN](docs/current/3DLUT_API_GUIDE_EN.md) — 3D LUT operation manual
- [`docs/current/3DLUT_DEEP_DIVE_2026-10-07.md`](docs/current/3DLUT_DEEP_DIVE_2026-10-07.md) / [EN](docs/current/3DLUT_DEEP_DIVE_2026-10-07_EN.md) — 3D LUT deep-dive dossier
- [`docs/current/P7_3DLUT_PATHS_2026-10-07.md`](docs/current/P7_3DLUT_PATHS_2026-10-07.md) — ★★★★★ all three C++ 3D-LUT paths decoded (RTTI + 3 vtables); ★ View and Still are independent ⇒ editing the View table does not affect photos
- [`docs/current/NATIVE_UI_DESIGN_2026-10-07.md`](docs/current/NATIVE_UI_DESIGN_2026-10-07.md) — native UI design: widget mapping / CJK decision / implementation order
- [`docs/current/CAMERA_MENU_ARCHITECTURE_2026-10-07.md`](docs/current/CAMERA_MENU_ARCHITECTURE_2026-10-07.md) — ★★★★★ camera system-menu rendering dossier (mod menu vs system menu; proof that **p7 has no menus**)
- [`docs/current/CAMERA_APP_STRUCTURE_2026-10-07.md`](docs/current/CAMERA_APP_STRUCTURE_2026-10-07.md) — ★★★★ the official app's structure (di-camera-app: 4 modules / Manager bus + State machine / 111 .so dependencies / on-device layout + 25 Edje themes)
- [`docs/current/ILAUNCHER_FIRMWARE_FLASH_2026-10-07.md`](docs/current/ILAUNCHER_FIRMWARE_FLASH_2026-10-07.md) — ★★★★★ iLauncher firmware-flash RE: proof it **does not flash the camera** (it only copies the firmware to the SD card, the camera self-updates)
- [`docs/current/RE_PROGRESS_2026-10-08.md`](docs/current/RE_PROGRESS_2026-10-08.md) — ★★★★★ **consolidated reverse-engineering progress** (this is the one-stop summary of everything below)
- [`docs/current/NX500_ARCHITECTURE.md`](docs/current/NX500_ARCHITECTURE.md) — full system architecture (incl. the complete EP register dump)
- [`SYNC.md`](SYNC.md) — install / incremental sync / WiFi push / rollback (bilingual)

**Archive (conclusions may be superseded)**

- [`docs/archive/`](docs/archive/) — 2026-10-05 / 10-06 stage reports; includes disproven conclusions (e.g. mod_gui "13 keys", p6/p13 "dual-boot kernels")

**Reverse-engineering evidence**

- [`docs/evidence/p7/`](docs/evidence/p7/) — key Ghidra fragments of the p7 firmware
- [`docs/evidence/discovery/`](docs/evidence/discovery/) — 3D-LUT discovery-phase scripts and intermediates

**Module docs**

- `scripts/nx-rc/thumb/README.md` — thumbnail module deployment (bilingual)
- `scripts/nx-rc/push/README.md` — WiFi push usage (bilingual)

---

## ★★ 3D LUT / EP path (2026-10-06 on-device breakthrough)

★ **Userspace 3D-LUT register writes are live on a real camera**: after the write the image visibly changes (confirmed by eye on the camera).

### Fully solved

| # | Capability                     | Verification                                                    |
| - | ------------------------------ | --------------------------------------------------------------- |
| 1 | Authoritative physical addresses of the 10 EP blocks | `ioctl(fd, _IOR('h',100,...))` → **10/10 match earlier measurement** |
| 2 | EP register read/write         | `mmap(phys, PROT_WRITE, /dev/drime5_ep)`                        |
| 3 | CMA memory read/write          | `mmap(phys, PROT_WRITE, /dev/d5_sma)`                           |
| 4 | p7's authoritative 6-step write sequence | Reproduced → **the image really changed**               |

### Authoritative 3D-LUT register definitions (p7 firmware)

```
+0x000 bit0      OnOff master switch   FUN_004cf3d4
+0x004 bits[1:0] SelCbCr               FUN_004cf3fc
+0x004 bits[5:4] SelLUT channel        FUN_004cf414
+0x004 bit8      LUT0 data source      FUN_004cf42c
+0x004 bit12     LUT1 data source      FUN_004cf444
+0x008 bit0      write-start pulse ★   FUN_004cf45c
+0x008 bit8/bit4 read-side cleanup     FUN_004cf484
+0x00c           LUT0 data address     FUN_004cf4b4
+0x010           LUT1 data address
```

★ **The complete 6-step sequence — not one step may be skipped** (miss ② or ⑥ and nothing at all happens):

```c
b[0x000] |= 1;  b[0x008] &= ~1UL;  b[0x008] |= 1UL;
b[0x00c] = lut_phys;  b[0x004] &= 0xffffffcfUL;  b[0x008] &= ~0x100UL;
```

★ Objective success criterion: **after the sequence, `+0x008` stays at 1 = hardware accepted the start.**
★ Hard constraint: **the LUT physical address must be 256-byte aligned** (`(addr & 0xff) == 0`).

### ★ Samsung's four built-in LUT profiles (contents already read out)

| Buffer       | Character    | Profile                  |
| ------------ | ------------ | ------------------------ |
| `0x81101e00` | perfectly linear | ★ pure identity      |
| `0x81115200` | R↑ G↓        | ★ warm tone / skin       |
| `0x810fd100` | non-monotonic | stylised curves         |
| `0x81106b00` | same as #1   | (same)                   |

LUT format = **17³ 3D LUT, 16-bit × 3 channels interleaved** (R increments from `0x0001`, G/B step down in sync).

### ⇒★★ The final Magic-Lantern path: patch the P7 firmware

★ Those four LUT buffers live at `0x81xxxxxx`, **above Linux's `mem=512M`, and the p7 page table only covers `0x80000000..0x80ffffff`** ⇒ **Linux userspace can never read or write them.**
⇒ This is not "the writer is in p7"; it is "**the LUT data buffers themselves live in p7's address space**".
⇒ ★ Entry point locked: `FUN_0009a3e8` (where one of four constants is chosen and returned).

### ★★ Zero-risk, available today: 4-profile colour switching

★ **No firmware patch needed** — write one of `0x810fd100` / `0x81106b00` / `0x81115200` / `0x81101e00` into 3DLUT's `+0x0c` to switch among the four built-in profiles.

**Docs**

- [`docs/archive/WORK_REPORT_2026-10-06.md`](docs/archive/WORK_REPORT_2026-10-06.md) / [EN](docs/archive/WORK_REPORT_2026-10-06_EN.md) — the day's work report (breakthrough process + 7 self-corrections + 9 iron rules)
- [`docs/archive/_2026-10-06_purged/EP_3DLUT_WRITE_EXPERIMENTS_2026-10-06.md`](docs/archive/_2026-10-06_purged/EP_3DLUT_WRITE_EXPERIMENTS_2026-10-06.md) — all 11 write experiments (some conclusions corrected on 10-07)
- [`docs/archive/EP_PATH_OPEN_2026-10-06.md`](docs/archive/EP_PATH_OPEN_2026-10-06.md) — kernel ioctl + mmap path
- [`docs/archive/LIBUDD5_EP_API_MAP_2026-10-06.md`](docs/archive/LIBUDD5_EP_API_MAP_2026-10-06.md) / [EN](docs/archive/LIBUDD5_EP_API_MAP_2026-10-06_EN.md) — libudd5 API map

**Summary**

Verified on a real NX500: **userspace 3D-LUT register writes work and visibly change the image.**
All 10 EP block addresses come authoritatively from the kernel
(`ioctl(fd, _IOR('h',100,...))`, 10/10 matching earlier `/dev/mem` measurements), and the
6-step write sequence was reproduced from the P7 firmware's own decompilation — steps ② and ⑥
(clear the pulse bit, clear the read-side flag) were why the first five attempts did nothing.
**Objective success criterion: after the sequence, `+0x008` stays at 1** (the hardware accepted the start).

Then the decisive finding: P7 holds **four preset LUT buffers**
(`0x810fd100` / `0x81106b00` / `0x81115200` / `0x81101e00`) which read out as Samsung's four
built-in colour profiles (identity / warm-skin / stylised curves), format = **17³ 3D LUT,
16-bit × 3 channels interleaved**. Those addresses sit above the Linux 512 MB limit and outside
the P7 page table, so **Linux userspace can never read or write them** ⇒ Magic Lantern must
patch P7 — not because "the writer is in P7", but because **the LUT buffers themselves live in
P7's address space**.

★ **Shippable today with zero risk**: writing one of those four addresses into 3DLUT's `+0x00c`
switches between the four built-in profiles — no firmware patch required.

**Tools** (`test_server/isp/` + `test_server/sysarch/`)

- `udd5.py` — in-house ELF + Capstone disassembler (cross-validated with pyelftools 16/16)
- `regmap.py` — automatic EP-register offset extraction · `crosscheck.py` — cross-verification
- `epinfo` / `epdump2` / `epwr` / `eplut10` / `rd` — read-only and write probes (ARM)

---

## ★ Reverse-engineering highlights

On 2026-10-05 three framework-level judgements were overturned by measurement (plus the 10-06 corrections above):

| Earlier judgement              | Measured conclusion                                                                 |
| ------------------------------ | ----------------------------------------------------------------------------------- |
| `d5_ipcc` is the main cross-core channel | ❌ **empty shell**: ioctl returns 0 but never fills anything; `size=8` encoding SIGILLs outright |
| The two cores are isolated, no communication | ❌ `drime5_ep` has fired its interrupt **1.49 million times**; `d5_sma` has a 144 MB shared region @ `0x94000000` |
| The 3D-LUT hardware is uninitialised | ❌ **OnOff measured = 1 (it is on)**; and **register writes were verified on-device to change the image** |
| The handle wall is unbreakable | ⚠️ only for the vendor library. Direct `mmap` of the hardware **bypasses the handle** (**both read and write measured**) |

> ★★ **Major 10-06 correction**: the earlier "**never write EP registers** / you can only pull the battery"
> **has been disproven by measurement**. The truth:
>
> - The EP blocks are a pure mmap device on `/dev/drime5_ep`; `open` performs **zero hardware initialisation** (proven from source)
> - Following p7's 6-step sequence, the image **visibly changed** (confirmed by eye)
> - The risk is far lower than feared: **the LUT is soft state; it recovers automatically after a touch or a focus**
> - ⚠️ But "userspace writing LUT **data**" is impossible — the buffers live in p7's address space (see above)

> Film-simulation exploration (recipe + .cube LUT + capdtm ISP) lives in a separate repo:
> [nx500-filmsim](https://github.com/WApaperplane/nx500-filmsim).

**Been down a dead end already?** See **§7 methodology iron rules** and **§9.3 excluded paths** of the consolidated report
(9 disproven routes + 13 hardware/cross-compilation constraints — all of them easy ways to waste hours).
