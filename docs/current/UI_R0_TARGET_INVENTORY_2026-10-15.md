# UI-R0：目标样本与证据清单（2026-10-15）

> **任务来源**：`NATIVE_UI_ROADMAP_2026-10-15.md` §4（UI-R0）/ §9 首批执行包第 1 项。
> **完成标准**：固定目标 App、资源、库版本；写兼容性清单和证据索引；原版与 C-2 等变体哈希分开；file offset/VA/运行地址各有规则；证据能复现。
> **口径**：✅ = 本机实测（可直接复现）｜🔶 = 既有记录引用（出处已注）｜❓ = 未验证（附验证法）
> **性质**：离线产物；零写机。

---

## 0. 一句话

**目标 = NX500 v1.12 官方 rootfs 内的 `di-camera-app`（md5 `ae44293e…`，4,773,516 B，EXEC 非 PIE）；基线资源 = 4×`.edj` + EFL 1.7.99 全系 + libc-2.13；地址三体系（file 偏移 / 链接 VA / 运行地址）规则已 `readelf` 实证；C-2 两代变体哈希单列。**

---

## 1. 目标 App（原版基线）

| 项 | 值 | 来源 |
|---|---|---|
| 相机内路径 | `/usr/apps/com.samsung.di-camera-app/bin/di-camera-app` | 🔶 DICAM_MOD_DESIGN |
| 本地镜像 A（提取物） | `E:/NXWA/fw/v1.12/extract/di-camera-app/com.samsung.di-camera-app/bin/di-camera-app` | ✅ 本机 |
| 本地镜像 B（rootfs 副本） | WSL `NXKS2:/opt/nxks2/rootfs-112/usr/apps/com.samsung.di-camera-app/bin/di-camera-app` | ✅ 本机 |
| **md5**（两镜像互证一致） | **`ae44293e969101d1cf0a93cbe9b99f75`** | ✅ `md5sum` ×2 |
| 大小 | 4,773,516 B（0x48D46C） | ✅ |
| 类型 | **EXEC（非 PIE）**，interp `/lib/ld-linux.so.3` | ✅ `readelf -h/-l` |
| Entry point | `0xae948` | ✅ `readelf -h` |
| ELF Flags | `0x5000002`（Version5 EABI） | ✅ |
| 签名 | `author-signature.xml`（RSA-SHA256；bin+res 摘要）存在；**运行时裸 exec 无校验**（unit 不验签名） | ✅ 文件在位 / 🔶 运行面无校验（有 `systemctl restart` 先例） |
| 反编译分析基座 | `E:/ghidra_out/di-camera-app.arm_dump/`（Ghidra ImageBase `0x8000`，语言 ARM:LE:32:v7） | ✅ 00_header.txt |

**复现**：

```bash
md5sum /e/NXWA/fw/v1.12/extract/di-camera-app/com.samsung.di-camera-app/bin/di-camera-app
wsl -d NXKS2 -- bash -lc "readelf -h /opt/nxks2/rootfs-112/usr/apps/com.samsung.di-camera-app/bin/di-camera-app"
```

---

## 2. ★ 变体登记（与原版分开）

| 变体 | 样本 | md5 | 桩 | 用途 | 位置 |
|---|---|---|---|---|---|
| **原版 v1.12** | `di-camera-app` | `ae44293e969101d1cf0a93cbe9b99f75` | — | 基线 / 一切补丁的 src | extract + rootfs-112（双证） |
| **C-2 v1** | `di-camera-app_c2_v116.patched` | `0e1da8b326f49728e9394f98a53ffd35` | 16B 短桩 | W-4 首验灰度 | `fw/v1.12/dicam/`（两克隆一致 ✅） |
| **C-2 v2** | `di-camera-app.c2.v2` | `48d94bd63e4479fc931ae1a1fee4e94b` | 248B 拼接桩（含白名单） | 交付族 | 同上 |

**C-2 补丁点（file ↔ VA 双列）**：

| # | 内容 | file offset | 链接 VA | old → new |
|---|---|---|---|---|
| P1 | 命令名改名 `uscom`→`film` | `0x3656DC` | `0x36D6DC` | `7573636f6d00` → `66696c6d0000` |
| P2 | 桩宿主 `FUN_000ca3a8` 头部 | `0xC23A8` | `0xCA3A8` | v1=16B / v2=248B（见 json） |

- 规格文件：`fw/v1.12/dicam/c2_bytepatch.json`（v1）/ `c2_bytepatch.v2.json`（v2）——含逐项 old/new 字节（回滚依据）
- 桩源码与构建：`test_server/dicam/stub_v2.s` + `build_stub_v2.sh`（248 B，上限 656）；补丁器 `mk_c2_patch.py`；QEMU 验证 `test_server/dicam/c2_qemu/RESULTS.md`（T1–T5 全绿）
- ❗ 纪律：**变体只在匹配样本（md5 == `ae44293e…`）上打补丁**；两克隆副本 md5 已互证一致

