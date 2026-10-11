# U5 上机结果 · 单分区回滚演练闭环（2026-10-11）

> 执行：木一（相机操作）+ 小A（工具链/分析）。承接 `TASKFLOW_2026-10-10.md` §3 W-3（设计草案）。
> 一句话：**"改坏 → 恢复"闭环跑通 1 轮，p12 整块回读与基线逐字节仅差偏移 0 一处；G4-2 转绿 ⇒ G4 全绿 ⇒ L4「改 p7」放行。**
> 证据：`raw8/gates/u5/rollback_drill.json` + `raw8/gates/u5/p12_readback.bin`。

---

## 0. 判据达成

| 判据 | 结果 |
|---|---|
| 闭环 ≥1 次 | ✅ **1 轮**：A'（改坏）→ R（恢复），两次刷写 UI 均 **接受 + 完成 + 自动重启** |
| 改坏确实生效 | ✅ A' 后读回 `p12[0] == 0x5A`；md5(p12[0:28672]) == `dc194f05…` == 本地 `pcache_5a.bin` |
| 恢复确实完整 | ✅ R 后读回 `p12[0] == 0x00`；md5(p12[0:28672]) == `11f6a32f…` |
| ★ 超判据（整块） | ✅ **整块 p12 5,242,368 B 与基线逐字节仅差偏移 0 一处**（`0x01`→`0x00`），其余 5,242,367 B 全等 |
| boot0/boot1 | ✅ 全程未触碰（铁律：绝不碰） |

## 1. 实验包（两枚，均在 SD 根备好）

| 包 | 内容 | 差异 vs 上场态 | md5 | 结果 |
|---|---|---|---|---|
| **A'** `slp_u5_a_5a_v114.bin` | U4 补丁件 + img8[0] `0x01`→`0x5A` + version→1.14 | 数据 1B + version 4B + CRC 4B | `d80f549e…` | **接受、完成、重启、telnet 活**；读回 `0x5A` ✓ |
| **R** `slp_u5_r_orig_v115.bin` | 内容回归原样（img8[0]=`0x00`）+ version→1.15 | 数据 1B + version 4B + CRC 4B | `9d871915…` | **接受、完成、重启**；读回 `0x00` ✓ |

- 中间件 `slp_u5_a_tmp.bin`（`65517fdb…`）为 A' 构造过程中的过渡产物，未上机。
- version 递增（1.13→1.14→1.15）是**必要手段**：U4 已实测 **UI 层只放行"文件版本 > 设备版本"**，同版本判灰。

## 2. 执行时间线（20:2x–21:14）

```
20:25  构造 A'（pcache_5a.bin + slp_tool.py 重打包）与 R
20:2x-20:3x  FTP 上传两包；相机端 md5 核验
       → A' 刷入：UI 接受 → 完成 → 自动重启 → telnet 活
       → 读回 p12[0] == 0x5A ✓（A' 生效）
       → R 刷入：UI 接受 → 完成 → 自动重启
       ★ 观察：R 刷入后 telnet 短时 Refused（~4 min），Ping 正常
21:10  telnet 自行恢复；uptime 计到 281s ⇒ 整机已完整重启
21:13  整块 p12 dd → SD → FTP 拉回 → 逐字节比对
21:14  gate_flow.py --only G4 ⇒ G4-2 PASS ⇒ **G4 全绿 5/5**
```

## 3. 验收细节（证据）

- **整块比对**：回读 `p12_readback.bin` md5 `4b34d5e89d81ae3d9abeb1ceb4923a18`，
  与基线 `raw8/emmcbak/p12.bin`（`54b0d27c…`）**仅偏移 0 一处不同**。
- **双路径互证"已回到纯净"**：
  1. 把 U4 补丁件 `pcache_patched.bin`（byte0=`0x01`）首字节归零 → md5 `11f6a32f…` == 相机回读的 28672B md5；
  2. 把基线 `p12.bin` 首字节归零 → md5 `4b34d5e8…` == 相机回读的整块 md5。
  两条独立推导同时命中 ⇒ 现态 = 纯净态，无残留。
- **运维观察（重要，供 L4 用）**：**刷机后 telnet 会有一段不可用窗口**（本次约 4 min，
  此前亦见 `ConnectionRefused` 而 Ping 通）。这与 `FW_NATIVE_UI_ONEKEY_FEASIBILITY` 记录的
  "mod 初始化头号脆弱点（需机身侧手动开蓝牙）"同源。⇒ **A1/L4 刷机后不要立刻判"变砖"**，
  至少等 5 min 并重试 21/23 端口，再做结论。

## 4. 判据修正 / 新发现

1. ★ **`raw8/emmcbak/p12.bin` 不是纯净基线**：其采集时间（MANIFEST 20:38:52）在 U4 刷写之后，
   img8[0] 已为 `0x01`（补丁态）。本次演练改用"归零推导 + 双路径互证"绕过。
   已补出 **`raw8/emmcbak/p12_pristine.bin`（md5 `4b34d5e89d81ae3d9abeb1ceb4923a18`）**
   作为 L4 前唯一回滚参照，MANIFEST 已注明。
2. `/etc/version.info` 在 U5 之后仍为 **1.12 / NX500**——证明我们改的 version 串是
   **SLP 外层（UI 反降级判据用）**，与 rootfs 内实际版本文件无关。U4 文档 §3 的同款观察得到第二次确认。
3. 备份资产里的"采后即偏"风险是本轮暴露的**流程缺陷**：今后凡"刷写后仍要再备份"的场合，
   必须在 MANIFEST 里显式标注该备份对应的是**哪个固件态**。

## 5. 附带产出

- `test_server/sysarch/u5_verify.py`（新）：整块 p12 回读 → FTP 拉回 → 与基线逐字节比对 → 自动落
  `raw8/gates/u5/rollback_drill.json`（含 `drills`/`ok` 门控字段）。**可复用于 L4 前后比对。**
- `raw8/emmcbak/p12_pristine.bin` + MANIFEST 补充说明。
- `raw8/gates/u5/p12_readback.bin`（证据留档）。

## 6. 意义

- **G4 全绿（G4-0 / G4-0b / G4-1 / G4-2 全 PASS）⇒ 能力放行矩阵 5/5 ⇒ L4「改 p7 分区」解锁。**
- 至此"有本钱改 p7"三件套齐备：**官方完整件兜底**（`.uploads/fw/nx500_v1.12.bin`，335MB）
  + **eMMC 关键分区备份 + 手动 boot0/boot1** + **同一条工具链的改坏/恢复双向闭环实证**。
- 下一步 = **A1**（首选「扩 `FUN_00051090` 跳转表边界 + 补 0x130–0x133 handler」，
  以打通外部全 7 维直推；设计见 `rea-out/A1_p7_normalizer_patch_design.md`）。

---

*生成：2026-10-11 21:16 · 分支 `nxwa` · 证据本地：`raw8/gates/u5/rollback_drill.json`*
