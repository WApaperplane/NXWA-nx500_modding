# 论坛分享文案（复制用）/ Forum Post (copy-paste ready)

---

## 版本 A：详细版（技术社区 / 适合 GitHub Issues、DepthFirst、Zig forums 等）

### NX500 胶片仿真模组 FilmLab + 系统层逆向进展报告

**TL;DR**
- 做完了 **FilmLab 胶片仿真模组**：9 个配方、一键切换、按键交互，实测可用
- 挖出了 NX500 ISP 的部分控制面，含**物理→虚拟地址换算公式**和 **3D LUT / 硬件颗粒的完整控制链**
- 顺手定位了一个「进相册即死机」的故障 —— **是三星 1.12 固件自身的 bug**，跟模组无关
- **避坑清单**（10 条已证伪的路线 + 6 条硬件约束）放在最后，可能帮别人省几天时间

---

### 一、FilmLab（已完成）

**架构**
```
SD 卡 recipes.json  →  mkgui 生成动态菜单  →  mod_gui 一键
  →  filmlab.sh apply  →  prefman set ×7 + setusr 20  →  ISP 实时生效（~2 秒）
```

**几个关键设计决策**

1. **固定写 slot 9（UI「自定义1」）**。最初我让配方轮换写入不同槽位，结果是「用户不知道写到哪了」—— 这等于不够一键。改成固定槽后，相机 UI 恒显示「自定义1」，按一下取景器立刻变。
2. **配方存 SD 卡，不存相机**。加配方 = 只改一个 JSON，菜单零改动，数量不限。
3. **按 S1 键轮换配方**，走社区的 `EV_*.sh` 按键机制（原文件备份为 `.orig`）。

**9 个配方**：portra400 / velvia50 / trix400 / ektachrome / hp5 / superia400 / monowarm / ektachrome_cyan / cine_teal

其中 **monowarm 是机身独有能力**：`SAT=0`（纯黑白）但保留 R/B 增益差 = 暖调黑白。PC 端的矩阵引擎做不到这个。

**★ 诚实说明能力边界**：7 维 PW = 逐像素同值的全局向量（RGB 增益 + HUE/SAT/SHARP/CONTRAST）。能做胶片风格化、色彩偏移、反差；**不能做真 tone curve、亮度分区、胶片颗粒**。参照 `voxivoid/recipe-lab-sony-pmca`（Sony 同级方案，26 个 1 字节槽位做出 77 个配方），本方案已达到同级别控制粒度。

---

### 二、系统层逆向（可直接用的部分）

**① 物理→虚拟地址换算**
```c
virt_of_phys(p) = p - 0xB7FC000;
```
两个独立样本完全一致，且验证落在 `/proc/<pid>/maps` 的 ISP 寄存器窗口段内。**拿到它就能算任意硬件寄存器地址。**

**② 3D LUT / 硬件颗粒（NOG）的完整用户态控制链**

`libudd5.so` 符号表**未剥离**，388 个符号全带名字：
```c
d5_ep_3dl_load_lut(handle, mode, table, data)   // 加载 LUT（双表，Cb/Cr 独立）
_udd_ep_3dl_reg_SetReg / SetAddress / rw_Start / SelLUT / SelCbCr_ch
_udd_ep_nog_set_std_sigma  /  _udd_ep_nog_set_gamma  /  _udd_ep_nog_select_rv_type
```
**实测 `d5_ep_open()` 在独立进程里成功分配全部 9 个寄存器组**，而且是真实虚拟地址（页对齐）—— 说明库自己 open 设备节点 mmap 了硬件寄存器，**这是一条绕过 `/dev/mem` STRICT_DEVMEM 限制的合法通道**。

**③ 一个死代码的排除（省下数小时）**

`libcapture-fw-prod.so` 有 1835 个未剥离符号，`CAttributeHandler` 类 324 个方法，包括看起来最诱人的 `setPWBracket(char, char)`（真正的明暗部曲线控制）。**但堆扫描全部零命中 —— 运行时从不调用。**

> ★ **方法论教训（本文最重要一条）**：`/proc/<pid>/maps` 里有这个库，**只证明被加载，不证明被调用**。正确判据是**在目标进程内存里搜该库的关键函数地址，看有没有被引用**。这一步应该放在深挖之前，否则白花几小时。

我写了个工具 `heapscan`（直读 `/proc/pid/mem`，3.4MB 秒级扫完），判定死代码非常快。

**④ 硬件约束（实测，3.5 内核）**

| 项 | 结果 |
|---|---|
| `/dev/mem` 读寄存器 | ✗ `CONFIG_STRICT_DEVMEM` |
| `poker` 写 `.text` | ✗ 内核只读保护 |
| `poker` 写 `.data` | ✓ |
| **CPU NX 位** | **无**（ARMv7 → `.data` 里的代码可执行）|
| 根文件系统 | ext4 **ro** |
| 内存 | CMA 静态预留 360MiB → 实际可用仅 ~142MB |

