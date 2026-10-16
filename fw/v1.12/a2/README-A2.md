# A2 补丁镜像（p7 段）—— 刷入教程

> 本目录的 **`p7_a2.bin`** 是 `NXWA-A2` 补丁的 **p7 分区镜像**（12,075,648 B）。
> 它是「**全 7 维 PW 一键**」的固件前提：写入相机的 p7 分区后，`filmlab.sh` 的直推可**一次写入全部 7 个维度**（R/G/B/HUE/SAT/SHARP/CON）。
> 未刷 A2 时一切照旧（直推段静默无效，不会崩），全维效果仍可用「画面向导 → 自定义1」保底。

---

## 适用范围

- **仅 NX500**（NX1 无此构建）；基于 NX500 **官方固件 1.12** 验证。
- 前提：相机已装 mod、能 telnet 登录（root / 空密码）——即主菜单里 **IP 行点击已开 Telnet**。

## 前置检查（两个数字先对上）

| 项 | 值 |
| --- | --- |
| `p7_a2.bin` md5 | `712c6fd0a49371ec05ce94c367b0d5c7` |
| 文件大小 | `12075648` 字节 |

> 把本包解压到 SD 卡后，镜像位于 **`/mnt/mmc/patch-a2/p7_a2.bin`**（FTP 根 = SD 卡根）。

---

## 两条安装通道（二选一）

| 通道 | 做法 | 适合 |
|---|---|---|
| **A. 轻量（本文档正文）** | p7 段镜像 `p7_a2.bin` + telnet `dd` 写入 | 已开 telnet 的机器；写入约 1 秒 |
| **B. 完整整包** | 下载 Release 附件 `slp_a2_p7_v117.bin` → 放 SD 卡根、改名 `nx500.bin` → 机身菜单「设置 → 设备信息 → 固件更新」刷入 | 不想动 telnet；走官方刷机链 |

> 二者刷入的 p7 内容**等价**。通道 B 下载入口：GitHub `v2.88.0-nxwa.2` Release 页下方 **Assets** 区（含 `.md5` 校验文件）。

## 刷入步骤（telnet 下逐条执行）

```sh
# 0) 校验镜像（必须等于 712c6fd0a49371ec05ce94c367b0d5c7，不等就停）
md5sum /mnt/mmc/patch-a2/p7_a2.bin

# 1) 备份当前 p7 —— 回退全靠它，务必执行！
dd if=/dev/mmcblk0p7 of=/mnt/mmc/p7_backup_$(date +%s).bin bs=1M
sync

# 2) 写入 A2（约 1 秒）
dd if=/mnt/mmc/patch-a2/p7_a2.bin of=/dev/mmcblk0p7 bs=1M
sync; sync; sync

# 3) 回读校验
#    12 MiB 读回 = 镜像 12,075,648 B + 分区尾部 507,264 B 零区
dd if=/dev/mmcblk0p7 bs=1M count=12 2>/dev/null | md5sum
#    标准情况应输出：69050a17ea9fdbcdab4cf32e7b5ffdb2
#    若不符：① 重跑本步一次；② 仍不符 → 拉回本地与 p7_a2.bin 逐字节比对
#    （FTP 到 SD 后用仓库 tools/nx-fetch.py；常见原因 = 分区尾部有历史非零数据或写入不完整）
```

⚠️ **写入前后各核对该设备名是 `/dev/mmcblk0p7`**（p7 = ISP 固件分区；NX500 实测）。机型/环境不同时**不要盲抄**，先用 `cat /proc/partitions` 或既有资料确认。

## 生效

- **正常关机 → 开机**（p7 固件在下次启动时加载；正常开关机即可）。
- ⛔ **绝对不要** `systemctl restart di-camera-app` —— 实测会**卡死整机**（须物理断电重启）。

## 验证成功

```sh
# 一键直推一条配方（例如 portra400）
sh /opt/usr/nx-ks/filmlab.sh pwpush portra400 --yes

# 客观判据（ISP 手上 7 维 vs 配方槽位）
sh /opt/usr/nx-ks/filmlab.sh check
```

- 画面**立即变化**（配方效果）+ `check` 判据通过 = **成功**。
- 若 `pwpush` 执行后画面无变化：先确认步骤 3 回读 md5 是否一致、是否已「正常关机开机」一次。

## 回退

```sh
# 用备份写回（把 <时间戳> 换成第 1 步实际生成的文件名）
dd if=/mnt/mmc/p7_backup_<时间戳>.bin of=/dev/mmcblk0p7 bs=1M
sync; sync; sync
```

然后**正常关机 → 开机**。或重刷官方 1.12 固件（走官方 SD 刷机链）——两条路都可行。

## ⚠️ 风险与纪律

- 写入期间**不要断电、不要拔卡**；建议电量充足或接外接电源（写入本身约 1 秒，风险窗口极小）。
- **写错分区后果严重**（如误写 `mmcblk0p1`）——执行前把命令读两遍、分区名核对两遍。
- 本补丁为 NXWA 社区构建，**自担风险**；官方固件升级会重写 p7 ⇒ **升级后需重新刷入本镜像**。
- 分区（30 MB）比镜像（12 MB）大：写入后**剩余部分保持原样**（实测为全零），这是正常的。

## 数字台账（核对用）

| 物件 | md5 |
| --- | --- |
| `p7_a2.bin`（本目录） | `712c6fd0a49371ec05ce94c367b0d5c7` |
| 完整刷机包 `slp_a2_p7_v117.bin`（352 MB，走官方 SD 刷机链，**自 2026-10-16 起作为 Release 附件提供**：`v2.88.0-nxwa.2` 页 Assets 区） | `44b61efc0625874b62ef6a45517ffda8` |

## 原理一句话

A2 在 p7 里加了一段「档位池直写」通道：外部发 `seq 0x134..0x13A`（7 个原始值）+ `0x13B`（触发）→ p7 写参数槽 → 走官方「档位应用」链把 7 维一起送进 ISP —— 于是「一键」达成。细节见仓库 `docs/current/A2_PATCH_DESIGN_2026-10-14.md` 与 `A2_READBACK_VERDICT_2026-10-15.md`。
