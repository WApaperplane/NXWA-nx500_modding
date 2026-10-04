# FilmLab SD 卡配方架构（2026-10-04 14:30 定案，14:50 实机跑通）

> 起因：木一指出"配方可以存SD 卡上，像 nx-ks 模组那样调用"。
> 这一句改变了架构定位——**槽位不是配方，槽位只是"当前选中项"。**

## 一、★ 核心认知修正

| 之前的错误认知 | 修正后 |
|---|---|
| "机身只有 3 个自定义槽，配方上限 3-8 个" | **配方在 SD 卡，数量不限**。prefman 槽只是"当前正在显示的那一个" |
| "3槽轮转是限制" | 轮转成本 = 写 7 个 int + 1 条 setusr ≈ **1 秒**。加配方 = JSON 加一行 |
| "配方管理要靠 Web 台" | **SD 卡 JSON + 一个 shell 脚本**就够了，无需 Web |

## 二、架构

```
/mnt/mmc/filmlab/
  recipes.json        ← 配方库（N 个配方，唯一真相源）
  last.log            ← 调用历史
/mnt/mmc/_pwtest/flab.sh   ← 引擎脚本（list/show/apply/quick/preset/dump/slots）

调用方式（三种都通）：
  1. telnet:sh flab.sh apply portra400
  2. mod_gui:  button|  Portra 400  |/mnt/mmc/_pwtest/flab.sh apply portra400
  3. 批量化:  for r in portra400 trix400 monowarm; do sh flab.sh apply $r; done
```

### ★ 配方数量与槽位的关系

```
SD 卡JSON 有N 个配方
        ↓ 每次 apply：写 prefman slot 9/10/11 之一 + setusr 切 enum
机身 UI 显示 3 个自定义槽（= slot 9/10/11）
        ↓
**同一时刻只有 1 个配方"在位"，但库里可以有几百个**
```

## 三、★ prefman 官方命名表（14:30 挖到，这是最有价值的产出）

`prefman info 0` → **672 个命名条目**，覆盖全部相机设置。这是**厂商自己写的偏移定义**，
比任何反汇编都可靠。**以后所有 prefman 偏移都必须查这张表，不能凭记忆写。**

已拉到 PC：`test_server/pwfilter/b1/info0.txt`（34KB）

### prefman 的 11 个段（之前只知道 1个）

| ID | 名称 | 大小 | 内容 |
|---|---|---|---|
| 0 | app | 64KB+ | **672 个命名条目**（设置字典） |
| 1 | app_restore | - | 恢复默认 |
| 2 | line | - | - |
| 3 | sysrw | - | - |
| **4** | **adj_sys** | 2048 | 系统调整 |
| 5 | adj_cap | 2048 | 拍摄调整 |
| **6** | **adj_iq** | **2048** | **画质调整**（未命名，107 个非零条目，位域打包） |
| 7 | adj_vfpn | 22528 | 视口降噪 |
| **8** | **adj_cs** | **62464** | **色彩空间**（★ 未探索，可能含 CCM） |
| **9** | **adj_dpc** | **5242880** | **去马赛克处理**（5MB，★ 未探索） |
| **10** | **adj_dpc2** | **1048576** | 去马赛克 2（1MB） |
| 11 | (其他) | - | - |

★ **`fetch {ID}` 可把整段导出成文件，`dump {ID}` 整段 hex dump，`addr {ID} off type val`
可以把 prefman 条目翻译成 ISP 寄存器地址** —— 这三条是继续深挖的入口。

### PW 7 维的完整命名（7 维 × 14 风格 = 98 项，0xa3ec-0xa554）

```
     风格R      G      B      HUE    SAT    SHARP  CONTRAST
STANDARD 3ec   420   454   488    4bc    4f0    524
VIVID     3f0   424   458   48c    4c0    4f4    528
PORTRAIT  3f4   428   45c   490    4c4    4f8    52c
...
CUSTOM_1  410   444   478   4ac    4e0    514    548
CUSTOM_2  414   448   47c   4b0    4e4    518    54c
CUSTOM_3  418   44c   480   4b4    4e8    51c    550
CUSTOM_4  41c   450   484   4b8    4ec    520    554← ★ prefman 有，UI 无
OFF       3d8   -     -     3e8    3dc    3e0    3e4    ← 只有 5 项（缺 R/G/B）
```
**★ 这张表独立验证了我们的 slot 公式**（`41964 + N*4`）—— CUSTOM_1/2/3/4 = slot 9/10/11/12，4/4 全对。

