# MCB 命令号 × 名字 —— 静态枚举全表（2026-10-08 · D4/U02）

> 承接 [`MCB_PROTOCOL_AND_ST_TABLE_2026-10-08.md`](MCB_PROTOCOL_AND_ST_TABLE_2026-10-08.md) §3.3（当时只有 mcbtest `capture_command_string` 的 ~40 条采样）。
> 本篇给出**静态枚举表的实锤位置**与**8 域 68 条全表**。
> 机器可读全表：`raw8/repro/mcb_command_enum_table.txt`。原始证据：`raw8/repro/capfw/`。

---

## 0. 一句话结论

**静态枚举表不是 `{u16 id, char* name}` 数组，而是导出函数 `capture_command_string`（`libcapture-fw-prod.so`，VA `0x511e0`，2152 B，编译成二分 if-switch）；名字串按"域 + 命令号"顺序连续排在 `.rodata 0xa34b8..0xa39d8`。它在 `OperateCapture@0x46b58` 处经 `mcb_debug_set_command_name_function` 注册进 MCB 层。据此重建出覆盖全部 8 个域、共 68 条命令号↔名字的完整表**（比旧采样 40 条新增 28 条，零冲突）。

- 8 域全覆盖：`SYS_`(7) `STILL_`(14) `LV_`(15) `MOVIE_`(4) `LENS_`(6) `QUICKPB_`(4) `FLASH_`(7) `PRD_`(11) = **68**
- 名字**整串存储**（如 `SYS_CIS_CLEANING` 是单串，非"前缀+后缀"拼接）——此前"名字不是整串存的"猜测**证伪**（见 §4）
- 唯一的空洞：`LENS_ 0x506–0x508`（枚举内无定义，落入 `unknown`）

## 1. 表结构与反汇编证据（硬证据）

### 1.1 宿主与定位

| 项 | 值 |
|---|---|
| 文件 | `/opt/nxks2/rootfs-112/usr/lib/libcapture-fw-prod.so`（734600 B，ARM EABI5，**stripped**） |
| MD5 | `78765796c0003f1a84c51bc67b3b2ef4`（实测 `md5sum`）|
| 函数 | `capture_command_string`，**导出**符号，VA `0x511e0`，size **2152**（`readelf -sW` 第 247 项）|
| 文件偏移 | `0x511e0`（本 .so 段 VA==文件偏移，无独立基址：`.text` Addr/Off 均 `0x28560`）|
| 名字串池 | `.rodata` VA `0xa34b8`(`SYS_CIS_CLEANING`) … `0xa39d8`(`PRD_ADJUST_REQUEST_DONE`) 连续排列 |
| 字面量池 | `0x5192c..0x51a44`（每个 case 的名字指针来源）|

调用链证据（注册点）：
```
46b50: ldr r3,[r4,r3]; mov r0,r3
46b58: bl 25f50 <mcb_debug_set_command_name_function@plt>   ; ← 注册 capture_command_string
```

### 1.2 结构 = 二分比较树 + 字面量池

`capture_command_string(int cmd)` 被编译成对命令号的**二分 if-else 树**（不是跳转表、更不是数据表）。每个命中分支形如：

```
51254: beq 515d0            ; cmd == 0x102 → 叶子 515d0
...
515d0: ldr r3, [pc, #856]   @ 51930        ; 取字面量(相对偏移)
515d4: add r3, pc, r3                      ; r3 = 名字指针
515d8: b   51920                           ; 公共返回
```
- 字面量池 `0x5192c..0x51a44` 存的是"相对 add 指令 PC 的偏移"；
  **名字 VA = (add 指令地址 + 8) + 字面量 = (ldr 地址 + 12) + 字面量**。
  验证：`0x515c4 + 12 + 0x00051ee8 = 0xa34b8` = `SYS_CIS_CLEANING` ✅
- 未命中分支统一跳到 `518f4`，用 `sprintf(buf, "0x%x", cmd)` 落 `DAT_000b3180`（即 `unknown` 缓冲）。

### 1.3 名字串池 = 按枚举序排列（关键旁证）

`.rodata 0xa34b8` 起，名字严格按 `域 → 命令号升序` 连续存放，与"枚举定义序"一致：

