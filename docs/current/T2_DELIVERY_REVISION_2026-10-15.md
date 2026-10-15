# T2 投递链修订（2026-10-15）

> **目的**：把 10-13 实机发现合并入 T2 投递件；给出「生效路径」再设计的候选与论证材料（供裁决）。
> **依据**：`CAMERA_ONLINE_PROBE_2026-10-13.md`（§1-2 时序与卡死实测 / 附 C 休眠联锁）；`NATIVE_UI_ROADMAP_2026-10-15.md` §5 修订块；`MEM_INJECTION_EVAL_2026-10-15.md` §3。
> **落地**：`scripts/dicam/dicam_patch_install.sh` 与 `dicam_patch_rollback.sh` 已修订（本日）；`dicam_patch_status.sh` 未改（只读工具，保持原样）。
> **口径**：✅ = 已证（实测）｜🔶 = 推断/设计 ｜ ❓ = 未决（附验证法）

---

## 0. 结论

0. ★★ **裁决（2026-10-15，用户拍板）：生效路径 = 候选 a（P5 前置）**。实施件已制作（`t2_premount.sh` + `dicam_p5_install.sh` + `dicam_p5_rollback.sh` + status 集成），详案见 **§6**。同批拍板：首探样本暂不上机（不着急）。
1. **两个缺口已确认**（§1）：T2 的两条设计前提被 10-13 实测推翻——mount 晚于 App exec 约 25s（时序）；「立即生效」所用的 restart 会卡死整机（风险）。
2. **脚本已修订**（§2）：install/rollback 去 restart、语义改为「只就位 → 待自然重启」、注释与判据对齐实机事实；语法/行尾/无残留 restart 均已复核 ✅。
3. **「生效路径」再设计**：三候选（§3，保留备查）——**已裁决为 a（P5 前置）**，落地见 §6。
4. 在实机验证前，**T2 不得宣称「安装即生效」**——脚本输出已按此措辞（「已就位；生效需等 App 自然重启 / P5 后为『下一次正常开机』」）。

---

## 1. 两个缺口（证据）

### 1.1 缺口 A：mount 晚于 App exec（时序）

- 实机实测：di-camera-app exec = **boot+12.2s**；init.sh（bluetoothd 钩子链）= **boot+37.8s**（CAMERA_ONLINE_PROBE §1-2，`/proc/<pid>/stat` 第 22 字段）。
- bind-mount 语义：改变「路径 → inode」的解析；**已 exec 的进程持有 exec 时打开的文件映射，不受后续 mount 影响**。
- ⇒ 每次冷启动，init.sh 建立的 mount 都晚于本次 App exec；旧前提「本块必须早于 `di-camera-app.service`」被推翻。
- 未决（= 候选 c 要回答）：本机为 hibernation 快照式启动（附 C）。「日常关机开机」究竟是 re-exec 还是 snapshot-resume；mount 表跨 resume 是否保留——均未实测 ❓。

### 1.2 缺口 B：restart 卡死（风险）

- 实测：`systemctl restart di-camera-app` ⇒ **整机卡死**（须物理重启），机理推断为 hibernation 联锁（附 C）。
- 旧脚本第 4 步「立即生效」= mount + restart ⇒ **已删除**。
- 牵连修订：`TASKFLOW_2026-10-12` 中 W-3/E-D4 演练判据（「restart 后画面正常 ⇒ 机制可用」）全部作废，改「自然关机开机」路径。

---

## 2. 脚本变更清单（本日）

| 文件 | 变更 |
|---|---|
| `dicam_patch_install.sh` | ① 头部新增「10-15 修订」段（时序实测 + restart 风险 + 「只就位」语义）；② init.sh 追加块注释更正（删旧前提，注明实际生效点见本文档）；③ 第 4 步「立即生效（重启 App）」→「建立 bind-mount（不再重启 App）」+ 新增 4b「生效语义（必读）」段；④ 收尾输出明确「当前运行进程仍是旧件」「功能判据需在自然重启后核对」 |
| `dicam_patch_rollback.sh` | ① 头部修订说明；② init.sh 清理 sed 兜底行补充（匹配新版注释行）；③ 第 3 步去掉 restart → 「正常关机→开机恢复」+ 明确当前进程仍是补丁件 |
| `dicam_patch_status.sh` | 未改（只读检查工具） |

复核 ✅：三者 `bash -n` 通过；无 CRLF（铁律 99）；全仓库 grep 无残留 `systemctl restart` 调用（仅注释中的禁止说明）。

---

