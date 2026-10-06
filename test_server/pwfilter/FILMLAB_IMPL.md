# FilmLab 实现方案 — 已实机跑通（2026-10-04）

> 设备：NX500 固件1.12| A 档 + 拍摄模式 | telnet 192.168.0.105
> 脚本：`test_server/pwfilter/filmlab-apply.sh`（相机端 `/opt/storage/sdcard/_pwtest/filmlab-apply.sh`，8577B）
> 上传器：`test_server/pwfilter/push_sh.py`（**自动转 LF**）

## 一、推翻旧研究的核心论断

`.uploads/filmsim_repo/FILM_SIM_RESEARCH.zh.md` 5.4 节写的「最终放弃原因」三条，
今天被实机全部推翻：

| 旧研究结论 | 实机验证 |
|---|---|
| 「PW_CUSTOM 子参数不在capdtm 暴露，只能 UI 手调」 | ❌ **错**。prefman `0x0a3ec` 起 14 槽 × 7 维全部可写，`save` + `load -a 0` 后保持 |
| 「0x14000b = CUSTOM3 无效」 | ⚠️ **半对**。`setusr` 切过去时 enum 回显为 CUSTOM2，但 **prefman 层槽位可写可读**（实测 13 槽全部读写命中） |
| 「槽位固件固定 3 个 CUSTOM，无法程序化写入子参数」 | ❌ **错**。这是当时只试 `setusr`/`capdtm` 一条路，没试 prefman |

**根因认知错位**：`setusr`（capdtm 的 DATA ID 层）和 `prefman`（存储层）是**两套独立索引**。
- `setusr` 只能切「引擎认的槽」，有白名单
- `prefman` 能写**全部 14 个槽**的参数

两者错位反而是好事：`setusr` 有效槽少，正好留出余量。

## 二、★核心坑：CRLF 行尾（浪费最多时间的一个坑）

Windows 端写 `.sh` 默认 CRLF。相机 busybox ash 会把 `\r` 当命令一部分：

```
空行       → ": command not found"
rd() {     → "syntax error near unexpected token '{'"
函数定义  → 全部失败
```

**排查过程（值得记住的教训）**：
1. 报错行号 16/20/34/44/48 → 查本地文件，**完全正常**（有中文注释、有完整函数）
2. 最小复现中文注释 → **通过**，排除中文编码问题
3. `md5sum` 对比本地/相机 → **完全一致**，排除传输损坏
4. `od -c` 看相机端原始字节 → `rd() {  \r  \n` ← **真凶**

**教训**：本地文件正常 + 远端 md5 一致 + 远端报语法错 → 一定是**行尾或不可见字符**，
`od -c` 是唯一可靠手段。已把 CRLF→LF 转换内置到 `push_sh.py`，不再手改。

## 三、已验证的维度表

### 持久层（prefman，`prefman save` + `sync`）
| 维度 | 偏移 | 格式 | 范围 |
|---|---|---|---|
| PW R/G/B 增益 | `0x0a3ec/0x0a420/0x0a454` + 参数步进 52 + 风格步进 4 | int32 | 中性 100 |
| PW HUE/SAT/SHARP/CONTRAST | `0x0a488/0x0a4bc/0x0a4f0/0x0a524` 同上 | int32 | 中性 10 |
| WB K 值 | `0x0a394` | **真实 Kelvin** | 2500-10000（100K/挡，**prefman 不裁剪**） |
| WB tint 二维 | `0x0a398-0x0a3c0`（10 预设） | `(A<<16)\|B` | 中性 `0x070007` |

**13 个PW 槽全部实测可写**（逐槽写入标记值 + prefman 读回，13/13 命中）。