```
a34b8 SYS_CIS_CLEANING / a34cc SYS_CONTROL_STROBE / a34e0 SYS_RESET / a34ec SYS_CHANGE_MODE
a34fc SYS_FILEDUMP_ACK / a3510 SYS_POWER_SAVE / a3520 SYS_POWER_OFF
a3530 STILL_START_CAPTURE / … / a3634 STILL_SET_AEL_BV
a3648 LV_START / … / a3738 LV_FD_FREEZE
a3748 MOVIE_START_RECORDING / … / a3790 MOVIE_TOUCH_AF
a37a0 LENS_POWER_ZOOM / … / a37f4 LENS_SET_MF_POSITION
a380c QUICKPB_CHECK_IMAGE / … / a3844 QUICKPB_DELETE_FILE
a3858 FLASH_EXT_HSS_ONOFF / … / a38d8 FLASH_EXT_DISPLAY_FNO
a38f0 PRD_CONTROL / … / a39c0 PRD_ADJUST_REQUEST_DONE
```

### 1.4 "不存在 {id,name} 表"的反证（硬证据）

- `readelf -rW`：全 .so 共 **1287 条 `.rel.dyn`**（另约 1000 条 `.rel.plt`），其中**指向名字池(0xa34b8–0xa3a00)的重定位 = 0 条**（`raw8/repro/capfw/reldump.txt`）。⇒ 没有任何数据段的指针数组引用这些名字。
- 名字的唯一引用者 = `capture_command_string` 函数内字面量池。
- `libmulticore-bridge.so` 内**无**任何 8 域名字串（全 rootfs grep：仅 `usr/bin/mcbtest` 与 `usr/lib/libcapture-fw-prod.so` 含 `SYS_CIS_CLEANING`）。

## 2. 全表（68 条 · 硬证据）

> 完整机器可读版含 `leaf VA / str VA`：`raw8/repro/mcb_command_enum_table.txt`。下表 `源` = `capture_command_string` 叶子地址 @ `str` 串地址。

### SYS_（域 0x01，基址 0x100）
| cmd | 名字 | 源 |
|---|---|---|
| 0x101 | SYS_CIS_CLEANING | leaf 0x515c4 / str 0xa34b8 |
| 0x102 | SYS_CONTROL_STROBE | 0x515d0 / 0xa34cc |
| 0x103 | SYS_RESET | 0x515dc / 0xa34e0 |
| 0x104 | SYS_CHANGE_MODE | 0x515e8 / 0xa34ec |
| 0x105 | SYS_FILEDUMP_ACK | 0x515f4 / 0xa34fc |
| 0x106 | SYS_POWER_SAVE | 0x51600 / 0xa3510 |
| 0x107 | SYS_POWER_OFF | 0x5160c / 0xa3520 |

### STILL_（域 0x02，基址 0x200）
| cmd | 名字 | 源 |
|---|---|---|
| 0x201 | STILL_START_CAPTURE | 0x51618 / 0xa3530 |
| 0x202 | STILL_STOP_CAPTURE | 0x51624 / 0xa3544 |
| 0x203 | STILL_CANCEL_QVIEW | 0x51630 / 0xa3558 |
| 0x204 | STILL_LOCK_AEAF | 0x5163c / 0xa356c |
| 0x205 | STILL_LOCK3A | 0x51648 / 0xa357c |
| 0x206 | STILL_CAF | 0x51654 / 0xa358c |
| 0x207 | STILL_MOVIE_AF | 0x51660 / 0xa3598 |
| 0x208 | STILL_TOUCH_AF | 0x5166c / 0xa35a8 |
| 0x209 | STILL_TRACKING_AF | 0x51678 / 0xa35b8 |
| 0x20a | STILL_SELECT_IMAGE_BEST_FACE | 0x51684 / 0xa35cc |
| 0x20b | STILL_SELECT_FACE_BEST_FACE | 0x51690 / 0xa35ec |
| 0x20c | STILL_RELEASE_BUFFER | 0x5169c / 0xa3608 |
| 0x20d | STILL_PROGRAM_SHIFT | 0x516a8 / 0xa3620 |
| 0x20e | STILL_SET_AEL_BV | 0x516b4 / 0xa3634 |

