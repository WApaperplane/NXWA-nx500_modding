# 实时风格通道 — 打通（2026-10-04 实机）

> 设备：NX500 固件 1.12（`drime5` 3.5.0）| 192.168.0.105 | A 档 + 拍摄模式
> 脚本：`test_server/pwfilter/pw-setusr.sh`（已上传 `/opt/storage/sdcard/_pwtest/pw-setusr.sh`，4959B，实测通过）

## 一、结论：你的思路成立，通道已打通

`st cap capdtm setusr` 可**实时切换 Picture Wizard 全部 13 个风格 + Smart Filter 13 种类型 + 强度档**。
渲染由相机 ISP 自己完成，**CPU 成本为零** —— 这就是 Recipe Lab 机制在NX500 上的对等物。

## 二、★ 最关键的一条：setusr 正确语法（社区文档没写，我错了 4 轮）

```
st cap capdtm setusr <索引> <完整DATA_ID_十六进制>
```

**第二参数必须是完整 DATA ID（0x140001 这种），不是裸值（1/2/3）。**

DATA ID 格式 = `0x<分组前缀><枚举序号>`：

| 维度 | 索引 | DATA ID 前缀 |
|---|---|---|
| USERDATA_PW | 20 | `0x14xxxx` |
| SMARTRANGE | 21 | `0x15xxxx` |
| FACETONE | 25 | `0x19xxxx` |
| SMARTART | 27 | `0x1bxxxx` |
| SMARTARTLEVEL | 28 | `0x1cxxxx` |
| COLORSPACE | 50 | `0x32xxxx` |
| SMARTFILTERTYPE | 62 | `0x3exxxx` |
| SMARTFILTERSIZE | 63 | `0x3fxxxx` |
| HDRARTLEVEL | 77 | `0x4dxxxx` |
| LLSLEVEL | 78 | `0x4exxxx` |

**错误返回 vs 正确返回**：
- ❌ `setusr 20 5`（裸值）→ `UserData is not set  -1179648`
- ✅ `setusr 20 0x140001`（完整 ID）→ `UserData is set` → `getusr 20` 变成 `PW_VIVID`

**我犯的错**：前4 轮一直传裸值（或第三参数传长度，那是 setvar 的格式），
把「参数格式错」误判成「dfmsd 未启动 / 相机不在拍摄模式」，
连带去查社区文档、启dfmsd、试 DFMS 工具——全是在错误前提下的排查。
**教训**：`UserData is not set` 是**参数格式错误**，不是「服务没起」。
判据：服务未起 vs 格式错误无法从这一个错误码区分，必须先穷举参数格式再动环境。

## 三、dfmsd 与本项目无关（澄清）

按社区文档 `DFMS Commands.md` / `Control-camera-from-command-line.md`：
`dfmsd -t &` 启动的日志是 `[SYS_DFMS] Launched dfmsd daemon with test mode`，
它是**脚本 / OSD 通道**（`dfmstool -s 'osd string 7Hello'`），与 capdtm / PW 无关。

实测：dfmsd 启动前后 `setusr` 结果**完全一样**（都是 not set，因为格式错）。
所以 **FilmLab 不需要 dfmsd**，不需要拉起任何额外服务。

`dfmstool -a` 的adj 数据是物理校准（`adj_sys` 出厂标记 / `adj_cap` CIS 序列号 /
`adj_iq` AWB 增益 / `adj_vfpn` 坏点 / `adj_cs` CS表 / `adj_dpc` 坏点表），
**不含风格曲线** —— 不是配方通道，别走这条路。

## 四、实机枚举结果

### Picture Wizard（索引 20，`0x14xxxx`）— 13 风格全部实时可切
```
0x140000 PW_STANDARD     0x140004 PW_FOREST
0x140001 PW_VIVID        0x140005 PW_RETRO
0x140002 PW_PORTRAIT     0x140006 PW_COOL
0x140003 PW_LANDSCAPE    0x140007 PW_CALM
                        0x140008 PW_CLASSIC
0x140009 PW_CUSTOM1      0x14000b PW_CUSTOM3
0x14000a PW_CUSTOM2      0x14000c PW_CUSTOM4
```
枚举名表在 0x14000b 处有bug（回显成 PW_CUSTOM2），但值本身正确。

