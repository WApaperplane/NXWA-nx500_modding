# p8（rtos_data）全零问题 —— 定性、验证路径与补救预案（2026-10-08）

> 承接 `OFFLINE_VERIFICATION_2026-10-08.md` §4 / `WORKFLOW_PLAN_2026-10-08.md` §8 遗留的**唯一真异常**：
> **`p8`（`rtos_data`，52,427,776 B = 50 MB）读出 0 个非零字节。**
> 当时明确写着：在解释清 **(a) 分区真空 / (b) 读错区域 / (c) 读保护** 之前，
> 「p8 是空的」**既不能证明分区是空的，也不能证明里面没东西**。
> 本篇**离线**推进到"三条候选只剩一条"，并给出**上机一次只读即可定案**的验证路径与判据表。
> 全程未触碰相机。

---

## 0. 一句话结论

> ★★★★ **最可能：p8 从未被写入 —— 这是设计如此，不是故障。**
> 六条相互独立的硬证据都指向同一结论（§1、§4）；其中最关键的一条是
> **Linux 侧对 p8 的实际使用者为 0**（此前疑似使用者 `delta.ua` 已排除，§2）。
> ★ 残余的不确定性**只有一条**——若要"确证"而非"高置信推定"，
> **需要一次零风险只读上机**：读 `/proc/diskstats` 看 p8 的**累计写入扇区数是否为 0**（§5）。
> 判据表已写死：**write==0 且 ro==0 ⇒ 定案（非故障）**；**write>0 ⇒ 转"读保护/坏块"分支**。

---

## 1. 硬证据（本轮新增 6 条，全部离线可复现）

| # | 证据 | 来源 | 对候选支的含义 |
|---|---|---|---|
| **E1** | `/etc/parttab` 里 **`rtos_data /dev/mmcblk0p8 50 **none** 3 None raw`** —— `image` 字段 = **`none`**、**无 mount-point** | rootfs-112 `/etc/parttab`（实读） | ⇒ **固件包内没有 p8 的镜像**（刷机不写）；⇒ **Linux 不挂载它** |
| **E2** | `/proc/partitions`：`179 8 **51199** mmcblk0p8` ⇒ 51199 KB = **52,427,776 B**，**与备份文件大小逐字节相符** | `raw8/blockdev.txt` | ⇒ **排除 (b) 的"读错分区/读错大小"**：设备节点对、长度对 |
| **E3** | Linux 侧全盘 grep（`mmcblk0p8`）：**只有两处** —— `parttab`（配置）与 `delta.ua`；**后者已排除**（§2） | rootfs-112 全树扫描 | ⇒ **Linux 侧真正的使用者 = 0** |
| **E4** | p7 固件里有 **EFS 命令表**（`0x79000` 附近，`{name, fn}` 8 B/项）与一族 EFS 字符串（§3） | `raw8/p7/p7_full.bin` + Ghidra 04/05 | ⇒ p7 **有**"校准数据 + NAND 读写"的完整能力，但它是**工厂/调试接口** |
| **E5** | 升级链的分区枚举（`fw_emmc_mkfs_preproc`）覆盖 `bootloader/vImage/pref/snapshot/pcache/devicem4`，**不含 p8** | D3 报告 `FW_UPGRADE_VERIFY_CHAIN_2026-10-08.md` | ⇒ **升级流程不碰 p8**（与 E1 的 `image=none` 自洽） |
| **E6** | ★ **eMMC 未写页读作 `0x00`** —— `p2`（pref，**确认一直在被 prefman 写**）却有 99.98% 是 `0x00` | `raw8/emmcbak/sparse_partition_report.txt` | ⇒ **"全零"与"从未写"完全自洽**；不需要"读保护"来解释 |

**六条合起来**：固件不填（E1/E5）、Linux 不挂（E1/E3）、升级不碰（E5）、
而"未写的页就是 0x00"（E6）⇒ **p8 全零是被四条独立机制共同保证的预期结果**。
唯一有写入能力的是 p7 的 EFS（E4），而那是**校准/生产流程**才走的路径。

---

## 2. ★ 重要排除：`delta.ua` 不是 p8 的使用者

初次 grep 会把 `/usr/bin/delta.ua`（217,508 B，2014-02-24）列为 `mmcblk0p8` 的引用者，
但它的字符串上下文揭示：

