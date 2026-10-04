# NX500 ISP 全能力清单 + 为什么 PW 之外没有别的（2026-10-04 14:30 定案）

## 一、libudd5 顶层 API 全清单（122 个 d5_ep_*）

| 模块 | 数量 | 代表函数 | 与画质关系 |
|---|---|---|---|
| `d5_ep_top_*` | 41 | `top_udd_open` / `top_clock_onoff` / `top_set_wdma_ctrl` | **时钟、DMA、中断**（非色彩） |
| `d5_ep_srsz_*` | 18 | `srsz_op_init` / `srsz_calc_ringpixel` | 缩放器 |
| `d5_ep_mc_*` | 14 | `set_path` / `registration_*` / `set_tnr_*` / `set_custom_param_yccmixer` | **MC 主控** |
| `d5_ep_lvr_*` | 10 | `lvr_set_rotation` / `lvr_set_flip` | **LIVR 旋转/翻转** |
| `d5_ep_ldc_*` | 6 | `ldc_calc_ldc_lut` | 镜头畸变校正 |
| `d5_ep_3dl*` | 3 | `3dlut_op_init` / `3dl_load_lut` / `3dl_save_lut` | **3D LUT** |
| `d5_ep_nog_*` | 2 | `nog_set_noisegen` / `nog_set_bypass` | **噪声/颗粒** |
| 其他 | 27 | `bitb_*` / `fd_*` / `jpeg_*` / `sma_*` / `ep_open` / `ep_close` | 位块/JPEG 编解码/地址转换 |

### ★ 122 个顶层 API 里，**直接控制画面的只有 8 个**
```
0x0105f0240  d5_ep_nog_set_noisegen              ← 颗粒
0x013c2c  228  d5_ep_3dlut_op_init              ← 3D LUT 初始化
0x013d10  260  d5_ep_3dl_load_lut               ← 3D LUT 加载
0x013e14  276  d5_ep_3dl_save_lut               ← 3D LUT 保存
0x029344  160  d5_ep_mc_set_tnr_frame           ← 时域降噪帧
0x0293e4  164  d5_ep_mc_set_tnr_bypass          ← 时域降噪开关
0x029488  288  d5_ep_mc_set_custom_param_yccmixer  ← PW 7 维落点
0x02b660   68  d5_ep_ldc_calc_ldc_lut           ← 镜头畸变表
```
**其余 114 个全是时钟 / DMA / 中断 / 缩放 / 位块 / JPEG 编解码等基础设施。**

### ★ 意外发现（之前没注意的模块）
| 模块 | 函数 | 意义 |
|---|---|---|
| **MC registration** | `d5_ep_mc_registration_init/param/set/get` (5个) | 镜头畸变/色散校正配准 |
| **TNR** | `d5_ep_mc_set_tnr_frame` / `set_tnr_bypass` | **时域降噪**（多帧合成） |
| **LIVR** | `d5_ep_lvr_set_rotation_angle` / `set_flip` | Liveview 旋转/翻转 |
| **BITB** | `d5_ep_bitb_block_copy` / `format_convert` | 位块搬运与格式转换 |
| **FD** | `d5_ep_fd_op_init` / `change_inbuf` / `change_outbuf` | 帧描述符缓冲 |
| **JPEG** | `d5_ep_jpeg_encoder` / `decoder` (1036B) | 硬件 JPEG 编解码 |
| **d5_ep_open/close** | `d5_ep_open` → `d5_udd_open` → `/dev/d5_ipcc` | **设备打开入口** |

## 二、★ 为什么 PW 之外没有别的（决定性证据）

### 证据 1：libudd5 内部零交叉引用
全库 552 个函数逐条反汇编，找谁 `bl` 了这些 API：

```
d5_ep_3dlut_op_init                    <- ★ 无内部调用者
d5_ep_3dl_load_lut                     <- ★ 无内部调用者
_udd_ep_3dl_reg_SelLUT                 <- ★ 无内部调用者
_udd_ep_3dl_ctrl_ConfigProcessMode     <- ★ 无内部调用者
d5_ep_mc_set_custom_param_yccmixer     <- ★ 无内部调用者
_udd_ep_nog_set_std_sigma              <- ★ 无内部调用者
```
**这些 API 在库内部一次都没被调用** → 它们是导出给外部（内核态 / ISP 固件 / DRM 驱动）用的。

### 证据 2：8 个加载 libudd5 的用户态二进制全部零命中
`Xorg` / `wpa_supplicant` / `deviced` / `enlightenment` / `di-camera-app` / `ap-setting-app` /
`libcapture-fw-prod.so` / `libudd5.so` 本身 —— 只有 libudd5 自己含这些符号名。

### 证据 3：`d5_ep_open` 的返回值不是 handle
```asm
d5_ep_open:
    d5_udd_open(...)          ; 打开 /dev/d5_ipcc
    cmp r3, #1 / #2 / #0      ; 判状态
    mvn r3, #0x63             ; 返回 -99
    mvn r3, #0                ; 返回 -1
```
**返回 0/-1/-2/-99 状态码，不返回句柄。** 说明 handle 由更上层（内核）持有。

## 三、★ 结论：机内能做到什么，不能做到什么

### ✅ 能做（已验证）
| 能力 | 通路 | 上限 |
|---|---|---|
| PW 7 维 | `prefman set` + `setusr 20` | 逐像素同值全局向量 |
| WB K + tint 双轴 | `prefman 0x0a394` / `0x0a3bc` | Kelvin 2500-10000 + A/B |
| SmartFilter 14 种 + 强度 | `setusr 62` / `63` | 厂商预设 |
| 高光降噪 | `setusr 121` GOLFREVERSE | 开关/档位 |
| 3 个自定义槽轮换 | `prefman slot 9/10/11` | 槽位限制 |
| **实时生效（零重启零 eMMC）** | 已验证 | — |

### ❌ 不能做（架构性封闭，不是没挖到）
| 能力 | 为什么不能 |
|---|---|
| **3D LUT（真曲线）** | handle 在内核，4 次尝试全 SIGSEGV |
| **硬件颗粒** | `.bss` 指针数组由内核填充 |
| **时域降噪参数** | TNR API 无用户态调用者 |
| **镜头畸变自定义** | LDC 表由内核算 |
| **Liveview 旋转/翻转** | LIVR API 无用户态调用者 |

**★ 一句话：NX500 的 ISP 色彩/画质能力，用户态只能"选预设 + 改 7 个标量"，
   任何"真曲线 / 真颗粒 / 降噪参数"都在内核态，用户态碰不到。**

## 四、这对"要不要做模组"的答案

如果期待"机内找到 PW 之外的调节空间"：
**这个空间不存在。** 122 个顶层 API 里能控制画面的只有 8 个，全部指向内核对象。

**如果期待"模组能带来 PW 原生做不到的东西"**：
能拿到的只有三样：
1. **recipe 库管理**（8→N 个配方、参数编辑、导入导出）—— 机身只有 3 个自定义槽
2. **组合空间**（PW 7 维 × SmartFilter 14 种 × 高光降噪 = 机身 UI 无法穷举的组合）
3. **PC 端 RAW 域出片**（真曲线、真颗粒 —— 机内物理上做不到）

**★ 但这三样里，只有第 3 样是"机身做不到"的。**
前两样本质是"管理机身已有的能力"，Recipe Lab 已经证明这条路能做到什么水平。
