# W-6 能力探针结果（2026-10-12）

> 目的：在动二进制之前，先把**零补丁可得能力**穷尽（`PATCH_SURFACE_REVIEW_2026-10-12.md` §3 / 判据 J1）。
> 方法：`st cap help` → 逐条**无参数**调用逼出 usage → 高价值项实跑并存档。全程只读。
> 相机：192.168.0.105（固件 1.12）· 产物：`raw8/gates/u1/`

---

## 0. 一句话

**`st cap` 有 23 条命令，mod 只用了 6 条。**本次探出 **5 条高价值零补丁通道** ——
其中 `ref` 是 **p7 的 T-Kernel RTOS 调试通道**（任务表/中断计数/栈），
`path dump ep` 能读 **`/dev/mem` 读不到**的 EP 寄存器区。**判据 J1 得到强力印证。**

---

## 1. `st cap` 完整命令表（运行时真值 · 23 条）

```
al  back  capdtm  capmm  capt  cis  dp  efs  fd  fenx  iq  iqr
lens  live  lockinfo  log  obj  path  ref  seq  sh  sh-ad  str
```

| 状态 | 命令 |
|---|---|
| ✅ **mod 已用**（6） | `capdtm`（属性读写）· `capt`（拍照）· `iq`（AF）· `iqr`（ISP 读）· `lens` · `sh` |
| ★ **本次探出可用**（5） | `lockinfo` · `path dump ep` · `ref` · `seq` · `back`（厂测） |
| ⛔ 空实现（0 字节输出） | `obj` · `al` · `str` · `path info` |
| ❓ 未探测（风险不明，故意跳过） | `sh` / `sh-ad`（疑为 shell 执行）· `capmm` · `cis` · `dp` · `efs` · `fd` · `fenx` · `log` · `live` |

---

## 2. ★★ 核心发现：`st cap ref` = p7（T-Kernel）调试通道

`st cap ref` 的 usage 原文（T-Kernel 的资源 dump 家族）：

```
usage: ref command [num]
    dump kernel resources
    command : mem,tsk,sem,flg,mbx,mbf,por,mtx,mpl,mpf,cyc,alm,dsp
ref reboot            reboot t-kernel system.
ref stack             dump all stack information
ref int {all}         interrupt count up to Int #63 / all
ref reg [tskid]       dump task registers
```

### 2.1 实测 `ref int` —— p7 中断计数（ISP 流水线活跃度）

```
INT#  name     count        INT#  name     count
 32 TIMER0     0             41 AWB        12306
 34 TIMER2     2             42 AF         12306
 38 SSIF       24625         43 …（下略，共 32 行）
 39 PP         36925
```

⇒ **SSIF / PP / AE / AWB / AF 的实时中断计数**。可用于判断"ISP 侧是否真的在处理"——
这是**除 `iqr` 之外的第二个客观活动指标**。

### 2.2 ★★★ 实测 `ref stack` —— p7 任务表 + **栈地址**（对 A1 有直接价值）

```
TSK STATE (MAX:150)
TID PRI:BPR Name          Top          Base         Size   Used(max)
  1 138:138 unknown       0x81823008 - 0x81829008 : 24576    9%
  2   6:  6 unknown       0x8182b808 - 0x8182fa08 : 16896    1%
  3 126:126 LogTask       0x8183f008 - 0x81843408 : 17408    9%
  4 110:110 MCB_Sender    0x81dc2008 - 0x81dc8008 : 24576    2%
  5  70: 70 MCB_Receiver  0x81dc8808 - 0x81dce808 : 24576    6%
  6  81: 81 CapBootShot   0x81df6008 - 0x81dfc008 : 24576    1%
  7  86: 86 AeMain        0x82187808 - 0x8218d808 : 24576    4%
  8  87: 87 AeComp        0x8218e808 - 0x82196808 : 32768    4%
  9  88: 88 AeMsg         0x82197008 - 0x8219d008 : 24576    3%
 10 123:123 SmartAuto     0x8219e008 - 0x821a5008 : 28672    1%
 （共 59 行）
```

**⇒ 对 A1 选址的直接意义（不用刷机就得到的前置验证）**：

| 项 | 值 |
|---|---|
| A1 特判块落点 | VA `0x80011504`（p7 镜像内，引导参数块尾部零区） |
| 所有任务栈范围 | `0x81823xxx` ~ `0x821a5xxx`（**远高于** 0x80011504，相差约 24 MB） |
| 结论 | ★ **特判块不会被任何任务栈覆盖** —— A1 Step1 想验证的风险之一，**已获旁证** |

> 注：这**不能**排除 `.data`/`.bss` 或引导期一次性写入的覆盖可能 —— 那些仍需 Step1 实测。
> 但它把"零区被运行期**栈**占用"这一条**先排除了**。

