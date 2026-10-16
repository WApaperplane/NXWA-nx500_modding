# M2 配方名显示设计（.mo 路线）· 2026-10-16

> **目标**：M1+M2 文案层——原生菜单「画面向导 → 自定义 1/2/3」显示为**配方名**（样机：Portra 400 / Gold 200 / TriX 400）。
> **输入**：`UI_R1_SUPPLEMENT §10`（.mo 文案链结案）；真机 zh_CN `di-camera-app.mo`（172,850B, `f2d60cd2…`，10-15 抓取归档）；`NATIVE_UI_ROADMAP` §4（UI-R2b 标签替换标准）。
> **性质**：设计 + 离线样机 + 投递件（**零写机**；上机动作列 §6 待放行）。
> **口径**：✅ 已证（离线实测）｜🔶 推断/设计 ｜ ❓ 未决（附验证法）

---

## 0. 结论

1. **替换工艺 = 「追加式」MO 修改**：新 msgstr 追加文件尾，仅改 translations 表对应条目 8 字节 —— 比等长替换更保守：**原字符串存储区、msgid 表、哈希表、排序、其余全部字节 100% 原样** ✅。
2. **样机已生成并 5 重验证**（§3）：真机件 → 三条 CUSTOM 替换 → `e531bd5f…`（+29B）✅。
3. **投递 = P5 生态第二条目**：复用 `t2_premount.sh`（v2 多条目，ExecStartPre 型 bind-mount）→ `/usr/share/locale/zh_CN/LC_MESSAGES/di-camera-app.mo`；文件放 p14（`/opt/usr/nx-ks/locale/zh_CN/`），**刷机存续 + 条件语义（文件不在 = 不改名）** ✅（设计件就绪，未上机）。
4. **生效语义**：正常关机 → 开机（禁 restart，沿既有铁律）。诚实边界：hibernation resume 场景下的 mount 保持性 = 与 P5 相同的未实测项（§4.3）。
5. **边界**：显示名为**静态**（重新生成 + 重投递可换名，工具一条命令）；「动态跟随配置」与「三槽选择一致性」属另一层，见 §7。

---

## 1. 接口点（为什么改 .mo）

`UI_R1_SUPPLEMENT §10` 已结案：菜单主显示名 = **`dcgettext(name)` 直查 `.mo`**（数据表 name 字段直接作为 msgid）。

| 目标词条 | idx | msgstr 现值 | 落点（trans 表） | 替换后（样机） |
|---|---|---|---|---|
| `CAP_MENU_CUSTOM_MODE_1` | 175 | 自定义 1 | len@0x4a24 / off@0x4a28 | **Portra 400** |
| `CAP_MENU_CUSTOM_MODE_2` | 176 | 自定义 2 | len@0x4a2c / off@0x4a30 | **Gold 200** |
| `CAP_MENU_CUSTOM_MODE_3` | 177 | 自定义 3 | len@0x4a34 / off@0x4a38 | **TriX 400** |

- 采样自 `recipes.json` 的 `label` 字段（95 条配方规范名）；具体三组可任意重生成（§5 复现）。
- `CAP_FN_PW`（图片向导）**默认不改**（保留官方语义）；如需改，工具已支持（§5.3 示例）。
- 文件属性：**无 header 元数据条目**（无 charset 声明）——真机 glibc 直接使用原字节（中文显示正常 = 既有铁证）；替换不触碰此性质。

**被否路线**（依据 §10）：~~改选项表 name 指针复用 msgid~~（文案种类受限于既有词条）；~~改 strcmp 链~~（主显示名不走 `GetDescriptionByTitle`）。

---

## 2. 替换工艺（追加式）

```
原文件 [header | orig表 | trans表 | hash表 | 字符串区………]
                                 ↑改这里(8B×3)        ↓
新文件  ……同上全原样…… + trans 表 3 项 (len,off) 改指 ──→ [追加区: 新串1\0 新串2\0 新串3\0]
```