```
BOOTLOADER   sboot.bin      /dev/mmcblk0p80
TZSW         tz.img         /dev/mmcblk0p81
PARAM        param.bin      /dev/mmcblk0p4
ROOTFS       delta.rootfs   /dev/mmcblk0p15
CSC          delta.csc      /dev/mmcblk0p12
BOOT         delta.boot     /dev/mmcblk0p5
```

这套 **`sboot / TZSW / PARAM / CSC / BOOT`** 是**三星手机（Android）的分区命名**，
而 `/dev/mmcblk0p80`、`p81` **根本不是 NX500 上的设备**（`/proc/partitions` 只到 `p14`）。

⇒ ★★★ **`delta.ua` 是从三星手机代码移植来的**（还带 `libdrm`/`libkms`/`libpng`/`libsmack` 依赖），
其 `p8x` 指向的是**手机分区表的遗留编号**，**与 NX500 的 `p8` 无关**。
⇒ **排除后，Linux 侧对 NX500 `p8` 的引用者归零。**

> 方法论提示（值得进铁律）：**"某二进制引用了 X" 必须连上下文一起看** ——
> 拼进来的字符串 `p80` 一度看起来像 `p8`，实际是另一个平台的设备号。

---

## 3. ★ 新发现：p7 侧有一张 EFS（校准数据）命令表 @ `0x79000`

在 p7 镜像里，`nand_write` / `nand_write2` / `nand_clear` / `rdnand` 等字符串**不是函数名**，
而是**一片密集的字符串指针数组**（文件偏移 `0x78FE0–0x790E4`，**4 B/项**，每项指向一个字符串）——
即 EFS/校准模块的 **rodata 字符串池**（不是命令分发表；本报告初稿曾误记为 `{name,fn}` 8 B/项，已更正）。

★ **该池被代码真实引用（不是死字符串）**：全镜像共 **165 处 `LDR` literal** 指向 `0x79000–0x79100`，
集中在 **VA `0x80078254`–`0x8007842C`**；命中的项包括 `"CAP_EFS"`(@`0x790E0`)、
`"AdjMainFunc"`(@`0x790D8`)、`"nand_write"`(@`0x79088`)。该处代码为 double 运算 + switch 分支
（`ldrd`/`strd` + `bl 0x804f9ba4`），与"校准系数计算"的形态吻合。

池中与校准直接相关的名字（节选）：

| 池中名字（节选） | 语义推断 |
|---|---|
| `nand_write` / `nand_write2` / `nand_clear` / `rdnand` | **NAND/eMMC 的写 / 擦 / 读** 操作 |
| `AdjMainFunc` / `CAP_EFS` | **Adjust（校准）主流程** / 校准数据捕获 |
| `[EFS] InitialCalibration Deinit OK/NG` | **初始校准**流程 |
| `horizon_test` / `[EFS_HORIZONTAL] Result NG!` | 水平/倾斜校准测试 |
| `EfsOffset,V1Coeff,V2Coeff,V3Coeff,Top_Delay,TM_D...` | ★ **校准系数**（LSC/时序等） |
| `FirstSpec,FirstAvg,SecendSpec,SecondAvg,…` | 校准测量（规格 vs 均值） |
| `shlength` / `tunning` / `dBValueEnable` / `offsetplus` / `display_log` / `ppskip` / `capssif` / `cappp` / `deinit` | 校准/诊断开关 |
| `set` / `check` / `get` / `cap` / `calc` | 通用子命令 |

伴随的打印串：`[EFS] Adjust Data write Done!!`、`[EFS] Result OK Nand write {Start,1,2,3,4,Done}!`、
`[EFS] No.%d Failed !!`、`[EFS] CIS-SH Length Set %f`。

**含义**：
- ★ p7 **确实有 EFS（Embedded File System）模块**：`[EFS]` 前缀字符串 15+ 条、
  `nand_write/nand_write2/nand_clear/rdnand`、`AdjMainFunc`/`CAP_EFS`/`InitialCalibration`/`horizon_test`、
  以及校准系数名 `EfsOffset,V1Coeff,V2Coeff,V3Coeff,Top_Delay,TM_D…` ——
  且**字符串池被 165 处 LDR 真实引用**（非死串）⇒ 这条能力是"活的"；
  另外 p7 里有 `emmcgrp`（eMMC 引脚组，与 `i2c0grp/spi0grp` 并列）⇒ **p7 具备 eMMC 硬件接口配置**；
- ★ 但这些名字是**校准/调试流程**的产物（`Init`+`Calibration`+`horizon_test`+`nand_clear`），
  **正常拍摄流程不会走它** ⇒ 与"p8 从未被写"一致；
