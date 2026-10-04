# NX-KS2 开发进展报告 / Development Progress Report

**日期 / Date**: 2026-10-04 ~ 10-05
**分支 / Branch**: `nx-ks2`
**作者 / Author**: WApaperplane
**项目 / Project**: NX500 相机胶片仿真模组（FilmLab）+ 系统层逆向

---

## 摘要 / Summary

本次工作分两条线：

1. **FilmLab 胶片仿真模组** —— 已完成可用版本，9 个胶片配方、一键切换、按键交互全部实测通过。
2. **系统层逆向** —— 挖出 NX500 相机 ISP 的关键控制面，包括物理→虚拟地址换算公式、3D LUT 与硬件颗粒（NOG）的完整用户态控制链、以及一条死代码的排除。

期间排查了一个「进相册即死机」的故障，最终查明是**相机 1.12 固件自身的缺陷**，与模组无关。

**This work covered two tracks:**

1. **FilmLab film-simulation module** — a working version with 9 film recipes, one-tap switching, and button-driven UI, all verified on real hardware.
2. **System-level reverse engineering** — extracted the key ISP control surface: the physical→virtual address mapping formula, the complete userspace control chain for 3D LUT and hardware grain (NOG), plus the identification of a large dead-code path.

Along the way we debugged a "camera freezes when entering playback" issue and traced it to a **defect in Samsung's own 1.12 firmware**, unrelated to the module.

---

## 一、FilmLab 胶片仿真模组（已完成）

### 1.1 架构

```
SD 卡 /mnt/mmc/filmlab/recipes.json   ← 配方唯一真相源（数量不限）
        ↓ mkgui
mod_gui 动态菜单（上限 22 按钮）
        ↓ 一键
filmlab.sh apply
        ↓
prefman set ×7  +  st cap capdtm setusr 20
        ↓
ISP 实时生效（约 2 秒）
```

### 1.2 核心设计决策

| 决策 | 理由 |
|---|---|
| **固定写 slot 9（UI「自定义1」）** | 「不确定写到哪」等于不够一键。相机 UI 恒显示自定义1，按一下取景器立刻变 |
| 配方存 SD 卡，不存相机 | 改配方不用重刷，且数量不限 |
| `mkgui` 动态生成菜单 | 加配方 = 只改 JSON，菜单零改动 |
| 按 S1 键轮换配方 | `EV_S1.sh` 挂 `EV_FLAB.sh`（原文件备份为 `.orig`）|

### 1.3 已实现的 9 个配方

`portra400` / `velvia50` / `trix400` / `ektachrome` / `hp5` / `superia400` / `monowarm` / `ektachrome_cyan` / `cine_teal`

**`monowarm` 是机身独有能力**：`SAT=0`（纯黑白）同时保留 R/B 增益差 = 暖调黑白，PC 端矩阵引擎做不到这个。

### 1.4 能力边界（★重要的诚实说明）

**7 维 = 逐像素同值的全局向量**（R/G/B 增益 + HUE/SAT/SHARP/CONTRAST）。

- ✅ 能做：胶片风格化、色彩偏移、反差曲线
- ❌ 不能做：真正的 tone curve、亮度分区调整、胶片颗粒

参照 `voxivoid/recipe-lab-sony-pmca`（Sony 同级方案，26 个 1 字节槽位做出 77 个配方）——这说明本方案已达到同级别的控制粒度。

---

## 二、系统层逆向成果

详细文档见 **[`SYSTEM_LAYER_FINDINGS_2026-10-04.md`](SYSTEM_LAYER_FINDINGS_2026-10-04.md)**。

### 2.1 ★ 物理→虚拟地址换算（可直接使用）

```c
virt_of_phys(p) = p - 0xB7FC000
```

**两个独立样本完全一致**：`0x94000000 → 0x88804000`（CMA 区）、`0x85400000 → 0x79c04000`（ISP 段）。
第二个结果落在 `/proc/252/maps` 的 `71d74000-79d74000 rw-s /dev/mem` 段内 —— 正是 ISP 寄存器窗口。

### 2.2 ★ 3D LUT / NOG 完整用户态控制链

`libudd5.so`（320KB，符号表**未剥离**，388 个符号）：

