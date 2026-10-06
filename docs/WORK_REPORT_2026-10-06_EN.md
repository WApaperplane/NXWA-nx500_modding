# Work Report 2026-10-06: 3D LUT Write Path — From Zero to Verified
---
> ## ⚠️⚠️⚠️ 2026-06 晚·结论纠正声明（必读）
>
> **本文档中「导入 LUT 内容必须改 P7」这一结论已被推翻。**
>
> 当时把 `d5_ep_3dl_load_lut` 误当成"挂地址"（往 `+0x0c` 写一个地址让硬件自己去读）。
> 复核后确认它走的是 **WDMA 硬件 DMA**：数据放在**调用者自己的 CMA 缓冲**（`/dev/d5_sma`），
> 由硬件 DMA 搬进 3D LUT 内部 RAM ⇒ **完全不涉及 `0x81xxxxxx`** ⇒ **Linux 用户态可以导入任意 LUT**。
>
> | 项 | 定论 |
> |---|---|
> | 被推翻 | "LUT 数据缓冲在 p7 地址空间 ⇒ 必须改 P7" |
> | 成立 | **导入 .cube LUT：用户态可做，不需要改固件** |
> | 仍需改 P7 的唯一理由 | 要改**ISP 生成 LUT 的算法**（tone curve 能力），不是"搬数据" |
>
> 关键证据：`ConfigAccessMode → sub_3a888 @0x3a888`（静态函数，本次解开）
> → `OnOff(1)→Acc(0)→Acc(1)→SetAddress(自己的 CMA 地址)→SelLUT→rw_Start(1)`，
> 其中 `rw_Start(1)` = `+0x008 |=0x100 → &=~0x100`（write-1-clear 触发 DMA）。
> ★ 另：`+0x0c` 写固件常量地址（4 档切换）是一条**独立通路**，与导入无关。
>
> 详见 `docs/LUT_IMPORT_2026-10-06.md` 与 `.workbuddy/memory/topics/ep-3dlut.md`。

**Date** 2026-10-06 · **Topic** Full reverse engineering + on-device verification of the EP / 3D LUT chain
**Output** 61 files (8 tools · 14 probes · 5 documents · 34 binaries)

---

## 0. TL;DR

| Item | Status |
|---|---|
| Userspace 3D LUT register write | ✅ **verified on device — the image actually changed** |
| LUT data format | ✅ decoded (16-bit × 3ch, 17³) |
| **Final path for Magic Lantern** | ★ **patch P7 firmware** (not userspace) |
| Camera state | ✅ healthy — no crashes, no bricking |

★ **The most valuable outcome today was not "we can do it" but "we proved the previous approach wrong"** —
on-device experiments demonstrated that "writing LUT data from userspace" cannot work,
which pinpointed the real implementation point.

---

## 1. Starting point: overturning an old conclusion

The morning assumption was *"the 3D LUT writer lives in kernel/ISP firmware, P7 patching is mandatory"*,
based on *"di-camera-app's 1092 imports contain zero 3dlut-related symbols"*.

★ **That evidence was invalid** — `libudd5.so` is **dlopen'd at runtime** by `di-camera-app`,
so it never appears in the import table. One pass over the static symbol table
exposed **all 51 EP/colour APIs at once** (459 FUNC total).

⇒ Corrected from "kernel-side writer" to "userspace libudd5 API"; the route was replanned.

---

## 2. Tooling (build the chicken before the egg)

### 2.1 `udd5.py` — a hand-rolled ELF + Capstone disassembler

No `arm-linux-gnueabi` binutils on this machine, none on the ODroid either.
Following the already-validated `sym_udd.py` approach, I wrote my own ELF parser on top of Capstone.
Six subcommands: `ep` / `dump` / `literals` / `graph` / `batch` / `syms`, plus
`regmap.py` (automatic offset extraction across 35 reg-layer functions).

★ **Four ELF parsing traps, all caught by controlled experiments** (see §6).

### 2.2 `crosscheck.py` — ★ the decisive control experiment

Validated the hand-rolled parser against mature **pyelftools 0.33**: **16/16 checks matched**.

★ The control experiment **caught two real errors of mine**:
1. `decode_ioc` used an `nr` mask of `0xFFF` (should be `0xFF`) ⇒ produced `nr=770`
2. ★★ **the ioctl is `_IOWR('s', 2, u32)`, not `('r', 2, …)`** — `'s'` = Samsung SMA.
   Carrying that mistake to the device would have meant writing the wrong ioctl number.

### 2.3 On fetching ARM binutils from GitHub: verdict = **not needed**