### PW 之外挖到的画质维度

| 地址 | 名称 | 意义 |
|---|---|---|
| 0x0a394 | APPPREF_WB_K_VALUE | Kelvin（2500-10000） |
| 0x0a398-0x0a3c0 | WB_*_DETAIL_BA_XY | 各光源 tint（A/B 双轴） |
| 0x0a3bc | WB_CUSTOM_DETAIL_BA_XY | 自定义 tint |
| **0x0a3c4/3c8/3cc** | **CWB_RED/GREEN/BLUE** | **★ 自定义 WB 三通道**（PW 之外的真维度） |
| 0x0a340 | SHUTTER_SPEED_INDEX | 快门 |
| 0x0a63c | **HIGH_ISO_NR** | **★ 高 ISO 降噪档位** |
| 0x0a5fc/0a600 | BRK_WB_SET / BRK_PW_TYPE | 包围架 |
| 0x0a5a4 | FOCUS_PEAKING_COLOR | 手动对焦峰值颜色 |
| 0x0a724 | FACE_RETOUCH_LEVEL | 人脸修饰 |

**★ 命名表里没有 NOISE / GRAIN / TONE / CURVE / LUT —— 印证"机内无颗粒与曲线维度"。**

## 四、★ 引擎脚本用法（实机跑通）

```sh
sh flab.sh list                # 列出 SD 卡全部配方 + 7 维
sh flab.sh show portra400      # 查看单个配方
sh flab.sh apply <recipe> [slot]   # 写槽 + 切风格（实时，约 1 秒）
sh flab.sh quick <recipe>      # 只切风格（零写入，槽已预写时）
sh flab.sh preset              # 预写 3 个可见槽 + save（开机保留）
sh flab.sh dump [slot]         # 读回槽位值
sh flab.sh slots               # 槽位映射表
```

**实机验证输出**（14:50）：
```
>>> 应用 'portra400' -> slot 9 (enum 9)
  已写入:
  R=106 G=100 B=93 HUE=11 SAT=9 SHARP=9 CON=8
  K=5900
  PW_TYPE = PW_CUSTOM1 (0x140009)
```

## 五、★ mod_gui 怎么接（这是模组化的关键）

`mod_gui` 格式已实测为纯文本管道分隔，每行 `类型|标签|命令`：
```
button|  Portra 400  |/mnt/mmc/_pwtest/flab.sh apply portra400
button|  TriX 400    |/mnt/mmc/_pwtest/flab.sh apply trix400
button|  MonoWarm    |/mnt/mmc/_pwtest/flab.sh apply monowarm
button|  Velvia 50   |/mnt/mmc/_pwtest/flab.sh apply velvia50
```
**mod_gui 的按钮数上限 24 → 最多 24 个一键配方。** 想更多就用子菜单或 telnet。
配方增删只改 JSON，**mod_gui 不用动**。

## 六、★ 六条铁律（今天踩出来的）

1. **`prefman set` 不需 `save` 即实时生效**（已实机多次验证）
2. **`prefman load -a 0` 会覆盖刚 set 的值** —— 绝对不要用，方向是反的
3. **`prefman save` 只在需要开机保留时用**（有 eMMC 磨损，一天几十次无碍）
4. **enum 与 slot 错位 1**：slot 11 = enum 12；**enum 11 是空洞**（`not set -1`）
5. **CUSTOM_4（slot 12）在 prefman 里完整存在但 UI 不显示** —— 白捡的第 4 槽
6. **所有 prefman 偏移必须查 `prefman info 0` 命名表**，不能凭记忆
   （我今天把 WB_K 写成 42004 = 0xa414，正确是 41876 = 0xa394，K 值直接写进了 PW 参数区）

## 七、JSON 格式要求（踩坑）

**每个字段必须独立成行。** 一行里放多个字段时，awk 的 `gsub(/[^0-9-]/,"")` 会把数字连成一片
（`"R_COLOR": 106, "G_COLOR": 100` → `106100`）。用 `json.dump(indent=2)` 生成即可。