### LV_（域 0x03，基址 0x300）
| cmd | 名字 | 源 |
|---|---|---|
| 0x301 | LV_START | 0x516c0 / 0xa3648 |
| 0x302 | LV_STOP | 0x516cc / 0xa3654 |
| 0x303 | LV_FACE_DETECTION | 0x516d8 / 0xa365c |
| 0x304 | LV_SCENE_DETECTION | 0x516e4 / 0xa3670 |
| 0x305 | LV_OBJECT_TRACKING | 0x516f0 / 0xa3684 |
| 0x306 | LV_OPTICAL_PREVIEW | 0x516fc / 0xa3698 |
| 0x307 | LV_MF_ENLARGE | 0x51708 / 0xa36ac |
| 0x308 | LV_IFN_ENABLE | 0x51714 / 0xa36bc |
| 0x309 | LV_PREPARE | 0x51720 / 0xa36cc |
| 0x30a | LV_SET_CENTER_AF | 0x5172c / 0xa36d8 |
| 0x30b | LV_OBJECT_TRACKING_HOLD | 0x51738 / 0xa36ec |
| 0x30c | LV_ZEBRA_CTRL | 0x51744 / 0xa3704 |
| 0x30d | LV_PANORAMA_DISPLAY | 0x51750 / 0xa3714 |
| 0x30e | LV_FD_SELFIE | 0x5175c / 0xa3728 |
| 0x30f | LV_FD_FREEZE | 0x51768 / 0xa3738 |

### MOVIE_（域 0x04，基址 0x400）
| cmd | 名字 | 源 |
|---|---|---|
| 0x401 | MOVIE_START_RECORDING | 0x51774 / 0xa3748 |
| 0x402 | MOVIE_STOP_RECORDING | 0x51780 / 0xa3760 |
| 0x403 | MOVIE_FRAMING_CAPTURE | 0x5178c / 0xa3778 |
| 0x404 | MOVIE_TOUCH_AF | 0x51798 / 0xa3790 |

### LENS_（域 0x05，基址 0x500；⚠ 0x506–0x508 空洞）
| cmd | 名字 | 源 |
|---|---|---|
| 0x501 | LENS_POWER_ZOOM | 0x517a4 / 0xa37a0 |
| 0x502 | LENS_SET_OIS | 0x517b0 / 0xa37b0 |
| 0x503 | LENS_MF_PERMISSION | 0x517bc / 0xa37c0 |
| 0x504 | LENS_3D_MODE | 0x517c8 / 0xa37d4 |
| 0x505 | LENS_FW_UPDATE | 0x517d4 / 0xa37e4 |
| 0x509 | LENS_SET_MF_POSITION | 0x517e0 / 0xa37f4 |

### QUICKPB_（域 0x06，基址 0x600）
| cmd | 名字 | 源 |
|---|---|---|
| 0x601 | QUICKPB_CHECK_IMAGE | 0x517ec / 0xa380c |
| 0x602 | QUICKPB_PB_REQUEST | 0x517f8 / 0xa3820 |
| 0x603 | QUICKPB_ZOOM | 0x51804 / 0xa3834 |
| 0x604 | QUICKPB_DELETE_FILE | 0x51810 / 0xa3844 |

### FLASH_（域 0x07，基址 0x700）
| cmd | 名字 | 源 |
|---|---|---|
| 0x701 | FLASH_EXT_HSS_ONOFF | 0x5181c / 0xa3858 |
| 0x702 | FLASH_EXT_MANUAL_ONOFF | 0x51828 / 0xa386c |
| 0x703 | FLASH_EXT_MULTI_ONOFF | 0x51834 / 0xa3884 |
| 0x704 | FLASH_EXT_EV | 0x51840 / 0xa389c |
| 0x705 | FLASH_EXT_GROUP_MODE | 0x5184c / 0xa38ac |
| 0x706 | FLASH_EXT_GROUP_EV | 0x51858 / 0xa38c4 |
| 0x707 | FLASH_EXT_DISPLAY_FNO | 0x51864 / 0xa38d8 |

