# T5 后端上机首验 + U7 步骤 1/2 记录（2026-10-16 晚 · 相机在线）

> 相机 `192.168.0.105`；telnet 23 / FTP 21 均通；`uptime = 16 min`（18:17 探测）⇒ **本会话尚未重启**
> 依据：`ONDEVICE_SOP_2026-10-16.md` §10（U7）；`T5_LUT_BACKEND_2026-10-16.md`
> 原始输出：`u7_2_dry_2026-10-16.log` / `u7_2_cmapick_2026-10-16.log` / `t5_backend_onmachine_2026-10-16.txt`

---

## 1. 环境事实（本轮新确认，全部实测）

| 事实 | 值 | 影响 |
|---|---|---|
| `busybox` 位置 | **仅 `/opt/usr/nx-ks/busybox`**（`/bin/busybox`、`/usr/bin/busybox` 均不存在） | 不在 PATH ⇒ 调用必须绝对路径；SOP/文档里的 `busybox sh …` 写法会 `command not found` |
| `/bin/sh` | **→ bash**（symlink） | 无 busybox sh 的场合可直接 `sh` |
| LUT 工具落位 | **全在 SD `/mnt/mmc/filmlab/`**（5 个 .arm + `lutpick.sh` + `lut_backend.sh`），`/opt/usr/nx-ks/` **无** lut 工具 | 后端脚本原先只找 `/opt/usr/nx-ks/lutload.arm` ⇒ 见 §2 |
| 表目录 | `/mnt/mmc/filmlab/luts/` 10 张 19712B 表（6 Kodak + A00/A01/A02 + `_identity`） | U7 序 1 通过 |
| 相机状态 | 基线 bind-mount = 无；P5 `ExecStartPre` **已在 unit 内**（`/usr/lib/systemd/system/di-camera-app.service:6`）；App 在跑（pid 247） | 等开关机后新挂生效 |

---

## 2. ★ 发现并修复：后端 `lutload` 落点缺陷

**首跑 probe（修复前）**：

```json
{"ok":true,"tools":{"cmasafe":1,"cmapick2":1,"lutapi":1,"lutload":0,"lutsentinel":1,"lutpick":1},"luts_count":10,"guard":0}
```

`lutload:0` —— 脚本用 `LOAD=$D/lutload.arm`（`/opt/usr/nx-ks/`），而工具实际在 SD。
**后果**：`rollback`（= factory_restore，T5 的关闭语义实现）会在关键时刻报「缺 lutload.arm」而**失效** —— 这是"上机才发现"的致命路径，离线自测（模拟后端）覆盖不到。

**修复（`lut_backend.sh`）**：

| 改动 | 内容 |
|---|---|
| ① 落点回退 | `LOAD=$D/lutload.arm` → **不存在则回退 `$MOD/lutload.arm`** |
| ② 解释器探测 | `BB` 增加 `command -v busybox` 兜底；两者皆无 ⇒ `RUNNER=sh`（不再硬拼不存在的 `$BB sh`） |
| ③ 守护终止 | `pkill -f lutsentinel.arm` → 优先 `$BB pkill`（PATH 无 busybox） |

**复跑 probe（修复后）**：

```json
{"ok":true,"tools":{"cmasafe":1,"cmapick2":1,"lutapi":1,"lutload":1,"lutsentinel":1,"lutpick":1},"luts_count":10,"guard":0,"precondition":"apply 前需前置抢回态（先对焦一次）"}
```

★ **双端 md5 一致**：`c2c04f2db529a69dce63eb1ba3f82a35`（本地 = `/mnt/mmc/filmlab/lut_backend.sh`，5529B，`-rwxr-xr-x` 保留）
★ `lut_backend.py --selftest`：**8/8 PASS**（契约模拟不受影响）

---

## 3. 工具链修复（本轮顺带，`tools/`）

