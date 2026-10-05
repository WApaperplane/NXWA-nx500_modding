# FilmLab「真一键」验证清单

> 目标：证明 2026-10-05 修复的`pw_force_reload()` 让「按 S1 立刻变」真正成立。
> 状态：**待上机验证**（相机 2026-10-05 15:09 探测不在线）
> 配套：`scripts/nx-rc/flab-verify.sh`（相机端）+ `test_server/shotstat.py`（PC 端）

---

## 零、为什么需要这份清单

修复前的 `apply` 收尾动作是：

```sh
stcap capdtm setusr 20 0x140009# 「写完再切一次，让 ISP 重读」
```

FilmLab 固定写 slot 9 → **enum 恒为 9** → 第二次写入的是与当前**完全相同的值** = 空操作。
ISP 收不到"风格变了"的通知 → 不重读 PW 段 → **按S1 没反应，必须回 GUI 把图片向导切走再切回来**。

**这不是延迟，是那次 setusr 根本没生效。** 修复后改为借道 `0x140009` 制造真实跳变。

★ **判定原则（来自本项目铁律）**：涉及"是否生效"的判定**必须用可自证的客观通道**，
**绝不能用"让用户看一眼取景器"**。本清单的每一条判据都是数值读数。

---

## 一、硬件与纪律（★违反会重演压死相机）

| 项 | 值 |
|---|---|
| 相机 IP | `192.168.0.105`（DHCP 会变，先 `ping` 确认）|
| telnet | 端口 23，root，空密码 |
| busybox | **必须绝对路径** `/opt/usr/nx-ks/busybox` |
| telnet 登录 shell | **禁止设 `LD_LIBRARY_PATH`**（会报 `You may not change $LD_LIBRARY_PATH`）|

**单核铁律**（违反 = 相机被压死，只能拔电池）：

1. **一次只跑一条命令**，串行。绝不在一个 telnet 会话里塞多条。
2. 首次验证**只跑 1 张照片**，不批量。
3. 绝不并发。绝不后台跑批量。
4. 症状识别：**telnet + FTP 双挂 = 相机被压死**，需拔电池。
5. 只读命令（`pre` / `dump` / `reload`）无风险；`shot` 会触发一次完整拍摄流程。

---

## 二、阶段 A · 前置检查（只读，零风险）

```sh
telnet 192.168.0.105
# 登录后
sh /opt/usr/nx-ks/nx-rc/flab-verify.sh pre
```

**通过判据**：

| # | 判据 | 期望|
|---|---|---|
| A1 | 引擎存在 | `✓ 引擎 /opt/usr/nx-ks/filmlab.sh` |
| A2 | 配方库存在 | `✓ 配方库 /mnt/mmc/filmlab/recipes.json` + 配方数 ≥ 1 |
| A3 | 相机进程活着 | `✓ di-camera-app pid=xxx` |
| A4 | 当前状态可读| 打出 `PW_TYPE` + `slot9` 7 维 + MemFree + loadavg |

★ **把 A4 输出的 slot9 七维抄下来**，这是后续所有比对的基线。

> ★★ **A1 若报「缺引擎」，不要去跑 `install.sh`——没用。**
> `install.sh` 只做 `cp -ar /mnt/mmc/scripts/* /opt/usr/nx-ks/`，
> 而母本 `scripts/` 下**没有** `filmlab.sh`（只有 `scripts/nx-rc/flab-verify.sh`）。
> 引擎走的是 **FTP 单独投递**路线：
> `test_server/filmsim/filmlab-apply.sh` → 相机 `/opt/usr/nx-ks/filmlab.sh`。
> 配方库在 SD 卡 `/mnt/mmc/filmlab/recipes.json`，由 `push.sh` 负责。

---

## 三、阶段 B · 验证 enum 跳变（★核心，只读）

```sh
sh /opt/usr/nx-ks/nx-rc/flab-verify.sh reload
```

脚本会手动分四步，每步都**回读验证**：

| 步 | 动作 | 期望回读 |
|---|---|---|
| [0] | 读当前 | 记录 T0 |
| [1] | `setusr 20 0x140009` | `0x140009` ✓ 跳变成功 |
| [2] | 再 `setusr 20 0x140009`（同值） | 回读不变 —— **这一步恰好复现原 bug** |
| [3] | `setusr 20 0x140000` | `0x140000` ✓ 二次跳变成功 |

**通过判据**：

| # | 判据 | 含义 |
|---|---|---|
| B1 | [1] 回读 = `0x140009` | `setusr` 通道正常 |
| B2 | [3] 回读 = `0x140000` | 借道机制可用（可反复跳变）|
| B3 | [2] 回读不变 | ★ **复现原 bug，证明"同值=空操作"就是根因** |

★ **B1/B2 失败时不要靠"多试几次"碰运气** —— 说明 `setusr` 通道在这台机器上不成立，
需要换触发重读的方式（回到设计阶段，不是重试阶段）。

---

## 四、阶段 C · roundtrip 完整闭环（★最关键）

