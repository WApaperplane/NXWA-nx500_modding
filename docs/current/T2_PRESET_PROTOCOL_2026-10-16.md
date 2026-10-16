# T2 —— 统一预设与适配器协议 v1（2026-10-16）

> **任务来源**：`FILMLAB_LUT_NATIVE_UI_GOALS_2026-10-16.md` §5（T2，P0：定义统一预设与适配器协议）。
> **性质**：协议设计 + **可执行模拟后端**（离线）。实机接入属 T3/T5/T8。
> **对应实现**：`test_server/lutpipe/preset_sim.py`（模拟器）+ `test_server/lutpipe/presets/schema_v1.json`（格式样张）。

---

## 0. 设计约束（来自 GOALS，逐条落实）

| GOALS 要求 | 本文对应 |
|---|---|
| 预设以**稳定 ID** 关联 显示名 / PW 参数 / LUT 资产 / 能力说明 | §1 `Preset` 结构（`id` 永不随显示名变化） |
| LUT 资产记录 **来源 / 内容哈希 / 表格式 / 输入色彩条件** | §1.2 `lut` 段（`sha256` + `input_color.verified`） |
| 三原厂自定义槽可作**快捷映射**，但配方库规模不与其绑定 | §1.3 `slot_map`（可选、独立、可空） |
| 状态至少区分：已选择 / 应用中 / 仅预览生效 / 拍摄效果已验证 / 失败 / **已被原厂操作修改** | §2 状态机（+`partial` 部分成功） |
| PW 成功而 LUT 失败 ⇒ **显示部分成功 + 恢复**；不得包装为原子事务 | §2.3 `partial` 语义 + §3.2 `ApplyResult` |
| UI 线程不执行耗时加载 / 同步 shell；完成后回填状态 | §4 异步约定（工作线程 + 有界队列） |
| 第一版：焦点只改选择；确认才应用；滚轮停留预览**后置** | §2.1 状态机首版边界 |
| **「关闭 LUT」= 停止守护 + 恢复确认过的原厂选表/配置**（不得以 identity 代替） | §3.3 `rollback` 语义 + `restore_factory()` |
| PW 与 LUT **应用顺序需实机确定**（不假定 PW 提交不触发 p7 重配置） | §3.4 `order` 可配置 + 顺序未知标记 |
| identity 仅作诊断，不宣称「原厂中性」 | §1.2 `purpose` 字段（`style` / `diagnostic`） |

---

## 1. 预设格式（`nxwa.preset/1`）

### 1.1 顶层

```json
{
  "schema": "nxwa.preset/1",
  "id": "portra400",                      // 稳定 ID：永不变；文件名/索引均用它
  "display_name": "Portra 400",           // 显示名：可本地化、可改，不承载语义
  "capability": { },                      // §1.2
  "pw": { "R":106,"G":100,"B":93,"HUE":11,"SAT":9,"SHARP":9,"CON":8 },
  "lut": { },                             // §1.2（可缺省）
  "slot_map": { },                        // §1.3（可缺省）
  "meta": { "author":"…","created":"…","notes":"…" }
}
```

- `pw` 字段名 = `recipes.json` 既有键（R_COLOR/G_COLOR/…/CONTRAST）的短名；值域 = A2 直推原始域（R/G/B 0–200；其余 0–20）。
- **`id` 与 `display_name` 强分离**：M2 文案工艺只动显示名，**不得**参与任何寻址（GOALS §3）。

### 1.2 能力块

