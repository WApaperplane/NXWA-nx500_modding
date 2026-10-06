# NX500 机内滤镜验证 — 逐步操作手册

> 生成日期：2026-10-04
> 目标：判定「prefman 改PW 参数 → 出片/取景画面是否变化」，这是整套机内滤镜路线的生死判据。
> 全部脚本已就绪：`test_server/pwfilter/`
> 相机端路径铁律已内置：busybox = `/opt/usr/nx-ks/busybox`，st = `/usr/bin/st`，prefman = `/usr/bin/prefman`

---

## 0. 前置条件（缺一不可）

| 项 | 要求 | 怎么确认 |
|---|---|---|
| 相机 | NX500 固件 1.12，已装 NX-KS2 mod | 相机能进拍摄界面 |
| SD 卡 | 已插卡且可写 | 之前装过mod 就有 |
| WiFi | 相机开WiFi，PC 同一网段 | 相机屏幕会显示 IP |
| Telnet | 已开（主菜单按钮或 `EV_MOBILE.sh`） | PC 能 telnet 上去 |
| PC 工具 | Git Bash + Python 3.13 | `test_server/telnet_run.py` |

**先记下相机 IP**（后面全要用）。用 `test_server/telnet_run.py` 的第一个参数传IP。

---

## 1. 把脚本送进相机

脚本现在在 `D:/download/NX-KS2-88/test_server/pwfilter/`，相机上还没有。两条路，选一条：

### 1A. SD 卡（推荐，一次搞定全部脚本）

把整个 `pwfilter/` 目录拷到 SD 卡的 `scripts/nx-rc/pwfilter/`，然后把仓库根的 `info.tg` + `nx_cs.adj` + `install.sh` 也拷到 SD 卡根，插卡等自动同步 + 重启。

同步后脚本在相机上的位置是 `/opt/usr/nx-ks/nx-rc/pwfilter/`。

### 1B. Telnet 直接写（只送一两个脚本时更快）

用 `telnet_run.py` 发 `cat > 文件 << 'EOF'` 逐段写入。适合脚本短的情况。

> 提醒：`install.sh` 走增量同步时**只覆盖不删除**，不会碰你已装的东西。

---

## 2. 【第一步·只读】连通性 + 命令面探测

这是**完全无副作用**的一步，先跑它。

```bash
cd /d/download/NX-KS2-88/test_server
python telnet_run.py <相机IP> \
  'ls -la /dev/fb*' \
  'cat /sys/class/graphics/fb0/virtual_size 2>/dev/null; cat /sys/class/graphics/fb0/bits_per_pixel 2>/dev/null' \
  'which st prefman; ls -la /usr/bin/prefman' \
  'st cap live' \
  'st app bb lcd'
```

**要盯的输出：**

| 输出 | 含义 | 若缺失怎么办 |
|---|---|---|
| `/dev/fb0` 存在 | 帧缓冲可用（内核源码级已证实应该有） | 记下来，转第 3 步用 HDMI |
| `virtual_size` + `bits_per_pixel` | 这两个数决定 `fb2jpg.py` 的参数 | 拿不到就用第 3 步 |
| `/usr/bin/st` 存在 | 命令面可用 | 必存在，否则 mod 没装对 |
| `/usr/bin/prefman` 存在 | **PW 参数写入通道** | 若不存在，整条 prefman 路线作废 |
| `st cap live` 有输出 | **liveview 控制面可用（重大发现）** | 若报 unknown，转第 4 步 |

> `st cap live` 这条是我 10-04 才查到的，之前完全没进视野。它带 `setpath 0-9`（含 `RawOut`）和 `dump 2-5`，**可能直接给出 liveview 数据流**，比 `/dev/fb0` 更好。

---

## 3. 【第二步】framebuffer 抓帧（`/dev/fb0` 路线）

```bash
# 相机端
sh /opt/usr/nx-ks/nx-rc/pwfilter/fb-probe.sh check
```

先看 `virtual_size` / `bits_per_pixel`，然后抓帧：

```bash
sh fb-probe.sh snapclean   # 关叠加层 + 抓一帧
sh fb-probe.sh loop 5      # 连抓 5 帧看是否连续刷新
```

**把raw 拉回 PC**：抓到的文件在 SD 卡 `/mnt/mmc/fbsnap/`。拔卡读，或者用 telnet + base64（3MB 太大，**建议直接拔卡**）。

**PC 端转换**：

