# NX-KS2 · 错误结论修正报告（2026-10-07）

> **目的**：用逆向/解包工具**主动复核**三层（固件层 / 系统层 / mod 层）的历史结论，
> 找出**被写进档案但是错的**判断，标注**根因**（哪条搜索通路失配），给出**正确版**。
> **方法**：capstone 5.0.9 全量反汇编 + pyelftools ELF 解析 + LZMA/gzip 解包 + 结构化头部解析 + MOV/MOVW/MOVT 常量重建。
> **纪律**：每条修正都给出**可复现的命令/证据**，不接受"我觉得"。

---

## 0. 修正总表（先看这个）

| # | 原结论（错） | 正确结论 | 层 | 严重度 |
|---|---|---|---|---|
| C1 | `mod_gui` 的 `key_down_callback` **只认 13 键**（F6~F10/KP_Home/Scroll_Lock/…）| ★ **只认 4 个 keysym**：`Super_L`/`Super_R`/`Menu`/`XF86PowerOff` | mod | ★★★★★ **推翻整个"波轮无解"论证链** |
| C2 | "13 键"来源 = `mod_gui.c` | ★ 来源是 **`keyinput.js`**（Web 遥控键映射，58 keysym）——**跨文件误植** | mod | ★★★★★ |
| C3 | p7 里**没有任何 EP 物理基址字面量** | ★ p7 有 **342 个 EP 寄存器访问**（MOV/MOVW+MOVT 立即数） | 固件 | ★★★★★ **旧搜索通路失配** |
| C4 | "EP 地址在 p7 里是**指令立即数**"（我上一轮的"修正"）| ★ 不精确：编码形态是 **MOV/MOVW + MOVT 配对**，**不是**单条立即数，也**不是**字面量池 | 固件 | ★★★★ |
| C5 | SMA `0x94000000` 在 p7 里是**死数据、无人引用** | ✅ **成立**（全镜像该常量仅出现 1 次，位于段表；**0 条代码引用**） | 固件 | ★★★ 确认（非修正）|
| C6 | `p6`/`p13` 是**主/备份两份同一内核** | ★ 是**两个不同工程师、不同构建号的内核**（`#7` vs `#1183`）；运行的是 p6 | 系统 | ★★★★ |
| C7 | `p7` 有效长度 `0xb8427b` | ★ `0xb8427c`（12075644）—— **off-by-one** | 系统 | ★★ |
| C8 | "1.13 固件"是本项目的重要参考基准 | ★ v1.13 == v1.12，**唯一差异是版本字符串 1 字节**（352MB 中只差 1 字节）| 系统 | ★★★ |
| C9 | p7 的 3DLUT 基址 `0x2082b000` 无引用 | ★ **有**（`mov r3,#0xb000; movt r3,#0x2082`）| 固件 | ★★★ 同 C3 根因 |

---

## 1. mod 层修正（C1 / C2）★ 最重要

### 1.1 原始错误结论

被写进**至少 6 处**文档/记忆（`ironclad-rules.md:968`、`MEMORY.md:59`、`2026-10-05.md:654/694`、`2026-10-07.md:1138`、`CONSOLIDATED_REPORT_2026-10-05.md:301`）：

> `mod_gui.c` 的 `key_down_callback` 是一串 `if strcmp`，**只认 13 个键**
> （`F6~F10` / `KP_Home` / `Scroll_Lock` / `XF86PowerOff` / `Hiragana` / `Muhenkan` /
> `Control_R` / `Alt_R` / `Katakana` / `XF86Reload` / `XF86WWW` / `KP_Enter`），
> `Up/Down/Left/Right` 与 `JOG1_CW/CCW` 全落 `else → quit_app()`。
> ⇒ **波轮必须自写 UI**（"铁壁"）。

### 1.2 复核方法（可复现）