| 字段 | 取值 | 语义 / UI 义务 |
|---|---|---|
| `pw` | bool | 含 PW 参数 |
| `lut` | bool | 含 LUT 资产 |
| `preview` | bool | 预览可用（LUT1 直灌或 PW 即时） |
| `still` | `native` / `postproc` / `none` | 成片**机制可达性**：原生直灌可达 / 需后处理 / 不承诺。（E4 后 LUT 直灌 ⇒ 只能 `postproc`/`none`；纯 PW 参数链 ⇒ `native`） |
| `still_verified` | bool | 成片路径**是否已实机验收**。`still=native` 但此值为 `false` ⇒ 状态机**不得**进入 `still_verified`，UI 按「仅预览生效」呈现（诚实边界） |
| `requires_firmware` | `null` / `"A2"` | 固件前提；探测不到 ⇒ PW 段降级「不生效」并如实显示 |
| `lut_asset` | `{ "file","sha256","format","input_color" }` | 见下 |
| `lut_asset.input_color.verified` | bool | **false ⇒ UI 不得宣称色彩准确/即导即用**（GOALS §6） |
| `lut_asset.purpose` | `style` / `diagnostic` | identity 类表必须标 `diagnostic`，且**不可**作为「关闭/恢复」手段 |

### 1.3 槽映射（可选）

```json
"slot_map": { "slot": 1, "verified": false }
```
- 语义 =「该预设当前映射到某原厂自定义槽」；`verified=false` 表示**只是文案/快捷映射，槽内容一致性未验证**（GOALS §3：改名样机不构成一致性完成）。

---

## 2. 状态机

### 2.1 状态与转移（首版）

```
select(preset)                confirm()                全部成功
  [idle] ─────────────► [selected] ────────────► [applying] ──────► [applied]
                                                      │                 │
                                    部分成功 ─────────┤                 ├─► [preview_only]      （仅预览生效；成片走 postproc/none）
                                                      ▼                 ├─► [still_verified]    （成片经实机验收后）
                                                  [partial]             └─► [external_modified] （原厂菜单改过参数）
                                                      │
                                       retry_failed() │ rollback()
                                                      ▼
                                             [applied] / [rolled_back]
```

| 状态 | 含义 | UI 呈现义务 |
|---|---|---|
| `idle` | 未选择 | — |
| `selected` | 焦点选中但**未应用**（滚动焦点只改这里） | 不得显示「已应用」 |
| `applying` | 应用中（工作线程） | 忙碌态；**拒绝并发确认**（合并/拒绝重复） |
| `applied` | 全部适配器成功 | 需带 `preview_only` / `still_verified` 子状态 |
| `partial` | 部分适配器失败 | **如实显示哪一部分成功/失败** + 提供「重试失败项 / 回滚成功项」 |
| `preview_only` | LUT/PW 仅预览生效 | 明示「成片不跟随」（当前 LUT 常态） |
| `still_verified` | 成片路径已实机验收 | 置位条件 = `capability.still=="native"` **且** `capability.still_verified==true`（两者缺一即按「仅预览生效」呈现） |
| `external_modified` | 检测到原厂侧改参（PW 值/槽被改） | 显示「已被修改」，禁止继续宣称精确匹配 |
| `rolled_back` | 已恢复应用前状态 | 明示恢复范围（PW / LUT / 两者） |

- **取消语义**：`cancel()` 仅在 `applying` 且适配器支持中断时有效；**已提交的写入不回滚**（除非显式 `rollback()`）——GOALS §3：不能假定取消等于回滚。
- **重复确认**：`applying` 期间的新 `confirm()` 合并或拒绝（标记 `busy`），不得排队执行第二个事务。

### 2.2 外部改参检测

- **PW**：与 `applied` 时记录的七维快照比对（`varlist`/直推回读）；
- **LUT**：比对 `Cfg.SelLUT` 与守护状态、目标 `LUT0` 地址；
- 任一不一致 ⇒ `external_modified`（**不自动恢复**，由用户决定重应用或清除）。

## 3. 适配器接口

### 3.1 接口（伪代码，两实现：`pw` / `lut`）

```
Applier:
  name() -> "pw" | "lut"
  probe(preset, ctx) -> ProbeReport        # 固件/落点/守护/表文件/哈希 逐项可用性
  apply(preset, ctx) -> ApplyResult        # 幂等；内部可轮询 cancel 标志
  rollback(preset, ctx) -> ApplyResult     # 回到本适配器 apply 前状态
  classify(preset, ctx) -> ResultClass     # 供控制器估算可行域（可选）
```

### 3.2 结果分级（**禁用原子化包装**）