- ★ 因此 `p8 rtos_data` 的最合理定位是：**RTOS 侧 EFS 的持久化区，由校准/生产流程写入**。

> ★★★★ **2026-10-08 追加更正（见 `P7_EFS_MODULE_2026-10-08.md`）：上面这条定位已被推翻。**
> 把 EFS 模块打开后确认：**EFS 的 `nand_write` 并不写 eMMC 分区**，
> 而是写 **MMIO 寄存器窗口 `0x85601000`**（`FUN_0004d518(0x{3e,42,46,4a}, 0x85601000, val, 4, 1)`）。
> ⇒ **EFS 与 p8 无对应关系**；「p8 从未被写入」的结论**被进一步加强**（潜在写入者又少一个）。
> 本篇 §6 的 U-a 因此**从"未决"变为"已答"**。

> ⚠️ 归属仍是推断：`p8` 与 EFS 的**物理对应**（EFS 落在哪个 LBA/分区）**尚未在静态层面钉死** ——
> p7 里**没有** `/dev/mmcblk*` 这类设备路径字符串（E 段扫描 0 命中），说明它走的是寄存器/LBA 直驱，
> 需要上机或用 p7 的 eMMC 寄存器访问点才能确认。这条**不影响主结论**（p8 未被写），
> 但决定了"若要让 p8 有内容该怎么做"。

---

## 4. 判据链：为什么"从未写入"是最优解释

```
p8 的写入者只可能是：① 固件刷写  ② Linux 运行时  ③ RTOS(p7)
  ① 固件刷写  → 排除：parttab image = none（E1）+ 升级链不含 p8（E5）
  ② Linux     → 排除：无挂载点（E1）+ 全树使用者 0（E3，delta.ua 已排除）
  ③ RTOS      → 存在能力（E4），但入口是"命令表驱动"的校准/生产流程，
                 零售机正常使用不触发
⇒ 三个写入者都"没写过" ⇒ 全零
且"未写页读作 0x00"在本机已被 p2 独立证明（E6） ⇒ 全零无需额外机制解释
⇒ 候选 (a) 分区真空/从未写 = 成立；候选 (b) 读错 = 被 E2 排除；
  候选 (c) 读保护 = 目前**没有正证据**，且若真被写保护，也只影响"写"，不改变"从未写"的结论
```

---

## 5. ★ 解决路径（上机一次只读，零风险）

> 纪律：21 端口先探（铁律 90）→ 一会话一条命令 → 结果 FTP 拉、不信回显 → 段间 60–120 s。

### P0 —— 决定性三连（定案用）

| # | 命令 | 看什么 |
|---|---|---|
| P0-1 | `cat /proc/diskstats > /tmp/ds.txt`（或直接 `grep mmcblk0p8 /proc/diskstats`） | ★ **p8 的累计写入扇区（字段 10）是否为 0**；顺带看 p1/p7/p2 的读写计数做对照 |
| P0-2 | `cat /sys/block/mmcblk0p8/start; cat /sys/block/mmcblk0p8/size; cat /sys/block/mmcblk0p8/ro; cat /sys/block/mmcblk0p8/force_ro` | 精确起始扇区（复原分区布局）+ **只读/写保护标志** |
| P0-3 | `blockdev --getsize64 /dev/mmcblk0p8` | 与 52,427,776 对照（再次确认节点长度） |

**判据表（结果 → 结论，写死）**：

| 观测 | 结论 |
|---|---|
| ★ **p8 write sectors == 0** 且 `ro == 0` 且 `force_ro == 0` | **定案：从未被写 ⇒ 全零天然成立 ⇒ 非故障，结案** |
| p8 write sectors == 0 但 `read sectors > 0` | 同上，并说明"RTOS/Linux 只读过、从未写" |
| **p8 write sectors > 0** | ⇒ **异常**：写过却读不出 ⇒ 转 §5-P2 的"读保护/坏块/映射"分支 |
| `ro == 1` 或 `force_ro == 1` | Linux 侧写保护 ⇒ 与"从未写"一致（并且解释了为何不可能被写） |

### P1 —— 整盘视角对照（排除分区映射问题）

```bash
# 用 P0-2 得到的 start，从整盘读同一区域（绕过分区节点）
dd if=/dev/mmcblk0 bs=512 skip=<p8_start> count=2048 2>/dev/null | md5sum
# 与 p8.bin 前 1MB 的 md5 对照
head -c 1048576 raw8/emmcbak/p8.bin | md5sum      # PC 侧先算好
```
- **相同** ⇒ 分区节点映射正确，该区域确实全零（强化主结论）
- **不同** ⇒ 分区映射/偏移有问题 ⇒ 落回候选 (b)

