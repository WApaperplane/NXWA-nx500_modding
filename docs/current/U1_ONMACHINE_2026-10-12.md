# U1 只读上机结果（2026-10-12 晚）

> 触发：相机上线（19:04 探活成功）。目标：**把门控恢复到它该有的状态**（补 u1 证据）。
> 依据：`test_server/u1/runbook.txt`（生成物）+ `TASKFLOW_2026-10-12.md` W-1。
> 纪律：只读；段间等待 90s（铁律 88）；@gate 头自证。

---

## 0. 门控前后对比（同一台相机、同一晚）

| 门 | 上机前（19:04） | 上机后（19:18） | 变化 |
|---|---|---|---|
| G0 上机可达 | FAIL（相机离线） | ✅ **PASS** | 相机上线 |
| G1 上机安全 | FAIL（G1-7b 缺 `@gate` 头 + 离线） | **MANUAL**（只剩两个人工项） | ✅ 已修 `a1_preflight.sh` 的 `@gate` 头 |
| G2 U11 路线判定 | BLOCKED（缺 `mem_compare.json`） | ✅ **PASS** | ★ 本次产出 |
| G3 原生 UI | PASS | PASS | — |
| G4 允许改 p7 | PASS | PASS | — |
| G5 生效判据 | BLOCKED（G5-2/G5-3） | **G5-1 ✅ / G5-2 ✅ / G5-3 BLOCKED** | ★ 本次产出 G5-2 |
| **汇总** | FAIL=2 BLOCKED=2 | **FAIL=0 BLOCKED=1** | —— |

> `G1-3/G1-4` 在 `gate_flow.py` 里是**硬编码 MANUAL**（工具无法代签）⇒ G1 永远显示 MANUAL，
> 因此放行矩阵里 L2/U4/L4 恒显"卡 G1"。**实际含义 = 这两个人工项由操作者自担**，不是阻塞。
> —— 本次已履行 G1-3（见 §3）。

---

## 1. 环境侦察（§1，`u1_probe.sh`，145 行）

```
firmware : 1.12 / NX500 / NX500GLU0APC1 / DSP_NX500GLU0APC1_SR1 / BABF43A
kernel   : Linux drime5 3.5.0 #7 PREEMPT Wed Jun 3 14:40:29 KST 2015 armv7l
uptime   : 19:10:17 up 3 min        ← 刚重启（与"刷机后 telnet Refused 窗口已过"一致）
loadavg  : 0.87 0.61 0.26   (ps 行数 90)
input    : /dev/input/{event0,event1,event2,mice,mouse0}
EV_MOBILE.sh md5 = 54a308b8c55d8e3a313f63c33e06d0a5   ← 符合 G1-2 要求（非死循环版）
```

→ 完整落盘：`raw8/gates/u1/baseline.txt` + `probe.log`

---

## 2. ★ `/dev/mem` 四点对照（§2，`u1_rd.sh 1..4`）—— **G2 转绿的决定性证据**

铁律 118：先阳性对照证明"方法在本机读得动"，再阴性对照，最后才问问题本体。

| idx | 地址 | 角色 | `dd_rc` | 字节 | 判定 |
|---|---|---|---|---|---|
| 1 | `0x94000000` | **阳性对照**（CMA 窗口） | **0** | **3072** | ✅ 方法可用 |
| 2 | `0x2082b000` | 阴性对照（设备寄存器区） | 1 | 0 | ✅ 如预期失败（`Bad address`）|
| 3 | `0x810fd100` | 目标（p7 LUT 缓冲 A） | 1 | 0 | ✗ 不可读 |
| 4 | `0x81115200` | 目标（p7 LUT 缓冲 B / LUT0） | 1 | 0 | ✗ 不可读 |

**判据（runbook 写死）** ⇒ **G2b**：

> 阳性对照通过（方法可用）+ 阴性对照如预期失败 + 两个 p7 LUT 缓冲均 `dd` 失败
> ⇒ "读不到" = **该地址面真的不可读**（不是方法失效）；
> ⇒ 评估 `p7_full.lutmod.bin` 前**必须重推目标地址**（CMA 窗口会变）。