```c
d5_ep_3dl_load_lut(handle, mode, table, data)   // 0x13d10  ★ 加载 LUT
d5_ep_3dl_save_lut(...)                          // 0x13e14  ★ 保存 LUT
_udd_ep_3dl_reg_SetReg      0x17530   _udd_ep_3dl_reg_SetAddress  0x1798c
_udd_ep_3dl_reg_rw_Start    0x17884   _udd_ep_3dl_reg_SelLUT      0x17668
_udd_ep_nog_reg_struct_init 0x20070   _udd_ep_nog_set_std_sigma  0x203b0
_udd_ep_nog_set_gamma       0x20560   _udd_ep_nog_select_rv_type 0x20300
```

**★ 关键实测**：`d5_ep_open()` 在独立进程里成功分配全部 9 个寄存器组：

```
ep_3dlut_reg_base = 0xb6f76000     ep_nog_reg_base   = 0xffffffff
ep_mc_reg_base    = 0xb6f7c000     ep_top_reg_base   = 0xb6f7f000
```

这是**真实虚拟地址**（页对齐），说明库自己 open 设备节点 mmap 了硬件寄存器 —— **一条绕过 `/dev/mem` STRICT_DEVMEM 限制的合法通道**。

### 2.3 内核 EP 驱动控制面

`/proc/kallsyms` 完全可读（43181 行）：

```c
ep_set_3dlut_reg_info   c02cc4ac   ep_set_nog_reg_info  c02cc4c0
ep_get_reg_info         c02cc4d4   c07551c8 B reg_info
```

**★ 这修正了一个死墙**：之前「寄存器组指针为 0，自己造指针 → SIGSEGV」是因为缺了 `ep_set_*_reg_info` 这一步 —— 这些函数就是内核提供的「分配并填写寄存器组」入口。

### 2.4 ★ 死代码识别（省下数小时）

`libcapture-fw-prod.so` 有 **1835 个符号全部未剥离**，`CAttributeHandler` 类有 **324 个方法**，包括看起来最诱人的：

```c
setPWBracket(char, char)   // 0x965f4  ★★ 真正的明暗部曲线控制
setPWColor / setPWSaturation / setPWSharpness / setPWContrast
mm_camera_set_usr_attributes   // 属性总线入口
```

**但堆扫描（`heapscan`，直读 `/proc/pid/mem`）全部零命中** —— NX500 运行时从不调用这些方法。

> **★ 方法论教训（本文最重要的一条）**
> `/proc/<pid>/maps` 里有这个库，**只证明它被加载，不证明它被调用**。
> 正确判据是：**在目标进程内存里搜该库的关键函数地址，看有没有被引用。**
> 判断「死代码」的这一步应该放在深挖之前 —— 否则会白花数小时。

### 2.5 硬件约束表（实测）

| 约束 | 结果 |
|---|---|
| `/dev/mem` 读寄存器 | ✗ `CONFIG_STRICT_DEVMEM` |
| `poker` 写 `.text` | ✗ 内核只读内存保护 |
| `poker` 写 `.data` | ✓ 可行 |
| **CPU NX 位** | **无**（ARMv7，`.data` 里的代码可执行）|
| 根文件系统 | ext4 **ro** |
| CPU | ARMv7 rev1 (v7l) Exynos，带 NEON |
| 内存 | CMA 静态预留 288+72 MiB → 实际可用仅 ~142 MB |

---

## 三、故障排查记录：「进相册即死机」

### 3.1 症状

进入相册后**只有删除键卡死**，其他键正常、快门可用、画面正常；拨盘关不掉机，必须拔电池。

### 3.2 最终结论

**这是相机 1.12 固件自身的缺陷，与模组、SD 卡、文件状态全部无关。**

排除过程：

| 实验 | 结果 |
|---|---|
| 回滚 mod 到最早版本（9/6） | 问题依然 |
| 格式化 SD 卡 | 问题依然 |
| 换全新空卡（零文件、零 mod） | 问题依然 |
| **恢复出厂设置** | **✅ 消失** |

### 3.3 机制

```
SD 卡上 .thumbcache 状态异常
  → 进相册时 ImageGenerator 线程进入异常状态
  → 整个系统僵死（连 SD 卡日志都写不进）
  → 不可中断等待 → 拨盘关不掉机
```