```sh
sh /opt/usr/nx-ks/nx-rc/flab-verify.sh roundtrip trix400
```

脚本自动完成：先应用一个**不同的对照配方** → 记录读数 → 应用目标配方 → 独立读回 → 出判据表。

**五条判据全过才算「一键」成立**：

| # | 判据 | 失败含义 |
|---|---|---|
| C1 | `enum = 0x140009` | 没落在目标槽|
| C2 | `PW_TYPE` 名称正确 | 风格没切过去 |
| C3 | `重读方式 = direct` 或 `via-...` | 借道逻辑没走到 |
| C4 | ★ **7 维与对照不同** | **ISP 没重读 PW 段 ← 本次要修的 bug** |
| C5 | 无 `VERIFY-FAIL` | 回读自证失败 |

★ **C4 是唯一能证明"画面真变了"的客观判据。** C1/C2/C3/C5 全过而 C4 不过，
说明写入的数值恰好与对照相同 → 换一对差异更大的配方（建议 `trix400` ↔ `velvia50`）。

**逐项人工核对**：脚本给的7 维读数要与 `recipes.json` 里该配方的值**逐项一致**。
不一致 = 写入失败（不是重读问题）。

---

## 五、阶段 D · 端到端：拍图 + 像素统计（★最终判据）

### D1 · 相机端拍两张

```sh
# 配方 1：纯黑白（SAT=0，最干净的判据）
sh /opt/usr/nx-ks/filmlab.sh apply trix400
sh /opt/usr/nx-ks/nx-rc/flab-verify.sh shot        # 记录last_shot.txt

# 配方 2：高饱和彩色
sh /opt/usr/nx-ks/filmlab.sh apply velvia50
sh /opt/usr/nx-ks/nx-rc/flab-verify.sh shot
```

★ **必须同一场景、同一构图**（不能转相机），否则判据失效。
★ 建议选一个有彩色物体的场景（花卉/衣物/肤色），纯灰墙测不出饱和度差异。

### D2 · PC 端拉图统计

```sh
cd D:/download/NX-KS2-88/test_server

# 噪声底（可选但强烈建议）：同配方连拍两张，量化"同配方也有差异"的幅度
C:/Users/31623/.workbuddy/binaries/python/envs/default/Scripts/python.exe \
  shotstat.py 192.168.0.105 --noise-floor 575PHOTO/A.JPG 575PHOTO/B.JPG

# 正式对比：黑白 vs 彩色
C:/Users/31623/.workbuddy/binaries/python/envs/default/Scripts/python.exe \
  shotstat.py 192.168.0.105 --compare 575PHOTO/SAM_A.JPG 575PHOTO/SAM_B.JPG
```

> ★ **无需任何代理参数**（脚本已内置 `ProxyHandler({})` 绕过系统代理）。
> 若改用 `curl` 抓图则**必须加 `--noproxy`**，否则 Windows 系统代理造成 502 假象。
> 抓图走 **80 端口**（8080 不行，实测）。
> ★ **退出码即判据**：`--compare` 判据不成立时返回 **1**，成立返回 **0**。
> 上层自动化必须看退出码，不能只看stdout 里有没有"✓"。

**通过判据**：

| # | 判据 | 实测基线（已用 demo 图验证过统计函数）|
|---|---|---|
| D1 | **纯黑白那张 `sat_mean < 0.08`** | `dcim_trix` 实测 `sat=0.0000`、`R=G=B=0.6156` |
| D2 | 通道均值最大差异 > 阈值 | 阈值 `0.0059`（≈1.5/255）；有噪声底时取其 **2.5 倍** |
| D3 | 两张 `lum` 不应差太大 | 差异过大说明曝光变了，不是色彩生效 |

★ **D1 是最硬的证据**：`SAT=0` 的配方如果真生效，画面必然 R≈G≈B、饱和度≈0。
这不是"看起来像黑白"，是数值上的 `spread=0.0000`。

**离线自测（不需要相机，用于确认判据本身没坏）**：

把 IP 写成 `local` 即可读本地文件，三个回归用例已全部实测通过：

```sh
cd D:/download/NX-KS2-88/test_server
PY=C:/Users/31623/.workbuddy/binaries/python/envs/default/Scripts/python.exe

# ① 彩色 vs trix(黑白) → 判据1+2 成立，退出码 0
"$PY" shotstat.py local --compare \
  filmsim/demo/dcim/100PHOTO_IMG_0001.JPG \
  filmsim/demo/dcim_trix/100PHOTO_IMG_0001.JPG; echo "rc=$?"

# ② 彩色 vs velvia(高饱和) → 判据1 不中、判据2 成立，退出码 0
"$PY" shotstat.py local --compare \
  filmsim/demo/dcim/100PHOTO_IMG_0001.JPG \
  filmsim/demo/dcim_velvia/100PHOTO_IMG_0001.JPG; echo "rc=$?"

# ③ 同配方两张 → 判据2 应判失败，退出码 1（证明判据不是"永远说OK"）
"$PY" shotstat.py local --compare \
  filmsim/demo/dcim_velvia/100PHOTO_IMG_0001.JPG \
  filmsim/demo/dcim_velvia/100PHOTO_IMG_0002.JPG; echo "rc=$?"
```

