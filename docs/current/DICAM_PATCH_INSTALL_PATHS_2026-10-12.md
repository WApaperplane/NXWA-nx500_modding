# di-camera-app 补丁：安装路径与 Release 布局（2026-10-12）

> **回答两个问题**：① 补丁装到相机的哪个路径；② 如果要发 GitHub Release，资产怎么摆、包怎么组。
> 决策依据：`MOD_DECISION_P7_APP_2026-10-12.md` D-5（T2 bind-mount）、D-6（桩 v2）。
> 打包工具：`test_server/dicam/make_dicam_patch_pack.py`。

---

## 0. 一句话

**补丁体落在 `/opt/usr/nx-ks/dicam/`（p14，刷固件不覆盖），靠 `init.sh` 开机 bind-mount 生效 ——
rootfs 一个字节都不改。** Release 上一个**独立小包**（约 1.6 MB 压缩后），**不含** SD 引导三件套。

---

## 1. 相机端路径（权威）

### 1.1 安装后的完整布局

```
/opt/usr/nx-ks/dicam/                       ★ 补丁体落点（p14 分区；刷固件不覆盖）
├─ di-camera-app.c2.v2                      补丁二进制 4,773,516 B（md5 48d94bd6…，★ 含参数净化）
├─ di-camera-app.v1.12.orig                 ★ 官方件备份，由 install 脚本首次运行时自动生成
│                                           （md5 ae44293e969101d1cf0a93cbe9b99f75）
├─ c2_bytepatch.v2.json                     逐项 old/new 字节（回滚依据）
├─ dicam_patch_install.sh                   补丁器（幂等）
├─ dicam_patch_rollback.sh                  卸载器（与 install 互逆）
└─ dicam_patch_status.sh                    状态检查（只读）

/opt/usr/nx-ks/init.sh                      ← 追加一个块（唯一改动的"系统"文件）
                                              # [dicam-T2] … mount --bind …
/usr/apps/com.samsung.di-camera-app/bin/di-camera-app
                                            ← bind-mount 挂载点（rootfs 内文件【字节不变】）
```

### 1.2 为什么是这个路径

| 选择 | 理由 |
|---|---|
| 落点 `p14`（`/opt/usr`） | 这是 mod 的唯一安全落点：**刷固件不覆盖**（SLP 容器不含 p14） |
| 不写 rootfs | rootfs 96% 满；且刷 SLP 时 idx6=rootfs 会被官方镜像重写 ⇒ 写进去也会丢 |
| `init.sh` 复挂 | `install.sh` 已建立的开机钩子（bluetoothd → init.sh）；每次开机自动重挂 |
| 挂载点不动字节 | 失败 = `umount` 即恢复，无需任何备份还原 |

### 1.3 三条操作命令（相机端，root）

```sh
# 安装（幂等；会备份官方件、写 init.sh 钩子、bind 挂载、重启 App）
sh /opt/usr/nx-ks/dicam/dicam_patch_install.sh

# 状态（只读；刷机后复查"T2 是否仍生效"）
sh /opt/usr/nx-ks/dicam/dicam_patch_status.sh

# 卸载（umount + 清 init.sh 块 + 重启 App）
sh /opt/usr/nx-ks/dicam/dicam_patch_rollback.sh
```

---

## 2. Release 资产布局

### 2.1 两个包，职责分离

| 包 | 内容 | 是否含补丁 |
|---|---|---|
| `NX-WA-<ver>.zip`（**主包**，已有） | `info.tg` + `nx_cs.adj` + `install.sh` + `scripts/` | ❌ 不含（但含 `scripts/dicam/` 脚本素材） |
| `NX-WA-DICAM-PATCH-<ver>-<stub>.zip`（**本包**，新增） | 见下 | ✅ 补丁二进制 + 补丁器 |

### 2.2 补丁包内部（★ 刻意很薄）

```
NX-WA-DICAM-PATCH-1.0-v2.zip
├─ README.md                   安装/判据/回滚说明（含路径表）
├─ dicam_patch_install.sh      补丁器
├─ dicam_patch_rollback.sh     卸载器
├─ dicam_patch_status.sh       状态检查
├─ di-camera-app.c2.v2         补丁二进制（4,773,516 B）
├─ c2_bytepatch.v2.json        回滚依据
└─ md5.txt                     逐文件 md5
```