---

### 三、故障排查：「进相册即死机」

**症状**：进相册后只有删除键卡死，其他键正常、快门可用；拨盘关不掉机，必须拔电池。

**结论：三星 1.12 固件自身的缺陷，与模组、SD 卡、文件状态全部无关。**

排除过程：

| 实验 | 结果 |
|---|---|
| 回滚 mod 到最早版本 | 依然复现 |
| 格式化 SD 卡 | 依然复现 |
| 换全新空卡（零文件零 mod） | 依然复现 |
| **恢复出厂设置** | **消失** |

**机制**：`.thumbcache` 状态异常 → 进相册时 `ImageGenerator` 线程进入异常状态 → 整机僵死（连 SD 卡日志都写不进）→ 不可中断等待。
**为什么格式化没用**：格式化只清 `DCIM/` 和根目录，**不清 `/mnt/mmc/.thumbcache/`**（隐藏目录，相机自己管）。

**★ 如果你也遇到类似问题：第一件事是恢复出厂，不是折腾 mod 或换卡。**

---

### 四、10 次错误假设（这一天的教训）

全部是同一个错：**把「同时出现的现象」当成原因**。

| # | 我的结论 | 被什么推翻 |
|---|---|---|
| 1 | slot 12 脏数据 | 清成中性后仍卡 |
| 2 | `iqr` hi16 是 PW 实时值 | 写 0，纹丝不动（是 ISP 常量表）|
| 3 | 0 字节缩略图 | 删完 31 个仍卡 |
| 4 | `ipcc_ioctl` 死锁链 | 重启后健康时它也卡 → 是常态 |
| 5 | 改配方是触发条件 | 配方没生效也卡 |
| 6 | 拍照累积 / 内存泄漏 | MemFree 稳定 27MB |
| 7 | 某线程空转 | 修正测量方法后增量为 **0** |
| 8 | `CAttributeHandler` 可用 | 堆扫描零命中 → 死代码 |
| 9 | `iqr` 挂死是先行指标 | 看门狗全程 ok，判据从未触发 |
| 10 | `400x82` 是相册尺寸 | 清空后它一个都不生成 |

**两条铁律：**
1. **立因果必须同时满足**「A 时 B 必发生」**和**「消除 A 后 B 消失」。「重启能恢复」只说明状态在内存里。
2. **症状复现时必须做正交切分** —— 同一个动作在哪个上下文做。真正切分出「进相册 vs 不进相册」这一步我本该在 19:00 就做，实际 22:10 才做出来，代价是 6 小时在 ISP 层挖死代码。

**三个技术错误**（都写进记忆了）：
- **jiffies ÷ 100，不是 ÷ 4** —— 算错导致误判元凶
- `awk '{print $14}'` 读 `/proc/PID/task/TID/stat` 会因 comm 含空格/括号而**字段错位** → 要先 `sed 's/.*) //'`
- **C++ 继承里 `dlsym` 要用基类方法名**（不带 `C` 后缀）

---

### 五、避坑清单

**已证伪的路线**（别重复踩）：

| 路径 | 墙 |
|---|---|
| 3D LUT 直写寄存器 | `/dev/mem` 被 STRICT_DEVMEM 限 |
| `capdtm setvar` 直写 PW | `varlist` 与 `getvar/setvar` 是**两套编号** |
| `iqr` 直写 | 是 ISP **常量表**，与用户设置无关 |
| `adj_*` 段（段 6-10）写入 | **只读常量**（5 处写入实验证实）|
| 劫持 `CAttributeHandler` | **死代码** |
| 劫持 GOT 槽调 3D LUT | `di-camera-app` **零个 3D LUT import** → 无槽可改 |
| `poker` 改 `.text` | 内核只读保护 |

**★ 3D LUT 是按需初始化的**：`libudd5.so` 加载在 4 个进程里，但 `ep_3dlut_reg_base` / `ep_mc_reg_base` / `ep_top_reg_base` **全是 0**。相机默认根本不用它。

**NX500 系统性特征**：任何「列表命令」打印的索引都不能假定可用于读写命令。必须「读列表 → 读命令验证 → 写命令验证」三步对齐。（我在 `setusr` / `getvar` / `varlist` 上连续踩了三次。）

**`prefman` 铁律**：
- `set` 免 save 即时生效（毫秒级、零 eMMC 写入）
- **`load -a 0` 千万别加** —— 从 eMMC 重载会覆盖刚 set 的值
- **`fetch` 会污染 `/opt/pref/pref_app.bin`**（忽略你给的路径）→ 一律用 `save_file`

