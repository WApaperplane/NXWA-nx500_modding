# FilmLab「一键滤镜」设计（PW 直推版 · 2026-10-09）

> 任务：基于 O3 解出的属性总线传输层（`ATTR_BUS_MCB_2026-10-09.md`），
> 把 filmlab 的「3 步链路」压缩为**一键**：点配方 → 7 维直进 ISP → 画面立即变。
> 形态：**设计 + 已落地资产**（pwsend.arm `seq` / pwcalib.sh / filmlab.sh 集成 / gen_pwpush.py）。
> 状态：**机制全通、工具就绪、CI 全绿**；唯剩上机校准（R/G/B/HUE 的 id 与编码）——
> 校准完成 → 置 `FILMLAB_PW=1` → 一键生效。全程 L1（零 G4 依赖）。

---

## 0. 一句话

> **旧链路**（只有第 3 步有效）：`apply 配方 → 人工打开画面向导 → 选「自定义1」`。
> **新链路**：`apply 配方` 一步内完成 `①写槽 ②切槽 ③PW 直推`——
> ③ 用 `SetVariableDataMCB(id,&v,4)` 把 7 维直接送进 ISP PW 引擎（= di-camera-app
> 确认动作的**字节级等价**），画面秒级生效，`check` 判据直接转 ✓。

---

## 1. 旧 vs 新（为什么旧链路必须"人工点"）

| | 旧（2026-10-08 定论） | 新（2026-10-09） |
|---|---|---|
| ① 存储 | `prefman set 0 0xa3ec…×7` + save | 同旧（保留） |
| ② 选择 | `setusr 20 0x140009`（借道切槽） | 同旧（保留） |
| ③ 参数 | ✗ **打不到 ISP**——只有 app「画面向导确认」会推 | ★ **`pwsend.arm` 直推**（同一 `SetVariableDataMCB` 通道） |
| 人工步骤 | 必须：画面向导 → 选「自定义1」 | **无**（`FILMLAB_PW=1`） |
| 判据 | `filmlab.sh check` 显示 ✗ | `check` 显示 **✓**（7 维对齐） |
| 保底 | — | 画面向导链路**始终保留**（slot9 有正规数据，重选即恢复） |

---

## 2. 新链路架构（apply 的动作序）

```
sh filmlab.sh apply <recipe>
  │  读 recipes.json 7 维（R/G/B/HUE/SAT/SHARP/CON）
  ├─ ① prefman set slot9 ×7  +  prefman save          （持久化，同旧）
  ├─ ② setusr 20 (借道切槽)                            （选择，同旧）
  ├─ ③ pw_direct(7 维) ── FILMLAB_PW=1 时              （★ 新增：直推）
  │     │  值编码（§3）
  │     └─ pwsend.arm seq <id v>… --yes
  │           └─ SetVariableDataMCB(id,&v,4) → CMCBAdapter::SetParam
  │               → CMulticoreBridge::Send(0x81, cmd=(id-0xff)|0x1300, 4, &v)
  │               → CSender 队列 → ipcc_write_pkt → p7 → ISP PW 引擎
  └─ check_isp_pw（只读判据）→ 期望 ✓
```

**幂等与回退**：③ 失败不影响 ① ②（已写入槽）；画面最坏情况 = 旧状态（等画面向导）。
`pw_direct` 的失败路径全部显式打印，**不重试**（单核 + MCB 队列保守）。

---

## 3. 值编码（核心表 —— 已离线自测）

`gen_pwpush.py --selftest` 全绿（往返精确）；shell 参考实现在 `filmlab.sh::pw_gain16/pw_raw16`。

| 维度 | 读回格式（已验证） | 发送值公式 | 例（portra800） |
|---|---|---|---|
| R/G/B COLOR | `(gain16<<16)\|0x00FF`；值 = `gain16×100/2032` | **`gain16 = ceil(值×2032/100)`** | 值109 → 0x08A7 |
| HUE/SAT/SHARP/CON | `(raw16<<16)\|0xD80A`；raw16 = `16×(值-10)+15`（**有符号**） | **`raw16 = 16×(值-10)+15`**（负→补码） | SAT=9 → 0xFFFF（-1） |

**为什么 ceil（而非 round / 下取整）**：实测 app 链路是"截断+截断"⇒ 读回系统性 −1
（109→108，仍在 check 的 5% 容差内）；我们选 **ceil** 让读回解码**严格回到配方值**，
使 `check` 判据逐项对齐（渲染差异 ≤1/2032，不可感）。★ 这是有意决策，非误差。

**发送容器**：一律 4 字节（低 16 位有效）。COLOR 走 int16（app 的 `getParam<short>` 路径），
SCALAR 负值按符号扩展（`-1 → FF FF FF FF`，= app 行为；p7 取低 16 位等价）。