> ⚠ **刻意不含 `info.tg` / `nx_cs.adj` / `install.sh`** ——
> 那三个是主包的 SD 引导三件套；本包若放同名 `install.sh`，用户解压到 SD 卡会**覆盖主包引导器**，
> 后果是把"智能引导器"换成一个只做补丁的脚本，再插卡就走错分支。这条是硬约束。

### 2.3 生成命令

```bash
python test_server/dicam/make_dicam_patch_pack.py --stub v2 --ver 1.0 --write
# → E:/NXWA/release/NX-WA-DICAM-PATCH-1.0-v2.zip（含 md5.txt）
# 默认 dry-run；--out 可改输出目录
```

---

## 3. 两条投递路（都收口到同一条相机端命令）

### 路 A：SD 增量同步（配主包，适合首次）

```
1. 把补丁包里的 dicam_patch_*.sh + di-camera-app.c2.v2 + c2_bytepatch.v2.json
   放进【主包】的 scripts/dicam/ 目录（仓库里本来就已在该位置 ⇒ 主包天然带上）
2. 按主包流程插卡 → 增量同步 → 文件落到相机 /opt/usr/nx-ks/dicam/
   （★ 同步【不会】自动执行补丁器 —— app 补丁必须显式触发）
3. 相机上：sh /opt/usr/nx-ks/dicam/dicam_patch_install.sh
```

### 路 B：FTP + telnet（已装机推荐，最直接）

```bash
# PC → 相机（FTP 根 = /mnt/mmc）
ftp> mkdir /_xfer/dicam
ftp> put di-camera-app.c2.v2   /_xfer/dicam/di-camera-app.c2
ftp> put dicam_patch_install.sh /_xfer/dicam/
ftp> put dicam_patch_rollback.sh /_xfer/dicam/
ftp> put dicam_patch_status.sh  /_xfer/dicam/
ftp> put c2_bytepatch.v2.json   /_xfer/dicam/

# 相机（telnet，一会话一条命令）
mkdir -p /opt/usr/nx-ks/dicam
cp -f /mnt/mmc/_xfer/dicam/* /opt/usr/nx-ks/dicam/
sh /opt/usr/nx-ks/dicam/dicam_patch_install.sh
```

> 注：`install` 脚本里补丁文件名固定为 `di-camera-app.c2`；v2 包内叫 `.c2.v2`，
> 投递时**改名**（或 `cp di-camera-app.c2.v2 di-camera-app.c2`）。

---

## 4. 与固件刷写的关系（★ 关键，决定 T2 选型）

| 事件 | 对补丁的影响 |
|---|---|
| 刷 A1 / 任何官方 SLP 包 | rootfs 内 `di-camera-app` **被官方版覆盖** ⇒ 但 bind-mount 仍指向 p14 的补丁体 ⇒ **补丁继续生效** |
| 刷机后自动重启 | `init.sh`（p14）跑 → 自动重挂 ⇒ **无需人工恢复** |
| 相机恢复出厂 | 视是否清 p14 而定 ⇒ 用 `dicam_patch_status.sh` 复查 |
| 想彻底退回官方 | `dicam_patch_rollback.sh`（umount + 清钩子） |

**这就是选 T2 而非 T1 的全部理由**（T1 写进 rootfs 的字节会在下次刷机时消失）。

---

## 5. 判据与回滚（写死）

| 阶段 | 判据 |
|---|---|
| 装上 | `st app help` 回显；`st app film "<短命令>"` 生效；`st app uscom` **不再**输出 UserSpec dump（改名生效的反证） |
| 持续 | `dicam_patch_status.sh`：mount 在 + 目标 md5 == 补丁 md5 + `init.sh` 含 `# [dicam-T2]` |
| 刷机后 | 同上（★ 抗刷机实证点） |
| 回滚 | rollback 后 `st app uscom` 又能输出 dump 表 |

**失败模式**：App 崩（画面黑）⇒ telnet 仍活 ⇒
`sh /opt/usr/nx-ks/dicam/dicam_patch_rollback.sh`（或 `umount` 挂载点）+ `systemctl restart di-camera-app`。
★ 记牢：unit 里 `Restart=always` 被注释，**崩了不自愈**。

---
*生成：2026-10-12 · 分支 `nxwa` · 工具 `test_server/dicam/make_dicam_patch_pack.py` · 相机端脚本 `scripts/dicam/*.sh`*
