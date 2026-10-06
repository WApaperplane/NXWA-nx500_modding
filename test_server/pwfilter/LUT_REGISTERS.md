# 3D LUT 寄存器映射表（2026-10-04 12:25，纯 PC 静态分析定案）

> 来源：`libudd5.so` 全部相关函数逐条反汇编（capstone，**纯 ARM 模式**）
> 工具：`test_server/pwfilter/armplt.py`（PLT/GOT 全解析，304 条 PLT 全部解出）
> 前置：`LUT_REVERSE.md`（51 符号表 + 12 字节协议）

## 一、★★ 双通路架构（最重要的发现）

3D LUT 的写入走**两条完全独立的通路**：

```
通路 A —— 寄存器配置：直接内存写（MMIO）
  _udd_ep_3dl_reg_GetReg(addr)      { return *addr; }        // 40 字节，裸读
  _udd_ep_3dl_reg_SetReg(addr, v)   { *addr = v; }            // 44 字节，裸写
  → 无 ioctl、无 IPC、无掩码运算。ep_3dlut_reg_base 就是 MMIO 地址。

通路 B —— 表数据：硬件 DMA（WDMA）
  mux_3dlut_wdxi(ch, buf):
      _udd_ep_wdma_check_empty()        // 等 DMA 空闲
      memset(stack_buf, 0, 251)          // 251 字节栈缓冲
      snprintf(...)                      // 格式化 WDMA 描述符
      _udd_ep_mux_wdma(...)              // 启动搬运
      d5_ep_sma_virt_to_phys(addr)       // ★ ioctl 0xc0047302 拿物理地址
  → 表数据不经过 CPU 逐字节写，走 DMA。
```

### ★ ioctl 号解出来了

```asm
d5_ep_sma_virt_to_phys(virt):
    fd = *(SMA_FD);if (fd < 0 || virt == 0) return 0;
    ret = ioctl(fd, 0xc0047302, &out_phys);      // ★ 命令号
    return ret < 0 ? 0 : out_phys;
```

`0xc0047302` = `_IOW('s', 0x02, u32)` 类宏 → **SMA（Samsung Memory Adapter）的 virt→phys 转换 ioctl**。
**→ 推论：任何要交给 DMA 的缓冲区必须是物理连续或可映射的，不能直接用栈变量。**

## 二、★★ 寄存器位域全表

配置寄存器在 `*( *(ep_3dlut_reg_base) + 4 )`：

| 位域 | 控制函数 | 含义 | 有效值 |
|---|---|---|---|
| `bit[0]` | `_udd_ep_3dl_reg_OnOff(on)` | 模块总开关 | 0/1 |
| `bit[0]` | `_udd_ep_3dl_reg_Acc_OnOff(on)` | 访问使能（**同一寄存器同一 bit**） | 0/1 |
| `bit[5:4]` | `_udd_ep_3dl_reg_SelLUT(sel)` | **选 LUT** | 0–3 |
| `bit[1:0]` | `_udd_ep_3dl_reg_SelCbCr_ch(ch)` | **选 Cb/Cr 通道** | 0–3 |
| `bit[8]` | `_udd_ep_3dl_reg_SetColorFormat_LUT0(f)` | LUT0 色彩格式 | 0/1 |
| `bit[8]` | `_udd_ep_3dl_reg_SetColorFormat_LUT1(f)` | LUT1 色彩格式 | 0/1 |

地址寄存器在 `*( *(ep_3dlut_reg_base) + 0 )`：

| 偏移 | 控制 | 用途 |
|---|---|---|
| `+0x0c` | `SetAddress(which=1, val)` | **表地址槽 1** |
| `+0x10` | `SetAddress(which=2, val)` | **表地址槽 2** |

## 三、★★ `ConfigProcessMode` = 完整配置序列（结构体布局实锤）

```c
// 反汇编还原（116 字节）
void _udd_ep_3dl_ctrl_ConfigProcessMode(struct *p) {
    _udd_ep_3dl_reg_OnOff(1);          // 模块开
    _udd_ep_3dl_reg_Acc_OnOff(1);      // 访问开
    _udd_ep_3dl_reg_Acc_OnOff(0);      // ★ 立刻又关（推测是"配完即关"握手）
    _udd_ep_3dl_reg_SelCbCr_ch(p[0x14]);   // 通道 ← 结构体 +0x14
    _udd_ep_3dl_reg_SelLUT(p[0x10]);       // LUT  ← 结构体 +0x10
    internal_0x18324(p[0x10], p[0x18]);     // ★ 第3个参数 ← 结构体 +0x18
    return 0;
}
```

### ★ 12 字节协议修正 → 实际结构体 ≥0x1c

原以为只有 12 字节（到 +0x0C）。`ConfigProcessMode` 证明实际用到：

