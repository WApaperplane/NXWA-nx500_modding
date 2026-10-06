# 相机端实机发现：libudd5 是全局基础库 + capture-fw-prod 是属性服务端

> 2026-10-04 12:25-12:30实机 telnet + FTP。相机 IP 192.168.0.105，**A 档 + 拍摄模式**。

## 一、★★★ 修正上一轮结论：libudd5 是全局库，所有进程都加载

`/proc/*/maps` 全扫，**6 个进程**把 `/usr/lib/libudd5.so` 映射在**紧邻自身 exe 的第一位**：

| PID | comm | exe | 说明 |
|---|---|---|---|
| 1039 | wpa_supplicant | /usr/sbin/wpa_supplicant | **WiFi —— 与相机业务无关** |
| 139 | Xorg | /usr/bin/Xorg | **显示服务器 —— 无关** |
| 193 | deviced | /usr/bin/deviced | 设备管理 |
| 197 | enlightenment | /usr/bin/enlightenment | **窗口管理器 —— 无关** |
| 252 | di-camera-app | /usr/apps/.../di-camera-app | 相机 UI |
| 290 | ap-setting-app | /usr/apps/.../ap-setting-app | 设置 UI |

maps 段（Xorg 为例）：
```
b6a76000-b6ac3000 r-xp 00000000 b3:0a 108  /usr/lib/libudd5.so
b6ac3000-b6aca000 ---p 0004d000 b3:0a 108  /usr/lib/libudd5.so
b6aca000-b6acc000 rw-p 0004c000 b3:0a 108  /usr/lib/libudd5.so
```
`r-xp` 偏移 `0x0000` 且排在 exe 之后第一位 → **DT_PRELOAD / 链接顺序首位**，不是普通 NEEDED。

### 排除的假设
| 假设 | 验证 | 结果 |
|---|---|---|
| `/etc/ld.so.preload` | `cat /etc/ld.so.preload` | 只有 `/usr/lib/libsys-assert.so`，**不含 udd5** |
| 进程 `LD_PRELOAD` 环境变量 | 读 `/proc/{139,193,197}/environ` | 只有 `deviced` 有 `LD_LIBRARY_PATH=:/usr/lib`，**无 PRELOAD** |
| `readelf -d` 看 NEEDED | 相机上**没有 readelf/objdump/nm** | 静默失败（我一度误读成"无匹配"，教训） |

### ★ 正确推论
**`libudd5.so` 是全局基础库 → `d5_ep_*` 是一套任何进程都能调用的 API。**
所以"谁在调 3D LUT"这个问法本身是错的。**它可能是 UI 层（di-camera-app）通过属性服务间接调的。**

## 二、★★★ 真正的相机属性服务端 = `libcapture-fw-prod.so`（734600 B，已拉到 PC）

di-camera-app 加载的相机相关库：
```
/usr/lib/libcapture-fw-prod.so   ← ★ capture firmware =相机属性服务端
/usr/lib/libudd5.so              ← 底层 ISP API
/usr/lib/libdi-sensor.so
/usr/lib/libsensor.so.1.1.0
/usr/lib/libSLP-db-util.so.0.1.0
/usr/lib/libdrm_slp.so.1.0.0
/usr/lib/libmmf-camcorder.so
```
**字符串扫描零命中 3D LUT，但符号表里有PW 全套 setter/getter** —— 上一轮"di-camera-app 不是调用者"的结论要再修正：
**它是通过 `libcapture-fw-prod.so` 这个服务端间接下发的。**

### libcapture-fw-prod.so 符号表（1988 个，节表全剥，用 PT_DYNAMIC 解出）

**架构**：`CAttributeHandler` 是主属性类，`Run(char*, int)` 为入口。

```
0x08f7b0  276  CAttributeHandler::Run(char*, int)      ← 入口
0x08f8c4  256  readAttribute()
0x08f9c4  256  readSystemAttr()
0x090134  284  writeAttribute()
0x09094c   36  writeUserAttr()
0x090970   88  writeVariableAttr()                    ← 变量写入
0x0909c8   68  writeUserSpecAttr()                    ← 用户自定义写入
```

**Picture Wizard 全套（★ 与 prefman 0x0a3ec 同一套语义的运行时入口）**：

