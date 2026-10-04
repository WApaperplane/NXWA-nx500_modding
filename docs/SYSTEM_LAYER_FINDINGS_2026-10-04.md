# NX500 系统层挖掘成果 — 2026-10-04

> 一天的工作，10 次假设被自己的实验推翻，2 个真正的突破。
> 本文只记录**被实测证实的**结论，所有被推翻的假设列在最后一节作为教训。

---

## 一、突破一：物理→虚拟地址换算（可直接用）

```c
virt_of_phys(p) = p - 0xB7FC000
```

**实测样本（两个独立值，完全一致）**

| 物理地址 | 虚拟地址 | 差值 | 来源 |
|---|---|---|---|
| `0x94000000` | `0x88804000` | `-0xB7FC000` | CMA 288MiB 区 |
| `0x85400000` | `0x79c04000` | `-0xB7FC000` | ISP 段 |

**验证**：`0x79c04000` 落在 `/proc/252/maps` 的
`71d74000-79d74000 rw-s /dev/mem`（offset=`0x99600000`，8MB）—— 正是 ISP 寄存器窗口。

**结论：这是统一线性映射，不是分段表。** 拿到它就能算任意硬件寄存器地址。

### 已知物理段换算表

| 物理（maps 的 offset 列） | 虚拟 | 大小 | 用途 |
|---|---|---|---|
| `0x99600000` | `0x79c04000` | 8 MB | **ISP 寄存器窗口** |
| `0x98200000` | `0x78204000` | 8 MB | ISP 相关 |
| `0x97800000` | `0x77804000` | 8 MB | — |
| `0x94000000` | `0x88804000` | 32 MB | CMA（288 MiB 的一部分）|
| `0x84c00000` | `0x78c04000` | ~5 MB | — |
| `0x854e0000` | `0x79504000` | 44 KB | — |
| `0x85600000` | `0x79604000` | 4 KB | — |
| `0x85500000` | `0x79524000` | 4 KB | — |

---

## 二、突破二：3D LUT 是活的（reg_base 已初始化）

在 `di-camera-app`（pid 252）进程内读 `libudd5.so` 的全局变量：

```
ep_3dlut_reg_base @ 0xb0e8d730 = 0x0103b7f   ← ★★ 有值，3D LUT 寄存器组已分配
ep_nog_reg_base   @ 0xb0e8d724 = 0xffffffff   ← NOG（硬件颗粒）未初始化
```

**`0x0103b7f` 不是 0 也不是 ffffffff → `ep_set_3dlut_reg_info` 已被相机调用过。**

`0x0103b7f` 拆解（Samsung ISP 寄存器典型编码）：
`0x01` = 块号｜`03` = 块内偏移高字节｜`b7f` = 低字节（位域待查手册确认）

### 3DLUT / NOG 全部符号（`libudd5.so`，320216 B，符号表未剥离）

```
★ 寄存器组基址全局变量
  ep_nog_reg_base      0x57724  .dynsym
  ep_3dlut_reg_base    0x57730  .dynsym
  _udd_ep_nog_regset0  0x57768
  _udd_ep_nog_regset1  0x57748

★ 3D LUT
  d5_ep_3dlut_op_init                 0x13c2c
  d5_ep_mc_set_custom_param_yccmixer 0x29488
  _udd_ep_mux_3dlut_rdxi / wdxi      0x34940 / 0x38560
  _udd_ep_demux_3dlut_rdxi / wdxi    0x3bb94 / 0x3c114

★ NOG（硬件颗粒发生器）
  _udd_ep_nog_reg_struct_init  0x20070   ← 初始化（必须先调这个）
  _udd_ep_nog_set_std_sigma   0x203b0   ← 颗粒强度
  _udd_ep_nog_set_gamma       0x20560   ← 颗粒分布
  _udd_ep_nog_select_rv_type  0x20300   ← 颗粒类型
  _udd_ep_nog_seed_load_switch 0x20250
  d5_ep_nog_set_noisegen      0x105f0
  d5_ep_nog_set_bypass        0x105cc
```

---

## 三、内核 EP 驱动完整控制面（`/proc/kallsyms` 可读，43181 行）

