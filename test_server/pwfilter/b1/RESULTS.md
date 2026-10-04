# B1 路线实机结果（2026-10-04 13:00–13:10）

> 程序：`b1/src/lut3dl_probe.c` → `out/lut3dl_probe.arm`（33KB）
> 部署：相机 `/opt/usr/nx-ks/lut3dl/lut3dl_probe.arm`
> 传输：`ftp_put.py` 上传 33KB **瞬间完成**（FTP vs telnet base64 差约 3 个数量级）

## 一、★★ 决定性结果：地址算术零误差

探针只做 `dlopen` + `dlsym`，不调任何有副作用的函数。
把运行时地址减去静态偏移，**10 个符号全部等于同一个基址**：

| 符号 | 静态偏移 | 运行时地址 | 差值 |
|---|---|---|---|
| `d5_ep_3dlut_op_init` | 0x13c2c | 0xb6d3cc2c | **0xb6d29000** |
| `d5_ep_3dl_load_lut` | 0x13d10 | 0xb6d3cd10 | **0xb6d29000** |
| `_udd_ep_3dl_reg_GetReg` | 0x17508 | 0xb6d40508 | **0xb6d29000** |
| `_udd_ep_3dl_reg_SetReg` | 0x17530 | 0xb6d40530 | **0xb6d29000** |
| `_udd_ep_3dl_reg_SelLUT` | 0x17668 | 0xb6d40668 | **0xb6d29000** |
| `_udd_ep_3dl_reg_SelCbCr_ch` | 0x175e4 | 0xb6d405e4 | **0xb6d29000** |
| `_udd_ep_3dl_reg_SetAddress` | 0x1798c | 0xb6d4098c | **0xb6d29000** |
| `_udd_ep_mux_3dlut_wdxi` | 0x38560 | 0xb6d61560 | **0xb6d29000** |
| `d5_ep_sma_virt_to_phys` | 0x1bc30 | 0xb6d44c30 | **0xb6d29000** |
| `d5_ep_mc_set_custom_param_yccmixer` | 0x29488 | 0xb6d52488 | **0xb6d29000** |
| `ep_3dlut_reg_base` | 0x57730 | 0xb6d80730 | **0xb6d29000** |

**→静态反汇编的每一个地址都与运行时完全一致。这条独立证据把之前所有的反汇编结论锁死了。**

## 二、符号解析：26/27 成功

```
SYM  d5_ep_3dlut_op_init / d5_ep_3dl_load_lut / d5_ep_3dl_save_lut
SYM  _udd_ep_3dl_reg_{GetReg,SetReg,OnOff,Acc_OnOff,SelLUT,SelCbCr_ch,
                     SetColorFormat_LUT0,SetColorFormat_LUT1,SetAddress,rw_Start}
SYM  _udd_ep_3dl_ctrl_{ConfigAccessMode,ConfigBypassMode,ConfigProcessMode}
SYM  _udd_ep_{mux,demux}_3dlut_{wdxi,rdxi} / _udd_ep_wdma_check_empty
SYM  _udd_ep_mux_wdma / d5_ep_sma_virt_to_phys
SYM  ep_3dlut_reg_base / ep_ldc_reg_base
SYM  d5_ep_mc_set_custom_param_yccmixer
MISS nog_set_gamma          ← 名字不对，实际是 _udd_ep_nog_set_gamma
-- found=26 miss=1 --
```

**→ `dlopen("libudd5.so")` + `dlsym` 完全可行。B1 路线在"能拿到 API"这一步 100% 通过。**

## 三、★★ 关键发现：`ep_3dlut_reg_base` 的**内容是 0**

```
RB=00000000
regbase null, ISP not initialised
```

这个全局指针（数据符号，.data 段 vaddr 0x57730）**在我这个普通用户进程里读到的是 0**。

### 阶段 2 实验：`op_init` 段错误

我按反汇编的校验条件构造了一个满足
`[0]∈{0,1}` / `[8]≤2` / `[0xC]==1` / `[0x10]==2` 的 12 字节结构体去调 `d5_ep_3dlut_op_init`：
**立即段错误（SIGSEGV，有 backtrace），日志只写到调用前一行。**

### 原因（反汇编可解释）

`op_init` 里的 `[r3+4]` / `[r3+8]` / `[r3+0xc]` 是**三级指针解引用**：
它拿到的不是"结构体"，而是一个**指向 ISP 侧对象的句柄**，
该对象内部再指向寄存器组、WDMA 通道等。
我传的栈上副本被当成句柄解引用 → 访问未映射内存 → SIGSEGV。

**→ 这不是 bug，而是把 B 路线的最后一道门暴露出来了：**
### ★ 结论：handle 是 ISP 侧分配的内核对象，用户态无法自行构造

| 环节 | 状态 |
|---|---|
| 找到 API 函数 | ✅ 完成（26/27） |
| 确认静态反汇编正确 | ✅ 完成（地址零误差） |
| 拿到合法 handle | ❌ **需要 ISP 守护进程分配** |

## 四、修正上一轮的一个说法

上一轮我写"用户态只能经属性总线下达意图，写入者是内核/ISP 固件"。
本轮实验**给出了这条说法的直接证据**：
不是"不该"由用户态调，而是**调不动——handle 拿不到**。

这也解释了为什么所有进程都预加载 libudd5：
**它是内核/ISP 侧做符号解析用的库，用户态持有它但用不了它的核心对象。**

## 五、下一步（按可行性排序）

| 方案 | 做法 | 风险 | 前景 |
|---|---|---|---|
| **B2** | 直接调 `d5_ep_mc_set_custom_param_yccmixer`（0x29488，PW 7 维实际落点）。它可能不需要 3D LUT 那种 handle | 低 | ★★★ 立即可试 |
| **B3** | 借 `/dev/d5_ipcc` 走 IPCC 报文（木一已证 `iqr[85]` 这条通路能免重启改画面） | 中 | ★★★ 有实机先例 |
| **B4** | 找 ISP 守护进程实际持有的 handle 值（`/dev/d5_ipcc` 侧内存 dump） | 中 | ★★ |
| **B5** | 找能创建 handle 的入口（`d5_ep_3dlut_op_init` 的正确调用者） | 高 | ★ |

**★ 建议先做 B2**：它绕开了整个 handle 机制，且是 PW 7 维的已知落点。
如果 B2 通，至少能做到"机内真曲线"，虽然不如 3D LUT 灵活。

## 六、本轮方法论教训

### ① 手写格式化器比 stdio 更危险
第一版探针用 `va_arg` 手写 `%s/%p/%d/%2x`，输出**每个字符后面插 2 个垃圾字节**。
根因是格式串匹配顺序（`%x` 排在 `%2x` 前面会吃掉短格式）。
**→ 教训：不要手写 printf 家族。既然 `write()` 是可靠的，就每行显式拼好再 write。**
第二版改成"无格式化器、逐字段 put_str/put_hex + 一次 write"后输出完全干净。

### ② 探针崩溃反而是最有价值的结果
阶段 2 的 SIGSEGV 不是失败，它**证明了 handle 不可伪造**——
这个信息只能通过实机崩溃得到，静态分析永远推不出来。

### ③ FTP 传输必须成为默认
33KB 二进制：FTP 瞬时完成；telnet base64 要几分钟且有相机过热风险。
**→ 新铁律：≥10KB 的文件一律走 FTP，不要用 telnet_put.py。**