| 地址 | 大小 | 方法 |
|---|---|---|
| 0x094e84 | 132 | `setPWColor` |
| 0x094d10 | 124 | `setPWSaturation` |
| 0x094d8c | 124 | `setPWSharpness` |
| 0x094e08 | 124 | `setPWContrast` |
| 0x096568 | 140 | `setPWBracketParam` |
| 0x0965f4 | 332 | `setPWBracket(unsigned char, unsigned char, unsigned char, unsigned char)` |
| 0x094f8c | 124 | `setWBKelvin` |
| 0x094f08 | 132 | `setWBDetail` |
| 0x095008 | 116 | `setCustomWBGain` |
| 0x092c7c | 36 | `getSmartFilterMode` |
| 0x093000 | 36 | `getColorSpace` |
| 0x092c34 | 36 | `getWhiteBalanceMode` |
| 0x092fb8 | 36 | `getPWBracketParam` |
| 0x092f94 | 36 | `getWBBracketParam` |

其他类：`CMiscHandler`（`onIPCC` = IPCC 版本协商 @0x8ed10）、
`CMCBAdapter`（`setCustomWB` / `setData(T_CUSTOM_WBE,...)`）、
`CNotifyHandler`（`onCustomWBDone`）、`CCaptureController`、`CCapturePublisher`。

### ★ 意义

**这是 PW 参数的运行时写入通路，比 prefman 更底层（prefman 是持久化层，这个是 setusr 那一层）。**
→ 之前用 `capdtm setusr` 猜格式失败，**现在可以直接看 `setPWColor` 的实现**，
   它必然揭示 PW 参数的打包格式和下发报文结构。

**`setPWBracket(u8,u8,u8,u8)` 有 4 个 u8 参数** —— 这可能就是 PW 的 R/G/B/HUE 打包方式。

## 三、已排除 / 关闭的线索

| 线索 | 结果 |
|---|---|
| `libudd5.so.debug` | **不存在**（MISS）。`.gnu_debuglink` 指向的名字是构建期产物，相机上没留 |
| `libcapture-fw-prod.so` 含 3D LUT 符号 | 字符串 3658 个，`3dl`/`d5_ep`/`LUT` **0 命中** |
| `libdi-sensor.so` / `libsensor.so` | 同上，0 命中 |

## 四、下一步（PC 侧，已无需相机）

1. **反汇编 `CAttributeHandler::setPWColor`（132 B）+ `setPWBracket`（332 B）**
   → 直接得到 PW 参数打包格式与 IPCC 报文结构。这是 A 方向路线的收尾。
2. **反汇编 `CAttributeHandler::Run`（276 B）** → 看属性分发的命令表结构
3. **反汇编 `CMiscHandler::onIPCC`（68 B）** → IPCC 协议版本
4. 若要继续追 3D LUT：在 `libcapture-fw-prod.so` 里查 `d5_ep_*` 的 **PLT/relocation**（不是字符串），
   节表剥了但 `DT_JMPREL`/`DT_PLTRELSZ` 还在，可解出它到底 import 了哪些 udd5 符号

## 五、本轮工具产出

- `armplt.py` 增加 `raw` 子命令（解无符号静态函数）—— 本轮用于挖 `0x18324`
- 剥节 .so 的符号表解法：**用 PT_DYNAMIC 拿 DT_STRTAB/DT_SYMTAB，
  用 DT_HASH 的 nchain（+4 偏移）精确得符号数**，不要靠 strsz 猜

## 六、★★★ PW 属性 ID 表定案（`setusr` 一直猜不出来的那个编码）

`CAttributeHandler::setXXX` 的实现模式高度统一：
```c
int CAttributeHandler::setPWColor() {
    if (this->type != 2) return -2;          // [r3,#4] 校验
    short v = (short)atoi(this->pwcolor_str); // 0x258d8 = atoi
    return set_attribute(0x10e, &v, 4);       // 0x284f4 = 通用下发
}
```
**→ 每个 setter 里的 `movw r0, #ID` 就是该属性的 DATA ID。**

| 属性 | ID (hex) | ID (dec) | 备注 |
|---|---|---|---|
| `setWBKelvin` | 0x105 | 261 | K 值 |
| `setWBDetail` | 0x106 | 262 | tint/明细 |
| **`setPWColor`** | **0x10e** | **270** | PW 颜色（R/G/B） |
| `setPWSaturation` | 0x110 | 272 | |
| `setPWSharpness` | 0x111 | 273 | |
| `setPWContrast` | 0x112 | 274 | |