```
ep_set_top_reg_info    c02cc40c      ep_set_ldc_reg_info   c02cc420
ep_set_mc_reg_info     c02cc434      ep_set_rsz_reg_info   c02cc448
ep_set_jpeg_reg_info   c02cc45c      ep_set_fd_reg_info    c02cc470
ep_set_bblt_reg_info   c02cc484      ep_set_lvr_reg_info   c02cc498
ep_set_3dlut_reg_info  c02cc4ac  ★   ep_set_nog_reg_info   c02cc4c0  ★
ep_get_reg_info        c02cc4d4  ★   ep_set_device_info    c02cc4f0
ep_dd_set_top_reg      c02cc504      ep_dma_reset          c02cc514
ep_pmu_requeset        c02cc530      ep_pmu_clear          c02cc538
ep_pmu_on_off          c02cc550      ep_set_clk_rate       c02cc554

c07551c8 B reg_info     ← ★ bss 全局变量，所有寄存器组配置存在这里
```

模块缩写：`top`=顶层 / `ldc`=镜头畸变 / `mc`=运动补偿(yccmixer 所属) /
`rsz`=resize / `jpeg` / `fd`=人脸检测 / `bblt`=BB LT / `lvr` / `3dlut` / `nog`

**★ 这修正了下午撞的死墙**：之前「寄存器组指针全为 0，自己造指针 → SIGSEGV」
是因为**缺了 `ep_set_*_reg_info` 这一步**——这些函数就是内核提供的
「分配并填写寄存器组」入口。**正确顺序：先 `ep_set_3dlut_reg_info`（内核分配）
→ 再 `d5_ep_mc_set_custom_param_yccmixer`（用该指针）。**

---

## 四、`CCapVirtualAddrIf` 单例（已实调通）

```c
// 静态函数，无 this 参数 → 探针进程里可安全调用
SingletonI<CCapVirtualAddrIf>::getInstance()   静态地址 0x626e4
```

**实调结果**（`b1/src/ispprobe.c` mode=2/3）：

```
instance = 0x0006f230
vtable   = 基址 + 0xb0010（_ZTV17CCapVirtualAddrIf ✓）
+0x04 = 0x94000000   ← dmesg 的 "cma: reserved 288 MiB at 94000000"
+0x08 = 0xbfffffff   ← 4GB-1，地址空间上限
+0x0c = VirtTopAddr  ← GetVirtTopAddr() 实调返回 0x887f8000
```

**★ 走 `SingletonI::getInstance()` 绕开了 `GetCameraIfHandle()` 的崩溃**
（后者需要相机框架已初始化，独立探针进程里必崩——这是硬约束）。

### 全部单例表

| 单例 | getInstance |
|---|---|
| **`CCapVirtualAddrIf`** | **`0x626e4`** ← 地址映射层 |
| `CCaptureController` | `0x3d1d4` |
| `CTraceLog` | `0x3e178` |
| `CCapturePublisher` | `0x80f14` |
| `CMCBAdapter` | `0x871f0` |

---

## 五、已确认是「死代码」的高价值发现（省下后续工作量）

### `libcapture-fw-prod.so`（1835 符号全未剥离）= **未被调用**

`CAttributeHandler` 有 **324 个方法**，包括看起来最诱人的：

| 静态地址 | 方法 | 说明 |
|---|---|---|
| `0x94e84` | `setPWColor` | 属性 ID `0x10E`（从 `movw r0,#0x10E` 指令读出）|
| `0x94d10` | `setPWSaturation` | 属性 ID `0x111`（★不是记忆里的 0x110）|
| `0x94d8c` | `setPWSharpness` | 属性 ID `0x112`（★不是 0x111）|
| `0x94e08` | `setPWContrast` | 属性 ID `0x113`（★不是 0x112）|
| **`0x965f4`** | **`setPWBracket(char, char)`** | ★★ 真正的明暗部曲线控制（带两个 int8）|
| `0x92fb8` | `getPWBracketParam` | 读当前曲线参数 |

**但 `heapscan` 扫遍堆（3.4 MB）+ `.data/.bss`（352 KB），全部零命中：**

| 搜的目标 | 命中 |
|---|---|
| `CAttributeHandler` vtable | **0** |
| `setPWColor` / `setPWSaturation` / `setPWContrast` | **0** |
| `setPWBracket` / `getPWBracketParam` | **0** |
| `writeUserAttr` | **0** |

**★ 结论：NX500 运行时 `di-camera-app` 从不引用这些方法。**
相机实际走的是 `st` / `capdtm` / `libudd5.so` 那条线（`prefman` + `setusr` + ipcc）。

