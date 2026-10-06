# 3D LUT 逆向进展（2026-10-04 12:00–12:20，PC 静态分析）

> 工具：`test_server/pwfilter/dis3dl4.py`（ARM 模式反汇编器，capstone 已装到 `test_server/pwfilter/`）
> 目标文件：`libudd5.so`（320216 B，`.text` 0x91c0–0x49c00，**全部纯 ARM 模式，无 Thumb 混排**）

## 一、修正旧结论：不是"一个 load 函数"，是完整寄存器级 API 家族

此前只记了`d5_ep_3dl_load_lut` 一个符号。实际 libudd5 里**3D LUT 相关符号共 51 个**，未剥离全部可读。

### 核心 9 个（按调用层次）

| 地址 | 大小 | 符号 | 作用 |
|---|---|---|---|
| 0x00013c2c | 228 | `d5_ep_3dlut_op_init` | 顶层初始化，校验参数 |
| 0x00013d10 | 260 | `d5_ep_3dl_load_lut` | **包装器**：构造 12B 结构体 → 调 ConfigAccessMode |
| 0x00013e14 | 276 | `d5_ep_3dl_save_lut` | **包装器**：同结构体，mode=2 |
| 0x00017508 | 40 | `_udd_ep_3dl_reg_GetReg` | 读寄存器 |
| 0x00017530 | 44 | `_udd_ep_3dl_reg_SetReg` | 写寄存器 |
| 0x0001755c | 136 | `_udd_ep_3dl_reg_OnOff` | 总开关 |
| 0x000175e4 | 132 | `_udd_ep_3dl_reg_SelCbCr_ch` | **选Cb/Cr 通道**（→三通道独立 LUT 的证据） |
| 0x00017668 | 132 | `_udd_ep_3dl_reg_SelLUT` | 选 LUT（→ 存在 LUT0/LUT1 两张） |
| 0x000176ec | 132 | `_udd_ep_3dl_reg_SetColorFormat_LUT0` | **LUT0 色彩格式**（独立于 LUT1） |
| 0x00017770 | 132 | `_udd_ep_3dl_reg_SetColorFormat_LUT1` | **LUT1 色彩格式** |
| 0x000177f4 | 144 | `_udd_ep_3dl_reg_Acc_OnOff` | 访问开关 |
| 0x00017884 | 264 | `_udd_ep_3dl_reg_rw_Start` | **读写启动**（真正搬运数据的入口） |
| 0x0001798c | 140 | `_udd_ep_3dl_reg_SetAddress` | **设表地址** |
| 0x0001863c | 40 | `_udd_ep_3dl_ctrl_ConfigBypassMode` | 旁路（可关） |
| 0x00018664 | 84 | `_udd_ep_3dl_ctrl_ConfigAccessMode` | **访问模式分发** |
| 0x000186b8 | 116 | `_udd_ep_3dl_ctrl_ConfigProcessMode` | 处理模式 |
| 0x00034940 | 1624 | `_udd_ep_mux_3dlut_rdxi` | **MUX 读通道**（1.6KB，最大） |
| 0x00038560 | 1032 | `_udd_ep_mux_3dlut_wdxi` | **MUX 写通道** |
| 0x0003bb94 | 140 | `_udd_ep_demux_3dlut_rdxi` | DEMUX 读 |
| 0x0003c114 | 288 | `_udd_ep_demux_3dlut_wdxi` | DEMUX 写 |
| 0x00057728 | 4 | `ep_ldc_reg_base` (OBJ) | LDC 寄存器基址 |
| 0x00057730 | 4 | `ep_3dlut_reg_base` (OBJ) | **3D LUT 寄存器基址** |

> `d5_ep_3dl_load_lut` 字符串表里还有 `Error : invalid ldc-lut's buffer` → LDC（镜头畸变）也共用同一套 LUT 机制。

## 二、★核心突破：调用协议已完全读出，格式不用猜

`d5_ep_3dl_load_lut(handle, index, lut_type, arg3)` 反汇编逐条：