### PRD_ 生产域（域 0xaa，基址 0xaa00；实号 0xaa01–0xaa0b）
| cmd | 名字 | 源 |
|---|---|---|
| 0xaa01 | PRD_CONTROL | 0x51870 / 0xa38f0 |
| 0xaa02 | PRD_BYPASS_SCRIPT | 0x5187c / 0xa38fc |
| 0xaa03 | PRD_WRITE_RESULT_TO_NAND | 0x51888 / 0xa3910 |
| 0xaa04 | PRD_WRITE_RESULT_TO_CSV | 0x51894 / 0xa392c |
| 0xaa05 | PRD_SET_FOCUS_POSITION | 0x518a0 / 0xa3944 |
| 0xaa06 | PRD_SET_AF_LED | 0x518ac / 0xa395c |
| 0xaa07 | PRD_WRITE_LOG_TO_NAND | 0x518b8 / 0xa396c |
| 0xaa08 | PRD_CAPTURE_YUV | 0x518c4 / 0xa3984 |
| 0xaa09 | PRD_CAPTURE_RAW_SSIF | 0x518d0 / 0xa3994 |
| 0xaa0a | PRD_CAPTURE_RAW_PP | 0x518dc / 0xa39ac |
| 0xaa0b | PRD_ADJUST_REQUEST_DONE | 0x518e8 / 0xa39c0 |

## 3. 与旧采样对比（新增 28 / 纠正 0 / 冲突 0）

旧采样 = `mcbtest` 的 `capture_command_string@0x34e2c`（1868 B，比本表**小**），共 40 条（`raw8/repro/mcb_command_dict_raw.txt`）。

- **本次静态重建 = 68 条**，旧 40 条**全部命中且号一致（0 冲突）**。
- **新增 28 条**（旧 switch 采样缺失——它们多来自二分树的 `bgt/blt` **边界叶子**，旧工只抓了显式 `==` 比较，边界情况漏采）：

| 域 | 新增 |
|---|---|
| SYS_ | 0x103 SYS_RESET、0x105 SYS_FILEDUMP_ACK |
| STILL_ | 0x202 STILL_STOP_CAPTURE、0x204 STILL_LOCK_AEAF、0x206 STILL_CAF、0x20b STILL_SELECT_FACE_BEST_FACE、0x20d STILL_PROGRAM_SHIFT |
| LV_ | 0x303 LV_FACE_DETECTION、0x305 LV_OBJECT_TRACKING、0x307 LV_MF_ENLARGE、0x309 LV_PREPARE、0x30e LV_FD_SELFIE |
| MOVIE_ | 0x403 MOVIE_FRAMING_CAPTURE |
| LENS_ | 0x503 LENS_MF_PERMISSION |
| FLASH_ | 0x702 FLASH_EXT_MANUAL_ONOFF、0x704 FLASH_EXT_EV、0x706 FLASH_EXT_GROUP_EV |
| **PRD_** | **全部 11 条**（0xaa01–0xaa0b；旧采样只标了"PRD_ 若干"无号无全名）|

- **纠正**：旧结论"ID 空间 0xaaXX"→ 精确为 **0xaa01–0xaa0b 密集**；旧"PRD_…"漏名 → 全部补齐、定号。

## 4. 未覆盖 / 推断 / 证伪项

| 项 | 结论 | 类别 |
|---|---|---|
| "名字不是整串存的、前缀+后缀分别存储" | **证伪**。名字均为单条整串（`SYS_CIS_CLEANING` 一个串），无前缀/后缀拆分表；`GetSubIDName` 的"域基址+子号"拼装只存在于 **libmulticore-bridge.so 的 MCC 类别层**（见 §5），与本 8 域无关 | 硬证据（证伪） |
| LENS_ 0x506 / 0x507 / 0x508 | 枚举内无定义，`capture_command_string` 返回 `0x506` 等十六进制 | 硬证据（空洞） |
| 各域未列号（如 SYS_ 0x108+、STILL_ 0x20f+…） | 该函数不覆盖 ⇒ 视为未定义/不存在 | 推断 |
| 现场活跃号 0xB0/0xB1/0xB6 | **不在本表**：它们属于 MCC **类别(CID)** 层，名字在 `libmulticore-bridge.so`（§5） | 硬证据（分层） |

## 5. 分层澄清（避免再混淆）

MCB 有**两个独立的编号空间**，此前文档易混：

