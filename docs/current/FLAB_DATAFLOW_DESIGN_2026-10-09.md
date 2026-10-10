# FilmLab 数据流设计：设置数据导入路径 + 便捷增删配方（2026-10-09）

> 任务：探讨「一键滤镜」设置数据的导入路径，设计便捷增删配方的链路。
> 形态：**数据模型 + 一条龙工具**（`flab.py` 新增；`filmlab.conf` 外置设置 + `filmlab.sh` source 集成）。
> 状态：已落地并离线验证（渲染字节级一致 / lint / conf 优先级 / 逃生门）。

---

## 0. 一句话

> **三类数据、三个文件、一条命令流**：
> `recipes.json`（配方）｜`filmlab.conf`（设置：PWID 校准结果/开关）｜`luts/*.bin`（LUT 表）。
> 全部由 PC 侧工具链管理：`flab.py`（配方+设置）与 `deploy_luts.py`（LUT），
> `deploy` 一条命令完成 **推 → 生效 → 菜单重建 → 回收核对**。

---

## 1. 数据模型（先分类，再谈路径）

| 数据 | 文件（相机端） | 谁改 | 变更频率 | 管理工具 |
|---|---|---|---|---|
| **配方**（7 维 + label） | `/mnt/mmc/filmlab/recipes.json` | 木一（增删改） | 经常 | `flab.py add/edit/rm` |
| **设置**（PWID 校准结果 / FILMLAB_PW 开关 / 参数） | `/mnt/mmc/filmlab/filmlab.conf` | 校准后固化 | 低 | `flab.py conf` |
| **LUT 表** | `/mnt/mmc/filmlab/luts/*.bin` | `.cube` 导入 | 中 | `deploy_luts.py` |
| 工具（.arm/.sh） | `/mnt/mmc/filmlab/` + `/opt/usr/nx-ks/` | 升级 | 低 | 各包 deploy 工具 |

**关键设计决策**：把 PWID 校准结果从"脚本内写死"改为"**外置设置数据**"——
校准完成的结束动作从"改 filmlab.sh + 重推脚本"变成"**推一个小 conf 文件**"。

---

## 2. 链路全景

```
[PC 侧]                                      [相机端]
┌─────────────────────────────┐
│ flab.py add/edit/rm         │  recipes.json
│   ↓ 严格缩进渲染（引擎兼容） │ ──── deploy ───► /mnt/mmc/filmlab/recipes.json
│ flab.py lint（模拟 awk 解析）│                      │
│ flab.py conf --set K=V      │  filmlab.conf        ▼
│   ↓                         │ ──── deploy ───► /mnt/mmc/filmlab/filmlab.conf
└─────────────────────────────┘                      │  filmlab.sh 启动时 source
                                                     ▼
                              telnet 一条龙：export（UI 用 txt）→ mkgui（菜单重建）
                                             → cur.idx 越界归一 → 回收菜单核对
```

**回环核对**（deploy 自动）：机上 md5 == 本地；菜单 `button|` 行数 == 配方数 + 2。

---

## 3. 便捷增删配方（新链路，替代旧"两步走"）

### 3.1 旧链路 vs 新链路

| | 旧（deploy_recipes.py） | 新（flab.py） |
|---|---|---|
| 加配方 | 编辑 `nx500_recipes.txt` → `mk_recipes_json.py` → `deploy_recipes.py a` → 人工核对 → `deploy_recipes.py b <idx>` | `flab.py add …` → `flab.py deploy`（一条龙） |
| 删配方 | 同左 + 手工关注 cur.idx | `flab.py rm …` → `deploy`（**自动归一 cur.idx**） |
| 格式保障 | 依赖 mk 脚本的缩进纪律 | 渲染器**逐字节复刻**引擎格式 + lint 模拟引擎解析 |
| 兜底 | — | `deploy_recipes.py` 两步走保留为"谨慎流" |

### 3.2 渲染器（为什么不能用 `json.dumps(indent=4)`）

引擎用 awk 解析（`jlist` 匹配 `^    "`、`jval` 遇 `^    \}` 退出），需要**混合缩进**：
`"recipes"` 2 空格｜配方键 4 空格｜字段 8 空格。`flab.py::render()` 手工渲染，
并在 add/rm 测试中验证：**对未变更内容与源文件逐字节一致**（diff 仅新增/删除行）。

### 3.3 lint（引擎兼容性校验，deploy 前强制）

`flab.py lint` 用 Python 复刻 `jlist`/`jval` 的解析逻辑，逐项验证：
- 每个配方键能被"4 空格规则"读到；7+1 个字段都能被 `jval` 读到；
- label 不含 `"` 与 `|`（会破坏 awk/UI 解析）；
- 值域哨兵：COLOR ∈ [40,220]、SCALAR ∈ [-10,30]（超界 warn）；
- 配方数 ≤ 21（mod_gui 菜单 22 按钮上限 - 2）。
**lint 不过 ⇒ 拒绝部署**（防"静默坏值 → 整屏黑"历史事故重演）。