### 实时层（setusr，引擎自渲染，零 CPU）
| 维度 | 索引 | DATA ID | 有效范围 |
|---|---|---|---|
| PW_TYPE | 20 | `0x140000+N` | N=0..10, 12（**11 无效**） |
| Smart Filter 类型 | 62 | `0x3e0000+N` | 0..13（14 种） |
| Smart Filter 强度 | 63 | `0x3f0000+N` | SIZE0..N |
| SmartRange | 21 | `0x150000+N` | 0/1 |
| SmartArt / 强度 | 27 / 28 | `0x1b0000+N` / `0x1c0000+N` | 未细测 |
| Facetone | 25 | `0x190000+N` | 未细测 |

**enum 回显有 bug**（N=10/11 都显 CUSTOM2，N=12/13 都显 CUSTOM4）→ **以 prefman 读回为准，别信getusr 的名字**。

## 四、8 个配方（全部实测通过）

| ID | tag | slot | PW 7 维 | K | tint | 实时效果 |
|---|---|---|---|---|---|---|
| portra400 | 人像暖调 | 9 | R106/G100/B93 H11 S9 Sh9 C8 | 5900 | 0x090004 | PW=CUSTOM1 |
| velvia50 | 风光高饱和 | 10 | R102/G110/B109 H10 S14 Sh11 C13 | 5500 | 0x050006 | PW=CUSTOM2 |
| trix400 | 黑白粗颗粒 | 11 | R100/G100/B100 H10 **S0** Sh13 C12 | 6300 | 中性 | PW=CUSTOM2 |
| ektachrome | 反转片冷调 | 12 | R96/G105/B108 H12 S13 Sh10 C11 | 7100 | 0x040008 | PW=CUSTOM4 |
| hp5 | 黑白中颗粒 | 10 | R100/G100/B100 H10 **S0** Sh11 C10 | 6300 | 中性 | PW=CUSTOM2 |
| superia400 | 民用负片 | 11 | R103/G99/B104 H13 S11 Sh9 C9 | 6100 | 0x080005 | PW=CUSTOM2 |
| monowarm | **暖调黑白** | 9 | R108/G100/B92 H10 **S0** Sh10 C11 | 5000 | 0x0c0002 | PW=CUSTOM1 |
| vignette | 暗角叠加 | 9 | R100/G100/B100 H10 S11 Sh10 C10 | 6300 | 中性 | **SmartFilter=VIGNETTING/SIZE1** |

**★ monowarm 是机身独有能力**：`SAT=0`（纯黑白）**同时保留 R/B 增益差** = 暖调黑白。
PC 端矩阵引擎做不到（归一化后必然是纯灰）。

**槽位轮转**：9/10/11/12 四槽，8 个配方每槽 2 个，切换时覆盖同一槽。

## 五、用法

```sh
SH=/opt/storage/sdcard/_pwtest/filmlab-apply.sh
sh $SH list                # 列出配方
sh $SH show portra400      # 配方详情 + 机内当前值
sh $SH apply portra400     # 应用（自动先备份 app 区）
sh $SH dump                # 14 槽全表诊断
sh $SH reset               # 恢复中性
```
子命令 `show` 的输出缓冲较大，telnet 观察时**会错位一位**——是回显延迟，不是逻辑错。
独立复查请单条执行。

## 六、待人工验证（唯一无法自动化的判据）

**取景器画面是否真的随配方变化。** 逐个切portra400 / velvia50 / trix400 / vignette 看画面。

预期：
- portra400 → 暖、对比低
- velvia50 → 通透高饱和
- trix400 → **纯黑白**（这个最容易肉眼确认）
- vignette → **四角压暗**（第二维叠加是否与 PW 同时生效，最关键的验证）

## 七、下一步

1. **人工验画面**（上面第6 节）
2. `mod_gui` 菜单挂载：`/opt/usr/nx-ks/mod_gui` + `app.cfg` 3 行格式（名称/版本/命令）
3. 挂载到 `/opt/usr/nx-ks/auto/nx-rc.sh`（与 push/thumb 同层，不新增机制）

`mod_gui` 限制（10-03 评估）：点击命令后立即 `quit_app()`，无图片，只能文字。
配方名用中文/英文取决于字体——**需实机确认相机 UI 字体是否有中文字形**。