**JSON 字段名必须与脚本查询一致**（`K` 不是 `kelvin`）—— 不一致时 `jval` 返回空，
`[ -n "$K" ] &&` 短路跳过写入，**静默失败**，读回旧值。

## 八、下一步

| 方向 | 内容 |
|---|---|
| **① mod_gui 接线** | 24 个一键配方按钮，配方增删只改 JSON |
| **② 配方扩到 30+** | 按胶片系列配齐（Portra 全系/ Velvia 全系/ Kodak/Ilford/Fuji） |
| **③ 挖adj_cs 段** | 62KB 色彩空间段，用 `fetch 8` 导出到 PC 分析（可能含 CCM 矩阵） |
| **④ 挖 adj_dpc 段** | 5MB 去马赛克段，`fetch 9` 导出（可能有降噪/锐化参数） |
| **⑤ 配方编辑器** | SD 卡上放一个简易编辑器（telnet + vi 或 Web 只做编辑不做预览） |

---

# ★★★ 追加：白平衡与 PW 的分离问题（14:55 木一指出，15:05 定案）

## 一、木一指出的问题（正确且比我意识到的更深）

> "白平衡和槽位是分开的，不是一步到位设置的。进入 mod_gui + X11 开发的时候需要在槽位中同步写入白平衡和 RGB。"

**实机验证：完全正确，而且比他说的更严重。**

| | 地址范围 | 说明 |
|---|---|---|
| PW EFFECT 段 | `0xa3d0 - 0xa554` | 7 维 × 14 风格 |
| WB 段 | `0xa390 - 0xa6a4` | **完全独立的地址区** |

**prefman 层面零联动。写 slot 不会带WB，写 WB 不会带 PW。**

### ★★ 更严重的一层：WB_TYPE 决定 K 是否生效

`WB_TYPE`（`0xa390`）是**白平衡模式开关**。相机默认 `WB_TYPE=10`，
但我们此前一直写 K 值而**没有设置模式**—— 如果模式是 `WB_AUTO`，
**ISP 根本不采用 K 值，整个白平衡是空的。**

**→ 也就是说：前面 8 个配方的 K 值其实全部没生效，
你看到的 Portra 400 效果只是 PW 7 维在起作用。**

## 二、★★ WB_TYPE 完整真值表（setusr 6 实机扫出，14:58）

`setusr 6 <0x060000|enum>`，前缀 `0x06` = 索引 6 的 hex。

| enum | 名称 | 含义 |
|---|---|---|
| 0 | WB_AUTO | **自动（K 被忽略）** |
| 1 | WB_AUTO_TUNGSTEN | 自动-钨丝 |
| 2 | WB_DAYLIGHT | 日光 |
| 3 | WB_CLOUDY | 阴天 |
| 4 | WB_FLUORESCENTW | 荧光 W |
| 5–7 | （未扫到，setusr 被拒） | — |
| 8 | WB_FLASH | 闪光 |
| 9 | WB_CUSTOM | 自定义 tint |
| **10** | **WB_MANUAL** | **★ 手动 K —— K 值只在这里生效** |
| 11+ | `not set -1` | 空洞 |

**★ tint 编码确认是 `(A<<16)|B`**，中性值 `0x00070007`（A=7 B=7）。
实测读回 `0x090004` = A=9 B=4，与写入的 `tint_a=9tint_b=4` 完全一致。

### WB 段完整地址（全部来自 prefman info 0 命名表）

| 地址 | 十进制 | 名称 |
|---|---|---|
| 0xa390 | 41872 | APPPREF_WB_TYPE |
| 0xa394 | 41876 | APPPREF_WB_K_VALUE |
| 0xa398 | 41880 | APPPREF_WB_AUTO_DETAIL_BA_XY |
| 0xa3bc | 41916 | APPPREF_WB_CUSTOM_DETAIL_BA_XY |
| 0xa3c0 | 41920 | APPPREF_WB_K_DETAIL_BA_XY ← K 模式的 tint |
| **0xa3c4** | 41924 | **APPPREF_CWB_RED** |
| **0xa3c8** | 41928 | **APPPREF_CWB_GREEN** |
| **0xa3cc** | 41932 | **APPPREF_CWB_BLUE** |