1. **业务命令号（本篇 8 域 68 条）**：`SYS_/STILL_/…/PRD_`，名字解析器 = `libcapture-fw-prod.so::capture_command_string`（本表）。这是相机业务通过 MCB 下发的命令。
2. **传输类别号 CID（0x10–0xF5，33 条）**：名字解析器 = `libmulticore-bridge.so::CIPCCDriverIf::GetCIDName(int)` @ VA `0x5304`（size 1512，readelf -sW；同为 if-switch），映射：
   `0x10 SYSTEM_POWER_ON_DONE / 0x11 NX_SET_ID / 0x12 IPCC_INTERFACE_VERSION / 0x13 FIRMWARE_VERSION / 0x14 SYSTEM_INIT_DONE / 0x20 SYSTEM_POWER_OFF_REQUEST / … / 0x83 COMMAND / 0x84 COMMAND_ACK / 0xb0 LOG_START / 0xb1 LOG_STOP / 0xb6 SHELL_COMMAND / 0xe0 ERROR / 0xf0..0xf5 FIRMWARE_UPDATE_*`。
   → 现场 0xB0/0xB1=LOG_START/STOP、0xB6=SHELL_COMMAND（`st cap` 走的正是 SHELL_COMMAND）。**此处"名字是整串存的"**，`GetSubIDName`/`MakeString` 只做"CID 名 + `0x`子号"拼接（`%s:0x%x`）。

**旁证（handler 表，非名字表）**：`libcapture-fw-prod.so` `.data` 中有一批 **R_ARM_ABS32 静态函数指针表**（`raw8/repro/capfw/handler_tables.txt`）。`CNotifyHandler::arpCategoryTbl`（11 项）给出 MCB 业务**类别枚举**：
`0=Empty, 1=System, 2=Still, 3=Liveview, 4=Movie, 5=Lens, 6=QuickPB, 7=Strobe, 8=Shutter, 9=Operation, 10=Production`；
各 `arp*NtfyFnc` 表按子号索引到 handler（如 `arpStillNtfyFnc` 42 项）。⇒ 与 8 个名字域**大体对应但不等价**（Strobe/Shutter 拆开、多出 Operation/Production），说明"域"是命名分组、类别是派发分组。

## 6. 复现步骤

```bash
# 1) WSL rootfs-112 中导出目标 .so
MSYS_NO_PATHCONV=1 wsl -d NXKS2 -u root -- bash -lc \
  'cp /opt/nxks2/rootfs-112/usr/lib/libcapture-fw-prod.so \
      /mnt/d/download/NX-KS2-88/raw8/repro/capfw/'

# 2) 反汇编命令名解析器（VA==off，0x511e0 起 2152B，含字面量池）
arm-linux-gnueabihf-objdump -d --start-address=0x511e0 --stop-address=0x51a48 \
  libcapture-fw-prod.so > ccs_disasm.txt

# 3) 重建 id->name（脚本内解析二分树 + 字面量池）
python3 raw8/repro/parse_ccs.py      # -> raw8/repro/mcb_command_enum_table.txt (68 行)
python3 raw8/repro/dump_tables.py    # .data 表内容
python3 raw8/repro/parse_handler_tables.py  # handler 表(读 capfw/reldump.txt)

# 4) 反证：无 {id,name} 指针表
readelf -rW libcapture-fw-prod.so | grep -cE 'a3[4-9][0-9a-f]{2}'   # => 0
```

**证据文件清单（raw8/repro/capfw/）**：`libcapture-fw-prod.so`、`mcbtest`、`ccs_disasm.txt`(函数+字面量池反汇编)、`enum_ccs_capfw.tsv`(中间结果)、`strings.txt`(节选)、`reldump.txt`(重定位)、`handler_tables.txt`。
脚本：`raw8/repro/{parse_ccs.py, dump_tables.py, parse_handler_tables.py, wsl_probe_*.sh}`。

## 7. 置信度分栏

- **硬证据（可直接引用）**：§1 全部（函数地址/大小、字面量池→串地址公式、串池连续序、0 指针重定位、注册点 0x46b58）、§2 全表 68 条（每条给 leaf/str 双地址）、§5 两个编号空间与 GetCIDName 33 条、handler 类别表。
- **推断**：各域"未列号即不存在"（基于该函数覆盖率）；LENS 0x506–0x508 空洞的非存在性。
- **证伪**：§4 首行"名字非整串存放"。