### 2.3 ★ 实测 `ref tsk` —— 比 `ref stack` 更详细的任务表

```
TSK STATE (MAX:150)
TID PRI:BPR SLT WUP SUS STS(*:NODISWAI)  ST+UT(x10) RID EXINF
  1 138:138   0   0   0  WAI-SLP              6+0   1
  2   6:  6   0   0   0  WAI-RMBF *[  1]      0+0   1  676f4c53  SLog
  3 126:126   0   0   0  WAI-FLG   [  3]     38+0   1  8141b2d4  LogTask
  4 110:110   0   0   0  WAI-FLG   [ 10]      0+0   1  8141cd38  MCB_Sender
  5  70: 70   0   0   0  RUN                  4+0   1  8141ca48  MCB_Receiver
  6  81: 81   0   0   0  WAI-FLG   [ 11]      0+0   1  8141b834  CapBootShot
 （共 59 行）
```

比 `ref stack` 多出：**运行状态**（`RUN` / `WAI-FLG` / `WAI-RMBF` / `WAI-SLP`）、**等待对象 ID**、
**栈使用 ST+UT**、**EXINF（任务附加信息指针）**。

★ **任务控制块的 EXINF 指针集中在 `0x8141xxxx`** —— 与栈区（`0x8182xxxx+`）一样，
**远高于补丁区 `0x80011504`** ⇒ "特判块不会被任务结构/栈覆盖"的旁证进一步加强。

### 2.4 实测 `ref mem` —— p7 内存池统计（★ 不是段布局）

```
C-MEMORY:  Blksz=2048 Total=16366 (32732 KB) Free=8243 (16486 KB) [50 % used]
U-MEMORY:  Blksz=2048 Total=4080  (8160 KB)  Free=4073 (8146 KB)  [1 % used]
```

- p7 用**自己的两个分配器**：C-MEMORY（连续，32 MB，用 50%）、U-MEMORY（用户，8 MB，仅 1%）
- 对"能否容纳更大的补丁块"有参考意义：U-MEMORY 尚余 **8146 KB**
- ⚠ **这不是段布局** —— 想回答"`0x11504` 属于哪个段"仍需别的路径

### 2.5 无收获项（如实记录）

| 命令 | 结果 |
|---|---|
| `ref mpl` | 仅表头 `MPL STATE (MAX:10):`、**无条目** ⇒ p7 不使用 T-Kernel 可变长内存池 |
| `ref mpf` | 同上（`MPF STATE (MAX:10):` 无条目）⇒ 不使用固定长内存池 |
| `ref reg 5` | `TASK REGISTER (TID:5)` + `ERR [0xffd70000]` ⇒ 无法 dump 该任务寄存器（疑权限/状态限制）|

### 2.6 ★ 仍未回答的关键问题

**「`0x11504` 属于 p7 的哪个段（只读/可写/是否被引导期写入）」—— `ref` 家族给不出段表。**

候选后续路径：
1. `ref dsp`（调度器）—— 未试
2. **静态**：p7 镜像的段属性 + 已有的 `scan_free.py` / `scan_bl.py` / `scan_holes.py`
3. **直接让 A1 Step1 回答** —— 它本来就是为此设计的（这也是"先测后打"的边界：有些问题只能在机上问）

---

## 3. ★ `st cap path dump ep` —— 零补丁读 EP 寄存器

`path` 的 usage：
```
st cap path dump        dump all registers
st cap path dump ep     dump EP registers
st cap path info        display all information
st cap path info ep     display EP information
```
（实测 `path info` / `path info ep` 输出为空；**`path dump ep` 有效，51 行**）

输出样例（3 块 × 16 行）：
```
EP top     [20821000] 00000000 00000000 00000000 000101FF  ................
           ...
EP LDC     [20823000] 00040FE4 03C005A0 03C005A0 00000000  ................
           ...
EP resize  [20826000] 05A00000 05A00000 03C00000 03C00000  ................
           ...
```

**意义**：地址 `0x2082xxxx` 正是我们刚用四点对照证明 **`/dev/mem` 读不到**的 EP 寄存器区
（`G2b` 结论）。⇒ **死路 #6 的正确表述得到补全**：
**"`/dev/mem` 读不到 ⇒ 走驱动"**，而 `st cap path dump ep` 提供了**第三条现成的只读通道**。

**边界**：它只 dump `top` / `LDC` / `resize` 三块（`0x20821000` / `0x20823000` / `0x20826000`），
**不含** 3DLUT 窗口（`0x2082b000`）与 ISP 参数块（`0x20821300` / `0x20821700`）
⇒ 仍需 `epmc.arm` 覆盖那些块。**二者互补，不是替代**。

---

## 4. `st cap lockinfo` —— 实时曝光/场景状态

