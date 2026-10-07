# NX500 UI 菜单写入与接入（完整机制 + 注入指南）

> 时间：2026-10-07 22:00
> 方法：仓库脚本静态分析（`scripts/`、`backup_original/`）+ 与原生模板逐字对比
> ★ 本文**推翻** `HANDOVER §4.5`「系统菜单由 p7 渲染，加菜单项要改 p7」这一笼统断言，
> 给出**三条零固件风险**的菜单注入路线。

---

## 〇、★★★★★ 三十秒速查

| 问题 | 答案 |
|---|---|
| 相机 UI 菜单怎么"写入"？ | ★ 菜单是**纯文本文件** `gui_*.NX500`，格式 `类型\|标签\|脚本`，放在 `/opt/usr/nx-ks/` |
| 怎么"接入"？ | ★ **三条件**：① 写好 `gui_xxx.NX500` ② 放进 `/opt/usr/nx-ks/` ③ 在主菜单挂一行 `button\|名字\|@/opt/usr/nx-ks/gui_xxx.NX500` |
| 需要改 p7 固件吗？ | ✘ **完全不需要**。这是 **mod_gui 用户态菜单**，与 p7 无关 |
| 改 `gui_ini.NX500` 为什么没用？ | ★ 它在每次开菜单时被 `gen_menu.sh` 从模板**重新生成覆盖** ⇒ 必须改**模板** `gui_tpl.NX500` |
| 现在能加菜单项吗？ | ★ **早就能**（`Mod v2.88`、`胶片配方`、`P7 固件` 都是后加的） |

---

## 一、★★★★★ 两套菜单，不要混淆

| | 相机原生菜单 | **mod_gui 菜单（可扩展）** |
|---|---|---|
| 渲染者 | **p7 固件** | `mod_gui`（用户态 ELF，14KB） |
| 内容 | 拍摄参数 / 播放 / 设置 | `gui_*.NX500` 文本定义 |
| 可否改 | ✘ 要改 p7 | ★★★ **可以，纯文本** |
| 入口 | 相机 MENU 键 | **EV 双击**（`EV_EV.sh`）或双击 WiFi |
| 本仓证据 | 无源码 | `scripts/gui_*.NX500` + `backup_original/` 原版 |

⇒ ★★★ **`HANDOVER §4.5` 的"UI 集成天花板"说的是第 1 套（原生菜单）；第 2 套从未被论证受限。**
　本文只讨论第 2 套 —— **它才是 mod 的常规 UI 载体**。

---

## 二、★★★★ 菜单文件格式（完整语法）

### 2.1 三要素

```
类型 | 标签 | 动作
```

| 字段 | 取值 | 说明 |
|---|---|---|
| **类型** | `button` / `checkbox` | 只有这两种（对应 mod_gui 的 4 种控件里对外暴露的 2 种） |
| **标签** | 任意文本 | ★ 显示名；实测 **≤6 全角字**（超出被挤成 `一 键...`） |
| **动作** | 脚本路径 / `@子菜单` | 裸路径=执行脚本；`@` 前缀=**跳转子菜单文件** |

### 2.2 实例（`backup_original/gui_ini.NX500`，相机开箱原版）

```
button|Time-Lapse|@/opt/usr/nx-ks/gui_tl.NX500
button|Custom Func.|@/opt/usr/nx-ks/gui_func.NX500

button|Focus + Profiles|@/opt/usr/nx-ks/gui_focus.NX500
button|Settings|@/opt/usr/nx-ks/gui_settings.NX500

button|Hibernate|hibernate.sh
checkbox|Remote Ctr|nx-rc.sh
```

⇒ ★★ **空行 = 视觉分组**（mod_gui 的 2 列网格按空行切段）。

### 2.3 完整菜单树（开箱原版）

```
gui_ini.NX500 (主菜单，6 项)
├─ button|Time-Lapse|        → gui_tl.NX500
├─ button|Custom Func.|      → gui_func.NX500        ← ★ 我们改得最多
├─ button|Focus + Profiles|  → gui_focus.NX500
├─ button|Settings|          → gui_settings.NX500
├─ button|Hibernate|         → hibernate.sh
└─ checkbox|Remote Ctr|      → nx-rc.sh
```

### 2.4 ★ 占位符（`gen_menu.sh` 支持的动态标签）