```
if (handle == 0)        return -1;         // 必须非空
if (index > 2)return -1;         // index ∈ {0,1,2}
if (lut_type != 0 && lut_type != 1) return -1;  // 仅 {0,1}

// 构造 12 字节结构体（栈上 fp-0x30 .. fp-0x20）
struct { u32 f30; u32 f2c; u32 f20; u32 handle; u32 lut_type; u32 index; }
   f30 = 1        // mode = 1  = LOAD
   f2c = 1
   f20 = index
   [ptr+0x04] = handle
   [ptr+0x08] = lut_type
   [ptr+0x0C] = index
return _udd_ep_3dl_ctrl_ConfigAccessMode(&st);
```

`d5_ep_3dl_save_lut` 结构体**完全相同，只有一个差异**：`f30 = 1` → `f30 = 2`。

`_udd_ep_3dl_ctrl_ConfigAccessMode(struct*)`：

```
switch (p[0x04]handle_or_mode) {
  case 1: _0x1838c(p);   // 写表路径
  case 2: _0x184e4(p);   // 读表路径
  default: return 0;
}
```

**→ 关键推论：`load_lut` / `save_lut` 不解析任何文件格式。** 它们接受一个**已由调用者填好的表结构指针**，只负责往寄存器灌 / 从寄存器读。
所以"LUT 文件格式"这个谜题**不是三星私有格式**，而是 `save_lut` 序列化的产物 —— 只要我们自造结构体直接送进 `ConfigAccessMode`，就可以完全绕开文件格式。

## 三、结构体布局（三函数交叉验证）

| 偏移 | `op_init` | `load_lut` | `save_lut` | 判定 |
|---|---|---|---|---|
| +0x00 | 0 或 1 | mode=1 | mode=2 | **模式：1=写/0=读** |
| +0x04 | — | handle | handle | handle |
| +0x08 | ≤2 | lut_type | lut_type | **0/1 = LUT0 / LUT1** |
| +0x0C | ==1 | index | index | 通道/表索引 |
| +0x10 | 2 | index | index | index 副本 |

`op_init` 校验：`[0]==0||[0]==1`、`[8]<=2`、`[0xC]==1`、`[0x10]==2`。

## 四、★ 硬边界（决定下一步拉什么）

`_0x1838c` / `_0x184e4` 两条路径**指令逐条几乎相同**（0x1838c–0x184d4 与 0x184e4–0x1850c 是两份拷贝），差别只在 `ConfigProcessMode` 分支。
函数体全是**指针追逐**（`[r3+8]` / `[r3+0xc]` 三级解引用），**没有任何立即数**表示 LUT 尺寸。

**结论：真正持有 LUT 数据缓冲区的结构体定义在 libudd5 之外/内部静态区，挖 libudd5 挖不出来。**
`load_lut` 传进来的 `arg3`（r3，第4 参数）**完全没被使用** —— 说明表缓冲区不是通过它传的，而是通过 handle 关联的全局状态。

## 五、★ 由此确定的 FTP 拉取清单（按性价比排序）

| # | 拉什么 | 为什么 | 大小 | 优先级 |
|---|---|---|---|---|
| **1** | **`libudd5.so.debug`** | `.gnu_debuglink` 节明确指向这个名字（0x4ddc7）→ **带完整调试符号/结构体定义**。这是唯一能直接读出 LUT 结构体定义的路径 | 未知 | ★★★ |
| **2** | `libudd5.so` 的 `.data`(0x4c8e0, 0x14ac) + `.bss`(0x4dd8c, 0x19fc) 原始字节 | 运行时可能存着**出厂默认 LUT 表**或表尺寸常量 | 12KB | ★★★ |
| **3** | 谁调用 `d5_ep_3dl_load_lut` / 谁调`_udd_ep_3dl_reg_SetAddress` | 找**现成.LUT/.cube 加载路径**和表的真实尺寸 | — | ★★★ |
| **4** | `/dev/d5_ipcc` 寄存器映射（`ep_3dlut_reg_base` 运行时值） | 确认 LUT 物理基址+ 尺寸反推 | — | ★★ |
| **5** | `/usr/apps/com.samsung.di-camera-app/lib/` 下全部 .so | 真正构造 LUT 结构体的地方大概在这里 | 数MB | ★★ |
| **6** | `/usr/lib/` 下 `lib*d5*.so` / `lib*ipcc*.so` / `lib*hal*.so` | 可能是更上层的封装 | 数 MB | ★★ |
| **7** | SD 卡与 eMMC 上 `*.cube` / `*.lut` / `*.3dl` 全盘 find | 若相机出厂自带 LUT，直接白给格式 | — | ★★ |
| **8** | `/dev/d5_ipcc` 与 `libudd5` 的 `ipcc_read_pkt` 对应表结构 dump | 木一已证 `iqr[85]` 免重启通路 → 同一层 | — | ★ |
| **9** | `libSLP-db-util.so` 的 SQLite 库文件 | 排除法：确认相机是否存 LUT 配置 | 小 | ★ |