### P2 —— 只有在 P0 出现"write>0 却读不出"时才走

| 分支 | 动作 | 风险 |
|---|---|---|
| eMMC 写保护 | `mmc extcsd read /dev/mmcblk0 \| grep -iE 'WR_PROT\|BOOT_PARTITION\|ENH'`（若 rootfs 有 mmc-utils） | 零（只读） |
| 读保护误置 | 检查 `/sys/block/mmcblk0p8/force_ro`；**不要**贸然 `echo 0 > force_ro`（写操作） | 中 |
| 坏块/区域不可读 | 分段读（每段 ≤3 KB / 铁律 88）看是否有非零/错误 | 低 |

### P3 —— 顺带解决的两个相邻缺口（同一次上机一起带走）

1. ★ **复原完整分区布局**：`for i in $(seq 1 14); do echo -n "p$i "; cat /sys/block/mmcblk0/mmcblk0p$i/start; done`
   —— `MANIFEST.txt` 现在**只有大小、没有起始扇区**，这是"单分区回滚"缺的一块（写错 offset = 变砖）。
2. ★ **`/proc/diskstats` 全表**：可同时回答"p9 snapshot / p12 pcache / p14 opt-usr 有没有在被写"，
   对 U5 的回滚演练有直接价值。

---

## 6. 仍未解决 / 明确标注为推断的部分

| # | 项 | 状态 |
|---|---|---|
| U-a | ~~**p8 与 p7 EFS 的物理对应**（EFS 落在哪个 LBA）~~ | ✅ **已答（不存在对应）**：EFS 写的是 MMIO `0x85601000`，不写 eMMC —— 见 `P7_EFS_MODULE_2026-10-08.md` |
| U-b | `rtos_data` 的**官方语义** | 推断 = "RTOS 持久化数据（校准/adjust）"。未见三星文档 |
| U-c | 读保护是否真的启用 | 无正证据；P0-2 可一次回答 |
| U-d | `p9 snapshot`（100 MB，LZO raw，**未备份**）也从未被分析 | 独立的未知项，建议并入同一次上机 |

---

## 7. 对项目的实际影响

| 项 | 变化 |
|---|---|
| 「p8 是唯一真异常」 | ★ **降级**：更可能是"设计如此"，而非异常 |
| 备份基座完整性 | ★ 影响有限 —— p8 若确实从未写，则**备份它就是备了一份零**；真正该补的是 **p14 opt-usr（真洞）** |
| U5 回滚演练 | ★ 不受影响（p8 不参与系统启动/升级） |
| 新线索 | ★ p7 的 **EFS 命令表**（`nand_write/AdjMainFunc/CAP_EFS/InitialCalibration`）是**从未被利用过的一条新入口**，将来若要在 RTOS 侧做校准/参数持久化，从这里入手 |

---

## 8. 复现步骤（离线部分，全部本轮可重放）

```bash
# E1 分区表
MSYS_NO_PATHCONV=1 wsl -d NXKS2 -u root -- cat /opt/nxks2/rootfs-112/etc/parttab
# E2 分区尺寸
grep mmcblk0p8 raw8/blockdev.txt
# E3 Linux 侧使用者
MSYS_NO_PATHCONV=1 wsl -d NXKS2 -u root -- grep -rl mmcblk0p8 /opt/nxks2/rootfs-112/etc /opt/nxks2/rootfs-112/usr /opt/nxks2/rootfs-112/lib
# E4 p7 的 EFS 字符串指针池（0x78FE0 起，4B/项 → 字符串）
python - <<'PY'
import struct
d=open('raw8/p7/p7_full.bin','rb').read(); B=0x80000000
def cs(va):
    o=va-B; e=d.find(b'\0',o); return d[o:e].decode('latin1','replace')
for o in range(0x78FE0,0x790F0,4):
    v=struct.unpack_from('<I',d,o)[0]
    if B<=v<B+len(d): print('0x%05X -> 0x%08X "%s"'%(o,v,cs(v)))
PY
# 引用者：扫 LDR literal 指向 0x79000-0x79100（本轮得 165 处，集中在 VA 0x80078254-0x8007842C）
```

---

*生成：2026-10-08 · 全程离线 · 未触碰相机 · 分支 `nx-ks2`*