### 3.4 删除的边界处理

- `cur.idx` 越界：deploy 时机上自动检测（`N=$(grep -c '"label"')`），越界归 0 ✓；
- `cycle` 的 `mod N` 本身有兜底（不会崩）；
- mkgui 菜单自动重建（按钮随配方数变化）+ 回收核对。

---

## 4. 设置数据（PWID 校准结果）导入路径

### 4.1 filmlab.conf（外置设置）

```
# /mnt/mmc/filmlab/filmlab.conf （KEY=VALUE，busybox sh 直接 source）
FILMLAB_PW=1          # 一键滤镜总开关
PWID_G=0x10f          # 校准实测（例）
PWID_B=0x113
PWID_H=0x114
```

- `filmlab.sh` 在变量默认段前 **source** 该文件（2026-10-09 集成）；
- **优先级：conf（持久）> 环境变量 > 脚本默认**；临时调试用 `FILMLAB_NO_CONF=1` 跳过 conf；
- 已离线验证：无 conf / 有 conf / 逃生门 三种场景行为正确。

### 4.2 校准结果固化的完整流程（与 pwcalib 衔接）

```
① 上机校准（test_server/pwsend/runbook.txt）→ readback 得实测 id 表
② PC 侧固化：
   python flab.py conf --set PWID_G=0x10f --set PWID_B=0x113 --set PWID_H=0x114 --set FILMLAB_PW=1
③ 推送生效：
   python flab.py deploy --conf
④ 相机端验证：filmlab.sh check → ✓（一键滤镜闭环）
```

### 4.3 安全语义

- conf 由 `flab.py` 管理（结构化写入、注释模板）；手工编辑也兼容（它就是 shell 键值对）；
- 空 conf / 缺 conf：`source` 静默失败，全部回默认值（行为=旧版）——**零破坏性**；
- `FILMLAB_PW=1` 且 pwpush 用的 id 未校准：pw_direct 对空 id 自动跳过（G/B/H 空则不发送）——不会发坏数据。

---

## 5. 一条龙操作手册（速查）

```bash
PY=C:/Users/31623/.workbuddy/binaries/python/versions/3.13.12/python.exe

# —— 配方 ——
$PY test_server/filmlab/flab.py list
$PY test_server/filmlab/flab.py add velvia100 --label "Velvia 100" \
      --r 105 --g 110 --b 108 --hue 10 --sat 14 --sharp 11 --con 13
$PY test_server/filmlab/flab.py rm xpro
$PY test_server/filmlab/flab.py lint
$PY test_server/filmlab/flab.py deploy [--host 192.168.0.105] [--sync-filmsim]

# —— 设置（校准结果等）——
$PY test_server/filmlab/flab.py conf --set FILMLAB_PW=1 --set PWID_G=0x10f
$PY test_server/filmlab/flab.py conf --show
$PY test_server/filmlab/flab.py deploy --conf

# —— LUT ——
$PY test_server/lutpipe/deploy_luts.py build-push --host 192.168.0.105
```

**部署后相机端（自动/手动）**：
```
filmlab.sh export     # recipes.txt（nxfilmui 用）—— deploy 已自动跑
filmlab.sh mkgui      # mod_gui 菜单重建 —— deploy 已自动跑
lutpick.sh list       # LUT 目录
```

---

## 6. 校验与安全（汇总）

| 环节 | 机制 | 验证状态 |
|---|---|---|
| 渲染 | 混合缩进逐字节复刻 | ✅ diff 仅差异行（add/rm 实测）|
| lint | 模拟 jlist/jval + 值域 + label 消毒 + 上限 | ✅ 对现状 18 配方 PASS |
| conf | 优先级 + 逃生门 + 空文件安全 | ✅ 三场景模拟通过 |
| 部署 | lint 门禁 + md5 核对 + 菜单 button 数核对 + cur.idx 归一 | ◐ 需上机首跑（工具链复用 deploy_recipes 的成熟模式）|
| 回滚 | 删配方=双向可逆（加回即可）；conf 可 unset；recipes 留备份 | ✅ |

---

## 7. 待办与进阶

| # | 项 | 备注 |
|---|---|---|
| 1 | deploy 首次上机实跑 | 需相机在线；先 `flab.py lint` 后 deploy |
| 2 | （可选）配方版本 diff | `flab.py` 可加"--diff 显示本次变更" |
| 3 | （可选）web 导入入口 | 相机已有 web 服务（80 端口）——可做"上传 recipes.json"页面；先不做（PC 链已足够便捷） |
| 4 | 配方库 >21 时的分页菜单 | 当前上限 21（mod_gui 限制）；超限时 lint 已警告 |

---

*生成：2026-10-09 · 分支 `nxwa` · 工具：`test_server/filmlab/flab.py`（新）· `filmlab.sh` conf 集成（新）*