### 判定「死代码」的正确方法（★今天最贵的教训）

```
✗ 错：/proc/<pid>/maps 里有这个库 → 假设它被用了
✓ 对：heapscan 搜该库的关键函数地址在目标进程内存里有没有被引用
```

**maps 只证明「被加载」，不证明「被调用」。**

---

## 六、已确认的硬件约束

| 约束 | 实测结果 | 影响 |
|---|---|---|
| **`/dev/mem` 读取** | `pread` 返回 -1 | `CONFIG_STRICT_DEVMEM` → **无法直接读寄存器** |
| **`/proc/<pid>/mem` 读设备内存** | `read` 返回 -1 | 内核禁止跨进程读设备映射区 |
| **`poker` 写 `.text`** | `Buffers not the same: ERROR` | 代码段不可写 → **劫持调用点不可行** |
| **`poker` 写 `.data`** | ✅ 成功 | 数据段可自由读写 |
| **CPU NX 位** | **无**（`Features` 行无 `nx`） | ARMv7；`.data` 里的代码**可能可执行** |
| **根文件系统** | `/dev/root` ext4 **ro** | 换不了 `.so` |
| **`LD_LIBRARY_PATH`** | `:/usr/lib:/usr/lib/driver` | 空首项=cwd，但 cwd=`/` → 不可利用 |
| **3.5 内核性能接口** | `/proc/softirqs`、`/proc/interrupts`、`/proc/PID/io` 全部不可用 | 常规 Linux 性能工具链失效 |

**★ 唯一剩下的寄存器访问通道 = `libudd5.so` 的封装函数**（内部走 `ioctl`，
由内核代理访问寄存器，用户态不需要碰 `/dev/mem`）。

**★ 唯一剩下的代码注入通道 = `poker` 写 `.data` + 无 NX**
（把 ARM shellcode 写进数据段 → 改 GOT 槽跳转）。
GOT 槽在 `di-camera-app` 的 `0x448adc` 起 4384 字节（rw-p，已验证可写）。

---

## 七、相机基线信息

| 项 | 值 |
|---|---|
| CPU | ARMv7 rev 1 (v7l)，Exynos，**带 neon**，`Features: swp half thumb fastmult vfp edsp neon vfpv3 tls`（无 nx）|
| 内存 | CMA 静态预留 `288 MiB + 72 MiB` @ `0x94000000` → **实际可用仅 ~142 MB** |
| 根文件系统 | `/dev/root` ext4 **ro**（`/usr/share/locale` 用 loop0 挂 squashfs，说明支持 loop 挂载）|
| `di-camera-app` | pid 252，`0x00008000-0x00441000`（**无 PIE，未重定位**）|
| 库加载 | `LD_LIBRARY_PATH=:/usr/lib:/usr/lib/driver`，cwd=`/` |

### 未剥离符号的库（★都是金矿，但要看是否真被调用）

| 库 | 大小 | 符号数 | 用途 | 是否被调用 |
|---|---|---|---|---|
| **`libudd5.so`** | 320 KB | 未剥离 | **3D LUT / NOG / ipcc 封装** | ✅ **是**（reg_base 有值）|
| `libsif.so` | 657 KB | 654 / 81 类 | SIF 图像框架（`DscFileHandler` 等）| ✅ 是 |
| `libcapture-fw-prod.so` | — | 1835 | 属性总线 | ❌ **死代码** |
| `libSLP-db-util.so` | 10 KB | — | （曾误传是 3DLUT 宿主，实际只有 3.8KB 代码）| — |

### `libsif.so` 关键地址（已用 `poker` 验证首指令合法）

| 运行时地址 | 静态 | 方法 |
|---|---|---|
| `0xb0c943c4` | `0x2c3c4` | `DscFileHandler::taskMain`（线程主函数）|
| `0xb0c95590` | `0x2d590` | **`DscFileHandler::writeChunks`** |
| `0xb0c99c44` | `0x31c44` | `DscFileHandler::operate(tImage_buffer*)` |
| `0xb0c9b8e0` | `0x338e0` | **`DscFileHandler::storageException(bool)`** |
| `0xb0c9c4d4` | `0x344d4` | `pauseOrResume(FileHandlerState)` |

---

## 八、`prefman` 完整用法（已实测）