---

## 3. 资源（基线）

### 3.1 `.edj` 主题（4 个，rootfs 实有）

| 文件 | 大小 (B) | md5 |
|---|---|---|
| `res/edje/nx_style.edj` | 1,087,293 | `d130c2bf6d6a2de90b6afb644825255d` |
| `res/edje/nx_style_hdmi.edj` | 254,230 | `4b38215c27908da39891b05f84730873` |
| `res/edje/nx_style_hdmi_720.edj` | 253,952 | `c08e032d056e9d23244e8c1565af0700` |
| `res/edje/tizen-hd.edj` | 1,990,094 | `090313fae2009af75044d8580b4f781c` |

（提取物与 rootfs-112 副本 md5 互证一致 ✅。`slp_edc_*.edj` 系其它 App 资源，**非**本 App——10-13 实地核查已结案。）

### 3.2 `res/` 全貌（提取物 4176 文件）

| 项 | 内容 | UI 相关性 |
|---|---|---|
| `res/edje/images/` | lcd + hdmi 两套（4106 文件） | 布局/图标素材 |
| **`res/locale/*/LC_MESSAGES/di-camera-app.mo`** | gettext 翻译（含 en） | ★ **菜单文案候选来源之一**（R1a 核查：文案走 msgid→mo 还是内嵌字符串） |
| `res/sounds/` | 提示音 | 低 |
| `author-signature.xml` | bin + res 的 SHA-256（base64）摘要 | 版本指纹（❗ 但运行不校验） |

---

## 4. 库版本（rootfs-112 实测）

| 类别 | 库 | 大小 (B) | 日期 | 备注 |
|---|---|---|---|---|
| libc | `ld-2.13.so` / `libc-2.13.so` | 122,148 / 1,171,712 | 2014-02-06 | `libc.so.6 → libc-2.13.so` |
| EFL | `libelementary.so.1.7.99` | 1,243,004 | 2015-05-21 | `libelementary.so → .1 → .1.7.99` |
| EFL | `libevas.so.1.7.99` | 739,008 | 2014-09-09 | |
| EFL | `libedje.so.1.7.99` | 375,280 | 2015-01-09 | 主题运行时 |
| EFL | `libecore.so.1.7.99`（+con/evas/fb/file/imf/input/ipc/x 全套） | 167,180 | 2014-06-27 | |
| EFL | `libeina.so.1.7.99` | 257,288 | 2014-02-24 | |
| EFL | `libeet.so.1.7.99` | 73,144 | 2014-02-24 | .edj 读写 |
| EFL | `libefreet.so.1.7.99`（+mime/trash） | 89,376 | 2014-02-24 | 菜单/桌面数据 |
| 三星私有 | `libdi-elementary.so` | 31,668 | 2015-01-13 | 127 符号（UI0 审计） |
| 三星私有 | `libgui.so` | 85,092 | 2015-01-05 | |
| 三星私有 | `libapex.so` | 40,440 | 2015-06-05 | |

**关键派生事实**（🔶 UI0 §3.1）：App DT_NEEDED 113 个、**不链 libdl、不调 dlopen**；宿主方案须外部注入。DT_NEEDED 全表见 UI0 审计。

---

## 5. ★ 地址三体系（规则写死，`readelf` 实证）

| 体系 | 定义 | 换算规则 | 用途 |
|---|---|---|---|
| **① file offset** | 二进制文件内字节偏移 | — | 打字节补丁（bytepatch.json 的 `file_off`） |
| **② 链接 VA** | ELF 链接地址（= Ghidra/REA 地址 = dump 地址） | **file < `0x4384AC` ⇒ VA = file + `0x8000`**；<br>**file ≥ `0x4384AC` ⇒ VA = file + `0x10000`** | 静态分析、Ghidra/REA 定位、R1 地址图 |
| **③ 运行地址** | 进程实际内存地址空间 | 可执行段按链接 VA 加载（EXEC 非 PIE）；**动态区（堆/mmap）另有规则 ❓** | poker 注入（先例 `0xb4095xxx`） |

**实证依据（readelf -l）**：

```
LOAD #1: Offset 0x000000 → VirtAddr 0x00008000  FileSiz 0x4384ac  R E
LOAD #2: Offset 0x4384ac → VirtAddr 0x004484ac  FileSiz 0x54c04   RW
⇒ 两段 delta 分别为 +0x8000 与 +0x10000（0x4484ac-0x4384ac）——两规则均由此出
```

- Entry `0xae948` 与 Ghidra dump `.text` 起点 `000ae948` **逐位一致** ⇒ dump 地址 ≡ 链接 VA 体系 ✅
- 校验样例：C-2 P1 file `0x3656DC` < `0x4384AC` ⇒ VA `0x36D6DC` ✓；P2 file `0xC23A8` ⇒ VA `0xCA3A8` ✓