```bash
cd /d/download/NX-KS2-88/test_server/pwfilter
python fb2jpg.py <W> <H> <BPP> <raw文件路径>   # 输出 PNG
python fb2jpg.py --diff a.raw b.raw <W> <H> <BPP>   # 两帧差分，看是否在刷新
```

**判据：**

- `snap` 出文件 0 字节 → fbdev 未绑定，这是**正常的**（fbdev 常只支持 mmap 不支持 read）。转第 4 步。
- PNG 能打开且内容是相机界面 → 通了。
- `--diff` 报变化比例 < 0.1% → liveview 没在刷新，回第 4 步。
- `--diff` 报 1% 以上变化 → **通了**，liveview 在动。

### 3b. 内核源码的诚实警告

我在 `drm_fb_helper.c` 里查到一处**硬编码覆盖**：

```c
/* 原本按 CRTC 实际 mode 算 sizes... */
sizes.fb_width  = sizes.surface_width  = 64;   // ← 无条件覆盖
sizes.fb_height = sizes.surface_height = 64;
```

意思是：**`/dev/fb0` 很可能被注册成 64×64 的占位缓冲，不是 1024×768 的真实画面。**

这解释了为什么上一轮我说"fd0 一定行"可能过于乐观。`check` 的输出会直接告诉我们答案——如果 `virtual_size` 是 `64,64`，fb0 路线就到此为止，直接走第 4 步。

---

## 4. 【推荐路线】`st cap live` liveview 控制面

这是 10-04 才发现的通路，**优先级高于 fb0**。

```bash
sh /opt/usr/nx-ks/nx-rc/pwfilter/lv-probe.sh help
```

先看帮助全文（只读）。重点关注三组：

```bash
# A. 输出路径 —— 2=RawOut 最可能有原始数据落盘
st cap live setpath 2
st cap live dump 3# dump 3 帧
st cap live setpath 0        # 务必还原

# B. 帧率（决定调参预览的响应速度）
st cap live sd sensorframerate 30
st cap live sd outputframerate 30
st cap live sd dataframerate 30

# C. Smart Filter —— 可能比 prefman PW 更直接的滤镜通路
st cap live sd smartfiltermode 15# 15 = SmartFilterOFF
```

**完整探测跑一遍**：

```bash
sh lv-probe.sh status     # 当前状态（只读）
sh lv-probe.sh dump 3     # 试 dump（会改 setpath，测完自动还原 0）
sh lv-probe.sh sfilter    # 探测 17 个 smartfiltermode 值
```

**判据（这一条决定整条路线的走向）：**

| 结果 | 意义 | 下一步 |
|---|---|---|
| `setpath 2` + `dump 3` 之后 SD 卡/临时目录出现新文件 | **liveview 数据能落盘** | 直接做成预览通道，最优解 |
| `dump` 无输出但命令不报错 | 数据走内存（IPC out） | 转 HDMI 采集卡（第 5 步） |
| `smartfiltermode N` 改值后画面变化 | **Smart Filter 是比 prefman 更短的通路** | 优先攻这条 |
| `smartfiltermode` 报参数错| 实机固件裁剪了这条命令 | 回到 prefman 路线 |

---

## 5. 【备选】HDMI 采集卡（连续流唯一解）

内核实锤：`drime5_drm_hdmi.c:83` 的 `SET_GRAPHIC_CLONE_MODE` ioctl 就是官方"LCD 镜像到 TV"开关，`sclr.dp_path = D5_DP_TV_SLCD` 走硬件 scaler。

实操：
1. 买 USB HDMI 采集卡（约 50 元）
2. 相机接采集卡，PC 用 OBS / ffmpeg 收流
3. 相机端：`st app bb tv video`（TV 端关叠加层）

这条路**不依赖任何未验证的假设**，但要花钱。目前不急，等第 4 步结论。

---

## 6. 【核心判据】PW 参数到底改不改出片

前面都是通道探测，**这一步才是生死判据**。

### 6.1 先只读 dump 基线

```bash
sh /opt/usr/nx-ks/nx-rc/pwfilter/pw-probe.sh
```

阶段 1 会把全部 11 个 pref 区备份到 SD 卡（**这是回滚保险，必须跑**）。阶段 2 是只读探测。

**要记下来的：**

- 7 个 PW 参数的当前值和**值域**（是 `-100~100`？`-3~3`？无符号？）
- 13 种风格之间差异有多大（RETRO / CLASSIC 应该和 STANDARD 明显不同）
- `APPPREF_CHECKSUM` (0x0fcbc) 写入前后变不变

