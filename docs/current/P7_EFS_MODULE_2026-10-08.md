# p7 的 EFS 模块 —— 逆向分析（2026-10-08）

> 承接 `P8_ZERO_INVESTIGATION_2026-10-08.md`（p8 全零调查）。该文把"p8 = RTOS 侧 EFS 的持久化区"
> 列为**待定的推断（U-a）**。本篇用 **Ghidra 伪代码 + objdump + 引用面脚本**把 EFS 模块打开，
> 结论**推翻了那条推断**：**EFS 根本不写 eMMC 分区**。
> 全程离线，未触碰相机。

---

## 0. 一句话结论

> ★★★★ **p7 的 EFS 模块 = 一个 15,144 B 的独立函数 `FUN_000765b0`**
> （日志标签 `CAP_EFS` / `AdjMainFunc`，源文件线索 `product/CaptureInterface/CapAdjIf.cpp`，
> 类名 `CEfsController`），它是一套**工厂校准数据的计算 + 落盘例程**。
>
> ★★★★★ **而它的"`nand_write`"并不是写 NAND/eMMC 分区，而是写 MMIO 寄存器窗口 `0x85601000`**：
> 4 次 `FUN_0004d518(offset, 0x85601000, val, 4, 1)`，offset = `0x3e / 0x42 / 0x46 / 0x4a`。
> ⇒ **p8（rtos_data）不是 EFS 的落点** ⇒ 上一轮"p8 = EFS 持久化区"的推断**撤销**；
> 「p8 从未被任何组件写入」这一结论**被进一步加强**。

---

## 1. 方法（用了哪些逆向工具 / 怎么用的）

| 工具 | 用途 | 关键点 |
|---|---|---|
| **引用面脚本**（自写 Python，铁律 112 的 MOV/MOVW+MOVT 重建） | ① 找"谁引用 EFS 数据区" ② 找硬件常量 | 发现 165 处 LDR 全落**同一函数** |
| **Ghidra 伪代码**（`raw8/p7/ghidra/53_all_pseudocode.c`，7073 函数） | 读 `FUN_000765b0` 全文、子函数、调用链 | ★ **索引 `52_pseudocode_index.txt` 的 `out_line` 是"函数序号"不是行号** —— 必须按 `grep -n "// ==== FUN_xxx"` 定位（本轮踩过） |
| **Ghidra 函数表 / strings / 字符串指针池** | 类归属、命令名、日志标签 | 数据区 `0x78FE0–0x790E4` |
| `arm-linux-gnueabihf-objdump` | 反汇编引用点与数据区 | 与伪代码交叉验证 |

---

## 2. 模块画像（硬证据）

### 2.1 它就是**一个函数**

- **165 处** LDR 引用 EFS 数据区（`0x79000–0x79100`）的指令，**全部落在 `FUN_000765b0` 内**（0x765b0，size **15,144 B**）。
- EFS 相关的**数据池槽**（`0x77358` = `"[EFS] Adjust Data write Done!!"`、`0x773ac` = `"CAP_EFS"`、
  `0x773a8` = `"AdjMainFunc"`、`0x77390`、`0x773b4`…）经"池槽 → LDR"两级反查，**也只被 `FUN_000765b0` 读取**。
  ⇒ **EFS 自包含**，没有第二个 EFS 函数。

### 2.2 名字与归属

| 项 | 值 | 证据 |
|---|---|---|
| **日志模块名** | `CAP_EFS` | 数据槽 `0x773ac` → 字符串 `0x806ED0F0` |
| **日志函数名** | `AdjMainFunc` | 数据槽 `0x773a8` → 字符串 `0x805737D4` |
| **日志格式** | `FUN_00046484(模块名, 函数名, 行号, 0, 5, fmt, ...)` ×76 | 如 `FUN_00046484(CAP_EFS, AdjMainFunc, 0x68d, 0, 5, …)` |
| **源文件线索** | `product/CaptureInterface/CapAdjIf.cpp` | `0x806EE470`，被 `FUN_0004b3b4` 的日志宏引用 |
| **类名** | `CEfsController` / `EfsController` | A 区 mangled 名（`0x57380b`、`0x573986`…）+ B 区字符串（`0x6F8C43`…） |
| **调用入口** | 被**更大的命令分发器**在某子命令匹配后调用（`DAT_0007acc8` 分支） | 伪代码 53993 行 |

### 2.3 命令集（`strcmp` 分发）

`FUN_0050bea4(argv, <池槽>)` ×50 —— 命令名存在数据区：

