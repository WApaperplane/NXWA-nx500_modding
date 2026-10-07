# 任务4 · 3D LUT 相关 ioctl / 消息 ID / 魔数全量收集

- 伪代码 `raw8/p7/ghidra/53_all_pseudocode.c` (19994774 字符 / 723985 行)
- 8 位十六进制常量共 **6855** 种(绝大多数是浮点位型/掩码, 不可当消息 ID)
- 消息形状调用点(第2实参=8位hex)**2498** 个
- 判定为消息 ID **7** 种, 合计 530 次

## 方法论（两处关键修正，避免假结论）

**(1) 派发函数必须用"函数体是否真的使用第 2 实参"判定, 不能靠调用次数。** 实测反例: `FUN_000465bc` 有 699 次"消息形状"调用(分数最高), 但**函数体内 `param_2` 出现 0 次** —— 它是个加锁/互斥辅助函数, 那些调用点第 2 实参恰好是 8 位 hex 纯属巧合。真正的派发器是 `FUN_00173f34`: 函数体内 `param_2` 被使用 2 次, 用法是 `param_2 & 0xffff` 与 `param_2 & 0xffff0000` —— **典型的消息 ID 位域拆解**。★★

**(2) 实参必须按括号深度切分。** 形如 `FUN_x(f(a,b), 0xID, ...)` 的第 1 实参含嵌套括号, 简单正则 `[^,()]+` 会漏掉。v3 按深度切分顶层实参。

**(3) 函数体提取必须先定位独立的 `{` 行。** 本文件格式是 `签名(可跨多行)\n\n{\n函数体`, 签名行本身不含 `{`, 直接按行首 `{` 计数会立刻配平、只截到 2 行。

| 被排除类别 | 数量 | 典型值 | 含义 |
|---|---|---|---|
| 静态地址(0x8xxxxxxx) | 1416 | `0x805cf974` | 排除 |
| IEEE754 浮点位型 | 274 | `0x3f800000`=1.0f `0x40000000`=2.0f `0x3fe00000`=1.75f | 排除 |
| 其他(高字节 0x85) | 139 | — | 排除 |
| 掩码(0xffxxxxxx) | 89 | `0xffffffff` `0xfffe00ff` | 排除 |
| 其他(高字节 0x81) | 32 | — | 排除 |
| 其他(高字节 0x39) | 5 | — | 排除 |
| 其他(高字节 0xc7) | 3 | — | 排除 |
| 其他(高字节 0x47) | 3 | — | 排除 |
| 其他(高字节 0x94) | 2 | — | 排除 |
| 其他(高字节 0x84) | 2 | — | 排除 |
| 其他(高字节 0xa1) | 1 | — | 排除 |
| 其他(高字节 0x4b) | 1 | — | 排除 |
| 其他(高字节 0x37) | 1 | — | 排除 |

## 核心发现

1. **消息派发函数 = `FUN_00173f34`**, 承担 4 次带消息 ID 的调用, 是三星 p7 固件的**命令/消息总入口**, 签名形如 `FUN_00173f34(<singleton>, <msgid>, <param>, <payload>)`。任何想改变 3D LUT 行为的 patch, 都要么改这里的 ID 分派, 要么改被它调用的 handler。★★
2. **消息 ID 空间是"高位=子系统 / 低位=序号"结构**: `0x1xxxxxxx` **5** 种、`0x2xxxxxxx` **2** 种、其余高位 **0** 种, 且低端序号连续(如 `0x10000001/0x10000002/0x10000003`、`0x20000002/0x20000003`)。这种编码可直接按高位切分子系统。★★
3. **3D LUT 的消息 ID 已定位为 `0x10000003`** —— 它是唯一上下文出现 `product/Backend/EP/3DLUT/CBackend_3dlut_Base.cpp` 的 ID(46 次调用)。由 05 文档独立验证: `View::_load` 调的灌入函数 `FUN_00179314` 内部 `mov r1, #0x20000003` 发的是**另一个** ID —— 两条线索交叉印证消息通道结构。★★

> 修正说明: 任务书把 `ADE_EP_3dlut_Param_SET` 当作关键入口, 但**该符号名只是二进制里的一个字符串**(偏移 `0x63f228`), 伪代码里没有任何数值消息 ID 与它直接绑定。实际控制 3D LUT 的是 `0x10000003` / `0x20000003` 这两个数值 ID。证据不足处已标注 ?待查。

