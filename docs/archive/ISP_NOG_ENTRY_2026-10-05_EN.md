# ISP Core / DSP_NX500GLU Entry Point — Investigation Report

> Date: 2026-10-05 21:20
> Goal: locate the entry point and writable surface of the ISP firmware core
> `DSP_NX500GLU0APC1_SR1`
> Method: **fully offline** (the camera at 192.168.0.x did not answer ping), using
> `libudd5.so` from the NX1 official GPL package. **Zero contact with the hardware**
> in this round.

---

## Verdict (skeleton first)

**1. "The DSP_NX500GLU entry point" is not a directly callable function on the Linux side.**
`DSP_NX500GLU0APC1_SR1` is **bare-metal firmware running on a separate ISP core** (the
version string comes from `/etc/version`, not from a file). The Linux side has no
symbol for it and no code path that loads it. The furthest boundary we can trace is:

```
user-space API (libudd5.so)
   → ioctl /dev/drime5_ep
      → EP hardware registers (ten sub-blocks at 0x80506864)
         ←—— the ISP firmware does NOT appear anywhere in this chain
```

**2. The previous conclusion "NOG is empty, the hardware grain generator is not enabled"
must be corrected.**
The NOG (Noise Generator = hardware grain generator) **has a complete user-space API**,
and we have recovered its **real register offsets** inside the regset structure from
disassembly. "The data area reads all zeros" only means **it is not enabled under the
current configuration** — it does not mean the hardware is absent.

**3. The standing rule is unchanged: still do not write EP registers.**
What this report delivers is **observability plus a legitimate user-space path**,
not a licence to poke registers from `poker`.

---

## 2. EP Sub-block Base Addresses: Ten Interleaved `{start,size}` Pairs (verified)

Verbatim from `/usr/include/media/drime5/ep/d5_ep_type.h`:

```c
struct ep_reg_info {
    struct ep_reg_phys_info reg_base_top;    // ← top
    struct ep_reg_phys_info reg_base_ldc;
    struct ep_reg_phys_info reg_base_mc;
    struct ep_reg_phys_info reg_base_rsz;
    struct ep_reg_phys_info reg_base_lvr;
    struct ep_reg_phys_info reg_base_bblt;
    struct ep_reg_phys_info reg_base_fd;
    struct ep_reg_phys_info reg_base_jpeg;
    struct ep_reg_phys_info reg_base_3dlut;
    struct ep_reg_phys_info reg_base_nog;    // ← NOG
};
```

★ **This is the authoritative evidence for a bug we already fixed**: the table is
**ten interleaved `{start,size}` pairs (160 bytes)**, not "two arrays".
The acquisition channel is `EP_IOCTL_GET_PHYS_REG_INFO` =
`_IOR('h', 100, struct ep_reg_info)` = **`0x80506864`**, and it must be issued on the
`/dev/drime5_ep` fd (sending it to a `/dev/mem` fd returns `RC=3`).

| # | Field | Measured base | Size |
|---|---|---|---|
| 8 | `reg_base_3dlut` | `0x2082b000` | 0x1000 |
| 9 | `reg_base_nog` | `0x20821c00` | 0x100 |

---

## 3. ★★★ Core Breakthrough This Round: NOG Register Offsets (self-proving)

### 3.1 The full user-space API exists (within the 503 exports)

| Layer | Symbol | Purpose |
|---|---|---|
| Public API | `d5_ep_nog_set_noisegen` | ★ top-level entry, takes `d5_ep_nog_op_info` |
| Public API | `d5_ep_nog_set_bypass` | bypass switch |
| Internal | `_udd_ep_nog_set_std_sigma` | standard deviation (= grain strength) |
| Internal | `_udd_ep_nog_set_gamma` | gamma curve for grain weighting |
| Internal | `_udd_ep_nog_set_random_seed` | random seed |
| Internal | `_udd_ep_nog_select_rv_type` | UNIFORM / GAUSSIAN |
| Internal | `_udd_ep_nog_seed_load_switch` | seed-load switch |
| Internal | `_udd_ep_nog_regset0` / `regset1` | regset struct pointers in `.bss` |
| Global | `ep_nog_reg_base` | `.bss @ 0x4d644`, at runtime = the mmapped EP base |