### 拉取命令（FTP 已在听 21 端口，root 空密码，根 = SD 卡）

```sh
# 系统文件先搬到 SD，FTP 根是 SD 卡
/opt/usr/nx-ks/busybox cp /usr/lib/libudd5.so.debug /mnt/mmc/_xfer/ 2>/dev/null
/opt/usr/nx-ks/busybox find / -name '*.cube' -o -name '*.lut' -o -name '*3dl*' > /mnt/mmc/_xfer/find_lut.txt
/opt/usr/nx-ks/busybox find /usr/apps/com.samsung.di-camera-app -name '*.so' > /mnt/mmc/_xfer/find_so.txt
/opt/usr/nx-ks/busybox cat /proc/self/maps > /mnt/mmc/_xfer/maps.txt
```
PC 侧用 `test_server/pwfilter/ftp_get.py` 拉（`_` 开头目录要 `cwd('/_xfer')`）。

## 六、已排除的猜测

- ❌ "LUT 文件格式是 33³/17³ RGBA" —— 本机不解析文件，见第二节。**DNG 的 3D LUT spec 只能当参考，不能当格式。**
- ❌ "从 load_lut 长度反推尺寸" —— 它是纯包装器，没有长度参数。
- ❌ "load_lut 的第 4 参数是缓冲区" —— 反汇编证明 `arg3` 完全未使用。
- ⚠️ libudd5 是**纯 ARM 模式**。用 Thumb 模式反汇编会得到垃圾（`0x2d 0xe9` push 被误当`.byte`）。已记入方法论。

## 七、★ 已完成的调用者定位（今天下午，无需相机）

**`di-camera-app` 4.7MB 全文扫描结果：30291 个字符串，`3dl` / `3DL` / `d5_ep` / `_ep_` / `SetLUT` / `ColorFormat` / `LUT0` / `LUT1` / `SelCbCr` / `wdxi` / `rdxi` 全部 0 命中。**
唯一 ipcc 相关符号只有两个：`dfms_start_ipcc` / `dfms_stop_ipcc`。

**→ 结论：3D LUT 的调用者不是 di-camera-app。**
→ 与此前发现一致：相机设置的真实通路藏在独立 ISP 守护进程里（`libSLP-db-util` 是同类的"隐藏层"，SQLite 但与相机设置无关）。
→ **di-camera-app 只是 UI 层**：符号表里有完整的 `CAPPGUIGadgetPWState` / `SetPWNaviList` / `03_WB_AWB_G` 状态机，即 Picture Wizard 的界面框架，但调下去走的是 IPCC 报文，不是直接调 3D LUT。

### 由此锁定的唯一未知：谁 loadlibudd5

`dlopen` / `dlsym` 是找到它的最快路径 —— 相机上跑：
```sh
for p in /proc/[0-9]*; do
  pid=$(basename $p)
  exe=$(readlink $p/exe 2>/dev/null)
  # libudd5 已加载？
  grep -l libudd5 $p/maps >/dev/null 2>&1 && echo "$pid $exe"
done
```
**这条 telnet 命令就够了，不用 FTP**（输出很小）。谁加载了 libudd5，就是谁在管3D LUT。

## 八、下一步

| 步骤 | 需要什么 | 是否要FTP | 状态 |
|---|---|---|---|
| 1. 反汇编 `_udd_ep_mux_3dlut_wdxi`（1032B）找尺寸/步进常量 | PC 已有 libudd5 | **否** | 待做 |
| 2. 谁 load 了 libudd5（`/proc/*/maps` 扫一遍） | 相机 | **否**（telnet 小输出） | 待做 |
| 3. 拉那个守护进程的 .so | 相机 | **是** | 待定，取决于 2 |
| 4. `libudd5.so.debug` | 相机 | **是** | 待做 |
| 5. `find / -name '*.cube' -o -name '*.lut'` | 相机 | **是** | 待做 |
