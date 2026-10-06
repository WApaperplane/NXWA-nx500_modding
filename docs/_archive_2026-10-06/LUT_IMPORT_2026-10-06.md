# 导入自定义 3D LUT（.cube）—— 完整方案

> 2026-10-06 ·★ **本文档推翻了我当天下午的结论**：
> 「导入 LUT 必须改 P7」是错的，**用户态可以导入任意 .cube**。
> 中英双语尚未成对（本篇仅中）—— ⚠️ 对外发布前需补 `_EN`。

---

## 0. 一句话

**不需要改固件。** `.cube` 在 PC 上转成 NXKS 二进制，放进 SD 卡，相机菜单里选一下即可。
随时 `restore` 退回出厂。

---

## 1. ★ 为什么不需要改 P7（下午的错判是怎么来的）

我当天下午把 `d5_ep_3dl_load_lut` 理解成"往 `+0x0c` 写一个地址，硬件自己去读那张表"，
并据此认为"那 4 个预置缓冲在 `0x81xxxxxx`，Linux 够不着 ⇒ 必须改 P7"。

**实际有两条独立通路：**

| 通路 | 机制 | 地址限制 |
|---|---|---|
| **A：挂地址**（我 10 次实验做的） | `+0x0c` 写地址，硬件自己去读 | 源地址须硬件可访问 ⇒ `0x81xxxxxx` 对 Linux 不可达 |
| ★★ **B：WDMA 硬件 DMA**（`load_lut` 真正走的） | 数据放**我自己的 CMA 缓冲**，硬件 DMA 搬进 3DLUT 内部 RAM | ★ **只需 `/dev/d5_sma` 可 mmap ⇒ 无限制** |

⇒ ★★ **我一直在测通路 A，而 `load_lut` 走的是通路 B。**
⇒ 所以"够不着"这个结论，从一开始就不适用于导入场景。

### 逆向证据（libudd5 最后一个未解环节，本次解开）
```
d5_ep_3dl_load_lut(buf, sel, lut_type, fmt)
  → d5_ep_sma_virt_to_phys(buf)      ← ★ 拿【调用者自己的 CMA 缓冲】物理地址
  → _udd_ep_3dl_ctrl_ConfigAccessMode(p)
      → sub_3a888 @0x3a888 (688B)     ← ★ 静态函数，无符号名，本次解开
```
`sub_3a888` 还原：
```c
OnOff(1);
Acc_OnOff(0);
Acc_OnOff(1);
switch (p[+0x10]) {                /* sel */
case 0: SetAddress(p[+8]->v,  p[+4]); color_format(sel, p[+8][8]);   break;
case 1: SetAddress(p[+0xc]->v, p[+4]); color_format(sel, p[+0xc][8]); break;
case 2: /* 两张都做 */                              break;
}
SelLUT(sel);
rw_Start(1);            /* ★★★ DMA 搬运在这里触发 */
```
★ `rw_Start(1)` 的真身（`_udd_ep_3dl_reg_rw_Start @0x1fd9c`）：
```c
v = GetReg(base + 8);
if (arg == 1) { v |= 0x100; SetReg(base+8, v); v &= ~0x100; SetReg(base+8, v); }  /* 写 */
else          { v |= 0x010; SetReg(base+8, v); v &= ~0x010; SetReg(base+8, v); }  /* 读 */
```
⇒ **write-1-clear 脉冲**。我实验里的 `+0x008` 脉冲做法其实是对的，只是语义理解错了。

---

## 2. 使用流程

### 第 1 步｜PC 端转换
```bash
cd test_server/filmsim
python cube2nxks.py "Kodak Portra 400.cube" out.nxks.bin
```
| 参数 | 作用 |
|---|---|
| `--size N` | 每通道级数（默认 17；常见 33/65）|
| `--layout hex\|planar` | `hex`= `0xXXXX` 文本（p7 调试用，默认）<br>`planar` = 裸 16-bit 二进制（导入用）|

支持任意 `.cube`（`LUT_3D_SIZE` / `DOMAIN_MIN` / `DOMAIN_MAX` / 注释 / 空行），自动三线性重采样。

### 第 2 步｜放进 SD 卡
FTP 根目录就是 SD 卡 → 传到 `/mnt/mmc/luts/`。