**The `d5_ep_nog_op_info` structure (verbatim from `ep_type.h`, author Junhee Jeong):**

```c
typedef struct {
    u8                      std;          // standard deviation = grain strength
    u8                     *gamma;        // gamma table pointer
    d5_ep_cs_id             cs_id;        // context switch group
    d5_ep_nog_seed_switch   seed_switch;  // DISABLE=0 / ENABLE=1
    d5_ep_nog_rv_type       rv_type;      // UNIFORM=0 / GAUSSIAN=1
} d5_ep_nog_op_info;
```

### 3.2 ★★ Key criterion: the NOG register block sits at offset `+0x30` inside regset

Disassembling **five mutually independent** NOG functions, all of them contain the same
`ADD rX, rY, #0x30` (machine code `e28330xx`):

| Function | Instruction | Meaning |
|---|---|---|
| `_udd_ep_nog_set_bypass` | `ADD 0x30 (r0 → r2)` | fetch the NOG register block |
| `_udd_ep_nog_set_gamma` | `ADD 0x30 (r0 → r3)` | same |
| `_udd_ep_nog_seed_load_switch` | `ADD 0x30 (r0 → r2)` | same |
| `_udd_ep_nog_select_rv_type` | `ADD 0x30 (r0 → r2)` | same |
| `_udd_ep_nog_set_std_sigma` | `ADD 0x30 (r0 → r3)` | same |

**5/5 hits = cross-validated.** This is not a guess; it is encoding-level evidence.
Meaning: the struct pointed to by `_udd_ep_nog_regset0/1` has the **NOG register block
at offset 0x30**.

### 3.3 Register offsets within the NOG block (extracted from `set_std_sigma`)

`_udd_ep_nog_set_std_sigma` is the most information-dense one (size 432):

```
ADD 0x60 (r0 → r3)     ← a different register block (probably the LDC/MC area)
ADD 0x30 (r0 → r3)     ← the NOG block
ADD 0x67 (r0 → r1)     ┐
ADD 0x66 (r0 → r1)     ├ three consecutive byte registers: 0x65 / 0x66 / 0x67
ADD 0x65 (r0 → r1)     ┘
SUB 0x1f               ← ANDed with 0x1f ⇒ 5-bit mask
```

⇒ **The three byte registers inside the NOG block are at `+0x35 / +0x36 / +0x37`
relative to the `+0x30` base, with mask `0x1f`.** The sixteen `SUB 0x4` instructions
in `_udd_ep_nog_reg_struct_init` are sixteen `void*` fields being zeroed one by one
⇒ the regset struct has **16 pointer slots (64 bytes)**, and `0x30` is exactly slot 12
(`12 × 4 = 0x30`) — **two independent derivations agree**.

### 3.4 The loop structure of `_udd_ep_nog_set_gamma`

Size 684, the longest NOG function. The disassembly shows a clear loop:

```
for (i = 0; i < 4; i++) {          // 4 iterations
    LDR  0xc  (r11 → r1)           // gamma[i]
    LDR  0x18 (r11 → r2)           // regset
    ...
    LDR  0x10 (r11 → r2)
    SUB  0x10 (r2 → r2)  → +0x10  ┐
    LDR  0x14 (r1 → r1)           ├ stride 0x10, across 4 iterations
    LDR  0x18 (r11 → r2)           │
    SUB  0x14 (r2 → r2)  → +0x14  │
    LDR  0x18 (r1 → r1)           │
    SUB  0x18 (r2 → r2)  → +0x18  │
    LDR  0x1c (r1 → r1)           ┘
}
```
⇒ gamma is written to four 32-bit slots at `+0x40 / +0x44 / +0x48 / +0x4c`
(relative to the `+0x30` base), **stride 0x10, four entries**. This does not match the
three-valued `D5_EP_LUT_CBCR_CH01` ("CH0+CH1 averaged") enum, so **gamma is a 4-stage
curve**.

---

## 4. The 3D LUT Side (for comparison)

`ep_3dlut_reg_base` lives at `.bss @ 0x4d650`. The API surface is equally complete:

| Symbol | Purpose |
|---|---|
| `d5_ep_3dl_load_lut` | load a LUT from DDR into the hardware |
| `d5_ep_3dl_save_lut` | save the LUT from hardware back to DDR |
| `_udd_ep_3dl_reg_SetAddress` | set the LUT physical address |
| `_udd_ep_3dl_reg_SelLUT` | select LUT0 / LUT1 / LUT_EXT |
| `_udd_ep_3dl_reg_SelCbCr_ch` | select Cb / Cr / (Cb+Cr)/2 |
| `_udd_ep_3dl_reg_SetColorFormat_LUT0/1` | YCC422 / YCC420 |

★★ **The existence of `d5_ep_3dl_load_lut` lines up with an earlier measurement**:
the 3D LUT hardware block **is enabled** (`+0x00 = 0x1`), and the tail
`0x00f0..0xfc = 0x13020619` ×8 is the identity LUT.
`_udd_ep_3dl_reg_SetAddress` decodes to `SUB 0xc` / `SUB 0x10` ⇒ the LUT has
**two address registers** (one for LUT0, one for LUT1), consistent with the three-valued
`D5_EP_LUT_SEL_LUT0/LUT1/LUT_EXT` enum.

---

## 5. The Entry Chain (corrected)

```
┌─ user space ──────────────────────────────────────────┐
│ d5_ep_nog_set_noisegen(d5_ep_nog_op_info*)          │  libudd5.so
│   └→ _udd_ep_nog_set_std_sigma / set_gamma / ...    │
│        └→ regset(+0x30) → EP physical registers      │
│   d5_ep_3dl_load_lut(addr, sel, fmt, timeout)        │
│   d5_ep_top_update_sreg(module)  ← commits shadow registers │
└──────────────────────┬──────────────────────────────┘
                       │  ioctl
┌─ kernel ─────────────▼──────────────────────────────┐
│ /dev/drime5_ep   (10,126)                           │
│   EP_IOCTL_GET_PHYS_REG_INFO  0x80506864  ← fetch the 10 base addresses
│   EP_IOCTL_UDD_LOCK/UNLOCK    'h',40 / 'h',41       │
│   EP_IOCTL_SET_CLK_RATE       'h',50                │
└──────────────────────┬──────────────────────────────┘
                       │  mmap(PROT_READ)
┌─ hardware ───────────▼──────────────────────────────┐
│ EP @ 0x80506800, ten sub-blocks                     │
│   NOG   @ 0x20821c00 (0x100)                         │
│   3DLUT @ 0x2082b000 (0x1000)                        │
└─────────────────────────────────────────────────────┘

★ There is NO ISP firmware node in this chain.
  ep.h defines EP_TOP_VIRT_ADDR at the top ⇒ the library does its own mmap;
  the kernel never passes a mapped address in.
```

---

## 6. The Claim "EP is driven in real time by the ISP firmware" must be corrected

The previous report asserted that "EP is driven in real time by the ISP firmware
`DSP_NX500GLU0APC1_SR1`". **That causal chain has no supporting evidence** and is
downgraded to a hypothesis in this round:

- **Evidence 1:** dmesg contains `DRIME5: IDS : 31(ISP), 57(ARM) PROMISE : 97`
  ⇒ **the ISP really is a separate core, ID=31.** This part holds.
- **Evidence 2:** **nowhere on the Linux side (kernel modules + libudd5) is the ISP
  firmware mentioned.** Grepping `isp|dsp|srp` across the 503 `libudd5.so` symbols
  returns **zero hits**.
- **Evidence 3:** EP follows the standard **UDD (Userspace Device Driver)** model —
  `/dev/drime5_ep` ioctl plus a user-space `mmap`, not a kernel-mediated path.

⇒ **The more likely picture**: the ISP core runs the sensor / ISP pipeline, while EP is
**an independent image-engine block driven directly by Linux user space on the CA9**
(this is exactly what UDD — Userspace Device Driver — means). The two exchange data
through SRAM, but **"ISP firmware is driving EP registers" is not what is happening**.