### 6.2 拍摄基线图

```bash
sh pw-preview.sh lcdvideo   # 关叠加层
sh pw-preview.sh snap       # 拍一张
```

浏览器打开 `http://<相机IP>:8080/`，进相册看最新一张。**记下这是基线。**

> 用web 相册而不是拔卡，是因为 dirlist CGI 是实时读SD 卡的，新照片立刻出现。

### 6.3 改一个参数，再拍

```bash
# 语法: set <offset> <十进制值>
# CUSTOM_1 的 SATURATION 在0x0a4e0
sh pw-preview.sh set 0x0a4e0 3
```

然后刷新相册对比。

### 6.4 判定

| 现象 | 结论 |
|---|---|
| **出片明显变了** | ✅ **prefman 路线全通**，整套方案成立 |
| 出片没变，但 `prefman get` 显示值变了 | 参数没被 ISP 读取 → 需要重启相机或找 reload 命令 |
| `prefman save` 报错 / 相机行为异常 | checksum 问题（最大风险点） |
| 相机变砖 | 立刻 `prefman load_file 0 <阶段1备份>` 恢复 |

**回滚命令**（阶段 1 备份的路径）：

```bash
prefman load_file 0 /mnt/mmc/pw-backup/app.bin
prefman save 0
sync && sync && sync
```

---

## 7. 【可选项】snapshot/diff 定死真实槽位

社区方法论（Recipe Lab 的做法）：**改一个东西，diff 一次**。

```bash
sh pw-snap.sh snapshot v1      # 抓基线
# → 去机身 Picture Wizard 界面，只改一个参数（比如把饱和度拖一格）
# → 插回 SD 卡
sh pw-snap.sh diff v1# 打印变化的那一行
```

**这是唯一能确定 PW 参数真实槽位与编码的方法**，比猜快几个数量级。值域靠这个定死，不是靠猜。

---

## 8. 建议的执行顺序

```
第1 步连通性探测（只读，5 分钟）
   ↓
第 2 步 fb-probe check（只读，2 分钟）→ 看 virtual_size 是不是 64x64
   ↓
   ├─ 是 64x64 → fb0 路线作废，直接第 3 步
   └─ 不是 → 抓帧测试，能用就用（省一台采集卡）
   ↓
第 3 步 lv-probe help + dump（关键，10 分钟）
   ↓
   ├─ dump 出文件 → 做成预览通道，方案收工
   └─ 没出文件 → 决定是否买 HDMI 采集卡
   ↓
第 4 步 pw-probe（只读备份 + 探测，10 分钟）★ 生死判据
   ↓
第 5 步 pw-preview snap → set → snap 对比
   ↓
   ├─ 画面变了 → 路线成立，开始做配方试验台
   └─ 没变 → 转 capdtm varlist / Smart Filter 路线
```

---

## 9. 每次测试后的收尾

```bash
# 恢复叠加层
st app bb lcd on

# 还原 liveview 路径
st cap live setpath 0
st cap live sd smartfiltermode 15

# 确认 liveview 正常（回到相机界面看一眼）
```

---

## 10. 已知风险清单

| 风险 | 触发条件 | 应对 |
|---|---|---|
| **checksum 拒写** | `prefman save` 后相机行为异常 | 阶段 1 备份 + `load_file` 回滚 |
| **变砖** | 改到签名区| 同上；不要碰0x0fcb8 之后的偏移 |
| **CPU 打满误判断连** | 大量 convert 占用单核 | 所有重活 `nice -n 19` |
| **SD 卡被清空** | 旧版 install.sh 行为 | 现在是增量同步，scripts 母本保留 |
| **prefman dump 含云token** | dump 日志外传 | **拔卡后的日志不要发网上** |

---

## 11. 每一步该给我什么

跑完一步，把**输出贴回来**。我需要的关键数据：

| 步骤 | 关键输出 |
|---|---|
| 1 | `st cap live` 有没有输出、`prefman` 在不在 |
| 2 | `virtual_size` 和 `bits_per_pixel` 的值 |
| 3 | `dump` 后有没有新文件、文件名和大小 |
| 4 | 7 个 PW 参数的值域 + 13 风格差异 + checksum 行为 |
| 5 | 改参数前后两张图的对比结论 |

**第 3 步和第 4 步的结果会直接改写方案**——如果 `st cap live dump` 能出数据，M2 的配方选择器和M3 的 HDMI 采集卡都可以砍掉。