```bash
# 1) 确认项目里只有一个 mod_gui，且两份副本一致
md5sum backup_original/mod_gui scripts/mod_gui      # 都是 e4453d552e3604fd8e6bcbb81ad8008c

# 2) 穷举镜像内所有可能键名（含 F1..F12 / KP_* / Hiragana / Muhenkan / Scroll_Lock …）
python - <<'PY'
d=open('scripts/mod_gui','rb').read()
for k in ['F6','F7','F8','F9','F10','KP_Home','Scroll_Lock','Hiragana','Hiragana_Katakana',
          'Muhenkan','Katakana','Control_R','Alt_R','XF86Reload','XF86WWW','KP_Enter',
          'Super_L','Super_R','Menu','XF86PowerOff']:
    c=d.count(k.encode()+b'\x00')
    if c: print('present:',k,c)
PY
```

**输出**：
```
present: Super_L 1
present: Super_R 1
present: Menu 1
present: XF86PowerOff 1
```

### 1.3 正确结论

★★★ **`mod_gui`（md5 e4453d55）的键处理只认 4 个 X11 keysym**：

| keysym | 对应机身动作 | 证据 |
|---|---|---|
| `Super_R` | 右键 / 某种组合 | rodata VA `0xa9f8` |
| `Menu` | 菜单键 | rodata VA `0xaa00` |
| `Super_L` | 左键 / 某种组合 | rodata VA `0xaa08` |
| `XF86PowerOff` | 电源键 → 执行 `st key click pwoff` | rodata VA `0xaa10` + `0xaa20` |

这四个字符串在 `.rodata` 里**严格等距排列（8 字节步长）**，就是一个**硬编码比较数组**的形态。
**没有** `F6-F10`、**没有** `KP_Home`、**没有** `Scroll_Lock`、**没有** `Hiragana`。

### 1.4 错误根因（C2）

那串 "13 键" 的真实出处是 **`backup_original/nx-rc/web_root/js/keyinput.js`**
—— 一个 **Web 遥控的 keycode→keysym 映射表**，共 **58 个 keysym**：

```
F1 F3 F4 F6 F7 F8 F9 F10 Henkan_Mode Hiragana_Katakana KP_Delete KP_Down KP_Enter
KP_Home KP_Left KP_Right KP_Up Left Menu Right Scroll_Lock Super_L Super_R
XF86AudioNext … XF86WWW XF86WebCam …（共 58）
```

⇒ ★★★★★ **教训（新铁律 111）**：**"某函数只认 N 个键"这类结论，必须钉死到"哪个二进制、哪个字段"**。
本项目把 **Web 遥控 JS 的键表** 误当成了 **mod_gui 二进制的键处理器**，
并据此推出"波轮无解"—— 一个**假根因**支撑了后续大量设计决策
（自写 EFL UI、放弃 mod_gui）。

### 1.5 波及与修正动作

- `test_server/filmlab/src/nxfilmui.c` 头部注释（第 5-9 行）**照抄了这个错误** ⇒ 需改注释。
  （代码本身按 `strcmp` 名字匹配，功能可能仍工作，但**注释误导后续读者**。）
- ★ **"波轮在 mod_gui 层无解"这个判断需要重做**：已知 mod_gui 只认 4 keysym，
  但**波轮是否发 `Super_L/Super_R` 事件**尚未实测 ⇒ 这是**该上机验证**的开放点，
  而不是"铁壁"。

---

## 2. 固件层修正（C3 / C4 / C5 / C9）

### 2.1 原始错误结论（C3）

`raw8/p7/ghidra/31_ep_access.txt` 与多份档案写：

> `--- 0x20820000 --- (镜像里没有这个常量)`
> `--- 0x20821c00 --- (镜像里没有这个常量)`
> `--- 0x2082b000 --- (镜像里没有这个常量)`
> ⇒ p7 里**没有任何 EP 物理基址字面量**。

### 2.2 复核方法与结果

**错误根因**：p7 是 ARMv7，这些 32 位地址**从来不以"连续 4 字节常量"存在**，
而是编译器用 **`movw`/`movt`（或 `mov`/`movt`）两条指令**拼出来：

```asm
; FUN_004b6894 内部（ISP 参数块 A，0x20821300）
004b6924  movw  ip, #0x130c        ; 低 16 位
004b6928  add   r6, r6, r0, lsl #8
004b6938  movt  ip, #0x2082        ; 高 16 位  ⇒ ip = 0x2082130c
004b693c  ldr   ip, [r6, ip]       ; 真正访问 EP
```