**★ `CWB_RED/GREEN/BLUE` 是自定义 WB 三通道 —— PW 之外的真维度。**

## 三、★★★ 修正后的原子写入（set_wb）

```c
// 用法: set_wb <K> <tint_a> <tint_b> [manual|auto|keep]
void set_wb(int K, int A, int B, char* mode) {
    // 1) 先切模式 —— 决定 K 是否被 ISP 采用
    if (mode == manual) {
        prefman_set(0xa390, 10);          // WB_MANUAL
        setusr(6, 0x06000a);              // 同步走属性总线
    } else if (mode == auto) {
        setusr(6, 0x060000);              // WB_AUTO，K 被忽略
    }
    // 2) 再写 K
    if (K) prefman_set(0xa394, K);
    // 3) 最后写 tint（两处都写，保证 K 模式与 Custom 模式一致）
    int BA = (A << 16) | B;
    prefman_set(0xa3c0, BA);              // K 模式 tint
    prefman_set(0xa3bc, BA);              // Custom 模式 tint
}
```

**★ 顺序是原子性的关键**：先切模式 → 再写 K → 最后写 tint。
反了会出现"模式已是 manual 但 K 还是旧值"的窗口。

## 四、★ 引擎新增能力

```sh
sh flab.sh wb <K> <a> <b> [manual|auto|keep]   # 单独设WB，不动 PW
sh flab.sh wbdump                # WB 段完整状态
sh flab.sh apply <recipe>        # ★ 现在 PW + WB 一次到位
```

**实机验证**（15:05）：
```
>>> 应用 'trix400' -> slot 10 (enum 10)
  R=100 G=100 B=100 HUE=10 SAT=0 SHARP=13 CON=12
  WB_TYPE = 10  K = 6300  tint A=7 B=7
  setusr WB = WB_MANUAL (0x6000a)
  PW_TYPE  = PW_CUSTOM2 (0x14000a)
```

**配方 JSON 每个recipe 新增 `wb_mode` 字段**（`manual`/`auto`/`keep`），
默认值 `manual`。字符串字段用 `jstr()` 读（`jval()` 只取数字）。

## 五、★★ 这对 mod_gui + X11 开发的三条硬要求

1. **每个配方必须同时携带 PW 7 维 + WB（TYPE/K/tint）**，
   JSON schema 里 PW 与 WB 是平级的两段，不是一个整体参数
2. **写入顺序固定：WB_TYPE → K → tint → PW 7 维 → setusr 20**
   （先定模式再写值，避免中间态）
3. **★ UI 上必须显示当前 WB 模式**。因为 `WB_AUTO` 下 K 值是死的，
   用户改了 K 却看不到效果会以为坏了 —— 这是最可能的用户投诉点

## 六、★顺带发现：`setusr 50 = COLORSPACE_SRGB`

**色彩空间可切**（`setusr 50`）。之前没扫到这段（索引 44-50）。
配合 `adj_cs`（62KB 未探索段），这是 PW+WB 之外的第三个调节维度。
**建议下一步扫 `setusr 50` 的全部枚举 + `fetch 8` 导出 adj_cs 段。**

## 七、setusr 索引 6-18 与 44-50 补扫结果

```
6=WB_CUSTOM(★)      7=AFMODE_AUTO     8=AFAREA_MULTI    9=FACEDETECT_OFF
10=DRIVE_SINGLE     11=BURSTRATE_RATE  12=FLASHMODE_OFF   13=METERING_MULTI
14=MOVIEMETERING    15=LINKAE2AF      16=BRIGHTNESSADJ   17=FRAMEEXPOSURE
18=MULTIEXPOSURE    48=AFLIGHT_HIGH   49=AEL_AEL         50=COLORSPACE_SRGB(★)
```

---

# ★★★ 追加二：mod_gui + X11 双层 UI（15:25–15:40）

## 一、v2 决策：白平衡交给用户

木一决定：**"保留白平衡设置先不去动，以自动白平衡为基础模式，由用户自己调整。"**

理由（我认同并补一条）：
- `WB_TYPE` 决定 K 是否生效，而**相机端 UI 不随 prefman 写入自动刷新**
- → 造成"写入了但看不出变化"的**不可验证状态**
- → 与其留一个用户看不懂的功能，不如让用户在机身 UI 上调（那是它该在的地方）

