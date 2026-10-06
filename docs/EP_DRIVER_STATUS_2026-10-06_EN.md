# EP Driver Status: Never Enabled in Userspace

**Date** 2026-10-06 · **Step** 1 (read-only, zero risk)
**Tools** `epglb.arm` (own process), `epfd.arm` (cross-process, read-only `/proc/PID/mem`)
**Safety** No libudd5 function called, no register written, no attach/ptrace

---

## TL;DR

★★★ **`di-camera-app` `dlopen`s libudd5 but never calls `d5_ep_open()`.**
The EP driver's userspace path is **completely unenabled** — this isn't
"couldn't find it", it's **confirmed absent**.

---

## Evidence

| Check | Method | Result |
|---|---|---|
| Does `di-camera-app` load libudd5 | `/proc/247/maps` | ✅ **yes**, 3 mappings |
| `fd_ep` value | `lseek+read /proc/247/mem` | `0xffffffff` = **-1** |
| `ep_3dlut_reg_base` | same | **0, not mapped** |
| `ep_nog_reg_base` | same | **0** |
| `path_ep_cs0` | same | **0** |
| **Who holds `/dev/drime5_ep`** | scan `/proc/*/fd/*` | ★★ **nobody** |
| What `di-camera-app` actually holds | `ls -la /proc/247/fd` | only `drime5-thermister` (fd 28) |
| **`/dev/drime5_ep` device node** | `ls -la /dev/drime5*` | ★★★ **exists** (char 10:126) |

---

## ★ Tool self-validation (avoiding the "grep zero result" trap)

Other symbols in the same batch read plausible values, proving the address
translation is correct — not random noise:

| Symbol | Value | Note |
|---|---|---|
| `ep_mc_default_config` | `7` | ★ **identical to my own-process dlopen read** |
| `g_d5_dev_ctx` | `0x15` (21) | device context index |
| `ycbcr2rgb_mtx_fd_udd` | `0x200` | valid config |
| `ycbcr2rgb_mtx_fd_udd_premovie_HD` | `0x254` | same as `_SD` |
| neighbour of `g_dd_mutex_lock` (`0x55570`) | `0x64` (100) | — |

⇒ **`fd_ep = -1` is a real reading, not a miscalculated-address artifact.**

---

## ★★★★ Two methodology corrections

### 1. `st_value` → runtime address

```
runtime_addr = seg_map_base + (st_value - seg_va_page)
```

⚠️ **`seg_va_page` must come from PT_LOAD's page-aligned `p_vaddr`, NOT the
`file_offset` in `/proc/pid/maps`.** maps' file_offset is page-aligned and
differs from `sh_offset` by `0x8000`/`0x97d8`. I got this wrong twice.

Real `libudd5`: `PT_LOAD[2] off_page=0x4c000 va_page=0x54000`
⇒ `fd_ep st_value=0x5556c` → `runtime = 0xb0e75000 + 0x156c = 0xb0e7656c` ✓

### 2. ★★★★★ I had been analysing the WRONG library

| | Analysed | **Real device** |
|---|---|---|
| Size | 279036 B | ★ **320216 B** |
| md5 | `abcbaaf7…` | ★ **`40c7b087…`** |
| FUNC symbols | 453 | **459** |
| `.data` sh_addr | `0x4a828` | **`0x548e0`** |

The old one came from the **NX1 GPL package**; the real one ships with
**NX500 1.12**.
⇒ ★★★ **All previous st_value / register offset tables are void.**
Use `libudd5_real.so` from now on.

★ The real version has **extra viewfinder matrices**:
```
ycbcr2rgb_mtx_fd_udd_premovie_HD
ycbcr2rgb_mtx_fd_udd_premovie_SD
```
(plus non-premovie variants) ⇒ ★★ **Still and Premovie are two separate
matrices — viewfinder isolation works naturally.**

---

## ★ ARM binutils: not needed

| Need | Solution | Result |
|---|---|---|
| ELF parsing cross-check | **pyelftools 0.33** | ✓ `crosscheck.py` **16/16 match** |
| Disassembly | Capstone 5.0.7 (have it) | objdump gives names, not semantics |

★ The controlled experiment **caught two real errors of mine**:
1. `decode_ioc` nr mask written as `0xFFF` (should be `0xFF`) ⇒ produced `nr=770`
2. ★★ **the ioctl is `_IOWR('s', 2, u32)`, not `('r', 2, …)`** — `'s'` = Samsung SMA.
   Carrying that error to the device = wrong ioctl number.

`zig 0.13.0` is in `.uploads/zig/`; cross-compilation doesn't need binutils.

---

## Corrections to earlier conclusions

| Earlier | Now |
|---|---|
| "3D LUT writer is userspace `libudd5`" | ⚠️ **half right**: the API is userspace, but **nobody calls it** |
| "EP base addresses: 10/10 bidirectional closure" | ⚠️ directionally right, but **built on the wrong library** |
| "just call `d5_ep_open()`" | ⚠️ now known: **the EP driver has never been enabled in userspace** |

---

## ★★★ Route decision required

`/dev/drime5_ep` **exists** (char 10:126) ⇒ the driver is compiled into the
kernel, nobody just opens it.

| Route | Method | Risk |
|---|---|---|
| **A. open it ourselves** | `open("/dev/drime5_ep")` + `d5_ep_open()` | ★ medium. Node exists, but why doesn't the camera open it? May contend with ISP firmware |
| **B. `/dev/mem` direct** | `epfull.arm` read side proven; write side untried | ★ **lowest**. No driver involvement |

★★ **Recommended next check**: find what the kernel's `drime5_ep` `open`
handler does (`grep drime5_ep /proc/kallsyms` → look for `request_irq` /
`ioremap` of the whole EP block).
- If it **re-initialises hardware** ⇒ **route A is forbidden** (conflicts with
  the working ISP firmware)
- If it only **`ioremap`s memory** ⇒ route A is viable and cleaner

---

## Artifacts

| File | Purpose |
|---|---|
| `epglb.c` / `.arm` | own-process dlopen + read globals (14/14 API symbols present) |
| `epfd.c` / `.arm` | cross-process read-only `/proc/PID/mem`, supports `-B` batch |
| `sh.py` | telnet command runner (works around silent echo) |
| `crosscheck.py` | pyelftools cross-validation (16/16) |
| `libudd5_real.so` | ★ **real device version** (320216 B) |
| `raw5/epglb_v1.txt` | step 1 raw output |
| `raw5/epfd_batch.txt` | cross-process batch read output |

---

## New ironclad rules (device operations)

| # | Rule |
|---|---|
| **43** | telnet gives **silent echo** on logged-in sessions ⇒ only reliable read is redirect to `/mnt/mmc/_xfer/` + FTP pull |
| **44** | `/proc/PID/mem`: use **`lseek`+`read`**, **not `pread`** (old kernel: pread → EINVAL) |
| **45** | FTP refuses `cwd` into system dirs like `/usr/lib` (550 Error) ⇒ `cp` to `/mnt/mmc/_xfer/` first |
| **46** | login via `minitel.MiniTel` (handles IAC negotiation), root with empty password |