**运行地址（③）现状**：EXEC 非 PIE ⇒ **代码/数据段（①→②体系）运行时按链接 VA 落位**；但 **堆/mmap 动态区**地址规律未逆向——既有先例仅 poker 9 地址（`0xb4095a08` 等，逐次开机可复现，🔶 `scripts/pokemon` 表）。❓ 验证法：上机 `cat /proc/<pid>/maps` 采集快照，与 poker 地址比对归类（只读）。

---

## 6. 证据索引（全部可复现）

### 6.1 分析基座（dump，本机 `E:/ghidra_out/di-camera-app.arm_dump/`）

| 文件 | 大小 | md5 | 内容 |
|---|---|---|---|
| `00_header.txt` | 208 B | `c28bcf2c3b795879d9a0d0023dbcb5e9` | 程序信息（ImageBase 0x8000, MD5 对照） |
| `01_memory_blocks.txt` | 2,250 B | `9b5eea60052e6c9d80d7050228484e27` | 段表（与 readelf 段映射互证） |
| `02_functions.txt` | 378,468 B | `aef42b57ba3434218070e9a8fbd4a21f` | 函数清单（9,258 项含地址） |
| `03_strings.txt` | 1,241,687 B | `0c9e06a6bd07472e9d8d0479f2d2f4ba` | 字符串（30,410 行，带地址） |
| `04_decompiled.c` | 11,608,069 B | `9ced0406ffb65ceb9b18a19b309d22cb` | 全量伪代码（373,438 行） |

### 6.2 定向工具

| 资产 | 位置 | 用途 |
|---|---|---|
| dicam 工具组（4 脚本） | `test_server/isp/dicam/`（`dicam_strings/xref/findref/dump.py`） | 字符串/引用/表转储 |
| C-2 链 | `test_server/dicam/`（`stub_v2.s`、`mk_c2_patch.py`、`c2_qemu/`） | 补丁生成/验证 |
| REA 6.4.0 | `tools/rea-wsl.sh` + `tools/rea-inspect-dicam.sh`；证据 `E:/NXWA/rea-evidence/` | 函数引用/调用形态补证 |

### 6.3 文档地图（`docs/current/`）

| 文档 | 内容 |
|---|---|
| `DICAM_MOD_DESIGN_2026-10-11.md` | C-2 全设计 + 关键地址速查 + 命令表 |
| `CAMERA_APP_STRUCTURE_2026-10-07.md` | App 模块与依赖（113 DT_NEEDED） |
| `CAMERA_MENU_ARCHITECTURE_2026-10-07.md` | 菜单 View/State 结构（R1a 起点） |
| `SHELL_TO_APP_ISOMORPHISM_2026-10-12.md` | st↔App 命令面同构 |
| `DICAM_PATCH_INSTALL_PATHS_2026-10-12.md` | 补丁安装路径与投递（含 T2） |
| `UI0_HOST_FEASIBILITY_2026-10-13.md` | 宿主注入审计（失效建议以实机报告为准） |
| `NATIVE_UI_ROADMAP_2026-10-15.md` | 本任务来源（R0–R7） |
| `MEM_INJECTION_EVAL_2026-10-15.md` | 投递候选评估（poker 降级 + T2 缺口） |

---

## 7. 兼容性清单（本清单即「已验证组合」的定义）

| 维度 | 已验证（本清单范围） | 未验证（不宣称） |
|---|---|---|
| 机身 | NX500 固件 v1.12（官方） | NX1 / 其它版本 |
| App 样本 | md5 == `ae44293e969101d1cf0a93cbe9b99f75` | 其它哈希（含未来版本） |
| 资源 | §3 的 4×edj 哈希集 | 其它主题变体 |
| 库 | §4 版本集（EFL 1.7.99 / libc-2.13） | 其它 rootfs |
| 已打过补丁的变体 | C-2 v1 / v2（§2，匹配样本上） | 其它补丁组合 |
| 修改生效面 | 仅「匹配样本」；**未支持样本一律拒绝修改**（R3a 要求） | — |

---

## 8. 完成标准自检（对照任务卡）

- [x] 固定目标 App 版本与哈希（§1，双镜像互证）
- [x] 资源（§3）与库版本（§4）清单
- [x] 兼容性清单（§7）与证据索引（§6）
- [x] 原版与 C-2 变体哈希**分开**（§2）
- [x] file offset / VA / 运行地址各自规则（§5，readelf 实证 + 先例标注）
- [x] 证据可复现（每条注复现命令/来源；dump 含 md5 台账）

---
*生成：2026-10-15 · 分支工作树（Codex 克隆）· 本任务为离线产物（零写机）；上游输入均已注出处。*