**与已实测的 setusr 编码对照（重大发现）**：
```
setusr 20  → 0x14000N   = PW_TYPE      （0x140000 + N）
setusr 21  → 0x15000N   = SMARTRANGE
setusr 25  → 0x19000N   = FACETONE
setusr 62  → 0x3e000N   = SmartFilter类型
setusr 63  → 0x3f000N   = SmartFilter 强度
setusr 27  → 0x1b000N   = SMARTART
setusr 28  → 0x1c000N   = SMARTART 强度
```
**→ setusr 的 `0x14000N` 形态 = `0x{index}0000 + N` 的基址 +序号。**
**→ 而属性服务端用的是 `0x1xx` 小整数 ID（260–274 区间连续）。**
**两套是不同编码体系：capdtm setusr 是"域+序号"，CAttributeHandler 是"全局属性 ID 连续表"。**
0x105–0x112 连续 ⇒ **这就是 PW 参数在属性总线上的真实 ID 段。**

### PW Bracket 的 13 个 ID
`setPWBracket(u8,u8,u8,u8)` 跳转表（`sub #1 / cmp #0xc` → 索引 1..13）给出连续 ID：
```
0x1b 0x1c 0x1d 0x1e 0x1f 0x20 0x21 0x22 0x23 0x24 0x25
= 十进制 27..39（13 个）
```
**→ 27–39 段是 PW Bracket（包围架/连拍）相关属性。**

## 七、★ 由此可推的实用结论

1. **A 路线（机内 PW）已完全闭环**：prefman 持久化 + CAttributeHandler 运行时下发，两层语义现在对齐了。
2. `setusr` 猜格式失败的原因清楚了：**它走的是 capdtm 自己的 `0xNN000N` 域编码，
   而真实属性 ID 是 `0x105..0x112` 这一段连续小整数**。
3. 下一步若要免重启改PW，可以直接走 `0x105..0x112` 这条属性总线
   （木一已证 `iqr[85]` 的 IPCC 通路能免重启改画面，说明属性总线可热写）。
4. 3D LUT 仍未在这三个库里出现 → 它要么在更下层的 ISP 守护进程，要么通过 `d5_ep_*` 直接调
   （需解 `libcapture-fw-prod.so` 的 `DT_JMPREL`，看它 import 了哪些 udd5 符号）。

## 八、★★★ 定案：capture-fw-prod 不通过符号引用调 3D LUT

`libcapture-fw-prod.so` 的 PLT import共 **1003 个**符号。逐一与本机 `libudd5.so` 的552 符号求交集：

**交集只有 22 个，且全是 libc 基础函数**：
```
__cxa_finalize  __dlog_print  __gmon_start__  close  fprintf  free  ioctl
malloc  memcpy  memset  mmap  munmap  open  printf  pthread_cond_signal
pthread_mutex_{init,lock,unlock}  puts  snprintf  sprintf  strlen
```
**→ 一个 `d5_ep_*` / `_ep_3dl*` 都没有。**
（`3dl`/`_ep_`/`d5_`/`Lut` 关键字在 1003 个 import 里唯一命中的是 `get_d5_sys_timer_utick` —— 无关注入。）

### 结论

**`libcapture-fw-prod.so` 虽然把 `libudd5.so` 映射进地址空间（DT_NEEDED），但不静态引用它的任何 API。**
它调ISP 走的是**运行时注册 / 回调 / ioctl** 机制，而非符号绑定。

**→ 3D LUT 的实际写入者是 ISP 侧的守护进程（DRIMe5 硬件守护），不在用户态 app 层。**
**→ 用户态这一侧（di-camera-app + capture-fw-prod）只能通过属性总线下发"意图"，
   由 ISP 守护进程翻译成 `d5_ep_3dl_*` 调用。**
**→ 所以 3D LUT 的调用者仍在 `/usr/bin` 下某个我们还没拉到的二进制里。**

### 下一步（收敛到 2 个动作）
1. **在相机上扫 `/usr/bin` 下所有可执行文件，找出哪个 import 了 udd5 的 `d5_ep_3dl_*`**
   （相机无 readelf，但可以用 `grep -c` 对二进制做字节串匹配 —— `d5_ep_3dl_load_lut` 是明文符号名）