| 工具 | 问题（实测） | 修复 |
|---|---|---|
| `nx-fetch.py` | 传相对名 `nxwa_dry.log` ⇒ telnet 侧 `cp: cannot stat`（CWD 非 `/mnt/mmc`，而 FTP 已 chroot 到 `/mnt/mmc` —— **两侧路径口径不一致**） | 入参统一为「FTP 相对」，内部转绝对路径；新增 `sync` + RETR 4 次退避重试 |
| `nx-probe.py` | 新建文件取回偶发 `550`（exFAT 目录项落盘延迟） | 包装命令尾部加 `sync`；`ftp_get` 4 次退避重试 |
| 调用纪律 | 长命令（cmapick 扫描 / 写表）经 telnet 直跑**会被会话超时截断**（输出只剩首行） | 一律 `setsid … > /mnt/mmc/xxx.log 2>&1 &` 后轮询取回（本轮已按此重跑，拿到完整输出） |

---

## 4. U7 步骤 1 —— `lutpick.sh list` ✅

```
=== LUT 目录：/mnt/mmc/filmlab/luts ===
  A00_color.bin  A01_color.bin  A02_color.bin
  Kodak_Ektachrome_100_VS.bin  Kodak_Elite_Chrome_400.bin  Kodak_Kodachrome_64_Generic.bin
  Kodak_Portra_160.bin  Kodak_Portra_400.bin  Kodak_Portra_800.bin  _identity.bin
  共 10 个表
  当前记账: Kodak_Portra_400  （软件记账，非硬件读回）
```

后端 `status`：

```json
{"ok":true,"guard":0,"current":"Kodak_Portra_400","sel":1,"note":"current 为软件记账（非硬件读回）"}
```

---

## 5. U7 步骤 2 —— `apply _identity --dry`（只读落点探测 + 安全闸）✅

完整输出见 `u7_2_dry_2026-10-16.log`。要点：

| 序 | 结果 |
|---|---|
| [1/3] cmapick2 落点探测（只读） | **落点 = `0x8f800000`**（region#2「dmesg 72MiB @ 0x8f800000」区起点；1MB 采样 72 点用时 78ms；region#1 `0x94000000` 全非零 = 完全占用） |
| [2/3] cmasafe 安全闸（只读四查） | 范围 **CMA#2 (0x8f800000+72MB) OK**；4KB 对齐 OK；黑名单 OK（避开 `0x94000000..0x94005000`）；**全零 20480B 逐字节 OK** ⇒ 通过 |
| [3/3] | `--dry`：**跳过 load**（无任何写入） |
| 后端 JSON | `{"ok":true,"level":"full","table":"_identity","sel":1,"dry":true,…}`；`RC=0` |

### ★ 两点必须记下的判据差异（不得默认等价）

1. **落点与 10-09 不同**：10-09 成功那次 `lutapi` 映射在 **`0x8f81e000`**（区内偏移 `0x1E000`）；本次 cmapick2 报的是 **区起点 `0x8f800000`**。
   ⇒ 需在正式写表前确认「是否接受区起点」（脚本注释里对 `0x94000000` 事故族的戒律指向"区起点"）。**未确认前不写。**
2. **cmapick2 自带告警**：末行仍打印「有 2 个候选落点 —— 不要尝试，先退出拍摄态让 ISP 释放」。当前相机处于**拍摄态**（取景运行中）。
   ⇒ 与 SOP §10 前置「相机停在菜单界面」一致：**写表步骤（序 3-4）须等相机进菜单 + 先对焦一次（抢回态）**。

---

## 6. 结论与下一步

**本轮已完成（零风险、零重启）**：门控复跑（`FAIL=0`）、T5 后端真机 probe/status 首验 + 一处**致命落点缺陷修复并双端验证**、工具链三处健壮性修复、U7 序 1/2 通过（`identity` 干跑全绿）。
**仍待用户动作**：

| 待办 | 需要 |
|---|---|
| U1 §3（挂载验证）/ U2（`st app film`）/ U5（菜单配方名） | **正常关机 → 开机一次**（P5 挂载必须在 App exec 前发生） |
| U7 序 3-8（写 identity / Portra 400 / 成片判据 / lutsentinel 守护） | 相机停在**菜单界面** + 用户**对焦一次**（抢回态）+ 目视取景器 |
| 落点口径裁决 | 区起点 `0x8f800000` 是否可用（对比 10-09 `0x8f81e000`） |

⛔ 全程未执行任何 `restart`、未做任何写入（`--dry`）。