```
init   g_test   dth   do_all   do   shlength   deinit
nand_write   nand_write2   nand_clear   rdnand
get   set   check   cap   calc   horizon_test
AdjMainFunc(日志名)   CAP_EFS(日志名)
```

### 2.4 数据对象

- **校准系数**：`EfsOffset, V1Coeff, V2Coeff, V3Coeff, Top_Delay, TM_D…`（池 `0x6F9B70`）
- **测量统计**：`Top/Middle/Bot` 的 `Avg, Max, Min, STD`（`0x6F9ACC/…9AEC/…9B10`）
- **测量表头**：`FirstSpec,FirstAvg,SecendSpec,SecondAvg,ThirdSpec,ThirdAvg, Result`
- **输出文件**：`g_test.csv` / `efs.csv` / `horizon.csv` / `log_file`
- **浮点**：函数内唯一常量是浮点立即数（`0x3FD99999≈0.4`、`0x47AE147B≈88888.9`、`0x51EB851F`…）
  ⇒ **本级不做位运算，做的是统计/系数计算**

### 2.5 ★★ 数据落点：**MMIO `0x85601000`，不是 eMMC**

`nand_write2` 分支（伪代码 52888-52902）与 `Adjust Data write` 分支（52603-52635）**完全同构**：

```c
/* 52880: 命中命令 "nand_write" / "nand_write2" */
local_6c = atoi(argv[0xc]); local_64 = atoi(argv[0x10]);
local_60 = atoi(argv[0x14]); local_5c = atoi(argv[0x18]);
FUN_0004d63c(2, "[EFS] Result OK Nand write 1!");      // 日志
FUN_0004d518(0x3e, 0x85601000, local_6c, 4, 1);        // ★ 写 MMIO +0x3e
FUN_0004d63c(2, "[EFS] Result OK Nand write 2!");
FUN_0004d518(0x42, 0x85601000, &local_64, 4, 1);       // ★ +0x42
FUN_0004d63c(2, "[EFS] Result OK Nand write 3!");
FUN_0004d518(0x46, 0x85601000, &local_60, 4, 1);       // ★ +0x46
FUN_0004d63c(2, "[EFS] Result OK Nand write 4!");
FUN_0004d518(0x4a, 0x85601000, &local_5c, 4, 1);       // ★ +0x4a
FUN_0004d63c(2, "[EFS] Result OK Nand write Done!");
```

**提交链**（逐层看实现）：

```
FUN_0004d518(off, base, ptr, len, flag)
  └─ FUN_0004b624(obj, ?, off, base, ptr, len, flag)     // 构造请求对象
        obj[0x38]=off ; obj[0x3c]=base ; obj[0x30]=1     // ★ opcode = 1（语义：写）
        obj[0x40]=ptr ; obj[0x44]=len  ; obj[0x48]=flag
        └─ FUN_0004b310 / FUN_0004b338(obj, &DAT_0000aa04)
        └─ FUN_0004b3b4(obj)
              └─ FUN_004dcbb8(0x806EE470 "…/CapAdjIf.cpp", …, 0x194, obj+0x20)   // 提交/分发
```

⇒ ★★★★ **`0x85601000 + {0x3e,0x42,0x46,0x4a}` 是"写目标"**，每次 4 字节（32-bit 寄存器）。
**反向验证**：`rdnand` 分支直接**读**同一批地址：
```
uVar8 = FUN_0004d518(0x3e, 0x85601000, param_1+0x19, 4, 1);   // 伪代码 52944
... 0x42 / 0x46 / 0x4a
param_1[0x19] += 1; param_1[0x1b] += 1; ...                    // 读回后自增（像在读一个计数器/索引）
```
以及伪代码里出现 `_DAT_8560123e` / `_DAT_85601242` / `_DAT_85601246` / `_DAT_8560124a`
（= `0x85601000 + 0x23e/0x242/0x246/0x24a`）—— 同一窗口的**直接读取**。

**旁的旁证**：`movt rX, #0x8560` 在 p7 里出现**数十处**，高度集中在
`0x80079xxx` / `0x802Axxxx`（EFS/校准代码区）⇒ `0x8560xxxx` 是该模块**广泛使用的 MMIO 区**；
同族的 `0x85C2xxxx` 是另一个区；D3 独立发现的板级版本寄存器 **`0x85180000`** 也在 `0x85xxxxxx`
（Linux 侧靠 `/dev/mem` mmap 读）⇒ **`0x85xxxxxx` 是 DRIMe5 的一片 MMIO 域**。