```
ApplyResult :=
  ok      : bool
  level   : "full" | "partial" | "failed"
  detail  : { per_step: [...], evidence_ref: "<raw8/…>" }
  restore : RestoreHandle | null            # 供 rollback
```
- **控制器只做逐适配器汇总**：`(pw_result, lut_result)` → 状态机 §2.1。
- **禁止**：把二者合成一个「全成功/全失败」布尔对外。

### 3.3 `rollback` 与「关闭/恢复」语义（GOALS §3 落实）

| 动作 | 实现 | **禁止** |
|---|---|---|
| `rollback_lut()` | 停止守护 → `op_init(sel=0,…)` 恢复原厂选表 → `lutload restore` | 写 identity 表冒充「关闭」 |
| `rollback_pw()` | 恢复 apply 前七维快照（经 A2 直推）或提示用户在原厂菜单重设 | 假定「参数提交不触发 p7 重配置」 |
| `restore_factory()` | 两者的组合恢复（目标 = 已确认的原厂状态） | 以 identity 作为「原厂中性」的证明 |

### 3.4 应用顺序（**未定，可配置**）

```json
"order": ["pw", "lut"],          // 首版默认；T4/实机裁决后定稿
"order_tbd": true                // 标记：顺序尚未实机验证（GOALS 要求不得假定）
```
- 顺序不确定的理由：PW 提交（A2 直推 → 槽变更 → 应用链）可能触发 p7 表重载 ⇒ 影响 LUT 存活；反之 LUT 写表需要「抢回态」静默期。二者交互须实机测（转 T4/T7）。

## 4. 线程与生命周期约定

- UI 线程只做：状态转移请求、界面刷新。**不执行**文件 IO / shell / 表装载。
- 工作线程：有界单队列（一次只跑一个预设事务）；完成后以消息回主循环。
- 对象销毁 / 模式切换（拍照↔回放）⇒ 拒绝陈旧请求回写 UI（丢弃带 generation 号 ≠ 当前的完成消息）。
- 失败/取消时**不假设** UI 与硬件一致 ⇒ 重读实际状态（`probe()`）后再显示。

---

## 5. 模拟后端与验证（`preset_sim.py`）

模拟器实现：`PwMock` / `LutMock`（可注入故障）+ `Controller`（状态机）；输出**状态轨迹**。

| 场景 | 注入 | 期望轨迹 |
|---|---|---|
| S1 全成功 | — | `idle→selected→applying→applied→preview_only` |
| S2 部分失败 | lut.apply 失败 | `…→applying→partial`（detail 标明 pw=ok / lut=fail）；可 `retry_failed` |
| S3 取消 | apply 中置 cancel | `applying→`（未提交步不回滚）`→partial/rolled_back` 按显式选择 |
| S4 外部改参 | 应用后 `external_change()` | `applied→external_modified` |
| S5 固件缺失 | `requires_firmware=A2` 且探测缺失 | pw 段降级「不生效」，状态如实标注；LUT 部分照常 |
| S6 关闭语义 | `close_lut()` | 走 `rollback_lut`（**不写 identity**）；轨迹记录恢复动作 |

运行：
```bash
python test_server/lutpipe/preset_sim.py --all        # 全部场景 + 轨迹
python test_server/lutpipe/preset_sim.py --scene S2   # 单场景
```

## 6. 未决（转下游任务）

| # | 项 | 归属 |
|---|---|---|
| 1 | `order`（PW/LUT 顺序）实机裁决 | T4/T7 + 上机 |
| 2 | `still: native` 何时可置位 | T8（成片链验收） |
| 3 | 原厂改参的**可靠检测**（varlist 采样点 / Cfg 读回频率） | T5/T8 |
| 4 | 槽映射一致性（三槽 = 三预设？） | U6 槽语义实验 + T3 |
| 5 | `.mo` 动态显示名（跟随预设） | 后续（M2 已知边界） |

---
*生成：2026-10-16 · 离线（协议 + 模拟后端）；实机接入属 T3/T5/T8。*