**v2 配方库**（`recipes/nx500_filmlab_sd.json`）：
- 8 个配方，**只含 PW 7 维**
- 原来的 `K` / `tint_a` / `tint_b` 降级为 `_wb_ref`（仅供参考，不写入）
- 新增 `wb_mode` 已移除

## 二、★ mod_gui 菜单（4 页，纯文本，实测格式）

格式：`类型|标签|命令`，`@` 开头是子菜单，最后两行固定「返回/取消」。

| 文件 | 内容 |
|---|---|
| `scripts/nx-rc/gui_filmlab.NX500` | 8 个配方按钮 + 更多 + 恢复中性 + WB 提示 |
| `gui_filmlab2.NX500` | 预设槽管理（把配方写进 3 个可见槽） |
| `gui_filmlab3.NX500` | 诊断页（list / dump / slots / wbdump，全只读） |
| `gui_filmlab4.NX500` | **白平衡实验页（★未验证，已在文件头标注警告）** |

mod_gui 按钮上限 24 → 最多 24 个一键配方。**配方增删只改 JSON，mod_gui 不动。**

## 三、★ X11 配方选择器（`filmlab/src/nxflab.c`）

**这是 mod_gui 做不到的部分**：图形化、7 维可视化、非 ASCII 支持的潜力。

### 已实现

- 720x480 全屏窗口，左栏配方列表（8 条），右栏 7 维条形图 + 中性刻线
- 上下键选配方 / 左右键选维度 / **Enter 应用**（调 `filmlab.sh apply <key>`）/ q 退出
- 配色：深色底+ 选中高亮 + 强调色
- 产物 `out/nxflab.arm` = **66KB**（`-O0 -s --gc-sections`）

### ★★ 两个必须记录的硬约束（实机踩到）

#### ① 相机 X server **没有 core font**

```
XLoadQueryFont("6x13") → 返回非 NULL（0x56e20）
XSetFont(...)          → 立即 BadFont 致命错误，Resource id=0x0
```

`Xorg :0 -ac` 启动时没有字体目录。**唯一可靠办法是自己画点阵。**

#### ② 自实现 5x7 点阵字体（`filmlab/src/font5x7.c` + `font5x7.h`）

- 95 个可打印 ASCII 字模，每字符 5 字节（每字节一列，bit0=顶行）
- 绘制用 `XFillRectangle` 逐点画
- `draw_text(d,win,gc,x,y,str,scale)` / `draw_text_n(...,maxch)`
- 代价：**中文无法显示**（label 含中文时退回显示 key）
- 收益：零依赖、不依赖任何字体服务

### ③ CRLF 又咬了一次

`recipes.txt` 从 Windows 上传后行尾变`\r\n`，导致最后一个字段带 `\r`，
"纯数字"校验失败 → **整行被跳过 → `loaded 0 recipes`**。

**修法双保险**：① 生成时强制 LF ② `parse_line` 里 `while(L>0 && (line[L-1]=='\r'||line[L-1]==' ')) line[--L]=0;`

**★ 这是同一个坑在一天内第三次出现（.sh / .json / .txt），必须写成铁律。**

## 四、★ 引擎 v2 新增子命令

```sh
sh filmlab.sh list                    # 8 个配方
sh filmlab.sh show <recipe>
sh filmlab.sh apply <recipe> [slot]   # ★ 只写 PW 7 维 + setusr 20，不碰 WB
sh filmlab.sh preset <recipe> [slot]  # ★ 预写槽（供 UI 零延迟选）
sh filmlab.sh reset                   # ★ 全部槽恢复出厂中性
sh filmlab.sh quick <recipe>          # 只切风格（零写入）
sh filmlab.sh dump [slot] / slots / wb / wbdump
```

**踩坑**：`preset` 原有硬编码版本（循环 3 槽），新插入的通用版本排在后面，
shell 先匹配到旧版 → 表现为"参数被忽略"。**已删除旧版。**
**教训：往 case 分支里插新分支前，先确认没有同名旧分支。**

## 五、★ 厂商槽垃圾字节（重要，影响可用槽判断）

用 `prefman get ... b`（单字节）与 `l`（32 位）双读对比：