---

## 3. 数据流（复原）

```
[工厂/调试触发命令]
      ↓  strcmp 分发（init / g_test / dth / do_all / …）
[CAM 测量采集]  →  [统计：Top/Mid/Bot 的 Avg/Max/Min/STD]（浮点库 FUN_004f9xxx）
      ↓
[计算校准系数] EfsOffset / V1Coeff / V2Coeff / V3Coeff / Top_Delay / TM_D…
      ↓  写入对象字段 param_1[0x19..0x47]
[写 4 个 MMIO 寄存器]  FUN_0004d518(0x{3e,42,46,4a}, 0x85601000, …)   ← ★ 落点在此
      ↓
[CSV 落盘]  g_test.csv / efs.csv / horizon.csv（通过文件 API，非本函数）
      ↓
[日志]  FUN_00046484(CAP_EFS, AdjMainFunc, 行号, …)  ×76
        FUN_0004d63c(事件类型, 消息)                  ×67   —— 构造 512 B 消息后提交
```

★ `FUN_0004d63c` 的实现已读：`memset(buf,0,512)` → `FUN_005156e0(buf, fmt, args)` → `FUN_0004b460(obj, type, buf, 512)`
⇒ 它是**"512 B 事件消息上报"**，不是数据落盘。**别把日志调用误当成写入**（本轮一度这么以为，已纠正）。

---

## 4. 对 p8 的**修正**（本篇最重要的外溢结论）

| 上一轮（`P8_ZERO_INVESTIGATION`）的表述 | 本篇结论 |
|---|---|
| 「p8 的最合理定位 = RTOS 侧 EFS 的持久化区，由校准/生产流程写入」 | ❌ **撤销**。**EFS 不写 eMMC 分区** —— 它写 MMIO `0x85601000` |
| 「p8 与 p7 EFS 的物理对应」列为**未决推断 U-a** | ✅ **有答案：不存在对应**。写 p8 的组件仍未找到，但**可以排除 EFS** |
| 「p8 从未被写入」 | ✅ **进一步加强**（少了一个潜在写入者） |

⇒ **p8 仍然全零，但"谁可能写它"的候选名单更短了**：
固件刷写（`image=none` ⇒ 排除）、Linux（无使用者 ⇒ 排除）、**EFS（写 MMIO ⇒ 排除）**。

---

## 5. 仍未解决（标为推断，不影响上面的结论）

| # | 项 | 说明 |
|---|---|---|
| U-1 | **`0x85601000` 窗口的硬件身份** | 是 NAND 控制器的数据口？还是 p7↔ISP 的共享寄存器？本轮只能确定"它是**写目标**"且"每次 4 字节" |
| U-2 | **数据是否最终由别的组件从该窗口搬到 eMMC** | 若硬件有"寄存器 → NAND 落盘"的自动路径，p8 仍可能被间接写；**需查 DRIMe5 手册或上机观测** |
| U-3 | `nand_clear` 的语义 | 命令存在，但其分支未逐条读完 |
| U-4 | `CEfsController` 的 vtable | 类名确证，但 vtable 未定位（`0x38xxxx` 之外的 A 区名字疑为裁剪残骸，铁律 116） |

**上机可答的判据（零风险只读）**：`cat /proc/diskstats`（p8 的**写入扇区是否为 0**）+ 若能在 p7 侧触发一次 `nand_write` 再读 p8 看是否变化 —— 后者属**写操作**，需单独评估，不建议现在做。

---

## 6. 复现步骤

```bash
# 1) 谁引用 EFS 数据区（165 处 → 同一函数）
python - <<'PY'   # 详见 P8 报告 §8 的引用面脚本，把目标区间换成 0x79000-0x79100
PY
# 2) Ghidra 伪代码（注意：不要用索引的 out_line，它是函数序号）
grep -n "==== FUN_000765b0" raw8/p7/ghidra/53_all_pseudocode.c    # → 52236
sed -n '52240,53914p' raw8/p7/ghidra/53_all_pseudocode.c          # 函数全文（1675 行）
# 3) 关键分支
grep -n "DAT_00079088\|0x85601000" raw8/p7/ghidra/53_all_pseudocode.c
# 4) 硬件常量（MOVW/MOVT）
python -c "...扫描 0x8560/0x85C2 的 movt（铁律 112）..."
```

---

*生成：2026-10-08 · 全程离线 · 未触碰相机 · 分支 `nx-ks2`*
