# PW 参数通道 —— 上机实测定论（2026-10-08 夜 · NX500 v1.12）

> 触发：木一实测反馈 —— **「机身 EV+AEL → 点配方 → 画面立即生效」不成立**；
> 真实链路仍是 `EV+AEL → 点配方 → 打开画面向导 → 选中自定义1 → 画面生效`。
> 本文是当晚**上机复测**的结论（不是推理），并给出**可复现的客观判据**。

---

## 0. 一句话结论

> **PW 的"画面生效"是三条独立通道；① 存储、② 选择 都到不了 ISP 的 PW 引擎，
> 只有 ③ 参数（由 di-camera-app 的"画面向导确认"推送）能改变画面。**
> 而 ③ 走的是**属性总线**（`CAttributeHandler::setPWColor… → set_attribute(0x10e/0x110/0x111/0x112)`），
> **`st` 命令面完全不暴露它** ⇒ 从 shell 侧"点一下配方就生效"**在架构上做不到**。

---

## 1. 客观判据（本轮新增，最重要）

`st cap capdtm varlist` 里的 PW 变量 = **ISP 手上真正在用的 7 维**：

| 变量 | 编码 | 解出 |
|---|---|---|
| `VARIABLE_PWCOLOR_R/G/B` | `(gain<<16) \| 0x00FF` | `gain ≈ (v>>16)/20.32` |
| `VARIABLE_PWHUE/SATURATION/SHARPNESS/CONTRAST` | 高 16 位是**有符号**：`raw16 = 16*(值-10)+15`，低 16 恒 `0xD80A` | **值 = 10 + (raw16-15)/16**（raw16 必须按补码还原！） |
| `VARIABLE_PWCOLOR`（聚合项） | 恒 `----------` | 未定义，别用 |

实测对照（slot9 = 88/112/125 冷调时）：
```
PWCOLOR_R=0x070000FF  → 0x0700=1792 → 88.2  ✓
PWCOLOR_G=0x08E000FF  → 0x08E0=2272 → 111.8 ✓
PWCOLOR_B=0x09F000FF  → 0x09F0=2544 → 125.2 ✓
PWSATURATION=0x005FD80A → raw16=0x005F=95 → 10+(95-15)/16=15 ✓（SAT=15）
PWSHARPNESS=0x002FD80A → 47 → 12 ✓   PWCONTRAST=0x004F…→79→14 ✓   PWHUE=0x003F…→63→13 ✓
```
★ **踩坑记录**：raw16 为负时（值 < 10）必须先转补码。SAT=9 的原始值就是 `0xFFFF`（不是 `0x??9F`）——
   按无符号解会把 `0xFF` 当成 255 → 解出 25。修正后实测 5 个值全对（9/8/7/11/15）。
⇒ 一组 32-bit 变量完整镜像了 PW 的 7 维 —— **这是"参数进没进 ISP"的唯一可信判据**。
（`st cap iqr` 不行：PW 变化只动 `eIQ_ID_EFFECT_MODE` 一个节点，7 维不在 iqr 里。）

本轮已把它做成命令：`sh /opt/usr/nx-ks/filmlab.sh check`（只读，零风险）。

---

## 2. 三条通道的实测结果

| 通道 | 动作 | prefman 读回 | **ISP 的 7 维** | 结论 |
|---|---|---|---|---|
| ① 存储 | `prefman set 0 0xa3ec… ×7` | ✅ 变（100/100/100 10/0/13/12） | ❌ **纹丝不动**（仍 88/111/125 / SAT15） | 打不到 ISP |
| ①+落盘 | `prefman save 0; sync` | ✅ | ❌ 仍不动 | 落盘只管持久化 |
| ② 选择 | `setusr 20 0x140009`（含借道 0x14000a） | — | ❌ 只改 `eIQ_ID_EFFECT_MODE` | 换风格名，不搬参数 |
| ③ 参数 | app「画面向导 → 确认自定义1」 | — | ✅（预期） | **唯一有效** |

上机原始输出（2026-10-08 22:5x）：
```
$ /opt/usr/nx-ks/filmlab.sh check
  ISP 现用参数:  R/G/B=88/111/125  HUE=13 SAT=15 SHARP=12 CON=14
  prefman slot9: R/G/B=100/100/100 HUE=10 SAT=0  SHARP=13 CON=12
  ✗ 判据：ISP 手上的 7 维 ≠ slot9 ⇒ 参数没进 ISP（画面不会按配方变）
```

### 2.1 顺带测出的两条硬事实

1. **不 `prefman save` ⇒ 重启回退**：apply 后相机（因下述事故）重启，slot9 从
   `100/100/100 10/0/13/12` 回退成 `88/112/125 13/15/12/14`。⇒ 引擎现已默认补 `prefman save 0; sync`。
2. **`setvar` 写 PW 变量 = 死路（再次确认，且危险）**：
   `getvar <n>` 的 id 与 `varlist` 显示下标不是一套（`getvar 13` 返回 2，而 `[13]` 是 FLASHEV=10）；
   id 是 p7 运行时注册的，**盲扫会写死 p7 capture 服务**（项目历史事故）。
   ⇒ 本项目**禁止**再试；引擎里的探测代码已移除，`pwvar` 只留一行"已作废"提示。

---

## 3. 为什么 `st` 够不到 ③（静态证据）

