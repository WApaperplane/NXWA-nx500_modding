# 属性总线传输层 —— 解开（O3 / 2026-10-09 · 全静态 + QEMU 验证）

> 任务（TASKFLOW §2-O3）：解 `set_attribute(0x10e/0x110/0x111/0x112)` 的 **app→ISP 传输层**；
> 产出"从用户态程序推 PW 7 维"的**可执行路径**（或证伪）。
> 本篇 = 结论 + 证据链 + POC 工具 + 上机实验设计。**全程离线，未触碰相机。**

---

## 0. 一句话

> **传输层已完全解开（5 层，字节级证据）**：
> `set_attribute(id,&v,4)` ⇔ `SetVariableDataMCB(id,&v,4)` → `CMCBAdapter::SetParam(cmd=(id-0xff)|0x1300,4,&v)`
> → `CMulticoreBridge::Send(0x81,cmd,4,&v)` → CSender 队列 → `ipcc_write_pkt` → p7。
> **可执行路径已成立**：`pwsend.arm`（POC，本仓已编译）直接 `dlopen(libcapture-fw-prod.so)` +
> `dlsym(SetVariableDataMCB)` 即可推送 —— 在 1.12 rootfs 上 dlsym **实测解析成功**。
> ⇒ **PW 参数不再只有"画面向导"一条路**；shell 侧推送成为可能（上机实验待排波次）。

---

## 1. 传输链全景（每一跳都有反汇编原文）

```
[di-camera-app] 画面向导确认
   │
   ▼
[libcapture-fw-prod.so]  CAttributeHandler::setPWColor/setPWSaturation/setPWSharpness/setPWContrast
   │   值 = getParam<short|int>(buf)     ← 空指针→0；取 T 宽度
   ▼
[1] SetVariableDataMCB(id, &v, 4)        @0x49f84（导出符号，GLOBAL DEFAULT）
   │     id → cmd:  cmd = ((id - 0xff) & 0xFFFF) | 0x1300      ← 0x49fbc 指令原文
   ▼
[2] CMCBAdapter::SetParam(cmd, 4, &v)    @0x83ea4
   │     → 硬编码首参 0x81（@0x83ec8 `mov r0, #0x81`）
   ▼
[3] CMulticoreBridge::Send(0x81, cmd, 4, &v)   libmulticore-bridge.so @0x6700（导出）
   │     → _mySender() → CSender::Send(this, 0x81, cmd, 4, &v)  @0x7898
   ▼
[4] CSender 队列 → CIPCCDriverIf::Send(u8*,len) → ipcc_write_pkt → p7 → ISP
```

### 1.1 PLT 反查方法（本仓新工具，解决"PLT 已被剥"）

`raw8/repro/capfw/pltmap.py` —— 通用 ELF32-ARM PLT 桩 → 符号映射器：
`.plt` 布局 = `PLT0(20B) + 桩#k(12B)`，桩 #k ⇔ `.rel.plt` 第 k 条（链接器惯例）。
在 libcapture-fw-prod.so 上自校验：`桩 #994 @0x284f4 ⇔ rel#994 = SetVariableDataMCB`
（且 0xb14f4 槽在 .got 段 0xb0560+0x115c 内，闭环）。
产物：`plt_symmap.tsv`（1003 条）· `plt_symmap_multicore.tsv`（177 条）。

### 1.2 pw id 表（来源 = 4 个 setter 的 movw）

| 属性 | setter 函数 | id | MCB cmd |
|---|---|---|---|
| PWCOLOR | `setPWColor` @0x94e84 | **0x10e** | 0x130F |
| PWSATURATION | `setPWSaturation` @0x94d10 | **0x110** | 0x1311 |
| PWSHARPNESS | `setPWSharpness` @0x94d8c | **0x111** | 0x1312 |
| PWCONTRAST | `setPWContrast` @0x94e08 | **0x112** | 0x1313 |

全库 `SetVariableDataMCB` 调用者共 **19 处**（枚举证据在案），另有
`mm_camera_set_var_attributes`（导出 @0x2a7f0，**id 范围校验 0xff..0x12b** —— 白名单依据）
与 `CAttributeHandler::writeVariableAttr`（动态 id 通用写入器）。

### 1.3 值语义（发送侧）

- `setPWColor`：`getParam<short>` → **int16**（符号扩展到 4B buffer）；低 16 位有效。
- `setPWSaturation/Sharpness/Contrast`：`getParam<int>` → **int32**。
- `getParam<T>` 实现 = `p==0 ? 0 : *p`（72B，空指针保护）。
- 与读回侧（`st cap capdtm varlist`）的**候选映射（待上机校准）**：
  发送值 ≈ 读回值高 16 位（如 SAT 读回 `0x005FD80A` → 高 16 = 0x5F = 95）。