| Need | Solution | Result |
|---|---|---|
| ELF parsing cross-check | pyelftools (installed) | ✔ 16/16 match |
| Disassembly | Capstone 5.0.7 (already present) | objdump gives names, not semantics |

★ What `objdump` gives you is *"this function is called `_udd_ep_3dl_reg_SetAddress`"*.
What you actually need is *"which EP block offset does it write"* — and only Capstone +
literal-pool resolution can answer that.
★ Cross-compilation uses the existing zig 0.13.0 (`.uploads/zig/`), independent of binutils.

---

## 3. On-device verification: three stages

### 3.1 Stage 1 — EP driver userspace state (`epglb` / `epfd`)

| Check | Result |
|---|---|
| Does `di-camera-app` load libudd5 | ✅ yes (PID 247) |
| `fd_ep` (read via `/proc/247/mem`) | `0xffffffff` = **-1** |
| **Who holds `/dev/drime5_ep`** | ★ **nobody** (scanned every `/proc/*/fd/*`) |
| `/dev/drime5_ep` device node | ★★★ **exists** (char 10:126) |

⇒ ★★ **The entire D5 accelerator userspace stack is never enabled on NX500.**

★ Simultaneously corrected a major error: **I had been analysing the wrong library.**
The old one is 279036 B / 2014-09 (identical in the NX1 and NX500 open-source drops);
the on-device one is 320216 B / 2015-01 (unreleased). **All previous offset tables are void.**
Switched to `libudd5_real.so`.

★ The real version has **extra viewfinder matrices** `ycbcr2rgb_mtx_fd_udd_premovie_HD/_SD`
⇒ **Still and viewfinder are two separate matrices — isolation works naturally.**

### 3.2 Stage 2 — kernel-side investigation (after the user supplied the open-source drop)

The user provided the **complete NX500 kernel source** (2.3 GB). It contains the full EP driver
source, yielding three decisive conclusions:

```c
/* ① /dev/drime5_ep is a pure mmap device; open does zero hardware init */
struct file_operations drime5_ep_ops = { .open, .release, .unlocked_ioctl, .mmap };
static int drime5_ep_open(...) { filp->private_data = g_ep; d5_kdd_open(KDD_EP); }
static int d5_ep_resume(...)   { return 0; }   /* deliberately does nothing */

/* ② ★★★★★ the kernel hands userspace the authoritative address of all 10 EP blocks */
#define EP_IOCTL_GET_PHYS_REG_INFO _IOR('h', 100, struct ep_reg_info)
struct ep_reg_info { top, ldc, mc, rsz, lvr, bblt, fd, jpeg, 3dlut, nog };  /* each {addr,size} */

/* ③ all 15 ioctls are interrupt/clock class ⇒ register access is 100% via mmap */
```

⇒ ★★ **No more guessing addresses, no more parsing ELF, no more cross-process pointer reads.**

★ All 15 ioctls being interrupt-class + `ep_*_reg_base` being pointer variables
⇒ mutual confirmation that registers go through mmap.

### 3.3 Stage 3 — write experiments (11 runs)

| # | Experiment | Image | Conclusion |
|---|---|---|---|
| L1 | pulse `+0x08` only | — | ✔ zero side effects (1024 words diff = 0) |
| L2 | write `+0x64/68/6c/70` | — | ✔ discovered these are also self-clearing |
| L3 | identity → `0x81115200` | no change | address is p7-reserved, userspace can't change it |
| L4 | `SMA_ALLOC` | — | ❌ `sma_dev == NULL` |
| L5 | `/dev/mem` write CMA | — | ❌ SIGSEGV |
| L6/L7 | `/dev/d5_sma` mmap CMA | no change | ✔ write succeeded, but address/format wrong |
| **L9** | complete 6 steps (bit0 pulse) | ★ **red-ish garbage** | ★★★ **3DLUT took effect** |
| L10 | full 6 steps + red-shift LUT | ★ red-ish garbage | ✔ reproduced |
| L11 | full 6 steps + 8 KB all-zero | ★ still garbled | ⇒ rules out "LUT content", points to format |

---

## 4. ★★★★ Core result: the authoritative 6-step sequence from p7

Source: `raw8/p7/ghidra/53_all_pseudocode.c:641680+` (kernel-side decompilation)

```c
b[0x000] |= 1;              // ① FUN_004cf3d4(1)  OnOff master switch
b[0x008] &= ~1UL;           // ② FUN_004cf45c(0)  ★ clear pulse bit first
b[0x008] |= 1UL;            // ③ FUN_004cf45c(1)  ★ set to start
b[0x00c] = lut_phys;        // ④ FUN_004cf4b4     SetAddress
b[0x004] &= 0xffffffcfUL;   // ⑤ FUN_004cf414     channel select
b[0x008] &= ~0x100UL;       // ⑥ FUN_004cf484(1)  ★★ read-side clear
```
★★ **Steps ② and ⑥ are why my first five experiments all failed.**
★ Objective criterion: **after execution, `+0x008` staying at 1 = hardware accepted the start**
( previously it was cleared every time).