### Smart Filter（索引 62，`0x3exxxx`）— 13 类型 + 独立强度档（索引 63）
```
0x3e0000 OFF              0x3e0007 WASH_DRAWING
0x3e0001 VIGNETTING       0x3e0008 OILPAINTING
0x3e0002 MINIATURE_H      0x3e0009 INKPAINTING
0x3e0003 MINIATURE_V      0x3e000a RADIALBLUR
0x3e0004 RANDOMMOSAIC     0x3e000b FISHEYE
0x3e0005 COLOREDPENCIL    0x3e000c ACRYL
0x3e0006 WATERCOLOR       0x3e000d NEGATIVE
```
`SMARTFILTERSIZE` 索引 63：`0x3f0000 SIZE0` / `0x3f0001 SIZE1` / `0x3f0002 SIZE2` …

**这是完全独立于 PW 的第二套实时滤镜维度，且带强度分级。**

### 其它已确认可读维度
SMARTRANGE(21) / SMARTART(27) / SMARTARTLEVEL(28) / FACETONE(25) /
COLORSPACE(50) / HDRARTLEVEL(77) / LLSLEVEL(78) / PWBRK×13 (35-47)

## 五、架构（你的方案，双通路）

```
按 EV 键 → gen_menu.sh → mod_gui
                            │
                 FilmLab 配方管理（app.cfg 挂载）
                            │ 选配方
        ┌───────────────────┴────────────────────┐
        │ ① prefman set→ 写 PW 7维参数块 0x0a3ec│  持久化配方数据
        │   prefman save && sync                 │  （重启后仍在）
        ├────────────────────────────────────────┤
        │ ② setusr 20 0x14000C← 切到 CUSTOM_4   │  实时生效
        │   setusr 62 0x3e0001← 叠Smart Filter  │  （ISP 自己渲染）
        └───────────────────┬────────────────────┘
                            ▼
                   liveview 实时出效果
```

**双重写入不是冗余**：只写 ① → 引擎可能缓存旧值；只写 ② → 重启丢失。
两条都写 = 既实时又持久。

**挂载位置**：`/opt/usr/nx-ks/auto/nx-rc.sh`（autoexec 启动脚本，
现有 push/thumb/daemon 都从这拉起，FilmLab 同层挂载，不新增机制）。
`mod_gui` 在 `/opt/usr/nx-ks/mod_gui`，**不在 PATH，需绝对路径**。

## 六、待人工验证的唯一一项

**setusr 改完后，取景器画面是否真的变化。** 这是全部工作中唯一不能自动化的判据。
测试：`sh /opt/storage/sdcard/_pwtest/pw-setusr.sh pw 1`（切VIVID）后看取景器。

注意：厂商 9 风格的曲线硬编码在 ISP 固件里（prefman 侧只存 `PW_TYPE` 选哪个，
出厂 9 个 slot 全= 中性值 = 未初始化），**所以肉眼变化应当只在 CUSTOM_1-4 上出现**。
若切 VIVID 也能看出变化，说明我对「厂商风格未初始化」的判断错了 —— 那是好事。

## 七、本轮方法论教训

1. **社区文档没有 setusr 语法**。`ST_CAP_CAPDTM.md` 只列了 userdata 表，
   没写setusr 怎么传参。必须实机穷举。
2. **单一错误码不能区分「环境未就绪」和「参数格式错」**。我因为先入为主认为是前者，
   浪费了 4 轮和一次 dfmsd 启动。以后遇到 `not set` 类错误，
   **先穷举参数格式**（值/ID/长度/有无第三参数），再查环境。
3. **穷举前先读同主题社区主仓库**（铁律重申）。`DFMS Commands.md` 第一行就写着
   dfmsd 的正确用法，若当时先读它，能更早排除 dfmsd 这条干扰线。
4. `busybox ps` 看不到其他进程（命名空间隔离），但 **`pgrep` 可以**——
   `EV_S1.sh` 里已在用 `pgrep di-camera-app`，这是现成的探测手段。
5. 相机单核，**连发命令会超时**。批量枚举要控制节奏（每条 sleep≥0.25s），
   否则 SSH/telnet 会话被 SIGTERM。