---

## 2. POC：`pwsend.arm`（已编译 + 已离线验证）

| 项 | 值 |
|---|---|
| 源码 | `test_server/pwsend/pwsend.c` |
| 产物 | `pwsend.arm`（md5 `3e71e88d0605209e6aa580c5d3655f75`，zig -O0） |
| 用法 | `pwsend.arm info` ｜ `send <id> <value> [--yes]`（默认 dry-run） |
| 白名单 | id ∈ [0x100, 0x12b]（来自 mm_camera 实机校验边界） |

**离线验证（QEMU + 1.12 rootfs）**：
```
$ qemu-arm-static -L rootfs-112 pwsend.arm info
OK: libcapture-fw-prod.so 已加载
OK: SetVariableDataMCB @ 0x40a11f84        ← dlsym 实测成功
$ pwsend.arm send 0x10e 0x0700             # dry-run：打印 id/cmd=0x130f，不发送
$ pwsend.arm send 0x99 1  → rc=4（白名单拒绝）
```

---

## 3. 上机实验设计（★ 待排波次；进门 = G0+G1）

**目标**：①验证通路 ②校准 id↔维度/值编码 ③给出"shell 推 PW"最终可行性判决。

| 序 | 动作 | 判据（写死） |
|---|---|---|
| 1 | 基线：`filmlab.sh check`（记录 4 维现值） | 得到对照基线 |
| 2 | 菜单界面：`pwsend.arm send 0x10e <v> --yes`，v 取"已知合法值的编码"（如 slot9 现值的 raw16） | 读回 varlist：PWCOLOR_* 至少一维高 16 位跟随 |
| 3 | 逐 id 扫描 0x10e..0x113（每次一个，间隔 ≥60s） | 定位哪个 id↔哪个变量（R/G/B/HUE 归属） |
| 4 | 若 2/3 成功：发一组完整 PW → 拍 1 张 | 成片风格跟随 ⇒ **全链路可用** |
| 5 | 若全失败（值不动）：记录负结论，回退"画面向导"③ 通道 | — |

**安全**：与"setvar 写死 capture"不同——本次走的是 **di-camera-app 自身的正常写入路径**
（同一条 `SetVariableDataMCB`），且 id 白名单 + 单发 + 不重试。
**回退**：重新走一次"画面向导选自定义1"（正常路径会覆盖），或重启相机。

---

## 4. 遗留（诚实清单）

| # | 项 | 影响 |
|---|---|---|
| 1 | 0x10e 的 **R/G/B 通道细分**（一个 id 三值如何区分） | 实验步骤 3 解决（或发现第三方 id） |
| 2 | **PWHUE 的 id**（4 个 setter 没有 Hue） | 实验步骤 3 顺带扫 |
| 3 | 0x81 的完整语义（首参=域/目标？） | 不影响使用（库内部处理） |
| 4 | p7 侧 0x1300 域的分发表（**变量名表已定位** `0xEF8514` 区，但 id↔name 结构未解） | 实验可交叉（发→读回跟随） |

---

## 5. 对旧结论的修正

| 出处 | 旧表述 | 本次 |
|---|---|---|
| `PW_PARAM_CHANNEL` §4 路 B | "需先解出 set_attribute 传输层（PLT 已被剥…）⇒ 属独立里程碑" | ✅ **已解**（本节全链）|
| `PW_PARAM_CHANNEL` §4 路 A（键注入） | 候选路 | 保持现状；**本路 B 已优先打通** |
| `RE_PROGRESS` "shell 无法推 PW" | 架构上做不到 | **修正**：shell 侧推 PW 路径成立（POC 在案），
上机验证后更新 |

---

## 6. 产物索引

| 文件 | 内容 |
|---|---|
| `raw8/repro/capfw/pltmap.py` | PLT→符号通用映射器（新） |
| `raw8/repro/capfw/disasm_range.py` | 按范围反汇编（新） |
| `raw8/repro/capfw/plt_symmap*.tsv` | 两个库的 PLT 全量映射（新） |
| `test_server/pwsend/pwsend.c` / `pwsend.arm` | POC 工具（新） |
| `raw8/repro/capfw/o3_find.sh` | 搜索脚本（新） |

*生成：2026-10-09 · 分支 `nxwa` · 全程离线 · 上机部分待 G0+G1 放行后按 §3 执行*
