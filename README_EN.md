# NX-WA

An enhancement mod for the **Samsung NX500 / NX1** (Tizen / DRIMe5), built on the community
[`ottokiksmaler/nx500_nx1_modding`](https://github.com/ottokiksmaler/nx500_nx1_modding) upstream.

> 这是一个三星 NX500 / NX1 相机的增强 mod，基于社区上游工程改造与扩展。中文版见 [README.md](README.md)。

**Repository**: **[WApaperplane/NXWA-nx500_modding](https://github.com/WApaperplane/NXWA-nx500_modding)**
(a fork of the community upstream; the old URL `WApaperplane/nx500_nx1_modding` still redirects. The on-camera install path `/opt/usr/nx-ks/` is unchanged.)

**Branches**: `master` = untouched upstream history (do not touch); **`nxwa` = this project's source (the branch this document lives on, also the default branch)**.

**License & attribution**: **AGPL-3.0** (derived from the community upstream, verified to be AGPL-3.0 itself) — upstream lineage table and the pre-release checklist live in [ATTRIBUTION.md](ATTRIBUTION.md).

**Releases**: see [Releases](https://github.com/WApaperplane/NXWA-nx500_modding/releases) (including the SD-card install-package zip).

---

## Highlights

- **FilmLab film recipes (68)** — negative / slide / B&W / cinema / stylised, five families, auto-generated 4-page menu. The recipe library lives on the SD card (editable, extensible).
- **PW direct push (three dimensions take effect instantly)**: `EV+AEL` → tap a recipe ⇒ **SAT / SHARP / CONTRAST are pushed straight into the ISP and the image changes within a second** (`pwsend.arm`, full 32-bit encoding, verified on-camera).
  ★ Honest limit: **all 7 dimensions (incl. R/G/B/HUE) have no external path** — p7's id normaliser only accepts `0x100–0x12e` and rejects `0x130–0x133` outright (on-camera negative result + static mechanism proof). For all 7, either confirm "Custom 1" once in the camera's Picture Wizard, or patch p7 (blocked by G4).
- **Objective criterion**: `sh /opt/usr/nx-ks/filmlab.sh check` reads the 7 values the ISP is *actually* using and compares them with the recipe slot (read-only, zero risk) — **"the value changed" ≠ "the value is consumed"**, and that rule underpins the whole project.
- **3D LUT pipeline** — any `.cube` → native table → preview direct-load (LUT1 + `lutsentinel` guard); `.cube ⇄ native table` converters included.
- **Web remote (`nx-rc`) photo gallery** — *collapsed directory model*: directories in reverse order, only the newest expanded by default, lazy loading + thumbnail cache. Fixes the first-paint stall on a single-core CPU when the SD card holds many directories.
- **Live directory source for the gallery** — the `dirlist` CGI on port 8080 does a real `readdir` on every request, so brand-new photos appear instantly (the port-80 daemon's list is a boot-time snapshot; new photos never show up there).
- **Thumbnail pre-warm** — enabling the remote spawns a background warmer (grid 320 px × newest 300 + lightbox 1024 px × newest 60, under `nice -n 19`, never disturbing shooting). The frontend shows progress; failed loads retry automatically.
- **IP + one-tap Telnet/FTP in the main menu** — regenerated on every open; the last row shows the current IP and Telnet state, one tap toggles it (replaces the `EV+WiFi` combo). No more repeated IP popups.
- **On-camera thumbnail CGI** — ImageMagick DCT resize + SD-card cache + `nice`-deprioritised, with frontend heartbeat debounce and concurrency limiting. Spurious "WiFi disconnected" states eliminated.
- **Port-8080 service cluster** (busybox httpd) — `thumb` (thumbnails) / `dirlist` (live directory) / `prewarm` (progress) / `push` (push the frontend over WiFi, no card pulling).
- **Shooting-parameter Web API** (`capdtm`); key-remap / bitrate / blackout and other original NX-KS modules preserved.
- **Brand-new sync pipeline** — the SD-card "smart installer" does an incremental sync on insertion (it never uninstalls by accident), plus over-the-air `push` over WiFi.

## Camera menu cheat-sheet

| Menu item | What it does |
| --- | --- |
| `IP: x.x.x.x [Telnet关]` | Shows the current WiFi IP; **tap = toggle Telnet(23) + FTP(21)**, with popup feedback |
| `远程控制` (checkbox) | Toggles the web remote (port 80); also starts the port-8080 cluster and thumbnail warm-up |
| **`EV + AEL`** (key combo) | ★ **FilmLab recipe menu** (4 pages / 22 items per page): tap a recipe → write slot + select slot + **three-dimension direct push**; press again = close. 【NX500 only】 |

The menu is regenerated every time it opens (`gen_menu.sh`), so the IP / Telnet state is always current.
PC-side troubleshooting: `test_server/telnet_run.py <camera-ip> 'command'` (non-interactive telnet, root, empty password).

## FilmLab recipes

> **The actual flow (since 2026-10-09)**: `EV + AEL` opens the recipe menu → tap a recipe
> → `apply` performs **① write slot (prefman slot9), ② select slot (setusr), ③ PW three-dimension direct push** (`FILMLAB_PW=1`).
> Step ③ makes the image change within a second; **R/G/B/HUE** cannot be pushed from a shell because p7's normaliser rejects them,
> so confirm once in the camera's **Picture Wizard → "Custom 1"** (that step moves all 7 dimensions into the ISP).

### The 68 built-in recipes (4-page menu)

| Family | Examples (68 total) |
| --- | --- |
| Colour negative | Portra 400/800/160 · Gold 100/200/400 · Ektar 100 · UltraMax 400 · Superia 200/400 · ColorPlus 200 · ProImage 100 · Fuji C200/400H/9000 · Vista 200/400 · Lomo 100/800 · Reala 100 · Solaris 100 |
| Slide | Velvia 50/50 风光/100/100F · Provia 100F/400X/1600 · Sensia 100 · Astia 100F · Ektachrome · Ektachrome E100 · EliteChrome 100 · Kodachrome · EK Cyan 冷调 |
| Black & white | TriX 400 · TriX 400 推档 · HP5 Plus · HP5 推1600 · Delta 100/3200 · T-MAX 100/400 · Acros 100 · FP4 Plus · Pan F Plus 50 · Neopan 100 · Kentmere 400 · XP2 Super · MonoWarm 暖调 · MonoCool 冷调 |
| Cinema | CineStill 800T / 50D · Vision3 250D / 500T · Double-X 5222 · Cine Teal |
| Stylised | 青橙 · 暖旧 · 冷峻 · 褪色 · 高调 · 低调 · 棕褐 · 漂白 · 蓝调时刻 · X-Pro 交叉 |

- B&W recipes use `SAT=0` (true monochrome); **MonoWarm / MonoCool are the warm / cool monochromes** (they keep a R/B gain difference).
- A recipe = a Picture-Wizard 7-dimensional vector (R/G/B gain + HUE / SAT / SHARP / CONTRAST), written to the UI's "Custom 1" slot — a fixed, predictable location.
- Colour recipes achieve their film cast via relative R/G/B gain differences plus saturation/contrast (more controllable than HUE).

### Adding / editing recipes (no code changes, no re-flash)

```
The authoritative recipe library (read directly by the engine): /mnt/mmc/filmlab/recipes.json
To add one: edit that JSON -> copy back to the SD card -> reopen the menu (it regenerates itself)
```

- Authoritative source in the repo: **`scripts/filmlab/recipes.json`** (68 recipes; `flab.py`'s `add/edit/rm/lint/conf/deploy` all work on it).
- One-shot deploy: `python test_server/filmlab/flab.py add …` → `lint` → `deploy` (push JSON + rebuild menu + verify readback).
- Offline regression (no camera needed): `sh test_server/filmlab/flab_sim.sh` (12 assertions).
- ⚠️ `test_server/filmsim/recipes/nx500_recipes.txt` is the **early 18-recipe table**, now stale — kept for history only. Do **not** treat it as the authoritative source.

### Known limits (honest notes)

- `mod_gui` inherently exits on click: you cannot scroll-compare; to compare, tap two recipes in a row and watch the change.
- **All 7 dimensions are not one-tap**: `R/G/B/HUE` require a Picture-Wizard confirmation on the camera body (reason above). This is a structural limit of the p7 firmware, not a script bug.
- White balance is not part of a recipe: adjust WB in the camera UI.
- A recipe is a **global colour vector** — no highlight roll-off, no zone-based exposure.
- Recipes are **NX500-only** (the prefman offsets were only measured on NX500 1.12); on NX1, `EV+AEL` automatically falls back to the community long-recording script (`EV_AEL.community.sh`).
- Advanced (telnet): `filmlab.sh list` / `dump` / `reset` / `cycle`.

## 3D LUT pipeline

| Capability | Status |
| --- | --- |
| Table format | Solved: `4913×4B {R,G,B,pad}`, index `((B*17+G)*17+R)*4`, slot stride `0x4D00`, 17 evenly spaced levels |
| Import | `.cube ⇄ native table` both ways (`test_server/isp/nx3dlut.py`, `test_server/lutpipe/deploy_luts.py`) |
| Preview | `lutpipe/lutpick.sh apply` — landing-spot probe → safety gate (`cmasafe`, 4 checks) → `lutapi load`; the viewfinder changes within a second |
| Survival | ★ **Write-to-take-effect law**: the write only lands when p7 is in the "reclaimed" state, and the shutter always triggers a reclaim ⇒ `lutsentinel.arm` guard + dual-channel isolation (table goes to LUT1, p7 only touches LUT0) |
| Stills | ★ **Established rule: preview = direct load (LUT1 + guard) / stills = post-processing (ksfilm)**. "Direct-load into stills" is a proven dead end (the capture flow actively reconfigures the LUT slot pool) |

## Quick start

Put the following on the root of an SD card, insert it into the camera and it runs automatically
(the camera firmware trigger chain: `info.tg` → `nx_cs.adj` → runs `install.sh`).
After installation, enable Bluetooth in the settings to start initialisation:

```
info.tg  nx_cs.adj  install.sh   <- repo root (smart installer: not installed = full install, installed = incremental sync)
scripts/                          <- the whole directory (module masters, synced into the camera)
```

- Supported firmware: NX500 **1.12** / NX1 **1.41** (other versions are refused).
- **Re-inserting the card when already installed = incremental sync** — overwrite only, never delete, never uninstall.
- To uninstall, use `uninstall.sh` from the camera menu.
- ★ **One-file package**: `NX-WA-<version>.zip` (see Releases) contains exactly the above — unzip to the SD-card root.

## Daily updates: two paths

| Method | Command / action | When |
| --- | --- | --- |
| SD smart installer | Copy the latest `scripts/` + `info.tg`/`nx_cs.adj`/`install.sh` to the SD → insert | Big releases / new modules |
| WiFi push | `scripts/nx-rc/push/push.sh <camera-ip>` | Web-frontend-only changes, no card pulling |

See [SYNC.md](SYNC.md) (bilingual install / sync / rollback guide).

## Layout

| Path | Description |
| --- | --- |
| `install.sh` `info.tg` `nx_cs.adj` | SD-root trigger trio (install / sync entry points) |
| `scripts/` | All module masters; sync target = the camera's `/opt/usr/nx-ks/` |
| `scripts/filmlab.sh` | ★ **FilmLab engine** (camera-side): recipes / apply / menu generation / `apply --fast` |
| `scripts/filmlab/recipes.json` | ★ **Authoritative recipe library** (68; copied to the SD card `/mnt/mmc/filmlab/` on first install) |
| `scripts/EV_AEL.sh` | FilmLab entry (`EV+AEL`); on NX1 falls back to `EV_AEL.community.sh` |
| `scripts/gui_filmlab*.NX500` | FilmLab menus: `1b` = recipe main menu (default); `2/3/4` = preset slots / WB / diagnostics |
| `scripts/nx-rc/` | Web remote: `web_root/`, `thumb/`, `capdtm/`, `push/` |
| `test_server/` | PC-side dev/verification environment (camera API mocks, toolchain, gates) |
| `test_server/pwsend/` | ★ PW direct-push tools (`pwsend.arm` / `pwcalib.sh` / `gen_pwpush.py`) + on-camera runbook |
| `test_server/lutpipe/` `test_server/isp/` | LUT deploy/guard tools and `.cube ⇄ native table` converters |
| `test_server/u6/` `test_server/u1/` | On-camera experiment packs and runbooks |
| `deploy/filmlab/` | Early FilmLab deployment artifacts (the `nxfilmui` native-UI experiments, kept for reference) |
| `uninstall_pkg/` | Camera-menu uninstall entry (manual confirmation) |

## Docs

> ★ **Docs are partitioned by freshness**: `docs/current/` (authoritative) / `docs/archive/` (historical) / `docs/evidence/` (RE evidence).
> Full index in [`docs/README.md`](docs/README.md).

**Current (★ start here)**

- [`docs/current/TASKFLOW_2026-10-10.md`](docs/current/TASKFLOW_2026-10-10.md) — ★★★★★ **current execution order** (offline P1–P7 / on-camera W-1→W-2→W-3 / post-gate A)
- [`docs/current/RE_PROGRESS_2026-10-08.md`](docs/current/RE_PROGRESS_2026-10-08.md) — ★★★★★ consolidated RE progress
- [`docs/current/HANDOVER_2026-10-07.md`](docs/current/HANDOVER_2026-10-07.md) / [`ERROR_CORRECTIONS_2026-10-07.md`](docs/current/ERROR_CORRECTIONS_2026-10-07.md) — handover / historical corrections C1–C9
- [`docs/current/PW_PARAM_CHANNEL_2026-10-08.md`](docs/current/PW_PARAM_CHANNEL_2026-10-08.md) — ★★★★★ PW three-channel on-camera verdict
- [`docs/current/PW_ID_MAP_FULL_2026-10-10.md`](docs/current/PW_ID_MAP_FULL_2026-10-10.md) — ★★★★★ full PW id map + **why R/G/B/HUE are unreachable** (normaliser domain `0x100–0x12e`)
- [`docs/current/PW_APPLY_TRIGGER_CHAIN_2026-10-10.md`](docs/current/PW_APPLY_TRIGGER_CHAIN_2026-10-10.md) — ★★★★★ the p7-side trigger chain of "Picture Wizard → Custom 1" + **path A falsified**
- [`docs/current/ATTR_BUS_MCB_2026-10-09.md`](docs/current/ATTR_BUS_MCB_2026-10-09.md) — ★★★★★ attribute-bus transport fully decoded
- [`docs/current/3DLUT_TABLE_FORMAT_2026-10-08.md`](docs/current/3DLUT_TABLE_FORMAT_2026-10-08.md) / [`3DLUT_APPLY_PATHS_2026-10-08.md`](docs/current/3DLUT_APPLY_PATHS_2026-10-08.md) — table format / five apply paths + QEMU reproduction
- [`docs/current/U6_ONMACHINE_RESULT_2026-10-09.md`](docs/current/U6_ONMACHINE_RESULT_2026-10-09.md) — ★★★★★ U6 on-camera results (write law / criteria rebuilt / E1✓ E3✓ E4✗)
- [`docs/current/P7_RECLAIM_COUNTERMEASURE_2026-10-09.md`](docs/current/P7_RECLAIM_COUNTERMEASURE_2026-10-09.md) — reclaim countermeasures (dual-channel isolation + guard + experiment matrix)
- [`docs/current/LUT_PIPELINE_DESIGN_2026-10-09.md`](docs/current/LUT_PIPELINE_DESIGN_2026-10-09.md) / [`FLAB_DATAFLOW_DESIGN_2026-10-09.md`](docs/current/FLAB_DATAFLOW_DESIGN_2026-10-09.md) — LUT pipeline / data-flow design
- [`docs/current/FW_NATIVE_UI_ONEKEY_FEASIBILITY_2026-10-10.md`](docs/current/FW_NATIVE_UI_ONEKEY_FEASIBILITY_2026-10-10.md) — ★★★★★ "native-UI one-key filter" feasibility (G-UI / G-ONEKEY / G-FILTER)
- [`docs/current/MODGUI_SPEED_AND_RECIPES_2026-10-10.md`](docs/current/MODGUI_SPEED_AND_RECIPES_2026-10-10.md) — ★★★★ menu popup 4× faster + recipes 35→68
- [`docs/current/CAMERA_MENU_ARCHITECTURE_2026-10-07.md`](docs/current/CAMERA_MENU_ARCHITECTURE_2026-10-07.md) — ★★★★★ camera system-menu dossier (**proof that p7 has no menus**)
- [`docs/current/CAMERA_APP_STRUCTURE_2026-10-07.md`](docs/current/CAMERA_APP_STRUCTURE_2026-10-07.md) / [`ILAUNCHER_FIRMWARE_FLASH_2026-10-07.md`](docs/current/ILAUNCHER_FIRMWARE_FLASH_2026-10-07.md) — official app structure / iLauncher flashing mechanics
- [`docs/current/NX500_ARCHITECTURE.md`](docs/current/NX500_ARCHITECTURE.md) — full system architecture (incl. complete EP register dump)
- [`SYNC.md`](SYNC.md) — install / incremental sync / WiFi push / rollback (bilingual)

**Archive** (conclusions may be superseded): `docs/archive/`
**Evidence**: `docs/evidence/p7/`, `docs/evidence/discovery/`
**Module docs**: `scripts/nx-rc/thumb/README.md`, `scripts/nx-rc/push/README.md`

---

## ★★ Errata & corrections (2026-10-10 documentation audit)

Several historical statements in this repo are **outdated or were disproven by later on-camera measurements**.
The following corrections are authoritative; **where they conflict with older text, this section wins**.

| # | Old statement | Correction | Evidence |
| - | --- | --- | --- |
| 1 | This fork = `github.com/WApaperplane/nxwa` | Canonical repo = **`github.com/WApaperplane/NXWA-nx500_modding`** (a fork; default branch `nxwa`; the old name still redirects) | `gh repo view`, measured |
| 2 | Upstream = `github.com/SamsungNX500/nx500_nx1_modding` | GitHub fork parent (which itself has no parent) = **`ottokiksmaler/nx500_nx1_modding`**; the `SamsungNX500/...` repository **does not exist** | `gh repo view`, measured |
| 3 | 18 built-in recipes | **68** (4-page menu) | `scripts/filmlab/recipes.json` |
| 4 | Authoritative recipe source = `nx500_recipes.txt` | Authoritative source = **`scripts/filmlab/recipes.json`**; the `.txt` is the early 18-recipe table | `flab.py` data flow |
| 5 | "Tap a recipe and it applies instantly / two steps to a look" | **Three dimensions (SAT/SHARP/CON) push instantly; all 7 need one Picture-Wizard confirmation on the camera body** | `PW_PARAM_CHANNEL`, `PW_ID_MAP_FULL` |
| 6 | "View and Still are independent ⇒ editing the View table does not affect photos" | ❌ **Disproven**: `View 4 profiles ⊆ Still 18` ⇒ both share one buffer pool; software-level isolation is impossible | `3DLUT_VIEW_STILL_ISOLATION_2026-10-08.md` |
| 7 | "Userspace cannot write LUT data" | **Fixed**: userspace *can* `lutapi load` its own table (LUT1 + guard). What it cannot do is read/write p7's four built-in buffers (`0x81xxxxxx`, outside the Linux mapping) | `U6_ONMACHINE_RESULT`, `3DLUT_APPLY_PATHS` |
| 8 | "One built-in LUT is pure identity / usable as a neutral baseline" | ❌ **Criterion void**: every factory table is a *style* table (the so-called identity slot is a low-contrast grey look) | `U6_ONMACHINE_RESULT` |
| 9 | "`setvar` can write PW variables" | ⛔ **Forbidden**: ids are registered by p7 at runtime; blind scanning once crashed the capture service | `ERROR_CORRECTIONS`, `PW_PARAM_CHANNEL` |

## ★ Reverse-engineering highlights

**Working (reproducible)**

| Capability | Status |
| --- | --- |
| PW three-dimension direct push | ✅ on-camera regression 3/3 (full 32-bit encoding; matches the official 17-entry encoding LUT bit-for-bit) |
| 3D LUT userspace load | ✅ `lutapi load` (requires p7 "reclaimed" state) + dual-channel isolation + guard |
| `.cube ⇄ native table` | ✅ format solved (4913×4B, `0x4D00` slot stride) |
| Camera system-menu extension | ✅ mod_gui overlay (4 widgets / 4 keysyms; replaces, cannot iterate) |
| Live web-gallery directory | ✅ port-8080 `dirlist` readdir |

**Structural ceilings (stated honestly)**

- **All 7 PW dimensions have no external path** (p7 normaliser domain `0x100–0x12e`) — needs one on-body confirmation or a p7 patch.
- **p7 has no UI** (Font / DrawText / Dialog / Widget: zero hits) ⇒ system menus can only be changed in the Linux-side `di-camera-app` (no source, very expensive).
- **Long-press / multi-tap / key combos are architecturally impossible** (the kernel consumes keys first) ⇒ "one-key" tops out at one key = one action.
- **Direct-loading LUTs into stills is a dead end** (the capture flow reconfigures the slot pool) ⇒ rule: preview direct-load / stills post-processing.
- **All factory LUT tables are style tables** ⇒ "write identity → neutral" is not a valid criterion.

**Toolchain**: Ghidra (p7 static), QEMU/Unicorn (offline reproduction), zig cross-compile (`arm-linux-gnueabi.2.15`, **`-O0` mandatory**), `gate_flow.py` (gates), `check_scripts.py` (CI).

**Dead ends already walked**: see `docs/current/ERROR_CORRECTIONS_2026-10-07.md` (C1–C9) and §8 of `RE_PROGRESS`.

> The film-simulation engine and `.cube` assets live in a separate public repo:
> [nx500-filmsim](https://github.com/WApaperplane/nx500-filmsim).