**操作纪律**：`killall -q busybox` **会自杀**（`telnetd` / `ftpd` / `httpd` 全是 busybox 软链接）。必须遍历 `/proc/*/cmdline` 精确匹配。

---

### 六、工具（已开源在仓库里）

| 工具 | 用途 |
|---|---|
| **`heapscan`** | 直读 `/proc/pid/mem` 批量扫内存 —— **判定死代码的核心** |
| **`symref.py`** | eip → 落在哪个 so + 符号名 |
| **`pltscan.py`** | PLT/GOT 映射 + 定位调用点 |
| **`arm2.py`** | ARM32 反汇编器（按位域规则解码）|
| `elfmap.py` / `libscan.py` / `cxx.py` / `rodump.py` | ELF 分析系列 |

**编译铁律**：`-target arm-linux-gnueabi.2.15 -O0 -mfloat-abi=soft`（`-O1`+ 实测段错误）。

---

### 完整技术文档

- [`SYSTEM_LAYER_FINDINGS_2026-10-04.md`](SYSTEM_LAYER_FINDINGS_2026-10-04.md) —— 全部系统层结论
- [`DEVELOPMENT_REPORT_2026-10-05.md`](DEVELOPMENT_REPORT_2026-10-05.md) —— 双语完整报告

**欢迎交流。** 尤其是如果你知道「什么条件下 NX500 会启用 3D LUT」，或者有 `/dev/d5_ep` 的调用序列格式，那条线就能立刻推进。

---
---

## 版本 B：精简版（Twitter / Reddit / 短帖）

**NX500 胶片仿真模组 + 系统层逆向进展**

✅ FilmLab 完成：9 个配方、一键切换、按键交互，实测可用
🔍 挖出 ISP 控制面：物理→虚拟换算公式 `virt = phys - 0xB7FC000`、3D LUT / 硬件颗粒完整控制链
🐛 定位一个「进相册即死机」故障 —— **三星 1.12 固件自身 bug**，与模组无关

**最值钱的一条方法论**：`/proc/pid/maps` 里有库 ≠ 被调用。判断死代码要在目标进程内存里搜关键函数地址。我写了个 `heapscan`（3.4MB 秒级扫完），省下几小时。

附避坑清单：7 条已证伪路线 + 6 条硬件约束 + 3 个技术错误（jiffies ÷ 100 不是 ÷ 4；`/proc/PID/task/*/stat` 字段错位；C++ dlsym 要用基类名）。

详细文档：https://github.com/WApaperplane/nx500_nx1_modding/tree/nx-ks2/docs

---
---

## 版本 C：英文版（For international communities）

**NX500 Film Simulation Module + System-Level RE Progress**

**TL;DR**
- Shipped **FilmLab**: 9 film recipes, one-tap switching, button-driven UI, verified on hardware
- Extracted key NX500 ISP internals: a physical→virtual address formula and the complete userspace control chain for 3D LUT + hardware grain (NOG)
- Debugged a "camera freezes on entering playback" issue — **it's a defect in Samsung's own 1.12 firmware**, unrelated to the module

**Most valuable takeaway (methodology)**: a library showing up in `/proc/<pid>/maps` only proves it was *loaded*, not that it's *called*. To identify dead code, scan the target process memory for the library's key function addresses. I wrote `heapscan` (reads `/proc/pid/mem` directly, 3.4MB in seconds) — it saved hours.

**Key findings:**
```c
virt_of_phys(p) = p - 0xB7FC000;   // verified on two independent samples
```
- 3D LUT is **initialized on demand** — `ep_3dlut_reg_base` is `0` by default across all 4 processes that load `libudd5.so`
- `di-camera-app` imports **zero** 3D LUT functions → no GOT slot to hijack
- `/dev/mem` is blocked (`CONFIG_STRICT_DEVMEM`), `.text` is kernel-protected, but **the CPU has no NX bit** and `.data` is writable
- `adj_*` segments (6-10) are **read-only constants** — verified by 5 write experiments

**Gotchas that cost me real time:**
1. jiffies ÷ **100**, not ÷ 4 (`/proc/PID/stat` utime is clock ticks, HZ=100)
2. `awk '{print $14}'` on `/proc/PID/task/TID/stat` **misaligns fields** when comm contains spaces/parens (`SIF Main)`) → strip with `sed 's/.*) //'` first
3. In C++ inheritance, `dlsym` needs the **base class** method name (no `C` suffix)
4. NX500 quirk: indexes printed by any "list command" cannot be assumed valid for read/write commands — always verify in three steps
5. `killall busybox` **kills your own telnet/ftp** (they're busybox symlinks)

Full docs: https://github.com/WApaperplane/nx500_nx1_modding/tree/nx-ks2/docs

**Questions welcome** — especially if you know what settings cause NX500 to initialize its 3D LUT, or the message format for `/dev/d5_ep`.