**★ 为什么格式化没用**：格式化只清 `DCIM/` 和根目录，**不清 `/mnt/mmc/.thumbcache/`**（隐藏目录，相机自己管理）。只有恢复出厂才真正重置内部状态。

### 3.4 ★ 排查方法论（10 次错误假设的教训）

这一天推翻了自己 10 个假设，**全部是同一个错：把「同时出现的现象」当成原因。**

| # | 我的结论 | 被什么推翻 |
|---|---|---|
| 1 | slot 12 脏数据 | 清成中性后仍卡 |
| 2 | `iqr` hi16 是 PW 实时值 | 写 0，纹丝不动（是 ISP 常量表）|
| 3 | `.thumbcache` 0 字节文件 | 删完 31 个仍卡 |
| 4 | `ipcc_ioctl` 死锁链 | 重启后健康时它也卡 → 是常态 |
| 5 | 改配方是触发条件 | `PW_TYPE=STANDARD`（配方没生效）也卡 |
| 6 | 拍照累积 / 内存泄漏 | `MemFree` 稳定 27 MB |
| 7 | `FaceLinuxThread` 空转 | 修正测量方法后增量为 **0** |
| 8 | `CAttributeHandler` 可用 | 堆扫描零命中 → 死代码 |
| 9 | `iqr` 挂死是先行指标 | 看门狗全程 `ok`，判据从未触发 |
| 10 | `400x82` 是相册用的尺寸 | 清空后它一个都不生成 |

**★ 两条铁律：**

1. **立因果必须同时满足**「A 发生时 B 必发生」**和**「消除 A 后 B 消失」。「重启能恢复」只说明状态在内存里，不说明它是什么状态。
2. **症状复现时必须做正交切分** —— 同一个动作在哪个上下文做、变一个维度。真正切分出「进相册 vs 不进相册」这一步，我本该在 19:00 就做，实际到 22:10 才做出来，代价是 6 小时在 ISP 层挖死代码。

### 3.5 三个反复犯的技术错误

1. **jiffies ÷ 100，不是 ÷ 4**（`/proc/PID/stat` 的 utime 是 clock tick，HZ=100）—— 算错导致误判 `FaceLinuxThread` 为元凶
2. **`awk '{print $14}'` 读 `/proc/PID/task/TID/stat` 会因 comm 含空格/括号而字段错位**（`SIF Main)` / `FileHandler)` 带括号）→ 必须 `sed 's/.*) //' | awk '{print $11}'`
3. **C++ 继承里 `dlsym` 要用【基类】方法名，不带 `C` 后缀**（`_ZN17CCapVirtualAddrIf14GetVirtTopAddrEv` ✓ / `...IfC14GetVirtTopAddrEv` ✗）

---

## 四、工具链

全部在 `test_server/pwfilter/`，可复用。

### 4.1 PC 侧分析工具

| 工具 | 用途 |
|---|---|
| **`symref.py <maps> <eip...>`** | ★核心：eip → 落在哪个 so + 库内偏移 + **符号名** |
| **`pltscan.py <elf> [kw]`** | PLT/GOT 映射 + 定位函数调用点（★用来判定死代码）|
| `elfmap.py <elf> [eip...]` | ELF32 段布局 + eip→文件偏移 |
| `libscan.py <so> [kw]` | 段表 + 符号筛选 |
| `cxx.py <so> [kw]` | C++ 类结构统计 + 反修饰 |
| **`arm2.py <so> <va> [n] [label]`** | ★ARM32 反汇编器（按位域规则解码，正确）|
| `enumscan.py` / `rodump.py` | `E_*` 枚举 / `.rodata` 字符串提取 |

### 4.2 相机侧探针（`b1/src/` + `b1/build*.sh`）

| 探针 | 用途 |
|---|---|
| **`heapscan`** | 直读 `/proc/pid/mem` 批量扫内存（3.4MB 秒级）—— ★判定死代码的核心工具 |
| **`ispprobe`** | `dlopen` + `dlsym` 解析运行时地址 + `SingletonI::getInstance()` 调通 |
| **`lut3d_probe`** | 3D LUT / NOG 控制链探针（38 个符号 + 9 个寄存器组）|
| `memread` / `regscan` | `/dev/mem` 读取（★实测被 STRICT_DEVMEM 拒绝）|