## 3. 三候选：生效路径再设计（★ 已裁决 = a，2026-10-15；本节保留备查）

### 候选 a：unit 本体前置挂载（P5 式）★ 已选（实施见 §6）

- **a1（ExecStartPre）**：给 rootfs `/usr/lib/systemd/system/di-camera-app.service` 的 [Service] 增一行
  `ExecStartPre=-/opt/usr/nx-ks/dicam/t2_premount.sh`
  （`-` 前缀：失败不阻止启动；脚本内做存在性判断 + `mount --bind`）。
- **a2（ExecStart wrapper）**：改 `ExecStart=` 为 `/opt/usr/nx-ks/dicam/t2_launch.sh`，脚本内先条件 mount 再 `exec` 原二进制。**时序保证最硬**（mount 与 exec 零间隙）。
- 前提：rootfs remount rw 一次（与既有 `bluetoothd` wrapper 同类先例——mod 早已在 rootfs 写文件，「零 rootfs 写入」本就不成立）。
- 代价：unit 为 rootfs 物，**刷机后被官方重写** ⇒ 需扩展「刷机后自动重装链」（把「检查/重打 unit 行」加入 *install.sh 全量安装分支*——注意 D-5 纪律「日常增量链不碰 rootfs」，本项应为全量分支专属）。
- 风险：低（`-` 前缀保证不阻止启动；脚本失败 = 退回无挂载 = 原厂行为）。
- 判据：正常关机开机后，`mount | grep di-camera-app` 在 App 启动前已就位；`st app film` 可用。
- 恢复：remount rw + 删行/wrapper 还原 + 自然重启。

### 候选 b：T1 就地补丁（放弃 T2 抗刷机性，换确定性）

- **操作**：remount rw → 按 `c2_bytepatch.v2.json` 就地改写两个补丁点（P1 8B + P2 248B）→ 无需 mount、无需 init.sh 块。
- 优点：**彻底无时序问题**（exec 时加载的就是改后文件）；文件身份可即时验证（md5 == `48d94bd6…`）。
- 代价：rootfs 被就地写入（96% 满——同尺寸改写不增空间）；**刷机后补丁随 rootfs 被官方重写而消失** ⇒ 接受「刷机后重放」（手动或专门链，不塞日常增量链）。
- 风险：低（写错 = App 崩；有 `c2_bytepatch.v2.json` 逆写 + 官方件备份）；恢复：反向字节写回。
- 判据：目标文件 md5 == `48d94bd63e4479fc931ae1a1fee4e94b`（v2 补丁）。

### 候选 c：生命周期实测（先做，可能原样解锁 T2）

- **问题**：是否存在「晚于 mount（boot+37.8s）的 App exec 时刻」？
  - 若「日常关机开机 = 快照 resume，进程不 re-exec」→ 需另找 re-exec 触发点（或转 a/b）；
  - 若「resume 保留 mount 表 **且** 存在某时点 re-exec」→ **T2 原样可用**（init.sh 维持 mount，re-exec 时自然加载补丁件）。
- **只读采集**（相机在线时）：
  1. 两次「正常关机→开机」后的 `/proc/<pid>/stat` starttime 与 PID 对比；
  2. `/proc/<pid>/maps` 中可执行文件行的 inode/device 变化；
  3. `mount | grep di-camera-app` 跨关机保持性；
  4. journal 的 App 启动记录（判断是否每次 boot 都 re-exec）。
- 代价：低（只读）；不确定性：结论可能「不存在」（则转 a/b）。
- 判据：找到「mount 在位 + App 随后 re-exec」的时点序列。

**建议考察顺序**：**c → a → b**（先拿便宜结论；a 时序最硬、改动可包装；b 最简单但损抗刷机性）。**a 与 b 不互斥**：可先 b 解锁功能验证、后 a 收敛为交付形态。

---

## 4. 上机验证清单（相机在线时执行）

- [ ] 现状快照：mount 表 + App PID/starttime + maps 可执行行（基线）
- [ ] 「正常关机→开机」×2：记录 PID、starttime、maps inode、mount 保持性（= 候选 c 的数据）
- [ ] 若选 a：remount rw → 注入 ExecStartPre/wrapper → 关机开机 → journal 验证 mount 早于 App exec
- [ ] 若选 b：remount rw → 就地补丁 → 验证 md5 → 关机开机 → `st app film` 判据

## 5. 遗留问题（❓）