| slot | HUE `l` | HUE `b` | 判定 |
|---|---|---|---|
| **0 STANDARD** | 200 | **-56** | ❌ 垃圾 |
| **3 LANDSCAPE** | 5000 | **-120** | ❌ 垃圾 |
| 1,2,4,5,6,7,8 | 10 | 10 | ✅ 干净 |
| **9,10,11 CUSTOM** | 11/9/10 | 同 | ✅ 我们的写入正常 |

**→ 修正我之前的结论"厂商 9 风格全是中性值"是错的**（那是 32 位读跨条目的拼接）。
**→ 但 CUSTOM_1/2/3 完全正常，所以我们的写入路径没问题。**
**→ 只用 CUSTOM 槽；厂商槽 0/3 的 HUE 不可碰。**

## 六、★ 验证方法论教训（重要）

木一指出我设计的实验无效：*"你写入数据的时候，相机端不会自动切换。我需要手动切到色温那块——我只能说这样是有变化的，但是我不知道这组实验到底有没有意义。"*

**判定：他的批评完全正确。** 手动切UI 这个动作本身就会让相机重新读参数，
所以"画面有变化"无法区分是"我的写入生效"还是"手动切换生效"——**不可证伪**。

**我今天已在同类问题上栽了三次**：
1. 把 `prefman load -a 0` 当成"刷新"（实际是覆盖）
2. 把手写 printf 的乱码当编码问题（实际是格式匹配顺序）
3. 这次：把不可靠的人工观察当判据

**→ 铁律：涉及"是否生效"的判定，必须用可自证的客观通道**
（读回寄存器值 / 拍图做像素统计 / 差分文件），**不能用"让用户看一眼"**。

**已验证的客观通道**：
- `prefman get` 读回（地址与命名表交叉验证）
- `st cap sh` 自动快门 + 80 端口拉 JPG 做像素统计（★ 尚未跑通完整链路）
- 特征色实验（红/绿/蓝，2026-10-04 14:00 成功用过一次）

## 七、下一步

| 方向 | 内容 |
|---|---|
| **① X11 加中文** | 点阵中文需预生成位图；或改用 EFL 字体（相机有 libelementary） |
| **② X11 加缩略图预览** | 用 `thumb-cgi` 现有能力生成配方预览图，X11 侧用 XLoadPixmap 贴图 |
| **③ mod_gui 部署验证** | 4 个 .NX500 推上相机，实机点一遍 |
| **④ 客观验证 WB** | `st cap sh` 连拍 3 张（3000K/5600K/8000K），拉 JPG 算 R/B 均值 |

---

# ★★★ 追加三：X11 退出机制（15:40，木一反馈"无法关闭窗口"）

## 一、问题

木一实机反馈：X11 界面显示正常，但**无法在相机上关闭**。

**根因：我漏了退出机制。** 原代码用 `XNextEvent` 无限阻塞，
只处理键盘事件——但**相机按键事件根本送不到这个窗口**
（它不是 EFL 窗口，没有输入焦点夺取）。所以 `q` / `Esc` 形同虚设。

**临时解决**：`kill -9 <pid>`（先删掉了 pid 1674）。

## 二、三条退出路径（已实机验证）

| 路径 | 实现 | 验证 |
|---|---|---|
| **① 信号** | `signal(SIGTERM/SIGINT/SIGHUP, on_sig)` + 循环里查 `g_quit` | ✅ 日志 `quit by signal` + `bye` |
| **② 空闲超时** | 事件循环改`XPending` + `select(200ms)` 轮询，`idle_limit` 秒无输入自动退 | ✅ 机制已就（第三参数控制）|
| **③ 屏幕提示** | 标题栏显示操作说明；**临近超时才显示 EXIT 提示**（防误触） | ✅ |

### ★ 关键改动：事件循环不再用 XNextEvent 阻塞

```c
/* 旧：XNextEvent 无限阻塞 → 信号处理函数设了 g_quit 也没人看 */
XNextEvent(d, &ev);

/* 新：先看有没有事件，没有就用 select 超时等 200ms，然后回来检查信号/超时 */
if (!XPending(d)) {
    fd_set fds; struct timeval tv;
    FD_ZERO(&fds); FD_SET(xfd, &fds);
    tv.tv_sec = 0; tv.tv_usec = 200000;
    select(xfd + 1, &fds, NULL, NULL, &tv);
    continue;      /* ← 回到循环头，先查 g_quit 和 idle */
}
XNextEvent(d, &ev);
last_input = time(NULL);
```