```asm
; FUN_004cf3d4（3DLUT OnOff）
004cf3d4  mov   r3, #0xb000        ; 注意：这里用普通 MOV（不是 MOVW）
004cf3d8  movt  r3, #0x2082        ; ⇒ r3 = 0x2082b000
004cf3dc  ldr   r3, [r3]
```

**重建脚本**（同时覆盖 `mov` / `movw` + `movt` 两种形态）：

<details><summary>常量重建器（关键代码）</summary>

```python
import struct, collections
data=open('raw8/p7/p7_full.bin','rb').read(); N=len(data)
mov_bases=collections.defaultdict(list)
for a in range(0,N-4,4):
    w=struct.unpack_from('<I',data,a)[0]; rd=(w>>12)&0xf
    # MOV 立即数（0xE3A0_xxxx）
    if (w & 0x0FE00000)==0x03A00000:
        i12=w&0xfff; rot=((i12>>8)&0xf)*2
        v=((i12&0xff)>>rot)|((i12&0xff)<<(32-rot)) if rot else (i12&0xff)
        mov_bases[rd].append((a,v&0xffffffff))
    # MOVW（0xE30_xxxx）
    if (w & 0xFFF00000)==0xE3000000:
        mov_bases[rd].append((a, ((w>>16)&0xf)<<12|(w&0xfff)))
res=[]
for a in range(0,N-4,4):
    w=struct.unpack_from('<I',data,a)[0]; rd=(w>>12)&0xf
    if (w & 0xFFF00000)==0xE3400000:            # MOVT（0xE34_xxxx）
        hi=((w>>16)&0xf)<<12|(w&0xfff)
        for pa,pv in mov_bases.get(rd,[]):
            if 0<=a-pa<=32: res.append(((hi<<16)|(pv&0xffff),pa,a))
```
</details>

**输出（EP 范围 `0x2080_0000–0x208F_FFFF`）**：

```
EP unique consts: 342
  0x20800000 : 24      0x20821000 : 47   ← ISP 参数块 A（含 +04..+28）
  0x20801000 : 6       0x20821c00 : 12   ← NOG（+04..+4c）
  0x20805000 : 11      0x20823000 : 79   ← ldc
  0x20810000 : 39      0x20824000 : 3    ← mc
  0x20811000 : 3       0x20826000 : 84   ← rsz
  0x20820000 : 5       0x20829000 : 4    ← fd
  0x2082a000 : 4       0x2082b000 : 1    ← 3dlut
                       0x20830000 : 17
```

### 2.3 正确结论（C3 / C4 / C9）

★★★ **p7 直接访问至少 342 个 EP 寄存器**，覆盖 EP 全部 10 个子块。
且 **ISP 参数块 A `0x20821300`（47 个访问）与块 B `0x20821700` 的写入路径完全确证**：

- 块 A 全部写入来自函数地址区间 **`0x4b6894–0x4b6b6c`**（`FUN_004b6894`）
- 块 B 全部写入来自 **`0x4b6b98–0x4b6f50`**（`FUN_004b6b98`）
- 两者**位域布局逐位一致** ⇒ 同一 ISP 参数结构写到**两个不同寄存器基址**

**C4 精确化**：EP 地址的编码形态是 **`MOV/MOVW + MOVT` 配对**，
既不是"字面量池"，也不是"单条立即数"。
★ 因此**只说"是指令立即数"仍然会误导**——真正的判据是
**"32 位常量被拆成两条 16 位指令"**（新铁律 112）。

**C9**：3DLUT 基址 `0x2082b000` **有 1 处引用**（`FUN_004cf3d4/3fc/414`），
旧结论"无引用"是同一个 MOVW/MOVT 失配根因。

### 2.4 ISP 参数块 A 的完整位域（从源级读出，供魔灯使用）