```
prefman info {ID}            → 命名条目表（info 0 = 672 条）
prefman set                  → ★免 save 即时生效（毫秒级、零 eMMC 写入）
prefman load -a0             → ★★ 千万别加！从 eMMC 重载会【覆盖】刚 set 的值
prefman save                 → 只在想持久化时用
prefman save_file {ID} <路径>→ ★真写到指定路径（安全）
prefman load_file {ID} <路径>→ 恢复（实测有效）
prefman fetch {ID} <路径>    → ★★ 忽略路径！写进 /opt/pref/pref_app.bin（污染活动文件）
```

**★ CHECKSUM（0x0fcbc）恒为 108，无需重算。prefman 不裁剪值域，调用方自己夹紧。**

### PW 参数块

```
基址 0x0a3ec，14 槽 × 7 维 × 4B
addr(参数i, 风格s) = 41964 + i*52 + s*4
i = 0..6 = R / G / B / HUE / SAT / SHARP / CONTRAST
★ 中性值：R/G/B = 100，HUE/SAT/SHARP/CONTRAST = 10
```

`0x0a3d4` = PW_TYPE，`0x0a3d0` = SMART_FILTER

### adj_* 段 = **只读常量**（5 处写入实验证实）

| 段 | 大小 | 非零率 | 判断 |
|---|---|---|---|
| 6 `adj_iq` | 3.5 KB | 1.6% | 空段 |
| 7 `adj_vfpn` | 24 KB | 90.6% | 满数据（固定模式噪声校正）|
| 8 `adj_cs` | 64 KB | 49.5% | 色彩空间（有 ASCII `"0100"` / `"Drim"` 结构）|
| 9 `adj_dpc` | 5.2 MB | — | 去马赛克 |
| 10 `adj_dpc2` | 1 MB | 10.5% | 去马塞克制表 |

**★ 每段只有一条命名条目（整块 blob），无字段级语义标注。写进去读回正常但 ISP 不理。**

`/opt/pref/default/` 有**完整未污染的出厂副本**（`pref_app.bin` / `pref_adj_*.bin`），
比被 `fetch` 污染过的 `/opt/pref/*.bin` 可靠，可用来恢复。

---

## 九、`st cap` 命令树

```sh
st cap capdtm usrlist      # userdata 索引 0-86 全表
st cap capdtm getvar <id>  # ★ 与 varlist 是【两套编号】，不能混用
st cap capdtm setvar <id> <data> <len>
st cap capdtm varlist
st cap iqr                  # 183 项 IQ 节点（★ 只读，且是 ISP 常量表）
st devman get/set [dev] [prop] [val]   # 相机所有节点读回 0，无可用属性
st firmware up              # 只支持 uImage / rom.bin / devicem4.bin
```

**★ NX500 系统性特征：任何「列表命令」打印的索引都不能假定可用于读写命令。**
必须「读列表 → 读命令验证 → 写命令验证」三步对齐。（今天在 `setusr` /
`getvar` / `varlist` 上连续踩了三次同一个坑。）

---

## 十、10 次被实测推翻的假设（★方法论教训）

| # | 时间 | 我的结论 | 被什么推翻 |
|---|---|---|---|
| 1 | 17:05 | slot 12 脏数据导致卡死 | 清成中性后**仍卡** |
| 2 | 17:53 | `iqr` hi16 是 PW 实时值 | 写 0，**纹丝不动**（是 ISP 常量表）|
| 3 | 18:55 | `.thumbcache` 0 字节文件导致卡死 | 删完 31 个，**仍卡** |
| 4 | 19:08 | `ipcc_ioctl` 死锁链 | **重启后完全正常时它也卡** → 是常态 |
| 5 | 19:18 | 改配方是触发条件 | `PW_TYPE=STANDARD`（配方没生效）**也卡** |
| 6 | 19:18 | 拍照累积 / 内存泄漏 | `MemFree` 稳定 27 MB |
| 7 | 20:06 | FaceLinuxThread 空转 | 修正 jiffies 除数 + stat 字段错位后**增量为 0** |
| 8 | 20:15 | `CAttributeHandler` 属性总线可用 | 堆扫描**零命中** → 死代码 |
| 9 | 21:20 | iqr 挂死是删除卡死的先行指标 | 看门狗全程 `IQR=ok`，**判据从未触发** |
| 10 | 22:20 | `400x82` 是相册用的尺寸 | 清空后**它一个都没生成**，相机只写 320x75/1024x85 |

