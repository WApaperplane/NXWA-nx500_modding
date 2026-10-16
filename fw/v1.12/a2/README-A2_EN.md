# A2 Patch Image (p7 segment) — Flashing Guide

> **`p7_a2.bin`** in this folder is the **p7-partition image** of the `NXWA-A2` patch (12,075,648 bytes).
> It is the firmware prerequisite for **all-7-dimension PW one-tap**: after it is written to the camera's p7 partition, `filmlab.sh` can push **all seven dimensions at once** (R/G/B/HUE/SAT/SHARP/CON).
> Without A2, everything behaves as before (the push step is silently ineffective — it does not crash); the full-range effect can still be obtained via "Picture Wizard → Custom 1".

---

## Scope

- **NX500 only** (no NX1 build); verified against NX500 **official firmware 1.12**.
- Prerequisite: the camera runs the mod and you can telnet in (root / empty password) — i.e. Telnet is enabled from the camera's main menu (tap the IP row).

## Pre-flight (match two numbers first)

| Item | Value |
| --- | --- |
| `p7_a2.bin` md5 | `712c6fd0a49371ec05ce94c367b0d5c7` |
| File size | `12075648` bytes |

> After extracting this package to the SD card, the image sits at **`/mnt/mmc/patch-a2/p7_a2.bin`** (the FTP root IS the SD-card root).

---

## Two installation channels (pick one)

| Channel | How | Suits |
|---|---|---|
| **A. Lightweight (this document)** | p7 segment image `p7_a2.bin` + telnet `dd` | Machines with telnet enabled; write takes ~1 s |
| **B. Full package** | Download release asset `slp_a2_p7_v117.bin` → put in SD root as `nx500.bin` → camera menu "Settings → Device Information → Firmware Update" | No telnet needed; uses the official flashing chain |

> Both write the **same** p7 content. Channel B download: GitHub `v2.88.0-nxwa.2` release page, **Assets** section (a `.md5` file is included).

## Flashing steps (run one by one over telnet)

```sh
# 0) Verify the image (must equal 712c6fd0a49371ec05ce94c367b0d5c7; stop if not)
md5sum /mnt/mmc/patch-a2/p7_a2.bin

# 1) Back up the current p7 — your only rollback; do NOT skip!
dd if=/dev/mmcblk0p7 of=/mnt/mmc/p7_backup_$(date +%s).bin bs=1M
sync

# 2) Write A2 (≈1 second)
dd if=/mnt/mmc/patch-a2/p7_a2.bin of=/dev/mmcblk0p7 bs=1M
sync; sync; sync

# 3) Read-back verification
#    12 MiB read = image 12,075,648 B + 507,264 B zero padding at the partition tail
dd if=/dev/mmcblk0p7 bs=1M count=12 2>/dev/null | md5sum
#    standard case expected: 69050a17ea9fdbcdab4cf32e7b5ffdb2
#    If mismatch: (1) re-run this step once; (2) still fails → pull it back and
#    byte-compare with p7_a2.bin (FTP to SD, then use tools/nx-fetch.py)
```

⚠️ **Double-check that the device is `/dev/mmcblk0p7`** (the ISP-firmware partition; measured on NX500) both before and after writing. On other models/environments **do not copy blindly** — confirm first (`cat /proc/partitions` or existing documentation).

## Activation

- **Normal power off → power on** (the p7 firmware loads on the next boot; a normal power cycle is enough).
- ⛔ **NEVER** `systemctl restart di-camera-app` — measured to **freeze the whole camera** (physical power-off required).

## Verify success

```sh
# One-tap push a recipe (e.g. portra400)
sh /opt/usr/nx-ks/filmlab.sh pwpush portra400 --yes

# Objective criterion (ISP's actual 7 values vs the recipe slot)
sh /opt/usr/nx-ks/filmlab.sh check
```

- The image **changes immediately** (recipe look) + `check` passes = **success**.
- If `pwpush` produces no visible change: first re-verify step 3's read-back md5, and make sure you did one **normal power-off → power-on**.

## Rollback

```sh
# Write the backup back (<timestamp> = the file created in step 1)
dd if=/mnt/mmc/p7_backup_<timestamp>.bin of=/dev/mmcblk0p7 bs=1M
sync; sync; sync
```

Then **normal power off → power on**. Alternatively re-flash official 1.12 via the official SD flashing chain — both routes work.

## ⚠️ Risks & discipline

- Do **not** cut power or pull the card while writing; a full battery or external power is recommended (the write itself takes ≈1 s — a tiny window).
- **Writing the wrong partition is serious** (e.g. `mmcblk0p1`) — read the command twice and double-check the partition name.
- This is a community (NXWA) build — **use at your own risk**; official firmware upgrades rewrite p7 ⇒ **re-flash this image afterwards**.
- The partition (30 MB) is larger than the image (12 MB): the tail stays untouched (measured all-zero). This is normal.

## Numbers for cross-checking

| Artifact | md5 |
| --- | --- |
| `p7_a2.bin` (this folder) | `712c6fd0a49371ec05ce94c367b0d5c7` |
| Full flashing package `slp_a2_p7_v117.bin` (352 MB, official SD chain, **available as a Release asset since 2026-10-16**: `v2.88.0-nxwa.2` page, Assets section) | `44b61efc0625874b62ef6a45517ffda8` |

## One-line mechanism

A2 adds a "slot-pool direct write" channel inside p7: an external `seq 0x134..0x13A` (7 raw values) + `0x13B` (trigger) → p7 writes the parameter slots → the official "slot apply" chain pushes all 7 dimensions into the ISP — that is how "one-tap" is achieved. Details: `docs/current/A2_PATCH_DESIGN_2026-10-14.md`, `A2_READBACK_VERDICT_2026-10-15.md`.