```
* Av :59, FnoNum :35, FnoDen :10       ← 光圈
* Tv :84, ShSpdNum : 1, ShSpdDen :40   ← 快门
* Iso :800                              ← 感光度
* DeltaEv :0 / ExpOutOfRange :0 / FlashFire :0
* SmartScene :0 / SubSmartScene :0 / SmartWarning :0
* EvNum :10 / EvDen :10 / UnderFlag :0
* fd run :0 / fd disp stop :0 / fd mark :0
* LargeWin :1 / ExtendArea :0 / FcousLensInit :1
```

⇒ **脚本可读实时曝光三元组与场景识别状态**（此前只能靠 capdtm 读单个属性）。
用途：曝光记录、自动联动、场景触发的 mod 逻辑。

---

## 5. 其它

| 命令 | 结果 |
|---|---|
| `st cap seq` | ✅ 345 B：`order/demand/log/loglevel/logid/orderid/status/list/check/wbtest/dump` —— **拍摄 sequencer 调试** |
| `st cap back` | ✅ 125 B：`uniteset` / `matr`（单元/材料测试，厂测） |
| `st cap obj` / `al` / `str` / `path info` | ⛔ 空实现（0 字节） |

---

## 6. 方法与教训

| # | 教训 |
|---|---|
| 1 | ★ **复合命令（`for` 循环 + 块重定向）在 telnet 里不可靠** —— 一次跑了 6 分钟只产出 9 字节，且把 loadavg 抬到 1.58 ⇒ **改为"逐条独立 + 各自重定向到文件"**（一次会话串几条简单命令 OK） |
| 2 | ★ **批量 `st cap` 有明显负载代价**（每条走 MCB、超时 10s）⇒ 分批 + 段间留白；观测到 loadavg 1.58 → 1.19 → 恢复 |
| 3 | ★ 输出量大的命令（`path dump ep`）**一律重定向到文件再 FTP 拉**，屏幕只回一行 —— 避免回显风暴（铁律 88 的"输出量"面） |
| 4 | `busybox timeout` 的行为与预期不符（`timeout: can't execute '12'`）⇒ 本次**不依赖 timeout**，靠 `st cap` 自身的 10s 超时 |
| 5 | `st cap <cmd>` **无参数调用是安全的**（走 usage 分支）—— **但 `sh` / `sh-ad` 例外**（用途疑为 shell 执行，**故意跳过**，需单独评估） |

---

## 7. 产物清单（`raw8/gates/u1/`）

| 文件 | 内容 |
|---|---|
| `path_dump_ep.txt` | EP 寄存器 dump（51 行 / 3297 B） |
| `ref_int.txt` | p7 中断计数（32 行） |
| `ref_stack.txt` | p7 任务表 + 栈（59 行 / 4143 B） |
| `lockinfo.txt` | 实时曝光/场景状态（35 行） |
| `cap_seq.txt` / `cap_ref.txt` / `cap_back.txt` | 各命令 usage |
| `cap_obj.txt` / `cap_al.txt` / `cap_str.txt` | 空实现（0 字节，作为反证留档） |

> 脚本：`test_server/u1/w6_cap_usage.sh`（枚举用，`@gate opens=rdonly`）

---

## 8. 结论：零补丁能力清单（更新 `PATCH_SURFACE_REVIEW` §3）

| 能力 | 通道 | 价值 | 状态 |
|---|---|---|---|
| p7 任务表 / 栈地址 | `st cap ref stack` | ★★★ A1 选址前置验证 | ✅ 实测 |
| p7 中断计数 | `st cap ref int` | ★★ ISP 活跃度判据 | ✅ 实测 |
| p7 内核资源 | `st cap ref mem|tsk|sem|…` | ★★ 段布局 / 任务寄存器 | ❓ 待探 |
| EP 寄存器（3 块） | `st cap path dump ep` | ★★ 零补丁读 `0x2082xxxx` | ✅ 实测 |
| 实时曝光/场景 | `st cap lockinfo` | ★★ 状态可读 | ✅ 实测 |
| 拍摄 sequencer | `st cap seq status|log` | ★ 流程调试 | ✅ usage 已得 |
| ISP 184 参数 | `st cap iqr` | ★★★ 唯一客观判据 | ✅ 已用 |
| 白平衡/质量/RAW/录像 pause | `st app nx capture …` | ★★（同构批次 2） | 命令已解，待接线 |
| MCB 命令字典（8 域） | `mcbtest` / `st cap` | ★★ | 部分已解 |

**⇒ 建议**：下一个 W-6 续篇只做 **`st cap ref mem`**（p7 段布局）——
它可能一次性回答 A1 的关键未知（`0x11504` 属于哪个段、是否只读）。

---
*生成：2026-10-12 19:35 · 相机 192.168.0.105 · 全程只读（未写入、未切换模式、未拍照）*