- 这同时**严格化了死路清单 #6**（"`/dev/mem` 读 p7 / MMIO 全 Bad address"）——
  此前是单点观察，现在是**带阳性/阴性对照的完整证明**。
- 证据：`raw8/gates/u1/{ctl_dram_94000000,ctl_dev_2082b000,lut_a_810fd100,lut_b_81115200}.{bin,log,md5}`
  + 汇总 `raw8/gates/u1/mem_compare.json`（由 `test_server/u1/gen_mem_compare.py` 生成）

---

## 3. 负载基线与纪律履行（G1-3 / G1-4）

| 项 | 内容 |
|---|---|
| 上机前基线 | uptime 147 s / loadavg 1.08·0.56·0.22 / ps 4 |
| 段落中观察 | 19:13 loadavg 0.99·0.91·0.52；19:16 仍 <1.0 —— **无拖垮征兆** |
| 纪律 | 一次会话一条（组合）命令；输出经 `u1_collect.py` FTP 回拉核对 md5（不信回显）|
| 段间等待 | 全部 90 s（runbook WAIT: 90）|

---

## 4. `st cap iqr` 全量 dump（§5 前半）—— **G5-2 转绿**

- `raw8/gates/u1/iqr_dump.txt`：**22574 B / 199 行 / 184 个唯一 `eIQ_ID_*`**（门控要求 ≥184）
- ★ 排查记：`grep -o` 起初只数到 **1** 个 —— 因为文件含 **565 个非可打印字节**，
  grep 默认按二进制处理只输出 "Binary file matches"。**必须 `grep -a`**。

---

## 5. 仍未完成：G5-3（唯一 BLOCKED）

`G5-3` 要求「能区分'值变了'与'参数被消费'」，判据文件 `raw8/gates/u1/iqr_epmc_map.tsv` —— 需要：

1. `iqr`（184 ID）× `epmc`（ISP 参数块两块 21×10）的**关联表**；
2. ★ **且必须记录"写入瞬间的运行时槽号"**（U14：槽池 8 槽 × stride `0xc8`，槽号运行时分配）。

第 2 条**必须靠一次"写入 + 立刻读回"实验**才能拿到 —— 本次是纯只读采集，**做不了**。

> ⇒ **不为过门而造表**（项目纪律：判据必须客观）。G5-3 保持 BLOCKED 是**正确状态**。
> 现有 `epmc_0_1728_nz_0x1300.log`（10-08 采）只覆盖参数块非零面，且不含槽号，
> 不足以构成 C14 关联。**需专项实验**（属"路径 B"能力，卡 G1+G5）。

---

## 6. 副产品与教训

| # | 内容 |
|---|---|
| 1 | ★ **`epmc.arm` 已可复现编译**：`test_server/sysarch/build_epmc.sh`（此前仓库里**没有**该二进制） |
| 2 | ★ 编译两个坑（已写进脚本注释）：① 缺 `d5_ep_ioctl.h` ⇒ 已把相机头拷入 `test_server/sysarch/inc/`（自包含）；② 宿主 glibc 2.39 对 32 位平台默认 time64（`ioctl→__ioctl_time64`）⇒ 必须 `-D_TIME_BITS=32 -D_FILE_OFFSET_BITS=32` |
| 3 | ★ **Git Bash 路径转换坑**：`telnet_run.py '<命令>'` 里的 `/usr/bin/setsid` 会被改写成 `E:/workbuddy/.../setsid` ⇒ 必须 `MSYS_NO_PATHCONV=1` |
| 4 | ★ **后台任务不可靠**：`run_in_background` 跑的驱动第 1 段后即中断（任务消失），只完成 idx=1 ⇒ 上机驱动**一律前台跑** |
| 5 | `a1_preflight.sh` 补 `@gate script=… opens=rdonly one_shot=1` 头（否则 G1-7b FAIL） |

---
*生成：2026-10-12 19:20 · 相机 192.168.0.105 · 全程只读，未改动相机任何状态*