## 1. 派发函数源码

```c
void FUN_00173f34(int param_1,uint param_2,int param_3,undefined4 param_4)

{
{
  uint *puVar1;
  int iVar2;
  int iVar3;
  int iVar4;
  undefined4 uVar5;
  int iVar6;
  uint uVar7;
  uint uVar8;
  undefined1 *puVar9;
  int aiStack_1d0 [2];
  int local_1c8;
  uint local_1c4;
  undefined1 auStack_1bc [20];
  undefined1 auStack_1a8 [384];
  
  iVar2 = FUN_00045fb8(DAT_00174204,DAT_00174208,0x109);
  if (iVar2 < 1) {
    return;
  }
  FUN_005156e0(auStack_1a8,param_4,&stack0x00000000);
  iVar2 = FUN_0050c1c4(auStack_1a8);
  uVar8 = param_2 & 0xffff;
  if (param_3 == 0) {
    iVar3 = FUN_004dd07c();
    iVar4 = FUN_004dd064();
    if (uVar8 == 0) {
      FUN_0050b97c(auStack_1bc,DAT_0017422c);
      FUN_0050c1c4(auStack_1bc);
      puVar9 = auStack_1bc;
      goto LAB_00174018;
    }
    FUN_0050b97c(auStack_1bc,DAT_00174214,iVar4 / 1000,iVar3 % 1000000);
    iVar3 = FUN_0050c1c4(auStack_1bc);
    puVar9 = auStack_1bc;
  }
  else {
    iVar3 = FUN_0050c1c4(param_3);
    iVar3 = -(iVar3 + 0x1bU & 0xfffffff8);
    local_1c8 = FUN_004dd07c();
    iVar4 = FUN_004dd064();
    puVar9 = (undefined1 *)((int)&local_1c8 + iVar3);
    iVar6 = local_1c8 % 1000000;
    *(int *)((int)aiStack_1d0 + iVar3) = param_3;
    FUN_0050b97c(puVar9,DAT_0017420c,iVar4 / 1000,iVar6);
    iVar3 = FUN_0050c1c4(puVar9);
    if (uVar8 == 0) goto LAB_00174018;
  }
  local_1c8 = DAT_00174218;
  uVar7 = *(int *)(DAT_00174218 + 0xf30) + 1;
  if (1000 < uVar7) {
    uVar7 = 0;
  }
  *(uint *)(DAT_00174218 + 0xf30) = uVar7;
  puVar1 = DAT_00174220;
  iVar4 = DAT_0017421c;
  if (iVar2 + iVar3 + 1 < 0x181) {
    FUN_0050b97c(DAT_0017421c + uVar7 * 0x180,DAT_00174210,puVar9,auStack_1a8);
    uVar7 = *puVar1;
    iVar2 = DAT_00174224;
  }
  else {
    local_1c4 = uVar7;
    uVar5 = FUN_0050c424(auStack_1a8,auStack_1a8,0x180 - (iVar3 + 1));
    puVar1 = DAT_00174220;
    iVar4 = DAT_0017421c;
    FUN_0050b97c(DAT_0017421c + local_1c4 * 0x180,DAT_00174210,puVar9,uVar5);
    uVar7 = *puVar1;
    iVar2 = DAT_00174224;
  }
```

## 2. 全部消息 ID 总表（按次数降序）

| # | 消息 ID | 高字节分区 | 次数 | 占比 | 主要调用方 | 上下文 LUT 字符串 |
|---|---|---|---|---|---|---|
| 1 | `0x10000001` | `0x10xxxxxx` | 278 | 52.5% | `FUN_00173f34`×278 | — |
| 2 | `0x20000003` | `0x20xxxxxx` | 182 | 34.3% | `FUN_00173f34`×182 | — |
| 3 | `0x10000003` | `0x10xxxxxx` | 46 | 8.7% | `FUN_00173f34`×46 | ★ `product/Backend/EP/3DLUT/CBackend_3dlut_Base.cpp`×2; `CBackend_3dlut_Base`×1 |
| 4 | `0x10000002` | `0x10xxxxxx` | 21 | 4.0% | `FUN_00173f34`×21 | — |
| 5 | `0x10001002` | `0x10xxxxxx` | 1 | 0.2% | `FUN_001191d8`×1 | — |
| 6 | `0x10028000` | `0x10xxxxxx` | 1 | 0.2% | `FUN_0004d4e0`×1 | — |
| 7 | `0x20804050` | `0x20xxxxxx` | 1 | 0.2% | `FUN_00011e70`×1 | — |