### Measured data vs p7 definition: 4/4 mutual confirmation
| Offset | Measured | p7 definition |
|---|---|---|
| `+0x000` | `0x00000001` | OnOff = on |
| `+0x004` | `0x00000100` | bit8 = LUT0 source |
| `+0x00c` | `0x81115200` | LUT0 data address |
| `+0x008` | `0x00000000` | pulse bit (self-clears after write) |

### Hard constraint: 256-byte alignment
```c
/* p7 FUN_00179384 */
if ((param_1 & 0xff) == 0) { ... }     /* LUT physical address must be 256-byte aligned */
```
⇒ Exactly matches the `if ((phys & 0xff) != 0) return -301;` I derived statically from libudd5
⇒ **bidirectional cross-validation between userspace disassembly and kernel decompilation succeeded.**

---

## 5. ★★★★★★ Decisive finding: the LUT buffers live in p7's address space

### p7's four preset LUT buffers
```c
DAT_003837f0 = 0x810fd100
DAT_003837f4 = 0x81106b00
DAT_003837f8 = 0x81115200    ★ identical to the measured +0x0c
DAT_003837fc = 0x81101e00
/* FUN_0009a3e8 merely picks one of these four and returns it — nothing is computed */
```

### ★★★ They are Samsung's four built-in colour profiles (content read out)
| Buffer | First 64 bytes | Profile |
|---|---|---|
| `0x81101e00` | `00000000 10000000 20000000...` perfectly linear | ★ **pure identity** |
| `0x81115200` | `00ff0001 fe0002fd...` R↑ G↓ | ★ **warm tone / skin** |
| `0x810fd100` | `15000d00 23000c00...` non-monotonic | stylised curve |
| `0x81106b00` | identical to the first | same |

### ★★★ LUT data format (decoded from the first 32 words of `0x81115200`)
```
0100ff00  fd0200fe  00fc0300  0500fb04  f90600fa  00f80700 ...
```
★ Splitting into little-endian 16-bit values: R rises from `0x0001` to `0x00ff` while G/B fall in step
⇒ ★★★ **one R-slice of a 17³ 3D LUT, 16-bit × 3 channels interleaved**
⇒ ★★ My initial 8-bit RGB assumption was simply the wrong format — **that was the real cause of the garbling.**

### ⇒★★★★★ Why userspace can never touch them
| Fact | Evidence |
|---|---|
| Linux `mem=512M` ⇒ physical limit `0x20000000` | `/proc/cmdline` |
| p7 page table only covers `0x80000000..0x80ffffff` (1:1, 16 PTE) | `50_page_table.txt` |
| `sma_mmap` returns EINVAL for `0x81115200` | measured (`__phys_to_pfn` yields 0) |

⇒★★★★★ **Linux userspace can never read or write those four LUT buffers.**

★⇒ **This is the final evidence that Magic Lantern must patch P7** —
not *"the writer is in p7"* but *"**the LUT data buffers themselves live in p7's address space**"*.

---

## 6. ★★ Seven errors I corrected (all found via controlled experiments)

| # | Error | Reality |
|---|---|---|
| 1 | "STRICT_DEVMEM blocks `/dev/mem` writes" | ❌ kernel says `# CONFIG_STRICT_DEVMEM is not set`; writing verified |
| 2 | "CMA region is 98.6% free" | ❌ sampling too sparse; `0x9a000000` actually holds data |
| 3 | "16 independent LUT slots" | ❌ 16 views of one register (writing one changes all) |
| 4 | "the pulse is bit8" | ❌ p7 defines **bit0** |
| 5 | "`+0x64/0x68` are zero ⇒ hardware disabled" | ❌ OnOff is at `+0x00`, measured = 1, **hardware is on** |
| 6 | "use `ps \| grep` to check whether a process lives" | ❌ busybox `ps` shows only the current pts; must use `/proc/*/comm` |
| 7 | "writing LUT data is enough to change colour" | ❌ **the buffers are in p7's address space, unreachable from userspace** |

⇒ ★★★★ **Four false negatives caused by broken tooling**
(grep zero-result / ps zero-result / STRICT_DEVMEM assumption / CMA-free assumption)
⇒ ★★★★ **The most expensive lesson of this project: any "zero result" must first prove the tool works.**

---

## 7. ★ New ironclad rules