```
%%IP%%   → 当前 mlan0 的 IPv4（无则 "WiFi未开"）
%%TN%%   → "Telnet开" / "Telnet关"（由 ps|grep telnetd 判定）
```
用法示例（`gui_tpl.NX500.p7` 实际在跑）：
```
button|IP: %%IP%% [%%TN%%]|telnet_toggle.sh
```

---

## 三、★★★★★ 全链路（谁在什么时候读菜单）

```
[用户按 EV 双击]  →  EV_EV.sh
                        │
                        ├─ nice -n -15 /opt/usr/nx-ks/loadgui.sh &
                        ▼
                    loadgui.sh
                        ├─ ① prefman 读 0xa690(NX500)/0x658(NX1) —— 判断"是否已改 UI"
                        ├─ ② 若非改机态：按 DIALMODE 恢复拍摄模式
                        ├─ ③ /opt/usr/nx-ks/gen_menu.sh    ← ★ 模板 → 菜单
                        │       gui_tpl.NX500 --(sed 替换 %%IP%%/%%TN%%)--> gui_ini.NX500
                        ├─ ④ nice +15 mod_gui /opt/usr/nx-ks/gui_ini   ← ★ 渲染
                        └─ ⑤ nice +19 br_menu.sh &        ← 后台刷新 IP/状态标签
```

★ 另一触发路径（`menu.sh`，由 `nx-rc.sh` 用）逻辑相同，也调 `gen_menu.sh` + `mod_gui`。

### 3.1 ★★★ 关键规则

| 规则 | 原因 | 证据 |
|---|---|---|
| ★ **改模板，不改 `gui_ini.NX500`** | 每次开菜单都从模板重新生成 `gui_ini` | `p7_install_ui.sh:6` 注释 + `gen_menu.sh` 逻辑 |
| ★ 模板缺失时**静默跳过生成** | 防呆：保证菜单永远可用 | `gen_menu.sh`: `[ -f "$TPL" ] \|\| exit 0` |
| ★ 按机型分模板 | `NX1` / 其它(NX500) | `gen_menu.sh` 的 `case "$MODEL"` |
| ★ 生成是**原子替换** | `> "$DST.tmp" && mv -f` | 避免半成品菜单 |

---

## 四、★★★★★ 三条注入路线（全部零固件风险）

### 路线 ①：改子菜单文件（★★★ 最简单，首选）

**场景**：往已有子菜单（如 `实用功能`）加一项。

```bash
# 1. 编好子菜单文件（本地）
cat > gui_func.NX500 <<'EOF'
button|实时调色|@/opt/usr/nx-ks/gui_live.NX500
button|内置色彩|@/opt/usr/nx-ks/gui_color4.NX500

button|返回|@/opt/usr/nx-ks/gui_ini.NX500
button|取消|/opt/usr/nx-ks/gui_exit.sh
EOF

# 2. 推到相机（FTP，见 §6）
# 3. 完成 —— 下次开菜单即生效（无需重启）
```

### 路线 ②：改主菜单模板（★★★ 加顶层入口）

**场景**：主菜单加一个新的顶层按钮。

```bash
# ★ 唯一改对的文件：/opt/usr/nx-ks/gui_tpl.NX500
# ✘ 不要改 gui_ini.NX500 —— 会被 gen_menu.sh 覆盖
sed -i '1i button|我的功能|@/opt/usr/nx-ks/gui_mine.NX500' \
    /opt/usr/nx-ks/gui_tpl.NX500
```

### 路线 ③：脚本动态生成（★★★★ 列表随数据变）

**场景**：菜单项数量/内容由运行时数据决定（如"选一个 LUT 文件"）。
**现成范例**：`scripts/nx-rc/lut_scan.sh`

```bash
GEN=/opt/usr/nx-ks/gui_lutlist.NX500
: > "$GEN"
for f in /mnt/mmc/*.cube; do
    echo "button|$(basename "$f" .cube)|apply_lut.sh $(basename "$f")" >> "$GEN"
done
echo "button|返回|@/opt/usr/nx-ks/gui_lutimport.NX500" >> "$GEN"
# 然后 gui_lutimport.NX500 里加一行跳转 @gui_lutlist.NX500
```

---

## 五、★★ 动作字段能做什么（`mod_gui` 的 `system("%s &")` 语义）

★ `FEATURE_MATRIX` G 层已解：mod_gui 点击后执行 **`system("<动作字段> &")`**。