1. **mount namespace**：App 是否在独立 namespace（若是，init.sh 的 mount 可见性需另验）。
2. **hibernation 恢复路径**对 mount 表与进程状态的影响（候选 c 核心）。
3. 「自然关机」是否总能触发 re-exec——本机快照机制细节未逆清。
4. `TASKFLOW_2026-10-12` 内 W-3/E-D4 原文判据的正式修订（文档层面，待执行）。

---

## 6. ★ P5 实施方案（裁决后落地件，2026-10-15）

### 6.1 组件清单（源在仓库 `scripts/dicam/`；语法/LF 已复核）

| 件 | 相机端落点 | 作用 |
|---|---|---|
| `t2_premount.sh` | `/opt/usr/nx-ks/dicam/t2_premount.sh` | 被 ExecStartPre 调用；**幂等**条件挂载（补丁体不存在 ⇒ 静默退出=禁用；已挂载 ⇒ 跳过）；任何失败皆 exit 0（不阻止 App 启动） |
| `dicam_p5_install.sh` | `/opt/usr/nx-ks/dicam/` | **注入器**：remount rw → 备份 unit（存 p14）→ 逐行改写注入 `ExecStartPre` → 自检（命中数==1）→ `sync` → remount ro → daemon-reload |
| `dicam_p5_rollback.sh` | 同上 | **恢复器**：精准移除该行（自检 0 命中），与注入器互逆 |
| `dicam_patch_status.sh` | 同上 | 已加「P5 前置」检查段（unit 行在位性） |

### 6.2 unit 改动（唯一 rootfs 写入点）

```ini
[Service]
+ ExecStartPre=-/opt/usr/nx-ks/dicam/t2_premount.sh    ← 新增（P5）
  ExecStart=/usr/apps/com.samsung.di-camera-app/bin/di-camera-app
```

- `-` 前缀：脚本失败**不阻止** App 启动（硬护栏）。
- 备份：`/opt/usr/nx-ks/dicam/di-camera-app.service.p5.bak`（p14，刷机不被写）。
- 注入方式：纯 POSIX sh 逐行改写（busybox 全兼容；不用 awk/sed 的 `i` 语法）。

### 6.3 生效语义（为什么覆盖缺口 A）

- systemd 在**每次 unit 启动**时执行 ExecStartPre——严格先于 ExecStart/exec ⇒ **冷启动下 mount 时序硬保证**（不再有 init.sh 的 25s 缺口）。
- **与 init.sh 复挂块并存安全**：两边都幂等（先挂者生效，后者跳过）；init.sh 链退为双保险。
- 🔶 诚实边界（未实测项）：本机日常「关机开机」若为 **hibernation resume**（进程不重新 exec），则 mount 的保持性依赖「快照中 mount 表被保留」——即**至少发生过一次冷启动完成挂载**后，后续 resume 沿用。刷机后重启、断电重启等均为冷启动路径，可完成首次挂载。
- ❗ 与缺口 B 的关系：本方案**全程无 restart**；回退唯「正常关机→开机」。

### 6.4 刷机后重装链

- 刷机 → rootfs 被官方重写 ⇒ unit 行被冲掉（与 bluetoothd hook 同理）；
- 恢复：SD 全量安装链装回 hook/init.sh 后，**重跑一次 `dicam_p5_install.sh`**；
- ⚠ 暂不改 `install.sh` 本体（安全分发器，改动需单独评估）；「init.sh 自动检查/补 unit 行」的自愈增强列 §6.6。

### 6.5 上机流程（就绪，待放行）

1. 同步 `scripts/dicam/*` → 相机 `/opt/usr/nx-ks/dicam/`（FTP 或 SD）；
2. `sh dicam_patch_status.sh` 确认补丁体在位；
3. `sh dicam_p5_install.sh`（注入；**无 restart**）；
4. **正常关机 → 开机**；
5. 验证：status 脚本（mount 在位 + P5 行在位）+ `/tmp/dicam_p5_mount.log` + `st app film` 功能判据；
6. 回退：`dicam_p5_rollback.sh` + 正常开关机。

### 6.6 遗留/增强候选

- init.sh 自愈（自动检查/补 unit 行）——涉及开机自动 remount rw，慎重评估后再做；
- 双挂栈深核对（上机时 `mount | grep` 确认始终单层）；
- daemon-reload 后若本次运行中发生「App 被拉起」，ExecStartPre 亦生效（预期无害，首次上机时观察）。

---
*生成：2026-10-15 · 分支工作树（Codex 克隆）· **裁决已落**（P5 前置 a）；实施件 v1 已就绪（离线编写，未上机验证）。零写机（脚本/文档为本地编辑）。*