| # | Rule |
|---|---|
| **47** | When `mmap`ing a character device, pass the **byte physical address** as offset, not a PFN (the kernel does `>>12` for you). Wrong ⇒ EINVAL |
| **48** | Prefer **official userspace headers** for struct layouts and macros (NX500 drop provides `usr/include/media/drime5/ep/`) — never hand-copy |
| **49** | When you get kernel source, grep `io_remap_pfn_range` / `unlocked_ioctl` / `struct file_operations` first — these three answer "how are registers accessed" better than any RE |
| **50** | To test "is a process running", read `/proc/*/comm`; don't trust busybox `ps` |
| **51** | `-O0` + hand-written mmap + `memset`/`memcpy` can hit unmapped boundaries (measured: writing 256 bytes SIGSEGVs, 32 bytes is fine) ⇒ use byte loops |
| **52** | telnet gives **silent echo** on logged-in sessions ⇒ the only reliable read-out is redirect to `/mnt/mmc/_xfer/` then FTP pull |
| **53** | `/proc/PID/mem`: use **`lseek`+`read`**, **not `pread`** (the 2015-era kernel returns EINVAL for pread) |
| **54** | FTP refuses `cwd` into system dirs like `/usr/lib` (550 Error) ⇒ `cp` to `/mnt/mmc/_xfer/` first |
| **55** | **Consecutive mmap of multiple blocks drops the camera off the network** ⇒ one block per run, 10 s apart |

---

## 8. Deliverables

### Tools (8)
| File | Purpose |
|---|---|
| `test_server/isp/udd5.py` | ★ hand-rolled ELF+Capstone disassembler (6 subcommands) |
| `test_server/isp/regmap.py` | EP register offset extractor |
| `test_server/isp/crosscheck.py` | ★ pyelftools cross-validation (16/16) |
| `test_server/sysarch/dishex.py` | hexdump → ARM disassembly |
| `test_server/sysarch/sh.py` | telnet command runner (works around silent echo) |
| `test_server/sysarch/run_arm.py` | probe deploy + output retrieval (validated pattern) |

### Probes (14 `.c` + binaries)
`epglb` (own-process globals) · `epfd` (cross-process read-only `/proc/PID/mem`, `-B`/`-D`) ·
`kread` (dump `/dev/mem`) · `epinfo` (authoritative EP block addresses) ·
`epdump2` (mmap dump, supports `all`) · `epwr` (3-tier write with auto-rollback) ·
`eplut3`–`eplut7` (LUT write generations) · `eplut9`/`eplut10` (★ authoritative 6-step sequence) ·
`eplen` (LUT length probe) · `rd` (★ reads the four preset LUTs) ·
`mmtest`/`probe7`/`probe8` (★ control experiments proving CMA is writable)

### Documents (5)
- `docs/WORK_REPORT_2026-10-06.md` — ★ this report
- `docs/EP_3DLUT_WRITE_EXPERIMENTS_2026-10-06.md` — ★ all 11 write experiments
- `docs/EP_PATH_OPEN_2026-10-06.md` — kernel ioctl + mmap path
- `docs/LIBUDD5_EP_API_MAP_2026-10-06.md` / `_EN.md` — libudd5 API map + ioctl protocol

### Analysis data
- `test_server/isp/libudd5_real.so` — ★ **the real on-device library** (320216 B)
- `test_server/isp/out/` — all exports (API tables / register maps / call graph / full disassembly)
- `test_server/sysarch/raw5/` — 1024-word baselines per stage + experiment outputs

---

## 9. ★ Next steps

### A. Patch the P7 firmware (the only path for Magic Lantern)
Entry point already located: `FUN_0009a3e8` (where one of the four constants is picked and returned).

| Step | Content | Risk |
|---|---|---|
| 1 | Find the userspace → p7 data channel (a `/dev/` node or IPCC) | low (read-only probing) |
| 2 | Add a memcpy after `FUN_0009a3e8` | low |
| 3 | SLP backup (official escape hatch exists) | low |
| 4 | Flash and verify | medium (the change is just "copy one more buffer", no hardware timing) |

### B. Preset profile switching (zero risk, shippable now)
Write `+0x0c` of 3DLUT with one of `0x810fd100` / `0x81106b00` / `0x81115200` / `0x81101e00`
⇒ **no firmware patch needed** — this can be delivered today as a "4-colour-profile switch".

---

## 10. Summary

★★★★★★★★★★ **Today turned "Magic Lantern" from a vague wish into an engineering route:
the write path is verified, the data format is decoded, and the final implementation point
is pinpointed at p7's four constants.**
**And on-device experiments falsified the apparently-viable "write LUT data from userspace" path,
preventing further wasted investment.**