```
FUN_004b6894(idx, param_2 /*struct*/, param_3 /*buf*/)
  base = 0x20821300 + (param_3?0x80:0) + idx*0x100     ; idx 0..0x14（21 槽，每槽 256B）
  +0x00 = param_2[0]
  +0x04 = param_2[1]   （条件成立时）
  +0x08 = param_2[2]&0x7ffff)<<0xc | (param_2[3]-8)>>1&7)<<8 | (param_2[4]&3)<<6
          | (*(u8*)(param_2+0x11)&3)<<4 | (*(u8*)(param_2+0x12)&3)
  +0x0c = old & 0xc00fffff | (param_2[6]&0x3ff)<<0x14
  +0x10 = old & 0xfffcf0bf | ((b2|b1<<1)&3)<<0x10 | ((u8)param_2[0x12]&0xf)<<8
  +0x18 = param_2[0xc]<<0x10 | param_2[0xd]&0xffff
  +0x1c = param_2[8]<<0x10  | param_2[9]&0xffff
  +0x20 = param_2[10]<<0x10 | param_2[0xb]&0xffff
  +0x24 = param_2[0xe]<<0x10| param_2[0xf]&0xffff
  +0x28 = (param_2[0x10]&0xff)<<8 | param_2[0x11]&0xff
  FUN_004ba6a8(idx & 0xff)     ; ★ commit/触发
```

★ 调用者 `FUN_0013cc18` 显示这是**多通道（至少 3 通道，描述符槽位 `+0xc9/+0x191/+0x259`）**
的参数恢复流程；槽位由 `FUN_004b6fa8(5/6/7,…)` 运行时分配。
`FUN_0013c498` 初始化 **8 个描述符槽**（`+0xc9,+0x191,+0x259,+0x310,+0x3c8,+0x480,+0x538,+0x5f0`，步长 0xc8），
全部置 `0xff`（=无效）。⇒ **p7 是 8 通道 ISP 流水线管理器**。

---

## 3. 系统层修正（C6 / C7 / C8）

### 3.1 C6 — p6/p13 不是"主/备份同一内核"

**原结论**（`topics/p7-isp-slp.md:38`）：
> p6/p13 都是 uImage 且 load==entry==0x86008000 ⇒ **主/备份两份内核**

**复核**（正确解 uImage 头 + 解压）：

| | p6（= `uImage`） | p13（= `rImage`） |
|---|---|---|
| magic | 0x27051956 ✓ | 0x27051956 ✓ |
| load == entry | 0x86008000 ✓ | 0x86008000 ✓ |
| compression | **5 = LZMA** | **5 = LZMA** |
| payload size | 3175976 | 6169752 |
| 解压后 | 7 474 108 (7.13MB) | 9 201 060 (8.77MB) |
| 构建者 | `hs2704.sung@SWDA7604` | `js0924.lee@SWDA7604` |
| 构建号 | **#7** | **#1183** |
| 构建时间 | Wed Jun 3 14:40:29 KST 2015 | Thu Jun 4 13:06:24 KST 2015 |
| 4KB 块匹配率（p6 vs p13） | colspan=2> **0.1%**（完全不同的镜像） | |

**运行中的系统**：`uname -a` = `Linux drime5 3.5.0 #7 PREEMPT Wed Jun 3 14:40:29 KST 2015`
⇒ ★ **运行的是 p6**。

**正确结论**：p6 与 p13 是 **两个独立构建的内核**（不同人、不同构建号、相差一天），
**不是同一内核的主/备副本**。p13（`rImage`，"recovery image"）更可能是**恢复/备用内核**，
但**不能**假设它与 p6 内容一致 —— 任何"刷 p13 等于刷 p6"的推演都是**错的**。

★ 影响：**刷机策略**。若计划改内核，必须明确目标分区（p6 是当前运行项）。

### 3.2 C7 — p7 有效长度 off-by-one

| 来源 | 值 | 字节数 |
|---|---|---|
| 旧记忆 | `0xb8427b` | 12075643 |
| ★ 实测 | **`0xb8427c`** | **12075644** |

（`p7_full.bin` = 12.25MB 切片的前 0xb8427c 字节有效；差异 1 字节，通常是长度字段含/不含终止符。）