## 3. ★ 3D LUT 相关消息 ID（上下文含 LUT 字符串，1 个）

| 消息 ID | 次数 | 占该 ID 全部调用 | LUT 字符串线索 |
|---|---|---|---|
| `0x10000003` | 46 | 8.7% | `product/Backend/EP/3DLUT/CBackend_3dlut_Base.cpp`×2; `CBackend_3dlut_Base`×1 |

### 逐条明细（含伪代码行号与原文）

#### `0x10000003` — 46 次

| 行号 | 调用原文 |
|---|---|
| 135108 | `FUN_00173f34(uVar1,0x10000003,0x80712dac,0x80712dc0,param_2,param_3);` |
| 135753 | `FUN_00173f34(uVar1,0x10000003,DAT_00113cd0,DAT_00113ce0,*(undefined4 *)(param_1 + 0x70));` |
| 135772 | `FUN_00173f34(uVar1,0x10000003,DAT_00113cd0,DAT_00113cdc);` |
| 135790 | `FUN_00173f34(uVar1,0x10000003,DAT_00113cd0,DAT_00113cd8);` |
| 135811 | `FUN_00173f34(uVar1,0x10000003,DAT_00113cd0,DAT_00113cd4,param_2);` |
| 136066 | `FUN_00173f34(uVar1,0x10000003,0x807135d0,0x80712dc0,param_2,param_3);` |
| 136327 | `uVar3 = FUN_00173f34(uVar2,0x10000003,DAT_00115720,DAT_00115728);` |
| 136795 | `FUN_00173f34(uVar1,0x10000003,DAT_0011634c,DAT_00116350,param_2,param_3);` |
| 137168 | `FUN_00173f34(uVar1,0x10000003,param_1[0x34a],DAT_00117174,param_3);` |
| 137183 | `FUN_00173f34(uVar1,0x10000003,0x80713d4c,0x80712dc0,param_2,param_3);` |
| 137559 | `FUN_00173f34(uVar2,0x10000003,DAT_00117dcc,DAT_00117dd8);` |
| 137682 | `FUN_00173f34(uVar1,0x10000003,DAT_001180d4,DAT_001180d8,param_2,param_3);` |
| 137821 | `FUN_00173f34(uVar1,0x10000003,DAT_00118344,DAT_00118348,param_2,param_3);` |
| 138521 | `FUN_00173f34(uVar1,0x10000003,0x80714040,0x80712dc0,param_2,param_3);` |
| 138822 | `FUN_00173f34(uVar3,0x10000003,DAT_00119f4c,DAT_00119f58,*(undefined4 *)(param_1 + 0xa0));` |

首参(singleton)取值分布: `uVar1`×30, `uVar2`×14, `uVar3`×1, `uVar4`×1

## 4. 全部消息 ID 详细画像

### `0x10000001` — 278 次

| 项 | 内容 |
|---|---|
| 次数 / 占比 | 278 / 52.5% |
| 高字节分区 | `0x10xxxxxx` |
| 调用方 | `FUN_00173f34`×278 |
| 首参取值 | `uVar2`×112, `uVar4`×50, `uVar3`×49, `uVar1`×45 |

### `0x20000003` — 182 次

| 项 | 内容 |
|---|---|
| 次数 / 占比 | 182 / 34.3% |
| 高字节分区 | `0x20xxxxxx` |
| 调用方 | `FUN_00173f34`×182 |
| 首参取值 | `uVar1`×122, `uVar2`×36, `uVar3`×12, `uVar5`×8 |
| 近邻字符串 | `CDD_ep_TOP_If`×25, `CDD_ep_RSZ_If`×6, `CMCIf`×5, `d5_ep_srsz_op_deinit(%d, %d)`×3, `d5_ep_udd_close(void)`×3 |

### `0x10000003` — 46 次

| 项 | 内容 |
|---|---|
| 次数 / 占比 | 46 / 8.7% |
| 高字节分区 | `0x10xxxxxx` |
| 调用方 | `FUN_00173f34`×46 |
| 首参取值 | `uVar1`×30, `uVar2`×14, `uVar3`×1, `uVar4`×1 |
| **★ LUT 字符串** | `product/Backend/EP/3DLUT/CBackend_3dlut_Base.cpp`×2, `CBackend_3dlut_Base`×1 |
| 近邻字符串 | `(OnInterrupt) Interrupt (IntSig=%d, AccSig=%d)!`×8, `CBackend_Nog_Base`×2, `product/Backend/EP/3DLUT/CBackend_3dlut_Base.cpp`×2, `_OnLoad`×2, `CBackend_MC_Base`×2 |