```
di-camera-app → CAttributeHandler::setPWColor / setPWSaturation / setPWSharpness / setPWContrast
              → set_attribute(0x10e / 0x110 / 0x111 / 0x112, &v, 4)      ← 属性总线
```
- 该总线与 capdtm 的 `0x14xxxx` userData 总线**不同编号体系**；
- `st cap capdtm` 只有 6 个子命令（setusr/getusr/setvar/getvar/usrlist/varlist，p7 帮助表 `0x6f3710` 实锤）；
- `st cap` 其余控制台（capt/fenx/live/dp/seq/capmm/face/back）也没有属性写入口。
⇒ **"点配方即生效"不可能靠 shell 实现**；要么让人点一次画面向导，要么走 app 侧通道（下一节）。

---

## 4. 下一步（唯一两个候选路子，均未打通，勿写进"已实现"）

| 路 | 内容 | 现状 |
|---|---|---|
| **A** | **键注入**：`st app nx key push/release/single <name>`（di-camera-app 自带，`UI/src/cmd/nx_cmd_key.cpp`）→ 复现"打开画面向导 → 确认自定义1" | 命令存在、返回 0，但**键名表未解**（`st app nx key show` 无输出；候选 `<name>` 探测无回显）⇒ 需要从二进制解键名表，或改成"人点一次" |
| **B** | **用户态助手**：自写 ARM 程序直调属性总线（`mm_camera_set_usr_attributes` / `set_attribute(0x10e…)`） | 需要先解出 `set_attribute` 的传输层（PLT 已被剥，需从 `libcapture-fw-prod.so` 的 `DT_JMPREL` 反查）⇒ 属独立里程碑 |

**在此之前，机身上仍是 3 步链路**（`EV+AEL → 点配方 → 画面向导选自定义1`），
而这 3 步里**只有第 3 步会让画面变** —— 这一事实已写进 README 与 `RE_PROGRESS`。

---

## 5. 本轮新增纪律（踩坑换来的）

| # | 纪律 | 代价 |
|---|---|---|
| 一 | ★ **单核相机上做图像处理必须带 `-define jpeg:size=WxW`**（libjpeg DCT 缩放） | 我漏了这一步，对 28MP JPEG 做 `-resize` ⇒ **整机重启**（uptime 归零） |
| 二 | 相机 **没有 `timeout`** applet（busybox 未编入）⇒ 脚本别依赖它 | sat.sh 静默失败 |
| 三 | ★ **Windows 上非 Edit 工具写 `.sh` 会引入 CRLF**（python `open(p,"w")` 默认文本模式） | CI 抓到 `scripts/filmlab.sh` 779 处 CRLF——必须 `newline="\n"` + 跑 `check_scripts.py` |
| 四 | FTP 侧路径 ≠ 机上路径：`FTP 根 = /mnt/mmc` ⇒ `STOR /_xfer/x`，而 `cp /mnt/mmc/_xfer/x` | 混用直接 `553 Error` |
| 五 | Git Bash 会把命令里的 `/opt/usr/...` 改写成 Windows 路径 ⇒ telnet/FTP 命令一律 `MSYS_NO_PATHCONV=1` | 已有记载，本轮再次踩到 |

*生成：2026-10-08 夜 · 上机轨（相机在线）· 地址已脱敏*

---

## 6. ★★★ 闭环验证（2026-10-08 23:13 · 木一在机身上点了一次"自定义1"）

**实验设计**：apply 配方 → 判据（`check`）→ 人工点一次画面向导 → 判据再跑。

| 时刻 | slot9（prefman） | ISP 手上那 7 维 | 判词 |
|---|---|---|---|
| `apply trix400` 后（无人操作） | 100/100/100 10/0/13/12 | **88/111/125 13/15/12/14**（旧的 ektachrome_cyan） | ✗ |
| `prefman save 0; sync` 后 | 同上 | 同上（**完全没变**） | ✗ |
| ★ 木一在机身「画面向导」里选中**自定义1** 后 | 109/101/94 11/9/8/7（portra800） | **108/100/93 11/9/8/7** | **✓** |

⇒ **③ 通道的唯一性被实证**：同一份 prefman 数据，只有"app 的 PW 确认动作"能把它搬进 ISP。
⇒ 判据本身也被双向验证（✗ / ✓ 各一次，且 ✓ 时 7 维逐个对上）。

**给未来的操作口径**：
```
sh /opt/usr/nx-ks/filmlab.sh apply <recipe>   # ① 写槽（+落盘）+ ② 切槽
# ↓ 这一步目前只能人来点（或等 A/B 两条路打通）
机身：打开「画面向导」→ 选中「自定义1」
sh /opt/usr/nx-ks/filmlab.sh check            # ★ 客观确认：✓ = 真的生效了
```

## 7. 路径 A（键注入）实测状态：命令在，但**注入未生效**

- `st app nx key push|released|single <name>`（`UI/src/cmd/nx_cmd_key.cpp`）确实存在，`st app` 返回 0；
- 键名候选在 app 里都能找到（`menu/ok/up/down/left/right/s1/s2/ev/fn/wifi/power/enter/select`…）；
- **但客观验证失败**：`nx key push s1` 后 `eIQ_ID_AF_LOCK_STATUS` 仍为 OFF；
  `nx key single s2` 后 DCIM 无新文件 ⇒ 注入没到 app 的输入层；
- 且执行该命令会**打断 telnet 会话**（与 `st app nx capture single` 同现象）；
- 线索：附近字符串有 `ERROR: XOpen() is FAILED` / `cmd_key_pressed|released` ⇒ 这条命令可能走
  X11/XTest 注入（机上有 Xorg + enlightenment），是否存在窗口/keysym 前提未验。
- ⇒ 需要解"键名表 + 注入路径"（`nx_cmd_key.cpp`），属**独立里程碑**，别再空试。