2. 若无人直接引用 → **调用者在更底层的内核模块或 ISP 固件里**，此时改走
   `/dev/d5_ipcc` + `d5_ep_mc_set_custom_param_yccmixer`（YCC mixer，符号地址已知 0x029488）

## 九、相机端脚本使用记录

```sh
# 推脚本（7598 字节）
python test_server/pwfilter/push_sh.py lut-probe.sh /mnt/mmc/_pwtest/lut-probe.sh 192.168.0.105
# 搬运
B=/opt/usr/nx-ks/busybox; O=/mnt/mmc/_xfer/odd3l; mkdir -p $O
cp /usr/lib/libcapture-fw-prod.so $O/    # 734600
# 拉取
python ftp_get.py --batch odd3l /mnt/mmc/_xfer/odd3l/libcapture-fw-prod.so
```

**注意**：`libudd5.so.debug` 相机上**不存在**（`.gnu_debuglink` 是构建期路径，未随产品发布）。
**相机上也没有 readelf / objdump / nm**，所有 ELF 分析必须在 PC 做。

## 十、★★★ 最终定案：3D LUT 无任何用户态静态调用者

在相机上对 8 个"已确认加载 libudd5"的二进制做明文符号名匹配（`grep -a`）：

| 文件 | d5_ep_3dl | ep_3dlut | yccmixer | ipcc_write |
|---|---|---|---|---|
| `/usr/bin/Xorg` | ✗ | ✗ | ✗ | ✗ |
| `/usr/sbin/wpa_supplicant` | ✗ | ✗ | ✗ | ✗ |
| `/usr/bin/deviced` | ✗ | ✗ | ✗ | ✗ |
| `/usr/bin/enlightenment` | ✗ | ✗ | ✗ | ✗ |
| `.../di-camera-app` | ✗ | ✗ | ✗ | ✗ |
| `.../ap-setting-app` | ✗ | ✗ | ✗ | ✗ |
| `/usr/lib/libcapture-fw-prod.so` | ✗ | ✗ | ✗ | ✗ |
| **`/usr/lib/libudd5.so`** | **✓** | **✓** | **✓** | **✓** |

### 结论（三条独立证据交叉验证）

1. **`libudd5.so` 只是被全局映射，用户态没有任何程序静态引用它的 3D LUT API。**
2. `libcapture-fw-prod.so` 的 1003 个 PLT import 与 libudd5 的 552 符号交集只有 22 个 libc 函数。
3. di-camera-app 4.7MB 全文 30291 字符串对 `3dl`/`d5_ep`/`SetLUT`/`wdxi` 零命中。

### ★ 所以 3D LUT 的写入者是内核侧 / ISP 固件

```
用户态（UI + 属性服务）              内核 / ISP
di-camera-app                IPCC   ┌──────────────────────┐
  → CAttributeHandler                │  DRIMe5 ISP 守护 /  │
  → setPWColor(0x10e)                │  d5_ep_3dl_load_lut │
       ↓                             │  ↓                  │
  属性总线（共享内存/ioctl）────────→ │  3D LUT 寄存器      │
                                     └──────────────────────┘
```
**用户态只能通过属性总线下达"意图"（如"把PW Color 设为 X"），
真正调`d5_ep_3dl_load_lut` 的是内核态/ISP 固件。**
这也解释了为什么 `libudd5.so` 要做成全局预加载——**它是给内核/ISP 侧做符号解析用的。**

### 由此确定的两条可行动路线

**路线 B1（推荐，绕过调用者）**：既然 `d5_ep_3dl_*` 是全局符号，
我们可以**直接从自己的程序里 `dlopen("libudd5.so")` + `dlsym("d5_ep_3dl_load_lut")`**，
自己构造 12 字节结构体调用它。协议已经完全读出（见 `LUT_REGISTERS.md`），剩下的只有表尺寸未知。

**路线 B2（兜底，YCC mixer）**：`_udd_ep_mc_set_custom_param_yccmixer`（0x029488）是
PW 7 维的实际落点，不依赖 3D LUT 机制，是 A 路线的高级形态。

**★ 未知项收敛到 3 个**：LUT 总节点数、每节点字节数/精度、通道序 RGB/BGR。
**这三个只需一次实机实验即可确定**：用 B1 路线写一张已知内容的表（纯红/纯蓝/灰阶梯），
看画面怎么变，反推尺寸与通道序。