**★ 这是通用教训：任何 `XNextEvent` / `read` 阻塞循环，
装了信号处理函数也不会被响应——必须用 `select`/`poll` 超时唤醒。**

### 用法

```sh
# 第3 参数 = 空闲多少秒自动退出（0 = 不自动退）
/opt/usr/nx-ks/filmlab/nxflab.arm /mnt/mmc/filmlab/recipes.txt /mnt/mmc/_pwtest/nxflab.log 60

# 手动关：
kill <pid>            # 或 pkill -f nxflab
```

**建议：mod_gui 里用 30-60 秒自动退出**，避免用户被卡在全屏界面。

## 三、测试脚本踩的两个坑

### ① `for p in /proc/[0-9]*` 遍历极慢

单核相机上遍历 200+ 进程要十几秒。**改用 `$!` 直接拿后台 PID**：
```sh
$BIN ... & P=$!
```

### ② `grep -q` 遇到 `/proc/*/comm` 会挂

必须 `grep -qa`（记忆里已有这条铁律：`grep` 处理二进制要加 `-a`，
但 `/proc` 下的二进制内容这次又踩了一次）。

**★ 现象：测试脚本卡在 `kill` 之后不动 → 误以为程序没退出。**
实际 `kill` 早就生效了（无残留进程 + 日志 `quit by signal`）。
**教训：测试脚本自身卡住 ≠ 被测程序有问题，必须用第二种手段交叉验证。**

## 四、mod_gui 接线（待验证）

`gui_filmlab.NX500` 里的 X11 入口应该带自动退出：
```
button|  图形选择器|/opt/usr/nx-ks/filmlab/nxflab.sh gui
```
`filmlab.sh gui` 包装成：
```sh
gui)
  /opt/usr/nx-ks/filmlab/nxflab.arm \
    /mnt/mmc/filmlab/recipes.txt /mnt/mmc/_pwtest/nxflab.log 45
  ;;
```
**★ 但 mod_gui 的 `quit_app()` 语义与 X11 阻塞冲突**——
`mod_gui` 启动外部命令后会立即退出自己的界面，X11 窗口却还在。
**这是待解决的问题**（可能需要 `wait` 或让 mod_gui 用 `sh -c "cmd; sleep"`）。


## 五、★ 当前状态快照（15:48，相机换电池重启前）

### 相机上已部署

| 路径 | 内容 | 状态 |
|---|---|---|
| `/opt/usr/nx-ks/filmlab.sh` | 配方引擎（8 子命令） | ✅ 已部署 |
| `/opt/usr/nx-ks/filmlab/nxflab.arm` | X11 选择器 69KB | ✅ 已部署 |
| `/mnt/mmc/filmlab/recipes.json` | 配方库 v2（8 个，只含 PW 7 维） | ✅ |
| `/mnt/mmc/filmlab/recipes.txt` | X11 用的配方表 | ✅ 已修正为 LF |
| `/mnt/mmc/_pwtest/` | 各种探针脚本 + 日志 | 临时区 |

### 引擎子命令

```
list / show / apply / preset / reset / quick / dump / slots / wb / wbdump / gui
sh filmlab.sh gui [秒]    # 启动 X11，默认 45 秒空闲自动退出
```

### ★ 重启后要做的三件事

1. **确认 telnet/FTP 恢复**（重启后 IP 可能变，先 `ping` 一下）
2. **重跑一次 `sh filmlab.sh gui 60`** —— 验证退出机制在重启后依然有效
3. **推 mod_gui 菜单到相机**（还没部署，只在 PC 上写了 5 个 .NX500）

### ★ 一个已知待解问题

`mod_gui` 的 `quit_app()` 语义与 X11 阻塞冲突：
mod_gui 启动外部命令后会立即退出自己的界面，但 X11 窗口还在。
**可能的解法**：
- mod_gui 命令写成 `sh -c "filmlab.sh gui 30; sleep 2"`（让 mod_gui 等）
- 或 X11 侧检测父进程消失后自动退出（prctl PR_SET_PDEATHSIG）
- 或干脆不通过 mod_gui 启动 X11，改成独立的 telnet 命令