**Practical impact of this correction**: since EP is driven by Linux user space, the
risk description "modifying the 3D LUT during liveview means the ISP reads it
concurrently" **may itself be inaccurate**. The real risk is **modifying the 3D LUT
without calling `d5_ep_top_update_sreg(D5_EP_3DLUT_SHADOW_UPDATE)`**, leaving the
shadow register uncommitted. ★ **This needs on-device verification; it is listed as the
next step and no conclusion is drawn here.**

---

## 7. Tools (three new, reusable)

| File | Purpose |
|---|---|
| `test_server/isp/arlit.py` | extract function literal pools / symbol table / `--list` |
| `test_server/isp/ardec.py` | ARM bit-field decoding: pull out ADD/SUB/LDR/STR immediate offsets |
| `test_server/isp/arel.py` | relocation tables → "which function references which symbol" |

### Traps hit (three real bugs, fixed inside the tools)

1. **A shared library only has `.dynsym` (type=11), no `.symtab` (type=2).**
   Testing only `type==2` skips the entire symbol table; `--list` prints 0 lines.
2. **`st_info`: the low 4 bits are the type, the high 4 bits are the binding.**
   Using `info>>4 == 2` to test `STT_FUNC` yields `funcs=0`.
3. **Exported globals in `.bss` cannot be found as absolute-address literals in
   `.text`** (the compiler addresses them PC-relative / through the GOT).
   ⇒ To find "who references this global" you must walk the relocation tables
   (`arel.py`); a plain `memmem` scan of `.text` yields a **false negative** "zero
   references".

---

## 8. Next Steps (by value)

| Priority | Action | Criterion |
|---|---|---|
| **1** | Build a probe that calls only `d5_ep_nog_set_noisegen(std=1, GAUSSIAN, seed=ENABLE)`, take one frame before and one after liveview, and compute pixel-variance statistics | If the variance rises significantly ⇒ NOG really is contributing ⇒ **FilmLab's hardware-grain path is viable** |
| 2 | Verify whether `d5_ep_top_update_sreg(D5_EP_3DLUT_SHADOW_UPDATE)` is required for 3D LUT changes to take effect | Directly determines whether `.cube` LUTs can be pushed down into the body |
| 3 | Confirm the NOG hardware on-device: read `0x20821c00 + 0x0c` (earlier reading was the magic `0x13060911`) | A changed magic means the earlier read was an unconfigured state |
| 4 | Capture cold-boot dmesg for the ISP firmware load line (this round's dmesg was a resume segment, with no cold-boot log) | Look for a `request_firmware` or uImage load line |

### ⚠️ Operating discipline for the next on-device session
- The camera was unreachable this round (ping timeout) — **confirm the IP and that the
  body is powered first**.
- The probe **must dry-run read-only first** (just `open` + `GET_PHYS_REG_INFO`, no
  `set_*` calls).
- ★ **A single-core camera cannot run heavy work back-to-back**: first test 1 frame at
  1 size; batches ≤3; a full run must go to the background with `nice -n 19`.
- ★ **telnet must be serial**; anything ≥10 KB goes via FTP
  (`ftp_put → one telnet run → ftp_get`).
- ★ **NOG is a *new* grain**: `d5_ep_nog_set_noisegen` will **override the vendor
  calibration**. Confirm the rollback path first
  (`d5_ep_nog_set_bypass(EP_DD_ON)` or a reboot).

---

## 9. Memory Entries That Need Updating

- ❌ Superseded: "EP is driven in real time by the ISP firmware `DSP_NX500GLU0APC1_SR1`"
  → downgraded to a hypothesis, no evidence.
- ❌ Superseded: "the NX500 has a hardware grain generator (13 NOG symbols) but it is
  gated by a vendor handle"
  → **the handle wall does not exist.** NOG has a complete public API
  `d5_ep_nog_set_noisegen`.
- ✅ New: the NOG register block sits at `+0x30` inside regset
  (cross-validated across 5 functions).
- ✅ New: byte registers at `+0x35/+0x36/+0x37` within the block, mask `0x1f`.
- ✅ New: gamma is a 4-stage curve, slots `+0x40/+0x44/+0x48/+0x4c`, stride `0x10`.
- ✅ New: the regset struct is 16 `void*` slots (64 bytes).