**共同模式（10 次全部同一个错）**：把「同时出现的现象」当成原因。

**★ 两条铁律：**
1. **立因果必须同时满足**「A 发生时 B 必发生」**和**「消除 A 后 B 消失」。
   「重启能恢复」只说明状态在内存里，不说明它是什么状态。
2. **症状复现时必须做正交切分**——同一个动作在哪个上下文做、变一个维度。
   真正切分出「进相册 vs 不进相册」这一步，我本该在 19:00 就做，
   实际到 22:10 才做出来，代价是 6 小时在 ISP 层挖死代码。

### 三个反复犯的技术错误

1. **jiffies ÷ 100，不是 ÷ 4**（`/proc/PID/stat` 的 utime 是 clock tick，HZ=100）
   → 我算错导致误判 FaceLinuxThread 为元凶
2. **`awk '{print $14}'` 读 `/proc/PID/task/TID/stat` 会因 comm 含空格/括号而字段错位**
   （`SIF Main)` / `FileHandler)` 带括号）→ 必须 `sed 's/.*) //' | awk '{print $11}'`
3. **C++ 继承里 `dlsym` 要用【基类】方法名，不带 `C` 后缀**
   （`_ZN17CCapVirtualAddrIf14GetVirtTopAddrEv` ✓ / `...IfC14GetVirtTopAddrEv` ✗ 全 0）

### 一个操作纪律

**`killall -q busybox` 会自杀** —— `telnetd` / `ftpd` / `httpd` 全是 busybox 的软链接。
在这台相机上停进程必须：遍历 `/proc/*/cmdline` 精确匹配 + `kill -9 <pid>`。

---

## 十一、工具链（PC 侧，全部在 `test_server/pwfilter/`）

| 工具 | 用途 |
|---|---|
| **`symref.py <maps> <eip...>`** | ★核心：eip → 落在哪个 so + 库内偏移 + **符号名** |
| `elfmap.py <elf> [eip...]` | ELF32 段布局 + eip→文件偏移 |
| `libscan.py <so> [kw]` | 段表 + 符号筛选 |
| `cxx.py <so> [kw]` | C++ 类结构统计 + 反修饰 |
| `armdis.py <so> <va> [name]` | ARM 反汇编（该 so 的 PT_LOAD 是 `off==va`）|
| `enumscan.py <so>` | 扫 `E_*` 枚举字符串 |
| `rodump.py <so> [kw]` | `.rodata` 字符串提取 + ID 表候选 |
| `pltfind.py <so> [kw]` | PLT import 筛选 |
| `armplt.py` | PLT 反汇编 |
| **B1 探针** `b1/src/*.c` + `b1/build*.sh` | 相机侧探针（`ispprobe` / `heapscan` / `memread` / `pw7_ycc` / `lut3dl_*`）|
| `ftp_put.py` / `ftp_get.py` | 传输（★远端路径必须写 `/mnt/mmc/...` 前缀）|
| `telnet_run.py <ip> <cmd>` | 远程执行（★必须串行，并发会打挂单核）|

**探针编译铁律**：`-target arm-linux-gnueabi.2.15 -O0 -mfloat-abi=soft`
（`-O1`+ 实测段错误）；需要 `dlopen` 时加 `-ldl`。

---

## 十二、下一步的建议顺序

| 优先级 | 方向 | 理由 |
|---|---|---|
| **1** | **`_udd_ep_*` 探针**：`reg_struct_init` → `3dlut_op_init` → 写 LUT | 唯一确认活着的 ISP 控制路径；符号地址已备齐，只差在 `di-camera-app` 上下文里调 |
| **2** | **shellcode 注入**：`poker` 写 `.data` + 无 NX + 改 GOT 槽 | 唯一能进 `di-camera-app` 代码空间的手段 |
| 3 | 修缩略图生成（预热对齐相机命名规则）| 与 web 相册共用一套代码，顺手解决死锁 |
| — | ~~3D LUT 直写寄存器~~ | `/dev/mem` 被 STRICT_DEVMEM 限制，已排除 |
| — | ~~CAttributeHandler 属性总线~~ | 死代码，已排除 |
| — | ~~劫持调用点~~ | `.text` 不可写，已排除 |