- **原理**：MO 的查找 = 「(msgid→index) 由 orig 表/hash 表决定」+「index→msgstr 由 trans 表项 (len, off) 决定」。只改后者的 3 项 ⇒ **所有查找数据结构不变，任何查找路径（hash/二分）命中的 index 不变**，读出的只有目标条目变化。
- **差异面（字节级实证）**：原 172,850B → 新 172,879B = **+29B**；共同前缀差异 = **12 字节**（3 项 × (len 变化 1B + off 变化 3B)），其余 100% 相同 ✅（证据 §3[2]）。
- **为什么不用 msgfmt 重编译**：不引入 gettext 工具链依赖（本机无）；不经过「.po 往返」丢失格式细节的风险；追加式改动面可证明最小。

---

## 3. 验证矩阵（全离线，2026-10-16）

| # | 验证器 | 对象 | 结果 |
|---|---|---|---|
| 1 | 自写解析器逐条对比（`mo_patch verify`） | 真机件 vs 样机 | **PASS**：2194 条全量，除 3 目标外 msgid/msgstr 全同 ✅ |
| 2 | 字节级 diff（`mo_patch diff`） | 真机件 vs 样机 | 差异 = **12B 表项 + 29B 尾区**，见证 §2 ✅ |
| 3 | glibc 双路径模拟（`--glibc-sim`） | 样机 | 目标 3 条：**hash 路径 steps=0 直命中 + 二分路径命中**，读出 = 新值 ✅；两文件 hash 域统计全同（覆盖 2194/2194、无重复） |
| 4 | Python gettext 端到端（smoke test） | **合成规范文件**（带 header）| build → patch → 标准解析器加载 → 查询全绿 ✅（证明产出物 = 合法 MO） |
| 5 | Python gettext 加载 | 真机件 | 不可用（无 header → 默认 ascii 解码失败）——**原文件同样失败**，属文件固有性质、非替换引入 ✅（该判定已内置工具输出） |

- 证据文件：`fw/v1.12/dicam/locale/m2sample_verify_2026-10-16.txt`（53 行完整输出）。
- 说明（3）：hash 表覆盖率完备但与 32 位参照实现部分吻合（`reachable=1389/2194`）——推测生成环境位宽差异；**本替换不依赖 hash 表行为**（hash 表字节未经触碰；若 glibc 加载期弃用该表则走二分，路径结论相同）。目标 3 条在两路径均直命中。
- ❗ 遗留观察：真机侧「glibc 实际走哪条路径」不影响本替换（§2 论证），无需额外验证；如将来做**结构级大改**（增删词条）才需要关注。

---

## 4. 投递设计（P5 生态）

### 4.1 链路

```
PC: fw/v1.12/dicam/locale/di-camera-app.zh_CN.m2sample.mo (+MANIFEST.md5)
  │  FTP（21）
  ▼
SD: /mnt/mmc/m2-locale/di-camera-app.zh_CN.m2sample.mo (+MANIFEST.md5)
  │ 相机端: sh /opt/usr/nx-ks/dicam/m2_locale.sh deploy   （md5 双校验）
  ▼
p14: /opt/usr/nx-ks/locale/zh_CN/di-camera-app.mo          （刷机存续区）
  │ 开机: di-camera-app.service ExecStartPre=-…/t2_premount.sh   （条件 bind-mount）
  ▼
rootfs 视图: /usr/share/locale/zh_CN/LC_MESSAGES/di-camera-app.mo ← 被挂载为 p14 件
  │ App 启动后 gettext 首次查询 → 读到新名
  ▼
菜单显示: 自定义 1/2/3 → Portra 400 / Gold 200 / TriX 400
```

### 4.2 组件清单（本日新增/修改）