| 动作写法 | 行为 | 用途 |
|---|---|---|
| `foo.sh` | `system("foo.sh &")` | 后台跑脚本 |
| `/abs/path.sh` | 绝对路径 | ★ 推荐（cwd 不确定） |
| `/abs/path.sh arg1 arg2` | 带参数 | ★ 动态生成菜单时的常用形态 |
| `@/abs/gui_x.NX500` | **不执行**，跳子菜单 | 树形导航 |

⇒ ★★ **一个菜单项 = 一条后台命令**，**不能表达"参数=值"**（这是 G 层天花板，斜率见 `NATIVE_UI_DESIGN`）。
　⇒ 需要"调参数"的交互（滑块/连续值）仍应走自建 EFL UI（N 层）。

---

## 六、★★★ 部署纪律（照抄已验证流程）

| 项 | 要求 | 依据 |
|---|---|---|
| 传输 | FTP（21）推文件；★ 大文件分块 + md5 | 铁律 99 |
| 权限 | `chmod +x /opt/usr/nx-ks/*.sh`（脚本）；NX500 菜单文件 644 | — |
| CRLF | ★ 上传前断言 `b'\r\n' not in data` | 铁律 100 |
| 路径 | 一律 `/opt/usr/nx-ks/` 绝对路径 | — |
| 生效 | 子菜单文件**即时**（下次开菜单）；模板改动也下次开菜单生效 | `gen_menu.sh` 时机 |
| 回滚 | `gui_exit.sh`（killall mod_gui + 恢复 SYSTEMFREQENCYSTATE） | 必须照抄这套收尾 |
| 备份 | 改前 `cp gui_func.NX500 gui_func.NX500.bak` | — |

### 6.1 高危隔离（沿用 N07 设计）

固件刷写这类操作**不进日常菜单**，用**门控标记文件**（如 `p7flash.ok`）控制入口是否出现：
```bash
[ -f /opt/usr/nx-ks/p7flash.ok ] && echo "button|P7 固件|@/opt/usr/nx-ks/gui_p7.NX500" >> "$GEN"
```

---

## 七、★ 实例：本仓已有的成功注入（★ 都是后加的）

| 菜单项 | 文件 | 证据 |
|---|---|---|
| `Mod v2.88` | `gui_func.NX500` | 原版无此项（`backup_original` 对比） |
| `胶片配方` | `gui_tpl.NX500.p7` | 原版主菜单只有 6 项 |
| `P7 固件` | `gui_tpl.NX500.p7` | 同上 |
| `实时调色`（设计）| `NATIVE_UI_DESIGN` L2 | 待实施 |
| `LUT 导入` | `gui_lutimport.NX500` | 已有文件 |

⇒ ★★★ **菜单注入早已是本项目的常规能力**，不是待攻克项。
　`HANDOVER §4.5` 的"UI 集成天花板"应**限定为"相机原生菜单"**，并补注本套机制。

---

## 八、★★★ 新增方法论判据

| # | 判据 |
|---|---|
| **121** | ★★★★★ **"某功能改不了"必须先问"改的是哪一套"**。相机常并存 N 套 UI（原生 p7 渲染 / mod 用户态 / Web），把一套的天花板套到另一套上会**误判整条路封死**。 |
| **122** | ★★★★ **菜单类功能先找它的"定义文件"与"生成器"**。`gui_ini` 是产物（会被覆盖），`gui_tpl` 是源 —— 改产物等于没改。 |
| **123** | ★★★ 配置/菜单类改动**生效时机在"下次启动"**，不要误判为"没生效"（与 prefman 的即时生效不同）。 |

---

## 九、下一步

| # | 动作 | 收益 | 风险 |
|---|---|---|---|
| P1 | 把「内置色彩 4 档」「实时调色」两项挂进 `gui_func.NX500`，指向已写好的脚本 | ★★★ 立即可交付 | 低 |
| P2 | 用路线③ 做「LUT 列表动态生成」+ 门控 | ★★★ 打通 LUT 导入 UI | 低 |
| P3 | 统计现网 `gui_*.NX500` 与模板的完整差异（防丢项） | ★★ 文档化现状 | 零 |

---

*文档结束。相关：`docs/current/NATIVE_UI_DESIGN_2026-10-07.md`（N 层自建 UI）、`docs/current/FEATURE_MATRIX_2026-10-07.md`（G 层 mod_gui）*
