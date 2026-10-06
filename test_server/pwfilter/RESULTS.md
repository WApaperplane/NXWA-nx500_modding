# Picture Wizard 机内滤镜 — 实机验证结论

> 验证日期：2026-10-03 晚 | 设备：NX500 固件 1.12（`drime5` 3.5.0） | IP 192.168.0.105
> 全部数据来自telnet 实测，非文档推断。

## 一、结论：prefman 路线成立

| 验证项 | 结果 |
|---|---|
| `/usr/bin/prefman` 可用 | ✅ |
| 13×7 PW 参数块偏移 | ✅ 与 `prefman info 0` 报告完全一致 |
| 写入内存 | ✅ `prefman set 0 <off> l <v>` |
| 落盘 | ✅ `prefman save` |
| **eMMC 真持久化** | ✅ **`prefman load -a 0` 重载后值保持** |
| CHECKSUM 是否需重算 | ❌ **不需要**，`APPPREF_CHECKSUM (0x0fcbc)` 恒为 108，不随参数变化 |
| 值域裁剪 | ❌ prefman 不裁剪，`-10..255` 原样接受 → **调用方自己约束** |
| 变砖风险 | 已排除（备份 + load_file 回滚路径已验证） |

## 二、真实偏移表（实机 `prefman info 0` 输出，非推算）

参数块基址 `0x0a3ec`，**按参数分组**：每参数占 13 个连续 slot（13 风格 × 4B = 52B），每风格步进 4B。

| 参数 | 基址(CUSTOM_x 前的风格) | 步进 |
|---|---|---|
| R_COLOR | `0x0a3ec` | +52 |
| G_COLOR | `0x0a420` | +52 |
| B_COLOR | `0x0a454` | +52 |
| HUE | `0x0a488` | +52 |
| SATURATION | `0x0a4bc` | +52 |
| SHARPNESS | `0x0a4f0` | +52 |
| CONTRAST | `0x0a524` | +52 |

CUSTOM_4 实测落点（脚本算术与 prefman info 交叉验证一致）：

```
R_COLOR 0x0a41c   G_COLOR 0x0a450   B_COLOR 0x0a484
HUE     0x0a4b8   SATURATION 0x0a4ec   SHARPNESS 0x0a520   CONTRAST 0x0a554
```

风格序号：STANDARD=0 VIVID=1 PORTRAIT=2 LANDSCAPE=3 FOREST=4 RETRO=5 COOL=6 CALM=7 CLASSIC=8 CUSTOM_1=9 CUSTOM_2=10 CUSTOM_3=11 CUSTOM_4=12

**注意 CUSTOM_3 在 prefman 侧存在且有独立数据**（见下表 C3 列 ≠ 中性），而社区文档说capdtm 侧 `0x14000b` 无效 —— 两套枚举不一致，CUSTOM_3 可用。

## 三、值域（实机 dump 全表）

**中性值：R/G/B = 100，HUE/SAT/SHARP/CONTRAST = 10。**

出厂 13 风格实测数据（`pw-set.sh dump`）：

```
参数        STD VIVD PORT LAND FORES RETRO COOL CALM CLASSIC  C1   C2   C3   C4
R_COLOR      100  100  100  100  100  100  100  100  100    103   95   98  100
G_COLOR      100  100  100  100  100  100  100  100  100    105  102  106  100
B_COLOR      100  100  100  100  100  100  100  100  100     83  104   97  100
HUE           10   10   10   10   10   10   10   10   10      8    8    8   10
SATURATION    10   10   10   10   10   10   10   10   10     10   12   11   10
SHARPNESS     10   10   10   10   10   10   10   10   10     10   10   10   10
CONTRAST      10   10   10   10   10   10   10   10   10      5   12    8   10
```

**读法**：
- 前 9 个厂商风格全部 = 中性值 → **出厂时这9 个 slot 是"未初始化"状态，不是曲线载体**
- **CUSTOM_1/2/3 有真实差异值**，是用户/出厂写过的实际配置 → **CUSTOM_1-4 才是真正可用的自定义槽**
- CUSTOM_4 原本也是全中性 → 已被本次验证写入 `SAT=30 / SHARP=15 / CONTRAST=5`