### 第 3 步｜相机端应用
**菜单**：P7 固件 → 色彩方案 → 导入 LUT → 选名字
**或 telnet**：
```bash
sh /opt/usr/nx-ks/lut_scan.sh                    # 列出所有
sh /opt/usr/nx-ks/lut_scan.sh apply<名字># 应用
/opt/usr/nx-ks/lutload.arm restore                # ★ 随时退回出厂
/opt/usr/nx-ks/lutload.arm read                   # 只读回寄存器
```

---

## 3. 交付文件

| 文件 | 作用 |
|---|---|
| `test_server/filmsim/cube2nxks.py` | .cube → NXKS 二进制转换器 |
| `test_server/sysarch/lutload.c` → **`lutload.arm`** (822KB) | ★ 导入器：`import` / `preset 0-3` / `restore` / `read` |
| `scripts/nx-rc/lut_scan.sh` | 扫库 + 动态生成菜单页（上限 22 项）|
| `scripts/nx-rc/lut_pick.sh` | 应用选中的 LUT |
| `scripts/nx-rc/lut_help.sh` | 相机端图文说明（`cat` 可读）|
| `scripts/nx-rc/gui_lutimport.NX500` | 导入子菜单 |

---

## 4. 已验证 / 未验证

### ★★ 已验证（对照组自证）
| 项 | 结果 |
|---|---|
| 转换器数学正确 | identity `.cube` 转换后**偏离 0**（PASS）|
| 转换器能出色彩偏移 | Portra 400 中灰偏离 **+8384**（偏暖，符合胶片特性）|
| 6 个 Kodak LUT 批量转换 | 全部成功，29478 B/个 |
| 交叉编译 | `-O0` 零警告；与已验证的 `eplut10.arm` 反汇编覆盖率一致（3.0% / 1069 vs 1073）⇒ **无非法指令** |
| ioctl 号 | `_IOR('h',100,80) = 0x80506864` —— ★ **与 NX1 官方头文件算出的值一致**（双向验证）|
| EP 结构体 | ★ 官方 `d5_ep_type.h`：`ep_reg_info` **恰好 10 块**，`reg_base_3dlut` = index 8，字段是 `unsigned int` |

### ★★ 未验证（必须实机，按优先级）
| # | 项 | 影响 |
|---|---|---|
| 1 | **CMA 落脚地址 `0x60000000` 是否合法**（我硬编码）| mmap 失败 ⇒ 需先探测可用地址 |
| 2 | **`SelCbCr_ch`(bits[1:0]) / `SelLUT`(bits[5:4]) 取值** | ★ **直接决定 LUT 有无效果** |
| 3 | **LUT 是 8-bit 还是 16-bit** | 决定文件长度（4913 vs 29478 B）|

### ★★ 实机判据（★ 第一试请跑 identity LUT）
| 现象 | 结论 |
|---|---|
| 画面与未挂 LUT 时**相同** | ★ **通路已通**（identity 数学上不改颜色，最干净的判据）|
| 花屏 | 格式错（8/16-bit 判定错），不是通路错 |
| 画面变了但颜色不对 | `SelCbCr_ch` / `SelLUT` 字段错 |

⇒ ★ **先跑 identity**，它把"通路对不对"和"数据对不对"两个变量分开。

---

## 5. ★ 仍需改 P7 的唯一理由（范围已收窄）

| 能力 | 能否用户态做 |
|---|---|
| 导入任意 `.cube`（含 tone curve）| ★★ **能**（本文档）|
| 4 档内置色彩切换 | ★ **能**（已实测）|
| PW 7 维 / K 值 / 色调两轴 | ★ **能**（已实机）|
| ~~改 ISP 生成 LUT 的算法~~ | ★ 需改 P7 —— 但**这已不是"导入 LUT"问题** |

⇒ ★★ **"魔灯必须改 P7"这个结论现在只剩一种情形成立：要动 ISP 的 LUT 生成算法，
而不是"把一张表搬进硬件"。**

---

## 6. 教训

★★★★ **"够不着"这个结论，必须问"够不着的是哪一条通路"。**
同一个硬件块有"挂地址"和"DMA 搬运"两条完全不同的通路，只测了一条就下全局结论，
会直接导致"改固件"这种高成本决策的错误。

★ 呼应铁律：**排除性判据在"另一条通路未测"时给假阴性。**
⇒ 新增判据规则：**同一硬件块，先枚举所有可能的访问通路，再谈"能不能"。**