实测数值（2026-10-05，留作阈值基线）：

| 用例 | 关键读数 | 退出码 |
|---|---|---|
| ① 彩色 vs trix | trix `R=G=B=0.6156`、`sat=0.0000`、`spread=0.0000`；Δ通道 `0.0990` | 0 |
| ② 彩色 vs velvia | velvia `sat=0.5330`；Δ通道 `0.1702` | 0 |
| ③ 同配方两张 | Δ通道 `0.0044` <阈值 `0.0059` → 正确判失败 | **1** |

---

## 六、阶段 E · 机身键实测（最后做）

阶段 A–D 全过之后，才测 S1 键：

```sh
# S1 键连按 3 次，每次之间回读
sh /opt/usr/nx-ks/filmlab.sh cycle
# 手动按 S1 → 再执行
st cap capdtm getusr 20      # 看 PW_TYPE / enum
sh /opt/usr/nx-ks/filmlab.sh dump 9
```

**通过判据**：每次按 S1 后 `enum` 仍为 `0x140009`（固定槽），
且 `cur.idx` 递增、7 维读数与 `recipes.json` 里对应配方一致。
`sh /opt/usr/nx-ks/nx-rc/flab-verify.sh report` 可汇总全部记录。

★ `cur.idx` 文件在 `/mnt/mmc/filmlab/cur.idx`，重启相机后应保持。

---

## 七、失败排查决策表

| 现象 | 最可能原因 | 下一步 |
|---|---|---|
| B1/B2 跳变失败 | `setusr` 通道不成立 | **别重试**。换触发方式（如经 mod_gui 按钮触发 UI 事件）|
| C1/C2 失败 | enum 映射错| 查 `enum_of_slot()`；slot 11 → enum 12 有错位 |
| C4 不过但C1/C2/C3/C5 过 | 两配方数值太接近 | 换差异大的配方（`trix400` ↔ `velvia50`）|
| C4 不过且 C3 报 `direct` | ISP 可能确实不重读同风格 | 回阶段 B 复核借道；考虑写非目标槽再切|
| D1 sat 仍 > 0.15 | `SAT=0` 没写进去 | `flab-verify.sh apply trix400` 看7 维读数是否为 0 |
| D2 差异在阈值边缘 | 场景/曝光干扰 | 固定场景重拍；先测噪声底定阈值 |
| telnet + FTP 双挂 | **相机被压死** | 拔电池。之后严格逐条执行，不批量 |

---

## 八、★ 已知的坑（别重踩）

1. **`prefman load -a 0` 会覆盖刚 set 的值** —— 绝对不要用来"刷新"。
2. **slot 12（CUSTOM_4）在 prefman 存在但 UI 不显示** —— 写进去是看不见的脏数据，
   实测残留 `R=240 G=240 B=40` 时相机"拍完照后台卡、照片删不掉"。`apply`/`preset` 已一律拒绝。
3. **JSON 每字段必须独立成行** —— 一行多项时 `awk gsub(/[^0-9-]/,"")` 会把数字连片
   （`"R":106,"G":100` → `106100`）。生成时强制 `indent=2`。
4. **字段名必须与脚本查询一致** —— `K` 不是 `kelvin`。不一致时 `[ -n "$K" ] &&` 短路，
   **静默失败读回旧值**，极难发现。
5. **busybox 无 `pidof`** —— 读 `/proc/[0-9]*/comm`。
6. **CRLF 是头号坑** —— `.sh` / `.json` / `.txt` 各咬过一次。生成时强制 LF，
   解析时剥尾部 `\r`。远端 md5 一致却语法错 ⇒ 必是行尾，`od -c` 是唯一可靠手段。
7. **改 `gui_ini.NX500` 会被覆盖** —— 必须改模板 `gui_tpl.NX500`。
8. **mod_gui 标签 ≤6 全角字符**，横线（——）会挤掉真字。

---

## 九、判定汇总模板（填完才算验证结束）

```
日期:2026-10-__    相机 IP: ____________    固件: NX500 / 1.12

阶段 A  A1□  A2□  A3□  A4□        基线 slot9: R=__ G=__ B=__ HUE=__ SAT=__ SHP=__ CON=__
阶段 B  B1□  B2□  B3□            T0=__ T1=__ T2=__ T3=__
阶段 C  C1□  C2□  C3□  C4□  C5□   before=__________ after=__________ reload=________
阶段 D  D1□  D2□  D3□            黑白 sat=______ 彩色 sat=______ ΔRGB=______ 阈值=______
阶段 E  S1 连按 3 次              enum=__  cur.idx=__→__→__

结论: □ 通过    □ 不通过（失败判据编号: ____）
```

★ **只有 7 个格子全勾才算通过。** 任何一条不过，先写进
`.workbuddy/memory/YYYY-MM-DD.md` 再动手改，不要靠反复重试碰运气。