### `0x10000002` — 21 次

| 项 | 内容 |
|---|---|
| 次数 / 占比 | 21 / 4.0% |
| 高字节分区 | `0x10xxxxxx` |
| 调用方 | `FUN_00173f34`×21 |
| 首参取值 | `uVar2`×13, `uVar3`×3, `uVar1`×2, `uVar5`×2 |
| 近邻字符串 | `d5_ipc_sw_reset(CTRL1)`×1 |

### `0x10001002` — 1 次

| 项 | 内容 |
|---|---|
| 次数 / 占比 | 1 / 0.2% |
| 高字节分区 | `0x10xxxxxx` |
| 调用方 | `FUN_001191d8`×1 |
| 首参取值 | `uVar2`×1 |

### `0x10028000` — 1 次

| 项 | 内容 |
|---|---|
| 次数 / 占比 | 1 / 0.2% |
| 高字节分区 | `0x10xxxxxx` |
| 调用方 | `FUN_0004d4e0`×1 |
| 首参取值 | `auStack_68`×1 |

### `0x20804050` — 1 次

| 项 | 内容 |
|---|---|
| 次数 / 占比 | 1 / 0.2% |
| 高字节分区 | `0x20xxxxxx` |
| 调用方 | `FUN_00011e70`×1 |
| 首参取值 | `DAT_002fc614`×1 |

## 5. 3D LUT API 名与格式串（从二进制直接读出）

| 字符串 | 文件偏移 | VA | 说明 |
|---|---|---|---|
| `ADE_EP_3dlut_Param_SET` | `0x63f228` | `0x8063f228` | **设置 3D LUT 参数的对外入口** |
| `ADE_d5_3dl_load_luttable` | `0x63f20c` | `0x8063f20c` | **把LUT 表灌进硬件** |
| `ADE_d5_3dl_cb_wdma0_0` | `0x63f1b4` | `0x8063f1b4` | 写 DMA 完成回调 |
| `ADE_d5_3dl_cb_wdma0_2` | `0x63f1cc` | `0x8063f1cc` | 写 DMA 完成回调 |
| `ADE_d5_3dl_cb_rdma0_err` | `0x63ec82` | `0x8063ec82` | 读 DMA 错误回调 |
| `ADE_d5_3dl_cb_rdma0_0` | `0x63f1e4` | `0x8063f1e4` | 读 DMA 完成回调 |
| `d5_ep_3dlut_op_init(0x%08X)` | `0x720838` | `0x80720838` | 3DLUT 初始化 |
| `d5_ep_3dl_load_lut(0x%08X,%d, %d, %d)` | `0x720858` | `0x80720858` | **加载 LUT: 4 参** |
| `d5_ep_3dl_save_lut(0x%08X, %d, %d, %d)` | `0x720880` | `0x80720880` | **保存 LUT: 4 参** |
| `_udd_ep_mux_3dlut_rdxi` | `0x6e6254` | `0x806e6254` | 底层读通道 |
| `_udd_ep_mux_3dlut_wdxi` | `0x6e632c` | `0x806e632c` | 底层写通道 |

`d5_ep_3dl_load_lut(0x%08X,%d, %d, %d)` 的格式串证明加载接口为 **4 参 = 地址 + 3 个整数**。后 3 个整数的语义(表长/网格/通道/标志)**证据不足, 需反汇编其实现确认** —— 标 ?待查, 不做臆断。

## 6. 复现

```bash
python scripts/discovery/t4_msg_ids.py
```

```python
import re
t = open(r'raw8/p7/ghidra/53_all_pseudocode.c', encoding='utf-8').read()
# 1) 按括号深度切分顶层实参(不能用 [^,()]+ ,会漏掉含嵌套括号的第1实参)
# 2) 只取第2实参是 8位hex 的调用, 按此分数选派发器
# 3) 高字节分类排除: 0x80=地址 0xff/fe/fc/ff=掩码 0x3f-0x45/0xc0-0xc1/0x7b-0x7f=IEEE754
```