**推论**：厂商风格（STANDARD/VIVID/PORTRAIT…）的曲线**硬编码在 ISP 固件常量里**，prefman 侧不存数据，只存"PW_TYPE 选哪个"。所以能改的只有 CUSTOM_1-4。

## 四、入口字段

| 偏移 | 字段 | 实测值 |
|---|---|---|
| `0x0a3d4` | `PW_TYPE` | **2048** |
| `0x0a3d0` | `SMART_FILTER` | **256** |

两个都是非零且非小整数 → 说明它们是**位域或缩放编码**，不是直接的枚举序号。`PW_TYPE` 决定用哪个风格，改它可以切风格。**具体编码规则未解**，需实机试验（写入不同值 → 看机身菜单显示哪个风格高亮）。

## 五、待验证的唯一生死判据

**改PW 参数后出片是否变化。** 本轮无法自动完成——相机不在拍摄模式（`ps` 无 capdtm 进程），需要人工操作。

验证步骤：

```
1. 机身：MENU → Picture Wizard → 选 CUSTOM_4 → 拍一张 → 存到 SD
2. PC  ：telnet 恢复中性值
   sh /opt/storage/sdcard/_pwtest/pw-set.sh CUSTOM_4 100 100 100 10 10 10 10
3. 机身：Picture Wizard 仍选 CUSTOM_4 → 同参数再拍一张
4. 对比两张：SAT 30→10 应明显降低饱和，SHARP 15→10 应变软
```

- **两张有差异** → ✅ 整套路线成立，进M2 做配方试验台
- **两张无差异** → 参数没进 ISP，转 capdtm `varlist` 路线（8 个 PW 实时变量）

## 六、命令与回滚

```bash
# 相机端脚本位置
/opt/storage/sdcard/_pwtest/pw-set.sh

sh pw-set.sh dump                # 打印13 风格全矩阵
sh pw-set.sh getCUSTOM_4         # 打印指定风格
sh pw-set.sh CUSTOM_4 100 100 100 10 30 15 5   # 写入并落盘（R G B HUE SAT SHARP CONTRAST）
sh pw-set.sh rollback            # 从备份恢复 app 区

# 备份文件
/opt/storage/sdcard/_pwtest/app.bak67340 字节
```

回滚命令（手动）：
```bash
prefman load_file 0 /opt/storage/sdcard/_pwtest/app.bak
prefman save 0
sync
```

## 七、坑

1. **`prefman load 0` 语法错**，要 `prefman load -a 0`（从 active 节点重载）
2. **busybox ash 下嵌套反引号失效** → 用 `$(( ))` 算术扩展
3. **`prefman dump` 含云服务 token / 账号 / MAC / 密码**，不可外传
4. **`/dev/fb0` 是 64×64 占位缓冲**（源码级 `drm_fb_helper.c` 无条件覆盖 `sizes.fb_width = 64`），且 `drime5_drm_fb_ops` 无 `.fb_read` → fb0 路线作废
5. **`st cap live dump` 无输出**，`loglevel 9` + `log all on` 后仍静默 → liveview dump 通道本轮未打通
6. **相机长时间运行会过热死机**（本次验证中重启一次），telnet 断开后需等重启完成

## 八、交付脚本

| 文件 | 用途 |
|---|---|
| `pw-set.sh` | 核心读写器（dump/get/写入/rollback），已在实机跑通 |
| `pw-read.py` | PC 端经 telnet 读 13×7 矩阵并打印 |
| `pw-probe.sh` | 三阶段探测（备份/只读/写入），写入段默认关闭 |
| `pw-snap.sh` | snapshot/diff（Recipe Lab 方法论移植） |
| `pw-preview.sh` | 写参数 + 自动触发拍摄 |
| `lv-probe.sh` | `st cap live` 控制面探测（setpath/dump/rate/sfilter） |
| `fb-probe.sh` | `/dev/fb0` 探测（已确认作废，留作记录） |
| `fb2jpg.py` | PC 端 raw→PNG 转换 + 帧间 diff（零依赖，实测通过） |
| `pw_offsets.py` | 从 Prefman_tool.md 自动解析偏移表 |