### 3.3 C8 — "1.13 固件"是无效参考

**原隐含假设**：`.uploads/fw/nx500_v1.13.bin` 是值得对比的新版本。

**复核**（`slp-firmware.py -p` + 逐块字节比较）：

```
v1.12 NX500.bin : 352121435 B  md5 df08b6f802d548ed03bb9e974c9a9bbd
v1.13 nx500.bin : 352121435 B  md5 a8509338e574319314ba9daa13994c4d

10 个 SLP 分区：长度 + CRC ★ 全部一致
全部差异：仅 64KB 块 0x0 中 1 字节  ⇒  0x07: 0x32('2') → 0x33('3')
                                 ⇒  版本字符串 "1.12" → "1.13"
```

**正确结论**：v1.13 与 v1.12 **在功能上完全相同**，只改了版本字符串。
⇒ ★ **任何"1.13 新增了 X"的推断都是错的**；版本校验是**纯字符串比较**
（这对改固件是**有利**信息：改版本号即可绕过版本检查）。

---

## 4. 确认正确（本轮复核后**维持**的关键结论）

| 结论 | 复核方法 | 状态 |
|---|---|---|
| SMA `0x94000000` 在 p7 中是**死数据**（段表条目，0 代码引用）| 全镜像字面量计数：命中 1 次（@0x9fc0）；LDR-literal 重建：0 引用 | ✅ 维持（**推翻** Ghidra "82 data refs" 的假阳性）|
| `mod_gui` 能力上限：只 4 控件 / 2 列网格 / 点击即退 / 动作只 `system("%s &")` | 字符串表：`elm_win/table/button/check`、`Exiting the app.`、`%s &` | ✅ 维持 |
| p7 = 三星自研 ISP IP（Cortex-A9 + MMU）| `DAT_00000230=0xc09`；Ghidra language `ARM:LE:32:v7` | ✅ 维持 |
| ISP 参数块 = **寄存器直写 ⇒ 不刷固件**（魔灯路径 B 可逆）| `FUN_004b6894` 无 flash 调用，纯 `str [reg]` | ✅ 维持 |

---

## 5. 新增/修订铁律

- **111 ★★★★★** "某函数只认 N 个键/只有 M 种输入"—— 必须**钉死到具体二进制 + 具体字段**，
  并给出**穷举反例检验**（把所有候选键名全试一遍 count==0）。
  **禁止**把同项目里**另一个文件**（如 Web 遥控 JS）的表当成目标二进制的行为。
  > 本项目错误示例：把 `keyinput.js`（Web 遥控，58 keysym）误当 `mod_gui`（真值 4 keysym），
  > 据此推出"波轮无解"，误导后续 2 天设计。

- **112 ★★★★★** ARMv7 上搜索 32 位常量（寄存器/外设基址）时，
  **必须同时覆盖 `MOV/MOVW` + `MOVT` 配对形态**，
  不能只搜"连续 4 字节字面量"，也不能只搜"已定义标量"。
  > 正确性判据：`movw rD,#lo` …(≤32B)… `movt rD,#hi` ⇒ 常量 = `(hi<<16)|lo`。

- **107（修订）** 原条"EP 地址是指令立即数"**改为**：
  "EP 地址由 **MOV/MOVW+MOVT 配对**在指令流里构造；
  伪代码（Ghidra）优先于裸字节搜索，因为伪代码已把配对折叠回常量。"

---

## 6. 待验证（静态不可判定，需上机）

| # | 待验证 | 为什么静态判不了 |
|---|---|---|
| V1 | 波轮（JOG）在机身是否发出 `Super_L/Super_R` 事件 | 需 ecore 日志看实际 keysym |
| V2 | mod_gui 在机身对 `Super_L/Super_R` 是否真的响应 | 需在机上按 |
| V3 | ISP 参数块 A/B 的写入是否可由**用户操作**触发（路径 B 前提）| 需 dump `iqr` 全 184 个 `eIQ_ID_*` 关联 |

---

*生成：2026-10-07 · 工具：capstone 5.0.9 / pyelftools 0.33 / Python 3.13.12 / slp-firmware.py*