---

## 4. id 表与校准实验（剩余的唯一未定项）

### 4.1 现状

| 维度 | id | 证据 |
|---|---|---|
| **SAT** | `0x110` | ★ 铁证（`setPWSaturation` 函数名 + movw 常量） |
| **SHARP** | `0x111` | ★ 铁证（`setPWSharpness`） |
| **CON** | `0x112` | ★ 铁证（`setPWContrast`） |
| **COLOR 主通道** | `0x10e` | ★ 铁证（`setPWColor`）——**但 R/G/B 三值如何分配未定** |
| G / B / HUE | 待定 | 候选 0x10f / 0x113 / …（见下实验） |

### 4.2 校准实验（pwcalib.sh；runbook 见 `test_server/pwsend/runbook.txt`）

**probe1（编码桥）**：`0x110←95, 0x111←63, 0x112←47`
→ readback 判据：三个标量读回 = 15/13/12 ⇒ **「发送值 = 读回高16位」假说成立**（判据的判据）。

**probe2（指纹）**：`0x10e←1000, 0x10f←1200, 0x113←79`
→ readback：命中项的**变量名**直接给出映射（如 `PWCOLOR_G 高16=1200` ⇒ 0x10f=G）。
→ R/G/B 第三通道若仍未定：以 1000 试 0x113/0x114 等（一次一个，间隔 ≥60s）。

**安全**：指纹值取"温和值"（1000/1200 对 COLOR 是低增益；79 对 SCALAR 是值14）——
不产生黑屏级扰动；实验后 `restore`（或画面向导保底）。
**r/g/b 备选假说**：若"单 id 多通道"读回全不中，测试"连续三次 0x10e"的顺序效应
（runbook [5] 备注）。

---

## 5. 工具与集成（已落地）

| 件 | 位置 | 状态 |
|---|---|---|
| `pwsend.arm`（send / seq / info） | `test_server/pwsend/` | ✅ 编译 + QEMU 验证（含负值、白名单、错误路径） |
| `pwcalib.sh`（snap/probe1/probe2/readback/restore） | 同上 | ✅ 语法/CI 过；objective readback 自动对照 |
| `gen_pwpush.py`（值编码器 + 对照表 + `.seq` 生成） | 同上 | ✅ selftest 全绿（往返精确） |
| `filmlab.sh` 集成（`pw_direct` + `pwpush` 子命令 + `FILMLAB_PW` 开关 + `PWID_*` 表） | `scripts/filmlab.sh` | ✅ 已改（默认关——行为与旧版完全一致）+ CI 过 |
| 上机 runbook | `test_server/pwsend/runbook.txt` | ✅ 9 步（probe1→readback→probe2→readback→restore→pwpush→apply 一键→固化） |
| 门控 lint | `gate_flow.py` G1-7c（三包合并） | ✅ PW=1脚本/OK |

**部署清单（相机端）**：
```
/mnt/mmc/filmlab/pwsend.arm      （chmod 755）
/mnt/mmc/filmlab/pwcalib.sh      （chmod 755）
/opt/usr/nx-ks/filmlab.sh        （新版替换）
```

**校准后固化（2 处）**：`filmlab.sh` 的 `PWID_*` 默认值 → 实测 id；
`FILMLAB_PW` 默认值 → 1（或在 `EV_*.sh` 里 export）。此后 **apply = 一键**。

---

## 6. 安全与回退

| 层 | 机制 |
|---|---|
| 白名单 | pwsend 仅允许 id ∈ [0x100, 0x12b]（= mm_camera 实机校验边界） |
| 值域 | 指纹值温和；空值/坏值直接拒绝（继承 filmlab 的"静默失败→破坏性写入"防线） |
| 速率 | 一次调用一条子命令；seq 条间 ≥150ms；失败**不重试** |
| 恢复（3 层） | ① `pwcalib.sh restore`（发回备份编码值）② 画面向导 → 自定义1（官方覆盖）③ 重启相机 |
| 可审计 | 每步落日志（`pwcalib_*.txt` / `filmlab last.log` 含 `pw=direct` 字段） |

---

## 7. 边界（明确不承诺的部分）

1. 一键盘的"立即"以 p7 的响应为准（预期 <1s；实测校准）。
2. 本设计**不**触碰固件、不写 p7 内存、不改 p7 —— 全程 L1，零 G4 依赖。
3. 与 3D LUT 通道**独立**（一个是 PW 参数引擎、一个是 LUT 表引擎；可叠加，见 LUT 链路文档 §4）。
4. `setvar` 仍为禁区（历史写死 capture 服务）；本链路走的是 app 正规发送路径。

---

*生成：2026-10-09 · 分支 `nxwa` · 离线完成；上机部分按 `test_server/pwsend/runbook.txt` 执行*