| 件 | 位置 | 状态 |
|---|---|---|
| 样机 .mo | `fw/v1.12/dicam/locale/di-camera-app.zh_CN.m2sample.mo`（`e531bd5f…`）| ✅ 生成+验证 |
| 清单 | 同目录 `MANIFEST.md5` / `m2sample_manifest.json` / `m2sample_verify_2026-10-16.txt` | ✅ |
| 部署器 | `scripts/dicam/m2_locale.sh`（相机端 deploy/remove/status）| ✅ 就绪（未上机）|
| 挂载器 v2 | `scripts/dicam/t2_premount.sh`（**多条目**：T2 补丁体 + M2 locale；单条目行为与 v1 一致）| ✅ 就绪（未上机）|
| 状态脚本 | `dicam_patch_status.sh` 增「M2 locale」段 | ✅ |
| 工具 | `tools/mo_patch.py`（info/get/set/verify/diff）+ `tools/mo_patch_smoke_test.py` | ✅ 入库 |

### 4.3 生效语义与边界

- **生效**：由 unit `ExecStartPre` 在 App exec 前完成挂载（时序硬保证，同 P5）；App 启动后 gettext 读到的即是样机。
- **禁用（条件语义）**：p14 无部署件 ⇒ premount 静默跳过 ⇒ 官方文案（完全可恢复）。
- 🔶 **诚实边界**：本机日常「关机开机」若为 hibernation resume（进程不重新 exec），mount 保持性依赖快照——与 `T2_DELIVERY_REVISION §6.3` 同一未实测项；**刷机后重启、断电重启均为冷启动路径**，可完成首次挂载。上机时记录（§6 观察项）。
- **回退**：① `m2_locale.sh remove` + 正常开关机；② 卸载 P5（`dicam_p5_rollback.sh`）；③ 重刷官方 SLP（兜底）。三路均机内完成、不依赖网络。
- ⛔ 全程禁 `systemctl restart di-camera-app`。

---

## 5. 复现（重新生成/换名）

### 5.1 依赖
- 源 .mo：真机 zh_CN 件（`E:/tmp/dicam_zh_CN.mo`，`f2d60cd2…`；相机在线可重新抓取：telnet cp → SD → FTP，见 `nx-fetch.py`）。
- 工具：`python tools/mo_patch.py`（纯标准库）。

### 5.2 重生成样机（换任意三个配方名）
```bash
python tools/mo_patch.py set E:/tmp/dicam_zh_CN.mo \
  fw/v1.12/dicam/locale/di-camera-app.zh_CN.m2sample.mo \
  --kv "CAP_MENU_CUSTOM_MODE_1=Portra 800" \
  --kv "CAP_MENU_CUSTOM_MODE_2=Superia 400" \
  --kv "CAP_MENU_CUSTOM_MODE_3=Ektachrome" \
  --expect-src-md5 f2d60cd2f2687de43089729fb06f436c \
  --manifest fw/v1.12/dicam/locale/m2sample_manifest.json
python tools/mo_patch.py verify E:/tmp/dicam_zh_CN.mo <新文件> --glibc-sim   # 复核
# 更新 MANIFEST.md5 后按 §6 走
```
- 名字来源建议 = `scripts/filmlab/recipes.json` 的 `label`（95 条）；长度建议 ≤24B（工具超限会 warn；UI 截断阈值未验）。

### 5.3 （可选）改「图片向导」名
```bash
python tools/mo_patch.py set <src> <out> --kv "CAP_FN_PW=胶片实验室"
```
- ⚠️ 默认**不做**：保持官方功能语义；如做，属产品口径决策（列 D1 待裁）。

---

## 6. 上机清单（U5，待放行）

**前置**：门控重跑（`gate_flow.py`）→ 相机在线（23/21）→ P5 已装（`dicam_p5_install.sh`；若未装，先装）。