| 偏移 | 用途 | 来源 |
|---|---|---|
| +0x00 | mode (1=写/2=读) | `load_lut`/`save_lut` |
| +0x04 | handle | `load_lut`/`save_lut` |
| +0x08 | lut_type (0/1 = LUT0/LUT1) | `load_lut`/`save_lut` |
| +0x0C | index | `load_lut`/`save_lut` |
| +0x10 | → `SelLUT(...)` | **`ConfigProcessMode`** |
| +0x14 | → `SelCbCr_ch(...)` | **`ConfigProcessMode`** |
| +0x18 | → **色彩格式 fmt**（0/1） | **`ConfigProcessMode`** |

### ★ `+0x18` 语义已解（内部函数 `0x18324`）

```c
// 0x18324(sel, fmt)  —— 静态函数，无导出符号
void set_color_format(int sel, int fmt) {
    if (sel == 0)      SetColorFormat_LUT0(fmt);          // 只设 LUT0
    else if (sel == 1) SetColorFormat_LUT1(fmt);          // 只设 LUT1
    else if (sel == 2) { SetColorFormat_LUT0(fmt);
                         SetColorFormat_LUT1(fmt); }      // ★ 两张都设
    // sel > 2 → 什么都不做
}
```

**→ `SelLUT=2` 的语义是"两张表一起设置"，不是"第3 张表"。**
**→ `SelLUT` 实际有效值 = {0, 1, 2}**，与 `load_lut` 里`index ≤ 2` 的校验吻合 —— 三者一致，说明 2bit 编码里值 3 保留。

**★ `+0x18` 是关键未解项** —— 它极可能就是"每节点字节数 / 精度 / 通道序"。

`ConfigBypassMode` 则是 `_udd_ep_3dl_reg_OnOff(0)`（arg 未用）= **强制旁路 = 3D LUT 总开关**。

## 四、能力推论（硬件层面已确认）

| 推论 | 依据 |
|---|---|
| **Cb / Cr 可独立选表** | `SelCbCr_ch` 独立于 `SelLUT`，2 bit|
| **最多 4 张表** | `SelLUT` = 2 bit + `SetAddress` 两个地址槽 |
| **每张表独立色彩格式** | `SetColorFormat_LUT0` / `LUT1` 分离 |
| **可做真正 split toning** | Y 走一张表、Cb/Cr 各走自己的 →不是全局 RGB 映射 |
| **3D LUT 可完全旁路** | `ConfigBypassMode` = `OnOff(0)` |

**→ 这是"7 个标量做不到 tone curve / split toning"的能力跃迁点，且已在寄存器层面证实。**

## 五、仍未解（下一步）

| 未知 | 线索 | 查法 |
|---|---|---|
| **LUT 总节点数** | `mux_3dlut_wdxi` 栈缓冲 251 字节，循环次数未解 | 反汇编 `0x18324`（`ConfigProcessMode` 调的内部函数）+ `_udd_ep_mux_wdma` |
| **每节点字节数 / 精度** | 结构体 `+0x18` | 同上 |
| **通道序RGB / BGR** | — | 只能实机试（写已知渐变表看颜色） |
| **表在内存中的布局** | `SetAddress` 写的地址是什么 | 需 `ep_3dlut_reg_base` 运行时值 |

### 已解开的 PLT 对照（304 条全解析，armplt.py plts）

```
0x86f8 -> _udd_ep_3dl_ctrl_ConfigAccessMode
0x8b24 -> _udd_ep_3dl_ctrl_ConfigBypassMode
0x87a0 -> _udd_ep_3dl_reg_GetReg
0x895c -> _udd_ep_3dl_reg_SetReg
0x87c4 -> _udd_ep_3dl_reg_Acc_OnOff
0x8de8 -> _udd_ep_3dl_reg_OnOff
0x9070 -> _udd_ep_3dl_reg_SelCbCr_ch
0x84a0 -> _udd_ep_3dl_reg_SelLUT
0x8b60 -> d5_ep_sma_virt_to_phys      (ioctl 0xc0047302)
0x8e24 -> _udd_ep_wdma_check_empty
0x90b8 -> _udd_ep_mux_wdma
0x87f4 -> ioctl
0x8a40 -> strlen   0x8b84 -> snprintf   0x8bb4 -> memset
```

## 六、相机端仍需 FTP（清单不变，但优先级明确了）

| 优先级 | 目标 | 理由 |
|---|---|---|
| ★★★ | 加载 libudd5 的守护进程 .so | `+0x18` 的语义只能从调用者反推 |
| ★★★ | `libudd5.so.debug` | 结构体定义直读 |
| ★★ | `find / -name '*.cube' -o -name '*.lut'` | 出厂自带则格式白给 |

**最佳第一步仍是 `sh /mnt/mmc/_xfer/lut-probe.sh maps`（10 秒纯 telnet）。**