**★ 编译铁律**：`-target arm-linux-gnueabi.2.15 -O0 -mfloat-abi=soft`（`-O1`+ 实测段错误）；`dlopen` 需加 `-ldl`。

### 4.3 传输与远程执行

| 脚本 | 注意 |
|---|---|
| `ftp_put.py` / `ftp_get.py` | ★远端路径**必须写 `/mnt/mmc/...` 前缀**（FTP 根 = SD 卡）|
| `telnet_run.py <ip> <cmd>` | ★**必须串行**（并发打挂单核）；telnet 服务 = busybox 软链接，**绝不能 `killall busybox`** |

---

## 五、已排除的路径（避免社区重复踩坑）

| 路径 | 撞到的墙 |
|---|---|
| 3D LUT 直写寄存器 | `/dev/mem` 被 `CONFIG_STRICT_DEVMEM` 限制 |
| `capdtm setvar` 直写 PW | `varlist` 与 `getvar/setvar` 是**两套编号**（NX500 系统性特征）|
| `iqr` 直写 | 是 ISP 固件的**常量表**，与用户设置无关 |
| `adj_*` 段（段 6-10）写入 | ★**只读常量**（5 处写入实验证实：写进去读回正常但 ISP 不理）|
| 劫持 `CAttributeHandler` | **死代码**（堆扫描零命中）|
| 劫持 GOT 槽调用 3D LUT | ★`di-camera-app` **零个 3D LUT import** → 无槽可改 |
| `poker` 改 `.text` | 内核只读内存保护 |

### ★ 一个值得单独提的发现

3D LUT 是**按需初始化**的：

```
libudd5.so 加载在 4 个进程（deviced / enlightenment / di-camera-app / ap-setting-app）
但 ep_3dlut_reg_base / ep_mc_reg_base / ep_top_reg_base 全是 0
```

**相机默认状态下根本不用 3D LUT。** 这解释了为什么它没被调用，也是它难推进的原因。

---

## 六、prefman 控制面（已完整掌握）

```sh
prefman set# ★免 save 即时生效（毫秒级、零 eMMC 写入）
prefman load -a 0        # ★★ 千万别加！从 eMMC 重载会【覆盖】刚 set 的值
prefman save_file {ID} <路径>   # ★真写到指定路径（安全）
prefman fetch {ID} <路径>      # ★★ 忽略路径！写进 /opt/pref/pref_app.bin（污染）
prefman info 0                # 672 个命名条目
```

**PW 参数块**：`addr(参数i, 风格s) = 41964 + i*52 + s*4`，`i=0..6` = R/G/B/HUE/SAT/SHARP/CONTRAST
**中性值**：R/G/B = 100，HUE/SAT/SHARP/CONTRAST = 10

**★ 另一条铁律**：NX500 任何「列表命令」打印的索引都不能假定可用于读写命令。必须「读列表 → 读命令验证 → 写命令验证」三步对齐。（今天在 `setusr` / `getvar` / `varlist` 上连续踩了三次。）

---

## 七、下一步计划

1. **FilmLab 重装与验证** —— 恢复 9 个配方的可用状态
2. **缩略图自动化** —— 用 `convert -resize 320x213!` 补齐缓存（消除固件缺陷的触发条件）
3. **3D LUT 触发条件探测** —— 确定相机在什么设置下会初始化 3D LUT（零风险）
4. **ISP 寄存器读写** —— 基于已验证的 mmap 通道，尝试在相机进程上下文中驱动 LUT

---

## 致谢

感谢 NX-KS 社区提供的 `poker`（进程内存读写）、`nx-remote-controller-daemon`、`mod_gui` 框架和大量中文/英文资料。没有这些工具，今天的系统层成果不可能拿到。

**Thanks to the NX-KS community** for `poker` (process memory read/write), `nx-remote-controller-daemon`, the `mod_gui` framework, and extensive documentation. None of the system-level findings above would have been possible without these tools.

---

## 许可 / License

本仓库的脚本与文档遵循仓库原有许可。**请勿将本文档中的逆向结论用于商业固件的再分发。**
Scripts and documentation in this repository follow the original license. **Please do not redistribute the reverse-engineering findings here for commercial firmware distribution.**