| 步 | 动作 | 判据 |
|---|---|---|
| 1 | PC→SD：样机目录 3 件（.mo / MANIFEST.md5）经 FTP 上传 `/mnt/mmc/m2-locale/` | 上传后 md5 一致 |
| 2 | telnet：`sh /opt/usr/nx-ks/dicam/m2_locale.sh deploy` | 双校验 OK、输出部署 md5 = `e531bd5f…` |
| 3 | `sh /opt/usr/nx-ks/dicam/m2_locale.sh status`（**挂载前**：应显示「未挂载」） | 基线记录 |
| 4 | **正常关机 → 开机** | — |
| 5 | `sh .../m2_locale.sh status` | 「目标 = 部署件（M2 生效中）」+ mount 在位 |
| 6 | **观察菜单**：MENU → 相机页 →「图片向导」→ 选项列表 | 三条原「自定义 1/2/3」→ **Portra 400 / Gold 200 / TriX 400** |
| 7 | 观察项（记录）：① 文本截断/溢出（13 字符 vs 原 3 字）；② 字体渲染（拉丁混排）；③ 与 OSD/SmartPanel 面是否同步（若该处也显示槽名）；④ 重启一次（冷启动）复查 mount 保持 | 记入 `raw8/gates/` |
| 8 | **回退演练**：`m2_locale.sh remove` → 正常开关机 → 菜单恢复「自定义 1/2/3」 | 恢复原样 |

- 本上机项**不影响拍摄/参数**（纯文案层；最坏 = 名字显示异常，功能零影响）。
- 可与其他上机批（U1-U3）合并执行；顺序建议：U1（P5 验证）→ U5（本项，P5 已验后的自然延伸）。

---

## 7. 未决 / 后续（诚实清单）

| # | 项 | 说明 | 验证法 |
|---|---|---|---|
| M2-U1 | **动态名**（跟随槽配置变化） | .mo 为静态文件；「换配方自动改显示名」需值层/内存层机制（poker 已降级、App 事务未接）⇒ 本设计不含 | 后续评估（值系统 GUI_Set_System_Value 侧写路径） |
| M2-U2 | **三槽选择一致性** | 显示名只解决「看到什么」；「选中槽 1 → 应用 Portra 400 值」的一致性取决于：① A2 直推把配方值写进槽区且 `0xda=10`（自定义1）⇒ **槽 1 一致性成立**（选择自定义1 重应用槽区值 = 配方值）；② 槽 2/3 的「独立存储写入」通道未证（A2 现只覆盖「自定义1」位置；`0x10e/0xdb` 槽存疑） | 上机只读实验 U6：切自定义 2/3 后回看自定义 1 值是否保留；再定 V2 方案 |
| M2-U3 | 其他语言 .mo（en 等） | 相机语言非中文时本样机不生效；en 件需相机在线抓取（同 zh_CN 流程） | 上机抓取 → 同工具生成 |
| M2-U4 | UI 截断阈值 | 名长 >24B 的警告是**经验值**，实际渲染宽度未测 | 上机观察项 7① |
| M2-U5 | 字体/CJK 边界 | 样机为拉丁名；中文配方名（如「波特拉」）应可行（原厂中文渲染链），未实测 | 上机用中文名样机复测（可选） |

---

## 8. 证据索引

- 样机与证据：`fw/v1.12/dicam/locale/`（.mo + MANIFEST.md5 + manifest.json + verify txt）
- 工具：`tools/mo_patch.py`、`tools/mo_patch_smoke_test.py`
- 投递件：`scripts/dicam/{m2_locale.sh, t2_premount.sh(v2), dicam_patch_status.sh}`
- 上游：`UI_R1_SUPPLEMENT_MENU_CHAIN_2026-10-15.md §10`、`UI_R2R3_DESIGN_2026-10-15.md §2`、`T2_DELIVERY_REVISION_2026-10-15.md §6`、`NATIVE_UI_ROADMAP_2026-10-15.md`（M1/M2 标准）

---
*生成：2026-10-16 · Codex 克隆工作树 · 全离线（工具生成 + 五重验证）；零写机（上机动作见 §6）。*
