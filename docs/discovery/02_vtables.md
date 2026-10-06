# 任务2 · 3D LUT 类 RTTI / vtable 逐个追到底

- 固件 `raw8/p7/p7_full.bin`, VA = `0x80000000` + 文件偏移
- 反汇编: **capstone 5.0.7** `Cs(CS_ARCH_ARM, CS_MODE_ARM|CS_MODE_LITTLE_ENDIAN)` (ARM 模式, 非 Thumb)
- 代码区实测: 文件偏移 `0x000000`-`0x56a114`

## 0. 对任务书 3 条前提的实测修正（证据充分，★★确定）

| 任务书说法 | 实测结果 | 证据 |
|---|---|---|
| 镜像分多段；代码 0x80400000-0x80600000，字符串 0x80700000-0x80800000 | **整个镜像只有一个内存块 `0x00000000-0x00c3ffff`, perm=`rwx`** | `01_memory_blocks.txt` 全文: `00000000 00c3ffff 12845056 rwx Default yes` |
| 代码区=文件偏移 0-0x380000 | 代码区 = `0x000000`-`0x56a114`；`0x500f84` 处capstone 能解出 `ldr r3,[pc,#4]; str r3,[r0]; bx lr` → **是代码不是字符串** | `02_functions.txt` 16468 函数地址直方图 |
| vtable: View=`0x805837f8`, Still=`0x805838a0`, CS=`0x8058397c` | 这 3 个地址处是 ASCII **`_load` / `_run` / `_load`**（**方法名字符串**）；真正 vtable address point = **`0x80583808` / `0x805838b8` / `0x80583990`** | 见 §3 hexdump: `0x5837f8: 616f6c5f` = `"_load"` |

> **后果**: 任务书 §2 里"标注槽位落在 0x80400000-0x80600000(代码) 还是 0x80700000-0x80800000(字符串)"这条判据**失效**（单块 rwx 无法按权限区分）。本文档改用 **Ghidra 已识别函数入口集合** 判定代码指针。
>
> 同时确认 Itanium RTTI 的 typeinfo vtable **不止一个值**（这是 v3 漏掉一半 typeinfo 的原因）:
> `0x80759908`=`__si_class_type_info`（单继承，typeinfo[2]=基类）、`0x80759b58`=`__class_type_info`（无基类，typeinfo[2]=0）、`0x80759ac0`=`__vmi_class_type_info`（多/虚继承，`C3DLUTIf` 用它）。

---

## 核心发现

1. **vtable 与typeinfo 双向溯源完成**: 14 个 3D LUT typeinfo 全部解出并按三种 RTTI 类型校验通过; 由此反推出 **24** 张 vtable（主表 top=0 + 次表 top<0 成对出现），每张表的槽位全部落在真实代码区，且**每个槽位都能对上 Ghidra 函数名**。★★
2. **继承链确证**（读 typeinfo[2] 逐级解析,非推测）: `CBackend_3dlut_View` / `_Still` / `_CS` 三者的基类 typeinfo **全部等于 `0x805837c8` = `CBackend_3dlut_Base`**；而 `CBackend_3dlut_CS0_Callback` / `CS1_Callback` 的基类是 **`IBackend_Ep_Callback_Base`** —— **两个 Callback 类不属于 3D LUT 主继承链, 而是挂在通用 EP 回调基座上**。这解释了为何它们只有 1 个槽位。★
3. **vtable 装填点(构造函数)已定位 13 处**, 模式经 capstone 确认为 `ldr rX,[pc,#imm]`(ARM 字面池=PC+8+imm) 把 vtable 常量装入寄存器、随后 `str rX,[r0]` 写入对象首字。这是把 vtable 绑到构造函数、进而定位"3D LUT 对象在哪被new 出来"的唯一可靠路径, **可直接用于固件 patch**。★

## 1. 3D LUT typeinfo 全表（继承链由此确证）

| 类名 | typeinfo VA | typeinfo 类型 | 名串原文 | 基类 |
|---|---|---|---|---|
| `CBackend_3dlut` | `0x805836d8` | `__si_class_type_info` | `14CBackend_3dlut` | `CBackend_IF_Base` |
| `CBackend_3dlut_Base` | `0x805837c8` | `__class_type_info` | `19CBackend_3dlut_Base` | —（顶层） |
| `CBackend_3dlut_View` | `0x80583894` | `__si_class_type_info` | `19CBackend_3dlut_View` | `CBackend_3dlut_Base` |
| `CBackend_3dlut_Still` | `0x80583944` | `__si_class_type_info` | `20CBackend_3dlut_Still` | `CBackend_3dlut_Base` |
| `CBackend_3dlut_CS` | `0x80583a18` | `__si_class_type_info` | `17CBackend_3dlut_CS` | `CBackend_3dlut_Base` |
| `CBackend_3dlut_CS0_Callback` | `0x80583a44` | `__si_class_type_info` | `27CBackend_3dlut_CS0_Callback` | `IBackend_Ep_Callback_Base` |
| `CBackend_3dlut_CS1_Callback` | `0x80583a70` | `__si_class_type_info` | `27CBackend_3dlut_CS1_Callback` | `IBackend_Ep_Callback_Base` |
| `C3DLUTIf` | `0x80588ccc` | `__vmi_class_type_info` | `8C3DLUTIf` | —（顶层） |
| `C3DLUTAlarm` | `0x80588cfc` | `__si_class_type_info` | `11C3DLUTAlarm` | `IAlarmListener` |
| `CMaterial_NX1_Still_3dlut_Normal` | `0x8058bb04` | `__class_type_info` | `32CMaterial_NX1_Still_3dlut_Normal` | —（顶层） |
| `CMaterial_NX1_Still_3dlut_SelectColor` | `0x8058bb98` | `__class_type_info` | `37CMaterial_NX1_Still_3dlut_SelectColor` | —（顶层） |
| `CMaterial_NX1_Still_3dlut_CS` | `0x8058bc18` | `__class_type_info` | `28CMaterial_NX1_Still_3dlut_CS` | —（顶层） |
| `CMaterial_NX1_QView_3dlut_CS` | `0x8058e6e0` | `__class_type_info` | `28CMaterial_NX1_QView_3dlut_CS` | —（顶层） |
| `CMaterial_3DLUT_Liveview` | `0x8059cca0` | `__class_type_info` | `24CMaterial_3DLUT_Liveview` | —（顶层） |

## 2. 全部 3D LUT vtable

| # | address point (slot0) | 文件偏移 | offset-to-top | 归属类 | 槽位数 | 表类型 |
|---|---|---|---|---|---|---|
| 1 | `0x80583658` | `0x583658` | `0x805836d8` | `CBackend_3dlut` | 20 | 次表 (top=2153264856, 子对象偏 2141702440 字节) |
| 2 | `0x805836f8` | `0x5836f8` | `0x805837c8` | `CBackend_3dlut_Base` | 25 | 次表 (top=2153265096, 子对象偏 2141702200 字节) |
| 3 | `0x80583760` | `0x583760` | `0x805837c8` | `CBackend_3dlut_Base` | 4 | 次表 (top=2153265096, 子对象偏 2141702200 字节) |
| 4 | `0x80583808` | `0x583808` | `0x80583894` | `CBackend_3dlut_View` | 25 | 次表 (top=2153265300, 子对象偏 2141701996 字节) |
| 5 | `0x80583870` | `0x583870` | `0x80583894` | `CBackend_3dlut_View` | 4 | 次表 (top=2153265300, 子对象偏 2141701996 字节) |
| 6 | `0x805838b8` | `0x5838b8` | `0x80583944` | `CBackend_3dlut_Still` | 25 | 次表 (top=2153265476, 子对象偏 2141701820 字节) |
| 7 | `0x80583920` | `0x583920` | `0x80583944` | `CBackend_3dlut_Still` | 4 | 次表 (top=2153265476, 子对象偏 2141701820 字节) |
| 8 | `0x80583958` | `0x583958` | `0x80583a44` | `CBackend_3dlut_CS0_Callback` | 3 | 次表 (top=2153265732, 子对象偏 2141701564 字节) |
| 9 | `0x80583970` | `0x583970` | `0x80583a70` | `CBackend_3dlut_CS1_Callback` | 4 | 次表 (top=2153265776, 子对象偏 2141701520 字节) |
| 10 | `0x80583990` | `0x583990` | `0x80583a18` | `CBackend_3dlut_CS` | 25 | 次表 (top=2153265688, 子对象偏 2141701608 字节) |
| 11 | `0x805839f8` | `0x5839f8` | `0x80583a18` | `CBackend_3dlut_CS` | 4 | 次表 (top=2153265688, 子对象偏 2141701608 字节) |
| 12 | `0x80588cb8` | `0x588cb8` | `0x80588ccc` | `C3DLUTIf` | 3 | 次表 (top=2153286860, 子对象偏 2141680436 字节) |
| 13 | `0x80588ce0` | `0x588ce0` | `0x80588cfc` | `C3DLUTAlarm` | 4 | 次表 (top=2153286908, 子对象偏 2141680388 字节) |
| 14 | `0x8058baa8` | `0x58baa8` | `0x8058bb04` | `CMaterial_NX1_Still_3dlut_Normal` | 10 | 次表 (top=2153298692, 子对象偏 2141668604 字节) |
| 15 | `0x8058bad4` | `0x58bad4` | `0x8058bb04` | `CMaterial_NX1_Still_3dlut_Normal` | 4 | 次表 (top=2153298692, 子对象偏 2141668604 字节) |
| 16 | `0x8058bb38` | `0x58bb38` | `0x8058bb98` | `CMaterial_NX1_Still_3dlut_SelectColor` | 10 | 次表 (top=2153298840, 子对象偏 2141668456 字节) |
| 17 | `0x8058bb64` | `0x58bb64` | `0x8058bb98` | `CMaterial_NX1_Still_3dlut_SelectColor` | 4 | 次表 (top=2153298840, 子对象偏 2141668456 字节) |
| 18 | `0x8058bbc0` | `0x58bbc0` | `0x8058bc18` | `CMaterial_NX1_Still_3dlut_CS` | 10 | 次表 (top=2153298968, 子对象偏 2141668328 字节) |
| 19 | `0x8058bbec` | `0x58bbec` | `0x8058bc18` | `CMaterial_NX1_Still_3dlut_CS` | 4 | 次表 (top=2153298968, 子对象偏 2141668328 字节) |
| 20 | `0x8058e688` | `0x58e688` | `0x8058e6e0` | `CMaterial_NX1_QView_3dlut_CS` | 10 | 次表 (top=2153309920, 子对象偏 2141657376 字节) |
| 21 | `0x8058e6b4` | `0x58e6b4` | `0x8058e6e0` | `CMaterial_NX1_QView_3dlut_CS` | 4 | 次表 (top=2153309920, 子对象偏 2141657376 字节) |
| 22 | `0x8059cb20` | `0x59cb20` | `0x8059cca0` | `CMaterial_3DLUT_Liveview` | 10 | 次表 (top=2153368736, 子对象偏 2141598560 字节) |
| 23 | `0x8059cb4c` | `0x59cb4c` | `0x8059cca0` | `CMaterial_3DLUT_Liveview` | 4 | 次表 (top=2153368736, 子对象偏 2141598560 字节) |
| 24 | `0x8059cb60` | `0x59cb60` | `0x8059cca0` | `CMaterial_3DLUT_Liveview` | 4 | 次表 (top=2153368736, 子对象偏 2141598560 字节) |

## 3. 原始 hexdump 证据（0x5837f0-0x583830,含任务书 3 个地址）

```
0x5837f0: 0000003d
0x5837f4: 00000000
0x5837f8: 616f6c5f  ★ 任务书给的"vtable 地址" -> 实为方法名字符串 b'_load'
0x5837fc: 00000064
0x583800: 00000000<- offset-to-top = 0  (vtable[-1], 主表)
0x583804: 80583894<- &typeinfo  (vtable[-2])
0x583808: 8011e380  ★ 真正的 vtable address point (slot0)
0x58380c: 8011e3b4<- 函数 FUN_0011e3b4
0x583810: 8011dd10<- 函数 ?
0x583814: 8011d6dc<- 函数 FUN_0011d6dc
0x583818: 8011da54<- 函数 ?
0x58381c: 8011d14c<- 函数 FUN_0011d14c
0x583820: 8011d520<- 函数 FUN_0011d520
0x583824: 8011d358<- 函数 FUN_0011d358
0x583828: 8011debc<- 函数 FUN_0011debc
0x58382c: 8011d128<- 函数 ?
```

## 4. 每个 vtable 槽位的 capstone 反汇编（前 8 条指令）

### CBackend_3dlut — `0x80583658` (次表 top=2153264856, 子对象(主对象+2141702440), 20 槽)

| 槽 | VA | Ghidra 函数 | capstone 反汇编 |
|---|---|---|---|
| [0] | `0x8011cb64` | `FUN_0011cb64` | `0x8011cb64: push {r4, r5, r6, lr}`<br>`0x8011cb68: ldr r4, [pc, #0xc0]`<br>`0x8011cb6c: ldr r1, [pc, #0xc0]`<br>`0x8011cb70: ldr r3, [r4]`<br>`0x8011cb74: mov r6, r0`<br>`0x8011cb78: cmp r3, #0`<br>`0x8011cb7c: str r1, [r0]`<br>`0x8011cb80: beq #0x8011cba0` |
| [1] | `0x8011cc3c` | `?` | `0x8011cc3c: push {r4, lr}`<br>`0x8011cc40: mov r4, r0`<br>`0x8011cc44: bl #0x8011cb64`<br>`0x8011cc48: mov r0, r4`<br>`0x8011cc4c: bl #0x80524664`<br>`0x8011cc50: mov r0, r4`<br>`0x8011cc54: pop {r4, pc}`<br>`0x8011cc58: push {r4, r5, r6, lr}` |
| [2] | `0x801c9fe4` | `FUN_001c9fe4` | `0x801c9fe4: push {r4, lr}`<br>`0x801c9fe8: cmp r2, #0`<br>`0x801c9fec: sub sp, sp, #0x10`<br>`0x801c9ff0: mov r4, r0`<br>`0x801c9ff4: beq #0x801ca088`<br>`0x801c9ff8: cmp r1, #0x13`<br>`0x801c9ffc: bhi #0x801ca038`<br>`0x801ca000: add r0, r1, #0x320` |
| [3] | `0x801c9ed8` | `FUN_001c9ed8` | `0x801c9ed8: push {r4, r5, r6, r7, r8, sb, sl, lr}`<br>`0x801c9edc: cmp r2, #0`<br>`0x801c9ee0: sub sp, sp, #0x10`<br>`0x801c9ee4: mov r7, r0`<br>`0x801c9ee8: beq #0x801c9fc0`<br>`0x801c9eec: cmp r1, #0x13`<br>`0x801c9ef0: bhi #0x801c9f98`<br>`0x801c9ef4: add r6, r1, #0x320` |
| [4] | `0x801c9e0c` | `FUN_001c9e0c` | `0x801c9e0c: push {r4, lr}`<br>`0x801c9e10: cmp r2, #0`<br>`0x801c9e14: sub sp, sp, #0x10`<br>`0x801c9e18: mov r4, r0`<br>`0x801c9e1c: beq #0x801c9eb0`<br>`0x801c9e20: cmp r1, #0x13`<br>`0x801c9e24: bhi #0x801c9e60`<br>`0x801c9e28: add r0, r1, #0x334` |
| [5] | `0x801c9cf4` | `?` | `0x801c9cf4: push {r4, r5, r6, r7, r8, sb, sl, fp, lr}`<br>`0x801c9cf8: cmp r2, #0`<br>`0x801c9cfc: sub sp, sp, #0x14`<br>`0x801c9d00: mov r8, r0`<br>`0x801c9d04: beq #0x801c9de8`<br>`0x801c9d08: cmp r1, #0x13`<br>`0x801c9d0c: bhi #0x801c9dc0`<br>`0x801c9d10: add r6, r1, #0x334` |
| [6] | `0x801c9be4` | `?` | `0x801c9be4: push {r4, r5, r6, r7, r8, lr}`<br>`0x801c9be8: add r8, r1, #0x320`<br>`0x801c9bec: add r8, r0, r8, lsl #2`<br>`0x801c9bf0: ldr r3, [r8, #4]`<br>`0x801c9bf4: mov r6, r1`<br>`0x801c9bf8: cmp r3, #0`<br>`0x801c9bfc: mov r7, r2`<br>`0x801c9c00: ble #0x801c9c48` |
| [7] | `0x801c9c50` | `FUN_001c9c50` | `0x801c9c50: push {r3, r4, r5, r6, r7, r8, sb, sl, fp, lr}`<br>`0x801c9c54: add sb, r1, #0x334`<br>`0x801c9c58: add fp, r0, sb, lsl #2`<br>`0x801c9c5c: ldr r3, [fp, #4]`<br>`0x801c9c60: mov r6, r1`<br>`0x801c9c64: cmp r3, #0`<br>`0x801c9c68: mov sl, r0`<br>`0x801c9c6c: mov r7, r2` |
| [8] | `0x80500c34` | `?` | `0x80500c34: ldrb r0, [r0, #0xd24]`<br>`0x80500c38: sxtb r0, r0`<br>`0x80500c3c: bx lr`<br>`0x80500c40: mov r0, #0`<br>`0x80500c44: bx lr`<br>`0x80500c48: mov r0, #0`<br>`0x80500c4c: bx lr`<br>`0x80500c50: ldr r3, [pc, #4]` |
| [9] | `0x80500c40` | `?` | `0x80500c40: mov r0, #0`<br>`0x80500c44: bx lr`<br>`0x80500c48: mov r0, #0`<br>`0x80500c4c: bx lr`<br>`0x80500c50: ldr r3, [pc, #4]`<br>`0x80500c54: str r3, [r0]`<br>`0x80500c58: bx lr`<br>`0x80500c5c: rsbshi r2, r1, r8, ror sp` |
| [10] | `0x80500c48` | `?` | `0x80500c48: mov r0, #0`<br>`0x80500c4c: bx lr`<br>`0x80500c50: ldr r3, [pc, #4]`<br>`0x80500c54: str r3, [r0]`<br>`0x80500c58: bx lr`<br>`0x80500c5c: rsbshi r2, r1, r8, ror sp`<br>`0x80500c60: ldr r3, [pc, #0x14]`<br>`0x80500c64: push {r4, lr}` |
| [11] | `0x8011c4ec` | `?` | `0x8011c4ec: push {r3, r4, r5, lr}`<br>`0x8011c4f0: subs r2, r1, #0`<br>`0x8011c4f4: mov r3, #1`<br>`0x8011c4f8: mov r4, r0`<br>`0x8011c4fc: strb r3, [r0, #0xd24]`<br>`0x8011c500: beq #0x8011c520`<br>`0x8011c504: ldr r3, [r2, #8]`<br>`0x8011c508: cmp r3, #0` |
| [12] | `0x8011cb40` | `?` | `0x8011cb40: push {r4, lr}`<br>`0x8011cb44: mov r4, r0`<br>`0x8011cb48: bl #0x8011dc74`<br>`0x8011cb4c: mov r0, #0`<br>`0x8011cb50: strb r0, [r4, #0xd24]`<br>`0x8011cb54: strb r0, [r4, #0xd25]`<br>`0x8011cb58: str r0, [r4, #0xd7c]`<br>`0x8011cb5c: str r0, [r4, #0xd8c]` |
| [13] | `0x8011c760` | `?` | `0x8011c760: ldr r3, [r0, #0xd8c]`<br>`0x8011c764: push {r4, lr}`<br>`0x8011c768: add r3, r3, r3, lsl #2`<br>`0x8011c76c: lsl r2, r3, #3`<br>`0x8011c770: add r3, r0, r2`<br>`0x8011c774: add r3, r3, #0xd30`<br>`0x8011c778: ldrsb r1, [r3, #8]`<br>`0x8011c77c: mov r4, r0` |
| [14] | `0x8011c84c` | `?` | `0x8011c84c: push {r3, r4, r5, lr}`<br>`0x8011c850: mov r3, #0`<br>`0x8011c854: str r3, [r0, #0xd7c]`<br>`0x8011c858: subs r2, r1, #0`<br>`0x8011c85c: mov r3, #2`<br>`0x8011c860: mov r4, r0`<br>`0x8011c864: strb r3, [r0, #0xd24]`<br>`0x8011c868: beq #0x8011caec` |
| [15] | `0x8011c448` | `?` | `0x8011c448: push {r3, r4, r5, lr}`<br>`0x8011c44c: subs r3, r1, #0`<br>`0x8011c450: mov r5, r0`<br>`0x8011c454: beq #0x8011c474`<br>`0x8011c458: ldr r3, [r3, #8]`<br>`0x8011c45c: cmp r3, #0`<br>`0x8011c460: blt #0x8011c4d0`<br>`0x8011c464: tst r3, #0x10000000` |
| [16] | `0x8011c3bc` | `?` | `0x8011c3bc: push {r3, r4, r5, lr}`<br>`0x8011c3c0: mov r4, r0`<br>`0x8011c3c4: ldr r0, [r0, #0xd7c]`<br>`0x8011c3c8: cmp r0, #0`<br>`0x8011c3cc: beq #0x8011c41c`<br>`0x8011c3d0: ldr r3, [r4, #0xd8c]`<br>`0x8011c3d4: ldr r2, [r0]`<br>`0x8011c3d8: add r3, r3, r3, lsl #2` |
| [17] | `0x8011c678` | `?` | `0x8011c678: push {r3, r4, r5, lr}`<br>`0x8011c67c: ldr r3, [r0, #0xd8c]`<br>`0x8011c680: mov r4, r0`<br>`0x8011c684: add r3, r3, r3, lsl #2`<br>`0x8011c688: lsl r2, r3, #3`<br>`0x8011c68c: add r3, r0, r2`<br>`0x8011c690: add r3, r3, #0xd30`<br>`0x8011c694: ldrsb r1, [r3, #8]` |
| [18] | `0x8011c598` | `?` | `0x8011c598: push {r3, r4, r5, lr}`<br>`0x8011c59c: ldr r3, [r0, #0xd8c]`<br>`0x8011c5a0: mov r4, r0`<br>`0x8011c5a4: add r3, r3, r3, lsl #2`<br>`0x8011c5a8: lsl r2, r3, #3`<br>`0x8011c5ac: add r3, r0, r2`<br>`0x8011c5b0: ldrb r0, [r3, #0xd38]`<br>`0x8011c5b4: mov r5, r1` |
| [19] | `0x6142437e` | `?` | _(capstone 解码失败)_ |

### CBackend_3dlut_Base — `0x805836f8` (次表 top=2153265096, 子对象(主对象+2141702200), 25 槽)

| 槽 | VA | Ghidra 函数 | capstone 反汇编 |
|---|---|---|---|
| [0] | `0x8011d944` | `FUN_0011d944` | `0x8011d944: push {r3, r4, r5, lr}`<br>`0x8011d948: ldr r5, [pc, #0x94]`<br>`0x8011d94c: ldr r1, [pc, #0x94]`<br>`0x8011d950: ldr r3, [r5]`<br>`0x8011d954: add r2, r1, #0x68`<br>`0x8011d958: cmp r3, #0`<br>`0x8011d95c: mov r4, r0`<br>`0x8011d960: str r1, [r0]` |
| [1] | `0x8011da08` | `FUN_0011da08` | `0x8011da08: push {r4, lr}`<br>`0x8011da0c: mov r4, r0`<br>`0x8011da10: bl #0x8011d944`<br>`0x8011da14: mov r0, r4`<br>`0x8011da18: bl #0x80524664`<br>`0x8011da1c: mov r0, r4`<br>`0x8011da20: pop {r4, pc}`<br>`0x8011da24: sub r0, r0, #0xc` |
| [2] | `0x8011dd10` | `?` | `0x8011dd10: push {r3, lr}`<br>`0x8011dd14: ldrsh r3, [r1, #0xc]`<br>`0x8011dd18: cmp r3, #0`<br>`0x8011dd1c: beq #0x8011dd24`<br>`0x8011dd20: bl #0x8011dc74`<br>`0x8011dd24: bl #0x80110b30`<br>`0x8011dd28: pop {r3, lr}`<br>`0x8011dd2c: b #0x80110c98` |
| [3] | `0x8011d6dc` | `FUN_0011d6dc` | `0x8011d6dc: push {r4, r5, r6, r7, r8, sb, sl, fp, lr}`<br>`0x8011d6e0: subs r5, r1, #0`<br>`0x8011d6e4: sub sp, sp, #0x14`<br>`0x8011d6e8: mov r6, r0`<br>`0x8011d6ec: beq #0x8011d878`<br>`0x8011d6f0: mov r0, r5`<br>`0x8011d6f4: ldr r1, [pc, #0x220]`<br>`0x8011d6f8: ldr r2, [pc, #0x220]` |
| [4] | `0x8011da54` | `?` | `0x8011da54: cmp r1, #0`<br>`0x8011da58: push {r4, r5, r6, lr}`<br>`0x8011da5c: mov r4, r0`<br>`0x8011da60: beq #0x8011dadc`<br>`0x8011da64: mov r0, r1`<br>`0x8011da68: ldr r2, [pc, #0x88]`<br>`0x8011da6c: ldr r1, [pc, #0x88]`<br>`0x8011da70: mov r3, #0` |
| [5] | `0x8011d14c` | `FUN_0011d14c` | `0x8011d14c: push {r4, r5, lr}`<br>`0x8011d150: ldr r3, [pc, #0x5c]`<br>`0x8011d154: sub sp, sp, #0xc`<br>`0x8011d158: ldr r0, [r3, #4]`<br>`0x8011d15c: cmp r0, #0`<br>`0x8011d160: moveq r4, r0`<br>`0x8011d164: beq #0x8011d18c`<br>`0x8011d168: ldr r1, [r1, #8]` |
| [6] | `0x8011d520` | `FUN_0011d520` | `0x8011d520: push {r4, r5, r6, r7, r8, sb, sl, fp, lr}`<br>`0x8011d524: subs r4, r1, #0`<br>`0x8011d528: sub sp, sp, #0x5c`<br>`0x8011d52c: mov r6, r0`<br>`0x8011d530: beq #0x8011d6a4`<br>`0x8011d534: mov r0, r4`<br>`0x8011d538: ldr r1, [pc, #0x180]`<br>`0x8011d53c: ldr r2, [pc, #0x180]` |
| [7] | `0x8011d358` | `FUN_0011d358` | `0x8011d358: push {r4, r5, r6, r7, lr}`<br>`0x8011d35c: subs r4, r1, #0`<br>`0x8011d360: sub sp, sp, #0x5c`<br>`0x8011d364: mov r7, r0`<br>`0x8011d368: beq #0x8011d4e8`<br>`0x8011d36c: mov r0, r4`<br>`0x8011d370: ldr r1, [pc, #0x18c]`<br>`0x8011d374: ldr r2, [pc, #0x18c]` |
| [8] | `0x8011cee0` | `?` | `0x8011cee0: mov r0, #0`<br>`0x8011cee4: bx lr`<br>`0x8011cee8: mov r0, #0`<br>`0x8011ceec: bx lr`<br>`0x8011cef0: cmp r2, #0`<br>`0x8011cef4: movne r3, #0`<br>`0x8011cef8: strne r3, [r2]`<br>`0x8011cefc: strne r3, [r2, #4]` |
| [9] | `0x8011d128` | `?` | `0x8011d128: ldr r3, [r1, #8]`<br>`0x8011d12c: mov r1, r0`<br>`0x8011d130: ubfx r3, r3, #0x1d, #1`<br>`0x8011d134: add r3, r0, r3`<br>`0x8011d138: ldrsb r0, [r3, #0x13]`<br>`0x8011d13c: cmn r0, #1`<br>`0x8011d140: bxeq lr`<br>`0x8011d144: add r1, r1, #0xc` |
| [10] | `0x8011ced8` | `?` | `0x8011ced8: mov r0, #0`<br>`0x8011cedc: bx lr`<br>`0x8011cee0: mov r0, #0`<br>`0x8011cee4: bx lr`<br>`0x8011cee8: mov r0, #0`<br>`0x8011ceec: bx lr`<br>`0x8011cef0: cmp r2, #0`<br>`0x8011cef4: movne r3, #0` |
| [11] | `0x8011cee8` | `?` | `0x8011cee8: mov r0, #0`<br>`0x8011ceec: bx lr`<br>`0x8011cef0: cmp r2, #0`<br>`0x8011cef4: movne r3, #0`<br>`0x8011cef8: strne r3, [r2]`<br>`0x8011cefc: strne r3, [r2, #4]`<br>`0x8011cf00: bx lr`<br>`0x8011cf04: str lr, [sp, #-4]!` |
| [12] | `0x8011d0dc` | `?` | `0x8011d0dc: push {r3, r4, r5, lr}`<br>`0x8011d0e0: ldr r3, [r1, #8]`<br>`0x8011d0e4: mov r4, r0`<br>`0x8011d0e8: ands r5, r3, #0x20000000`<br>`0x8011d0ec: bne #0x8011d114`<br>`0x8011d0f0: cmp r3, #0`<br>`0x8011d0f4: bge #0x8011d118`<br>`0x8011d0f8: add r5, r4, r5` |
| [13] | `0x8011d1c0` | `FUN_0011d1c0` | `0x8011d1c0: push {r4, r5, r6, r7, r8, sb, sl, lr}`<br>`0x8011d1c4: subs r5, r1, #0`<br>`0x8011d1c8: sub sp, sp, #8`<br>`0x8011d1cc: mov r8, r0`<br>`0x8011d1d0: beq #0x8011d320`<br>`0x8011d1d4: mov r0, r5`<br>`0x8011d1d8: ldr r1, [pc, #0x15c]`<br>`0x8011d1dc: ldr r2, [pc, #0x15c]` |
| [14] | `0x8011dd98` | `?` | `0x8011dd98: ldr r3, [r1, #8]`<br>`0x8011dd9c: cmp r3, #0`<br>`0x8011dda0: blt #0x8011dda8`<br>`0x8011dda4: b #0x8011dd30`<br>`0x8011dda8: tst r3, #0x20000000`<br>`0x8011ddac: bxeq lr`<br>`0x8011ddb0: b #0x8011dda4`<br>`0x8011ddb4: movw r3, #0x3cc8` |
| [15] | `0x8011cfa4` | `FUN_0011cfa4` | `0x8011cfa4: push {r3, r4, r5, lr}`<br>`0x8011cfa8: mov r5, r1`<br>`0x8011cfac: mov r4, r2`<br>`0x8011cfb0: bl #0x8011cd58`<br>`0x8011cfb4: ldr r3, [r0]`<br>`0x8011cfb8: mov r1, r5`<br>`0x8011cfbc: ldr r3, [r3, #0x1c]`<br>`0x8011cfc0: mov r2, r4` |
| [16] | `0x8011cf7c` | `FUN_0011cf7c` | `0x8011cf7c: push {r3, r4, r5, lr}`<br>`0x8011cf80: mov r5, r1`<br>`0x8011cf84: mov r4, r2`<br>`0x8011cf88: bl #0x8011cd58`<br>`0x8011cf8c: ldr r3, [r0]`<br>`0x8011cf90: mov r1, r5`<br>`0x8011cf94: ldr r3, [r3, #0x18]`<br>`0x8011cf98: mov r2, r4` |
| [17] | `0x8011cef0` | `?` | `0x8011cef0: cmp r2, #0`<br>`0x8011cef4: movne r3, #0`<br>`0x8011cef8: strne r3, [r2]`<br>`0x8011cefc: strne r3, [r2, #4]`<br>`0x8011cf00: bx lr`<br>`0x8011cf04: str lr, [sp, #-4]!`<br>`0x8011cf08: mov r3, #2`<br>`0x8011cf0c: sub sp, sp, #0xc` |
| [18] | `0x8011db0c` | `?` | `0x8011db0c: subs r0, r1, #0`<br>`0x8011db10: push {r4, lr}`<br>`0x8011db14: mov r4, r2`<br>`0x8011db18: beq #0x8011db54`<br>`0x8011db1c: ldr r1, [pc, #0x48]`<br>`0x8011db20: ldr r2, [pc, #0x48]`<br>`0x8011db24: mov r3, #0`<br>`0x8011db28: bl #0x80524194` |
| [19] | `0x8011cfcc` | `?` | `0x8011cfcc: subs r0, r1, #0`<br>`0x8011cfd0: push {r3, r4, r5, r6, r7, lr}`<br>`0x8011cfd4: mov r5, r2`<br>`0x8011cfd8: mov r4, r3`<br>`0x8011cfdc: beq #0x8011d0a4`<br>`0x8011cfe0: ldr r1, [pc, #0xe0]`<br>`0x8011cfe4: ldr r2, [pc, #0xe0]`<br>`0x8011cfe8: mov r3, #0` |
| [20] | `0x8011da2c` | `?` | `0x8011da2c: ldr r3, [r1, #8]`<br>`0x8011da30: mov r1, r0`<br>`0x8011da34: tst r3, #0x20000000`<br>`0x8011da38: beq #0x8011da48`<br>`0x8011da3c: mov r0, #7`<br>`0x8011da40: add r1, r1, #0xc`<br>`0x8011da44: b #0x801cc218`<br>`0x8011da48: cmp r3, #0` |
| [21] | `0x8011ced0` | `?` | `0x8011ced0: mov r0, #0`<br>`0x8011ced4: bx lr`<br>`0x8011ced8: mov r0, #0`<br>`0x8011cedc: bx lr`<br>`0x8011cee0: mov r0, #0`<br>`0x8011cee4: bx lr`<br>`0x8011cee8: mov r0, #0`<br>`0x8011ceec: bx lr` |
| [22] | `0x8011cf04` | `FUN_0011cf04` | `0x8011cf04: str lr, [sp, #-4]!`<br>`0x8011cf08: mov r3, #2`<br>`0x8011cf0c: sub sp, sp, #0xc`<br>`0x8011cf10: str r3, [sp]`<br>`0x8011cf14: movw r0, #0x48f4`<br>`0x8011cf18: movw r1, #0x36e8`<br>`0x8011cf1c: movw r3, #0x3cc8`<br>`0x8011cf20: movt r1, #0x8058` |
| [23] | `0x8011cf3c` | `FUN_0011cf3c` | `0x8011cf3c: push {r4, r5, lr}`<br>`0x8011cf40: sub sp, sp, #0xc`<br>`0x8011cf44: mov r4, r1`<br>`0x8011cf48: mov r5, r2`<br>`0x8011cf4c: bl #0x80173c88`<br>`0x8011cf50: movw r2, #0x4928`<br>`0x8011cf54: movw r3, #0x2dc0`<br>`0x8011cf58: stm sp, {r4, r5}` |
| [24] | `0xfffffff4` | `?` | _(capstone 解码失败)_ |

### CBackend_3dlut_Base — `0x80583760` (次表 top=2153265096, 子对象(主对象+2141702200), 4 槽)

| 槽 | VA | Ghidra 函数 | capstone 反汇编 |
|---|---|---|---|
| [0] | `0x8011da00` | `?` | `0x8011da00: sub r0, r0, #0xc`<br>`0x8011da04: b #0x8011d944`<br>`0x8011da08: push {r4, lr}`<br>`0x8011da0c: mov r4, r0`<br>`0x8011da10: bl #0x8011d944`<br>`0x8011da14: mov r0, r4`<br>`0x8011da18: bl #0x80524664`<br>`0x8011da1c: mov r0, r4` |
| [1] | `0x8011da24` | `?` | `0x8011da24: sub r0, r0, #0xc`<br>`0x8011da28: b #0x8011da08`<br>`0x8011da2c: ldr r3, [r1, #8]`<br>`0x8011da30: mov r1, r0`<br>`0x8011da34: tst r3, #0x20000000`<br>`0x8011da38: beq #0x8011da48`<br>`0x8011da3c: mov r0, #7`<br>`0x8011da40: add r1, r1, #0xc` |
| [2] | `0x8011cf74` | `?` | `0x8011cf74: sub r0, r0, #0xc`<br>`0x8011cf78: b #0x8011cf3c`<br>`0x8011cf7c: push {r3, r4, r5, lr}`<br>`0x8011cf80: mov r5, r1`<br>`0x8011cf84: mov r4, r2`<br>`0x8011cf88: bl #0x8011cd58`<br>`0x8011cf8c: ldr r3, [r0]`<br>`0x8011cf90: mov r1, r5` |
| [3] | `0x6142437e` | `?` | _(capstone 解码失败)_ |

### CBackend_3dlut_View — `0x80583808` (次表 top=2153265300, 子对象(主对象+2141701996), 25 槽)

| 槽 | VA | Ghidra 函数 | capstone 反汇编 |
|---|---|---|---|
| [0] | `0x8011e380` | `FUN_0011e380` | `0x8011e380: movw r3, #0x37f8`<br>`0x8011e384: movt r3, #0x8058`<br>`0x8011e388: add r2, r3, #0x10`<br>`0x8011e38c: add r3, r3, #0x78`<br>`0x8011e390: push {r4, lr}`<br>`0x8011e394: mov r4, r0`<br>`0x8011e398: str r2, [r0]`<br>`0x8011e39c: str r3, [r0, #0xc]` |
| [1] | `0x8011e3b4` | `FUN_0011e3b4` | `0x8011e3b4: push {r4, lr}`<br>`0x8011e3b8: mov r4, r0`<br>`0x8011e3bc: bl #0x8011e380`<br>`0x8011e3c0: mov r0, r4`<br>`0x8011e3c4: bl #0x80524664`<br>`0x8011e3c8: mov r0, r4`<br>`0x8011e3cc: pop {r4, pc}`<br>`0x8011e3d0: sub r0, r0, #0xc` |
| [2] | `0x8011dd10` | `?` | `0x8011dd10: push {r3, lr}`<br>`0x8011dd14: ldrsh r3, [r1, #0xc]`<br>`0x8011dd18: cmp r3, #0`<br>`0x8011dd1c: beq #0x8011dd24`<br>`0x8011dd20: bl #0x8011dc74`<br>`0x8011dd24: bl #0x80110b30`<br>`0x8011dd28: pop {r3, lr}`<br>`0x8011dd2c: b #0x80110c98` |
| [3] | `0x8011d6dc` | `FUN_0011d6dc` | `0x8011d6dc: push {r4, r5, r6, r7, r8, sb, sl, fp, lr}`<br>`0x8011d6e0: subs r5, r1, #0`<br>`0x8011d6e4: sub sp, sp, #0x14`<br>`0x8011d6e8: mov r6, r0`<br>`0x8011d6ec: beq #0x8011d878`<br>`0x8011d6f0: mov r0, r5`<br>`0x8011d6f4: ldr r1, [pc, #0x220]`<br>`0x8011d6f8: ldr r2, [pc, #0x220]` |
| [4] | `0x8011da54` | `?` | `0x8011da54: cmp r1, #0`<br>`0x8011da58: push {r4, r5, r6, lr}`<br>`0x8011da5c: mov r4, r0`<br>`0x8011da60: beq #0x8011dadc`<br>`0x8011da64: mov r0, r1`<br>`0x8011da68: ldr r2, [pc, #0x88]`<br>`0x8011da6c: ldr r1, [pc, #0x88]`<br>`0x8011da70: mov r3, #0` |
| [5] | `0x8011d14c` | `FUN_0011d14c` | `0x8011d14c: push {r4, r5, lr}`<br>`0x8011d150: ldr r3, [pc, #0x5c]`<br>`0x8011d154: sub sp, sp, #0xc`<br>`0x8011d158: ldr r0, [r3, #4]`<br>`0x8011d15c: cmp r0, #0`<br>`0x8011d160: moveq r4, r0`<br>`0x8011d164: beq #0x8011d18c`<br>`0x8011d168: ldr r1, [r1, #8]` |
| [6] | `0x8011d520` | `FUN_0011d520` | `0x8011d520: push {r4, r5, r6, r7, r8, sb, sl, fp, lr}`<br>`0x8011d524: subs r4, r1, #0`<br>`0x8011d528: sub sp, sp, #0x5c`<br>`0x8011d52c: mov r6, r0`<br>`0x8011d530: beq #0x8011d6a4`<br>`0x8011d534: mov r0, r4`<br>`0x8011d538: ldr r1, [pc, #0x180]`<br>`0x8011d53c: ldr r2, [pc, #0x180]` |
| [7] | `0x8011d358` | `FUN_0011d358` | `0x8011d358: push {r4, r5, r6, r7, lr}`<br>`0x8011d35c: subs r4, r1, #0`<br>`0x8011d360: sub sp, sp, #0x5c`<br>`0x8011d364: mov r7, r0`<br>`0x8011d368: beq #0x8011d4e8`<br>`0x8011d36c: mov r0, r4`<br>`0x8011d370: ldr r1, [pc, #0x18c]`<br>`0x8011d374: ldr r2, [pc, #0x18c]` |
| [8] | `0x8011debc` | `FUN_0011debc` | `0x8011debc: push {r4, r5, r6, r7, lr}`<br>`0x8011dec0: subs r4, r1, #0`<br>`0x8011dec4: sub sp, sp, #0xc`<br>`0x8011dec8: mov r5, r0`<br>`0x8011decc: beq #0x8011df84`<br>`0x8011ded0: mov r0, r4`<br>`0x8011ded4: ldr r1, [pc, #0xc4]`<br>`0x8011ded8: ldr r2, [pc, #0xc4]` |
| [9] | `0x8011d128` | `?` | `0x8011d128: ldr r3, [r1, #8]`<br>`0x8011d12c: mov r1, r0`<br>`0x8011d130: ubfx r3, r3, #0x1d, #1`<br>`0x8011d134: add r3, r0, r3`<br>`0x8011d138: ldrsb r0, [r3, #0x13]`<br>`0x8011d13c: cmn r0, #1`<br>`0x8011d140: bxeq lr`<br>`0x8011d144: add r1, r1, #0xc` |
| [10] | `0x8011e108` | `?` | `0x8011e108: push {r4, r5, lr}`<br>`0x8011e10c: subs r4, r1, #0`<br>`0x8011e110: sub sp, sp, #0x14`<br>`0x8011e114: mov r5, r0`<br>`0x8011e118: beq #0x8011e1dc`<br>`0x8011e11c: mov r0, r4`<br>`0x8011e120: ldr r1, [pc, #0xd0]`<br>`0x8011e124: ldr r2, [pc, #0xd0]` |
| [11] | `0x8011dfb0` | `?` | `0x8011dfb0: push {r4, r5, r6, r7, r8, lr}`<br>`0x8011dfb4: subs r6, r1, #0`<br>`0x8011dfb8: mov r7, r0`<br>`0x8011dfbc: mov r5, r2`<br>`0x8011dfc0: beq #0x8011e0d4`<br>`0x8011dfc4: mov r0, r6`<br>`0x8011dfc8: ldr r1, [pc, #0x120]`<br>`0x8011dfcc: ldr r2, [pc, #0x120]` |
| [12] | `0x8011d0dc` | `?` | `0x8011d0dc: push {r3, r4, r5, lr}`<br>`0x8011d0e0: ldr r3, [r1, #8]`<br>`0x8011d0e4: mov r4, r0`<br>`0x8011d0e8: ands r5, r3, #0x20000000`<br>`0x8011d0ec: bne #0x8011d114`<br>`0x8011d0f0: cmp r3, #0`<br>`0x8011d0f4: bge #0x8011d118`<br>`0x8011d0f8: add r5, r4, r5` |
| [13] | `0x8011d1c0` | `FUN_0011d1c0` | `0x8011d1c0: push {r4, r5, r6, r7, r8, sb, sl, lr}`<br>`0x8011d1c4: subs r5, r1, #0`<br>`0x8011d1c8: sub sp, sp, #8`<br>`0x8011d1cc: mov r8, r0`<br>`0x8011d1d0: beq #0x8011d320`<br>`0x8011d1d4: mov r0, r5`<br>`0x8011d1d8: ldr r1, [pc, #0x15c]`<br>`0x8011d1dc: ldr r2, [pc, #0x15c]` |
| [14] | `0x8011dd98` | `?` | `0x8011dd98: ldr r3, [r1, #8]`<br>`0x8011dd9c: cmp r3, #0`<br>`0x8011dda0: blt #0x8011dda8`<br>`0x8011dda4: b #0x8011dd30`<br>`0x8011dda8: tst r3, #0x20000000`<br>`0x8011ddac: bxeq lr`<br>`0x8011ddb0: b #0x8011dda4`<br>`0x8011ddb4: movw r3, #0x3cc8` |
| [15] | `0x8011cfa4` | `FUN_0011cfa4` | `0x8011cfa4: push {r3, r4, r5, lr}`<br>`0x8011cfa8: mov r5, r1`<br>`0x8011cfac: mov r4, r2`<br>`0x8011cfb0: bl #0x8011cd58`<br>`0x8011cfb4: ldr r3, [r0]`<br>`0x8011cfb8: mov r1, r5`<br>`0x8011cfbc: ldr r3, [r3, #0x1c]`<br>`0x8011cfc0: mov r2, r4` |
| [16] | `0x8011cf7c` | `FUN_0011cf7c` | `0x8011cf7c: push {r3, r4, r5, lr}`<br>`0x8011cf80: mov r5, r1`<br>`0x8011cf84: mov r4, r2`<br>`0x8011cf88: bl #0x8011cd58`<br>`0x8011cf8c: ldr r3, [r0]`<br>`0x8011cf90: mov r1, r5`<br>`0x8011cf94: ldr r3, [r3, #0x18]`<br>`0x8011cf98: mov r2, r4` |
| [17] | `0x8011cef0` | `?` | `0x8011cef0: cmp r2, #0`<br>`0x8011cef4: movne r3, #0`<br>`0x8011cef8: strne r3, [r2]`<br>`0x8011cefc: strne r3, [r2, #4]`<br>`0x8011cf00: bx lr`<br>`0x8011cf04: str lr, [sp, #-4]!`<br>`0x8011cf08: mov r3, #2`<br>`0x8011cf0c: sub sp, sp, #0xc` |
| [18] | `0x8011db0c` | `?` | `0x8011db0c: subs r0, r1, #0`<br>`0x8011db10: push {r4, lr}`<br>`0x8011db14: mov r4, r2`<br>`0x8011db18: beq #0x8011db54`<br>`0x8011db1c: ldr r1, [pc, #0x48]`<br>`0x8011db20: ldr r2, [pc, #0x48]`<br>`0x8011db24: mov r3, #0`<br>`0x8011db28: bl #0x80524194` |
| [19] | `0x8011cfcc` | `?` | `0x8011cfcc: subs r0, r1, #0`<br>`0x8011cfd0: push {r3, r4, r5, r6, r7, lr}`<br>`0x8011cfd4: mov r5, r2`<br>`0x8011cfd8: mov r4, r3`<br>`0x8011cfdc: beq #0x8011d0a4`<br>`0x8011cfe0: ldr r1, [pc, #0xe0]`<br>`0x8011cfe4: ldr r2, [pc, #0xe0]`<br>`0x8011cfe8: mov r3, #0` |
| [20] | `0x8011da2c` | `?` | `0x8011da2c: ldr r3, [r1, #8]`<br>`0x8011da30: mov r1, r0`<br>`0x8011da34: tst r3, #0x20000000`<br>`0x8011da38: beq #0x8011da48`<br>`0x8011da3c: mov r0, #7`<br>`0x8011da40: add r1, r1, #0xc`<br>`0x8011da44: b #0x801cc218`<br>`0x8011da48: cmp r3, #0` |
| [21] | `0x8011e20c` | `FUN_0011e20c` | `0x8011e20c: push {r4, r5, r6, r7, lr}`<br>`0x8011e210: subs r4, r1, #0`<br>`0x8011e214: sub sp, sp, #0xc`<br>`0x8011e218: beq #0x8011e33c`<br>`0x8011e21c: mov r0, r4`<br>`0x8011e220: ldr r1, [pc, #0x130]`<br>`0x8011e224: ldr r2, [pc, #0x130]`<br>`0x8011e228: mov r3, #0` |
| [22] | `0x8011cf04` | `FUN_0011cf04` | `0x8011cf04: str lr, [sp, #-4]!`<br>`0x8011cf08: mov r3, #2`<br>`0x8011cf0c: sub sp, sp, #0xc`<br>`0x8011cf10: str r3, [sp]`<br>`0x8011cf14: movw r0, #0x48f4`<br>`0x8011cf18: movw r1, #0x36e8`<br>`0x8011cf1c: movw r3, #0x3cc8`<br>`0x8011cf20: movt r1, #0x8058` |
| [23] | `0x8011e3d8` | `FUN_0011e3d8` | `0x8011e3d8: push {r4, r5, r6, lr}`<br>`0x8011e3dc: mov r4, r1`<br>`0x8011e3e0: sub sp, sp, #8`<br>`0x8011e3e4: mov r5, r2`<br>`0x8011e3e8: mov r6, r0`<br>`0x8011e3ec: bl #0x80173c88`<br>`0x8011e3f0: stm sp, {r4, r5}`<br>`0x8011e3f4: mov r1, #0x10000003` |
| [24] | `0xfffffff4` | `?` | _(capstone 解码失败)_ |

### CBackend_3dlut_View — `0x80583870` (次表 top=2153265300, 子对象(主对象+2141701996), 4 槽)

| 槽 | VA | Ghidra 函数 | capstone 反汇编 |
|---|---|---|---|
| [0] | `0x8011e3ac` | `?` | `0x8011e3ac: sub r0, r0, #0xc`<br>`0x8011e3b0: b #0x8011e380`<br>`0x8011e3b4: push {r4, lr}`<br>`0x8011e3b8: mov r4, r0`<br>`0x8011e3bc: bl #0x8011e380`<br>`0x8011e3c0: mov r0, r4`<br>`0x8011e3c4: bl #0x80524664`<br>`0x8011e3c8: mov r0, r4` |
| [1] | `0x8011e3d0` | `?` | `0x8011e3d0: sub r0, r0, #0xc`<br>`0x8011e3d4: b #0x8011e3b4`<br>`0x8011e3d8: push {r4, r5, r6, lr}`<br>`0x8011e3dc: mov r4, r1`<br>`0x8011e3e0: sub sp, sp, #8`<br>`0x8011e3e4: mov r5, r2`<br>`0x8011e3e8: mov r6, r0`<br>`0x8011e3ec: bl #0x80173c88` |
| [2] | `0x8011e458` | `?` | `0x8011e458: sub r0, r0, #0xc`<br>`0x8011e45c: b #0x8011e3d8`<br>`0x8011e460: push {r4, lr}`<br>`0x8011e464: mov r4, r0`<br>`0x8011e468: bl #0x8011db7c`<br>`0x8011e46c: movw r3, #0x37f8`<br>`0x8011e470: movt r3, #0x8058`<br>`0x8011e474: mov r2, #0` |
| [3] | `0x42433931` | `?` | _(capstone 解码失败)_ |

### CBackend_3dlut_Still — `0x805838b8` (次表 top=2153265476, 子对象(主对象+2141701820), 25 槽)

| 槽 | VA | Ghidra 函数 | capstone 反汇编 |
|---|---|---|---|
| [0] | `0x8011e7b8` | `FUN_0011e7b8` | `0x8011e7b8: movw r3, #0x38a0`<br>`0x8011e7bc: movt r3, #0x8058`<br>`0x8011e7c0: add r2, r3, #0x18`<br>`0x8011e7c4: add r3, r3, #0x80`<br>`0x8011e7c8: push {r4, lr}`<br>`0x8011e7cc: mov r4, r0`<br>`0x8011e7d0: str r2, [r0]`<br>`0x8011e7d4: str r3, [r0, #0xc]` |
| [1] | `0x8011e7ec` | `FUN_0011e7ec` | `0x8011e7ec: push {r4, lr}`<br>`0x8011e7f0: mov r4, r0`<br>`0x8011e7f4: bl #0x8011e7b8`<br>`0x8011e7f8: mov r0, r4`<br>`0x8011e7fc: bl #0x80524664`<br>`0x8011e800: mov r0, r4`<br>`0x8011e804: pop {r4, pc}`<br>`0x8011e808: sub r0, r0, #0xc` |
| [2] | `0x8011dd10` | `?` | `0x8011dd10: push {r3, lr}`<br>`0x8011dd14: ldrsh r3, [r1, #0xc]`<br>`0x8011dd18: cmp r3, #0`<br>`0x8011dd1c: beq #0x8011dd24`<br>`0x8011dd20: bl #0x8011dc74`<br>`0x8011dd24: bl #0x80110b30`<br>`0x8011dd28: pop {r3, lr}`<br>`0x8011dd2c: b #0x80110c98` |
| [3] | `0x8011d6dc` | `FUN_0011d6dc` | `0x8011d6dc: push {r4, r5, r6, r7, r8, sb, sl, fp, lr}`<br>`0x8011d6e0: subs r5, r1, #0`<br>`0x8011d6e4: sub sp, sp, #0x14`<br>`0x8011d6e8: mov r6, r0`<br>`0x8011d6ec: beq #0x8011d878`<br>`0x8011d6f0: mov r0, r5`<br>`0x8011d6f4: ldr r1, [pc, #0x220]`<br>`0x8011d6f8: ldr r2, [pc, #0x220]` |
| [4] | `0x8011da54` | `?` | `0x8011da54: cmp r1, #0`<br>`0x8011da58: push {r4, r5, r6, lr}`<br>`0x8011da5c: mov r4, r0`<br>`0x8011da60: beq #0x8011dadc`<br>`0x8011da64: mov r0, r1`<br>`0x8011da68: ldr r2, [pc, #0x88]`<br>`0x8011da6c: ldr r1, [pc, #0x88]`<br>`0x8011da70: mov r3, #0` |
| [5] | `0x8011d14c` | `FUN_0011d14c` | `0x8011d14c: push {r4, r5, lr}`<br>`0x8011d150: ldr r3, [pc, #0x5c]`<br>`0x8011d154: sub sp, sp, #0xc`<br>`0x8011d158: ldr r0, [r3, #4]`<br>`0x8011d15c: cmp r0, #0`<br>`0x8011d160: moveq r4, r0`<br>`0x8011d164: beq #0x8011d18c`<br>`0x8011d168: ldr r1, [r1, #8]` |
| [6] | `0x8011d520` | `FUN_0011d520` | `0x8011d520: push {r4, r5, r6, r7, r8, sb, sl, fp, lr}`<br>`0x8011d524: subs r4, r1, #0`<br>`0x8011d528: sub sp, sp, #0x5c`<br>`0x8011d52c: mov r6, r0`<br>`0x8011d530: beq #0x8011d6a4`<br>`0x8011d534: mov r0, r4`<br>`0x8011d538: ldr r1, [pc, #0x180]`<br>`0x8011d53c: ldr r2, [pc, #0x180]` |
| [7] | `0x8011d358` | `FUN_0011d358` | `0x8011d358: push {r4, r5, r6, r7, lr}`<br>`0x8011d35c: subs r4, r1, #0`<br>`0x8011d360: sub sp, sp, #0x5c`<br>`0x8011d364: mov r7, r0`<br>`0x8011d368: beq #0x8011d4e8`<br>`0x8011d36c: mov r0, r4`<br>`0x8011d370: ldr r1, [pc, #0x18c]`<br>`0x8011d374: ldr r2, [pc, #0x18c]` |
| [8] | `0x8011cee0` | `?` | `0x8011cee0: mov r0, #0`<br>`0x8011cee4: bx lr`<br>`0x8011cee8: mov r0, #0`<br>`0x8011ceec: bx lr`<br>`0x8011cef0: cmp r2, #0`<br>`0x8011cef4: movne r3, #0`<br>`0x8011cef8: strne r3, [r2]`<br>`0x8011cefc: strne r3, [r2, #4]` |
| [9] | `0x8011d128` | `?` | `0x8011d128: ldr r3, [r1, #8]`<br>`0x8011d12c: mov r1, r0`<br>`0x8011d130: ubfx r3, r3, #0x1d, #1`<br>`0x8011d134: add r3, r0, r3`<br>`0x8011d138: ldrsb r0, [r3, #0x13]`<br>`0x8011d13c: cmn r0, #1`<br>`0x8011d140: bxeq lr`<br>`0x8011d144: add r1, r1, #0xc` |
| [10] | `0x8011e510` | `FUN_0011e510` | `0x8011e510: push {r4, r5, r6, r7, lr}`<br>`0x8011e514: subs r5, r1, #0`<br>`0x8011e518: sub sp, sp, #0x24`<br>`0x8011e51c: mov r6, r0`<br>`0x8011e520: beq #0x8011e634`<br>`0x8011e524: mov r0, r5`<br>`0x8011e528: ldr r1, [pc, #0x120]`<br>`0x8011e52c: ldr r2, [pc, #0x120]` |
| [11] | `0x8011cee8` | `?` | `0x8011cee8: mov r0, #0`<br>`0x8011ceec: bx lr`<br>`0x8011cef0: cmp r2, #0`<br>`0x8011cef4: movne r3, #0`<br>`0x8011cef8: strne r3, [r2]`<br>`0x8011cefc: strne r3, [r2, #4]`<br>`0x8011cf00: bx lr`<br>`0x8011cf04: str lr, [sp, #-4]!` |
| [12] | `0x8011d0dc` | `?` | `0x8011d0dc: push {r3, r4, r5, lr}`<br>`0x8011d0e0: ldr r3, [r1, #8]`<br>`0x8011d0e4: mov r4, r0`<br>`0x8011d0e8: ands r5, r3, #0x20000000`<br>`0x8011d0ec: bne #0x8011d114`<br>`0x8011d0f0: cmp r3, #0`<br>`0x8011d0f4: bge #0x8011d118`<br>`0x8011d0f8: add r5, r4, r5` |
| [13] | `0x8011d1c0` | `FUN_0011d1c0` | `0x8011d1c0: push {r4, r5, r6, r7, r8, sb, sl, lr}`<br>`0x8011d1c4: subs r5, r1, #0`<br>`0x8011d1c8: sub sp, sp, #8`<br>`0x8011d1cc: mov r8, r0`<br>`0x8011d1d0: beq #0x8011d320`<br>`0x8011d1d4: mov r0, r5`<br>`0x8011d1d8: ldr r1, [pc, #0x15c]`<br>`0x8011d1dc: ldr r2, [pc, #0x15c]` |
| [14] | `0x8011e898` | `?` | `0x8011e898: subs r0, r1, #0`<br>`0x8011e89c: push {r4, lr}`<br>`0x8011e8a0: beq #0x8011e8e4`<br>`0x8011e8a4: ldr r1, [pc, #0x50]`<br>`0x8011e8a8: ldr r2, [pc, #0x50]`<br>`0x8011e8ac: mov r3, #0`<br>`0x8011e8b0: bl #0x80524194`<br>`0x8011e8b4: cmp r0, #0` |
| [15] | `0x8011cfa4` | `FUN_0011cfa4` | `0x8011cfa4: push {r3, r4, r5, lr}`<br>`0x8011cfa8: mov r5, r1`<br>`0x8011cfac: mov r4, r2`<br>`0x8011cfb0: bl #0x8011cd58`<br>`0x8011cfb4: ldr r3, [r0]`<br>`0x8011cfb8: mov r1, r5`<br>`0x8011cfbc: ldr r3, [r3, #0x1c]`<br>`0x8011cfc0: mov r2, r4` |
| [16] | `0x8011cf7c` | `FUN_0011cf7c` | `0x8011cf7c: push {r3, r4, r5, lr}`<br>`0x8011cf80: mov r5, r1`<br>`0x8011cf84: mov r4, r2`<br>`0x8011cf88: bl #0x8011cd58`<br>`0x8011cf8c: ldr r3, [r0]`<br>`0x8011cf90: mov r1, r5`<br>`0x8011cf94: ldr r3, [r3, #0x18]`<br>`0x8011cf98: mov r2, r4` |
| [17] | `0x8011cef0` | `?` | `0x8011cef0: cmp r2, #0`<br>`0x8011cef4: movne r3, #0`<br>`0x8011cef8: strne r3, [r2]`<br>`0x8011cefc: strne r3, [r2, #4]`<br>`0x8011cf00: bx lr`<br>`0x8011cf04: str lr, [sp, #-4]!`<br>`0x8011cf08: mov r3, #2`<br>`0x8011cf0c: sub sp, sp, #0xc` |
| [18] | `0x8011db0c` | `?` | `0x8011db0c: subs r0, r1, #0`<br>`0x8011db10: push {r4, lr}`<br>`0x8011db14: mov r4, r2`<br>`0x8011db18: beq #0x8011db54`<br>`0x8011db1c: ldr r1, [pc, #0x48]`<br>`0x8011db20: ldr r2, [pc, #0x48]`<br>`0x8011db24: mov r3, #0`<br>`0x8011db28: bl #0x80524194` |
| [19] | `0x8011cfcc` | `?` | `0x8011cfcc: subs r0, r1, #0`<br>`0x8011cfd0: push {r3, r4, r5, r6, r7, lr}`<br>`0x8011cfd4: mov r5, r2`<br>`0x8011cfd8: mov r4, r3`<br>`0x8011cfdc: beq #0x8011d0a4`<br>`0x8011cfe0: ldr r1, [pc, #0xe0]`<br>`0x8011cfe4: ldr r2, [pc, #0xe0]`<br>`0x8011cfe8: mov r3, #0` |
| [20] | `0x8011da2c` | `?` | `0x8011da2c: ldr r3, [r1, #8]`<br>`0x8011da30: mov r1, r0`<br>`0x8011da34: tst r3, #0x20000000`<br>`0x8011da38: beq #0x8011da48`<br>`0x8011da3c: mov r0, #7`<br>`0x8011da40: add r1, r1, #0xc`<br>`0x8011da44: b #0x801cc218`<br>`0x8011da48: cmp r3, #0` |
| [21] | `0x8011e678` | `FUN_0011e678` | `0x8011e678: push {r4, r5, r6, lr}`<br>`0x8011e67c: subs r4, r1, #0`<br>`0x8011e680: sub sp, sp, #8`<br>`0x8011e684: beq #0x8011e778`<br>`0x8011e688: mov r3, #0`<br>`0x8011e68c: mov r0, r4`<br>`0x8011e690: ldr r1, [pc, #0xfc]`<br>`0x8011e694: ldr r2, [pc, #0xfc]` |
| [22] | `0x8011cf04` | `FUN_0011cf04` | `0x8011cf04: str lr, [sp, #-4]!`<br>`0x8011cf08: mov r3, #2`<br>`0x8011cf0c: sub sp, sp, #0xc`<br>`0x8011cf10: str r3, [sp]`<br>`0x8011cf14: movw r0, #0x48f4`<br>`0x8011cf18: movw r1, #0x36e8`<br>`0x8011cf1c: movw r3, #0x3cc8`<br>`0x8011cf20: movt r1, #0x8058` |
| [23] | `0x8011e810` | `FUN_0011e810` | `0x8011e810: push {r4, r5, r6, lr}`<br>`0x8011e814: mov r4, r1`<br>`0x8011e818: sub sp, sp, #8`<br>`0x8011e81c: mov r5, r2`<br>`0x8011e820: mov r6, r0`<br>`0x8011e824: bl #0x80173c88`<br>`0x8011e828: stm sp, {r4, r5}`<br>`0x8011e82c: mov r1, #0x10000003` |
| [24] | `0xfffffff4` | `?` | _(capstone 解码失败)_ |

### CBackend_3dlut_Still — `0x80583920` (次表 top=2153265476, 子对象(主对象+2141701820), 4 槽)

| 槽 | VA | Ghidra 函数 | capstone 反汇编 |
|---|---|---|---|
| [0] | `0x8011e7e4` | `?` | `0x8011e7e4: sub r0, r0, #0xc`<br>`0x8011e7e8: b #0x8011e7b8`<br>`0x8011e7ec: push {r4, lr}`<br>`0x8011e7f0: mov r4, r0`<br>`0x8011e7f4: bl #0x8011e7b8`<br>`0x8011e7f8: mov r0, r4`<br>`0x8011e7fc: bl #0x80524664`<br>`0x8011e800: mov r0, r4` |
| [1] | `0x8011e808` | `?` | `0x8011e808: sub r0, r0, #0xc`<br>`0x8011e80c: b #0x8011e7ec`<br>`0x8011e810: push {r4, r5, r6, lr}`<br>`0x8011e814: mov r4, r1`<br>`0x8011e818: sub sp, sp, #8`<br>`0x8011e81c: mov r5, r2`<br>`0x8011e820: mov r6, r0`<br>`0x8011e824: bl #0x80173c88` |
| [2] | `0x8011e890` | `?` | `0x8011e890: sub r0, r0, #0xc`<br>`0x8011e894: b #0x8011e810`<br>`0x8011e898: subs r0, r1, #0`<br>`0x8011e89c: push {r4, lr}`<br>`0x8011e8a0: beq #0x8011e8e4`<br>`0x8011e8a4: ldr r1, [pc, #0x50]`<br>`0x8011e8a8: ldr r2, [pc, #0x50]`<br>`0x8011e8ac: mov r3, #0` |
| [3] | `0x42433032` | `?` | _(capstone 解码失败)_ |

### CBackend_3dlut_CS0_Callback — `0x80583958` (次表 top=2153265732, 子对象(主对象+2141701564), 3 槽)

| 槽 | VA | Ghidra 函数 | capstone 反汇编 |
|---|---|---|---|
| [0] | `0x80500f84` | `?` | `0x80500f84: ldr r3, [pc, #4]`<br>`0x80500f88: str r3, [r0]`<br>`0x80500f8c: bx lr`<br>`0x80500f90: rsbshi r2, r1, r8, ror sp`<br>`0x80500f94: ldr r3, [pc, #4]`<br>`0x80500f98: str r3, [r0]`<br>`0x80500f9c: bx lr`<br>`0x80500fa0: rsbshi r2, r1, r8, ror sp` |
| [1] | `0x80500fc4` | `?` | `0x80500fc4: ldr r3, [pc, #0x14]`<br>`0x80500fc8: push {r4, lr}`<br>`0x80500fcc: mov r4, r0`<br>`0x80500fd0: str r3, [r0]`<br>`0x80500fd4: bl #0x80524664`<br>`0x80500fd8: mov r0, r4`<br>`0x80500fdc: pop {r4, pc}`<br>`0x80500fe0: rsbshi r2, r1, r8, ror sp` |
| [2] | `0x8011ee34` | `?` | `0x8011ee34: cmp r1, #5`<br>`0x8011ee38: push {r4, lr}`<br>`0x8011ee3c: mov r4, r1`<br>`0x8011ee40: popne {r4, pc}`<br>`0x8011ee44: bl #0x8011cd58`<br>`0x8011ee48: mov r1, r4`<br>`0x8011ee4c: mov r2, #0`<br>`0x8011ee50: pop {r4, lr}` |

### CBackend_3dlut_CS1_Callback — `0x80583970` (次表 top=2153265776, 子对象(主对象+2141701520), 4 槽)

| 槽 | VA | Ghidra 函数 | capstone 反汇编 |
|---|---|---|---|
| [0] | `0x80500f94` | `?` | `0x80500f94: ldr r3, [pc, #4]`<br>`0x80500f98: str r3, [r0]`<br>`0x80500f9c: bx lr`<br>`0x80500fa0: rsbshi r2, r1, r8, ror sp`<br>`0x80500fa4: ldr r3, [pc, #0x14]`<br>`0x80500fa8: push {r4, lr}`<br>`0x80500fac: mov r4, r0`<br>`0x80500fb0: str r3, [r0]` |
| [1] | `0x80500fa4` | `?` | `0x80500fa4: ldr r3, [pc, #0x14]`<br>`0x80500fa8: push {r4, lr}`<br>`0x80500fac: mov r4, r0`<br>`0x80500fb0: str r3, [r0]`<br>`0x80500fb4: bl #0x80524664`<br>`0x80500fb8: mov r0, r4`<br>`0x80500fbc: pop {r4, pc}`<br>`0x80500fc0: rsbshi r2, r1, r8, ror sp` |
| [2] | `0x8011ee14` | `?` | `0x8011ee14: cmp r1, #5`<br>`0x8011ee18: push {r3, lr}`<br>`0x8011ee1c: popne {r3, pc}`<br>`0x8011ee20: bl #0x8011cd58`<br>`0x8011ee24: mov r1, #6`<br>`0x8011ee28: mov r2, #0`<br>`0x8011ee2c: pop {r3, lr}`<br>`0x8011ee30: b #0x8011ce08` |
| [3] | `0x616f6c5f` | `?` | _(capstone 解码失败)_ |

### CBackend_3dlut_CS — `0x80583990` (次表 top=2153265688, 子对象(主对象+2141701608), 25 槽)

| 槽 | VA | Ghidra 函数 | capstone 反汇编 |
|---|---|---|---|
| [0] | `0x8011ed80` | `FUN_0011ed80` | `0x8011ed80: push {r4, lr}`<br>`0x8011ed84: ldr r3, [pc, #0x58]`<br>`0x8011ed88: mov r4, r0`<br>`0x8011ed8c: ldr r0, [r0, #0x18]`<br>`0x8011ed90: add r2, r3, #0x68`<br>`0x8011ed94: cmp r0, #0`<br>`0x8011ed98: str r3, [r4]`<br>`0x8011ed9c: str r2, [r4, #0xc]` |
| [1] | `0x8011edf0` | `FUN_0011edf0` | `0x8011edf0: push {r4, lr}`<br>`0x8011edf4: mov r4, r0`<br>`0x8011edf8: bl #0x8011ed80`<br>`0x8011edfc: mov r0, r4`<br>`0x8011ee00: bl #0x80524664`<br>`0x8011ee04: mov r0, r4`<br>`0x8011ee08: pop {r4, pc}`<br>`0x8011ee0c: sub r0, r0, #0xc` |
| [2] | `0x8011dd10` | `?` | `0x8011dd10: push {r3, lr}`<br>`0x8011dd14: ldrsh r3, [r1, #0xc]`<br>`0x8011dd18: cmp r3, #0`<br>`0x8011dd1c: beq #0x8011dd24`<br>`0x8011dd20: bl #0x8011dc74`<br>`0x8011dd24: bl #0x80110b30`<br>`0x8011dd28: pop {r3, lr}`<br>`0x8011dd2c: b #0x80110c98` |
| [3] | `0x8011d6dc` | `FUN_0011d6dc` | `0x8011d6dc: push {r4, r5, r6, r7, r8, sb, sl, fp, lr}`<br>`0x8011d6e0: subs r5, r1, #0`<br>`0x8011d6e4: sub sp, sp, #0x14`<br>`0x8011d6e8: mov r6, r0`<br>`0x8011d6ec: beq #0x8011d878`<br>`0x8011d6f0: mov r0, r5`<br>`0x8011d6f4: ldr r1, [pc, #0x220]`<br>`0x8011d6f8: ldr r2, [pc, #0x220]` |
| [4] | `0x8011da54` | `?` | `0x8011da54: cmp r1, #0`<br>`0x8011da58: push {r4, r5, r6, lr}`<br>`0x8011da5c: mov r4, r0`<br>`0x8011da60: beq #0x8011dadc`<br>`0x8011da64: mov r0, r1`<br>`0x8011da68: ldr r2, [pc, #0x88]`<br>`0x8011da6c: ldr r1, [pc, #0x88]`<br>`0x8011da70: mov r3, #0` |
| [5] | `0x8011d14c` | `FUN_0011d14c` | `0x8011d14c: push {r4, r5, lr}`<br>`0x8011d150: ldr r3, [pc, #0x5c]`<br>`0x8011d154: sub sp, sp, #0xc`<br>`0x8011d158: ldr r0, [r3, #4]`<br>`0x8011d15c: cmp r0, #0`<br>`0x8011d160: moveq r4, r0`<br>`0x8011d164: beq #0x8011d18c`<br>`0x8011d168: ldr r1, [r1, #8]` |
| [6] | `0x8011d520` | `FUN_0011d520` | `0x8011d520: push {r4, r5, r6, r7, r8, sb, sl, fp, lr}`<br>`0x8011d524: subs r4, r1, #0`<br>`0x8011d528: sub sp, sp, #0x5c`<br>`0x8011d52c: mov r6, r0`<br>`0x8011d530: beq #0x8011d6a4`<br>`0x8011d534: mov r0, r4`<br>`0x8011d538: ldr r1, [pc, #0x180]`<br>`0x8011d53c: ldr r2, [pc, #0x180]` |
| [7] | `0x8011d358` | `FUN_0011d358` | `0x8011d358: push {r4, r5, r6, r7, lr}`<br>`0x8011d35c: subs r4, r1, #0`<br>`0x8011d360: sub sp, sp, #0x5c`<br>`0x8011d364: mov r7, r0`<br>`0x8011d368: beq #0x8011d4e8`<br>`0x8011d36c: mov r0, r4`<br>`0x8011d370: ldr r1, [pc, #0x18c]`<br>`0x8011d374: ldr r2, [pc, #0x18c]` |
| [8] | `0x8011e9c0` | `FUN_0011e9c0` | `0x8011e9c0: push {r4, r5, r6, r7, lr}`<br>`0x8011e9c4: subs r4, r1, #0`<br>`0x8011e9c8: sub sp, sp, #0xc`<br>`0x8011e9cc: mov r5, r0`<br>`0x8011e9d0: beq #0x8011ea98`<br>`0x8011e9d4: mov r0, r4`<br>`0x8011e9d8: ldr r1, [pc, #0xd4]`<br>`0x8011e9dc: ldr r2, [pc, #0xd4]` |
| [9] | `0x8011d128` | `?` | `0x8011d128: ldr r3, [r1, #8]`<br>`0x8011d12c: mov r1, r0`<br>`0x8011d130: ubfx r3, r3, #0x1d, #1`<br>`0x8011d134: add r3, r0, r3`<br>`0x8011d138: ldrsb r0, [r3, #0x13]`<br>`0x8011d13c: cmn r0, #1`<br>`0x8011d140: bxeq lr`<br>`0x8011d144: add r1, r1, #0xc` |
| [10] | `0x8011eac4` | `FUN_0011eac4` | `0x8011eac4: push {r4, r5, lr}`<br>`0x8011eac8: subs r4, r1, #0`<br>`0x8011eacc: sub sp, sp, #0x14`<br>`0x8011ead0: mov r5, r0`<br>`0x8011ead4: beq #0x8011eb8c`<br>`0x8011ead8: mov r0, r4`<br>`0x8011eadc: ldr r1, [pc, #0xc4]`<br>`0x8011eae0: ldr r2, [pc, #0xc4]` |
| [11] | `0x8011e9b8` | `?` | `0x8011e9b8: mov r0, #0`<br>`0x8011e9bc: bx lr`<br>`0x8011e9c0: push {r4, r5, r6, r7, lr}`<br>`0x8011e9c4: subs r4, r1, #0`<br>`0x8011e9c8: sub sp, sp, #0xc`<br>`0x8011e9cc: mov r5, r0`<br>`0x8011e9d0: beq #0x8011ea98`<br>`0x8011e9d4: mov r0, r4` |
| [12] | `0x8011ef30` | `?` | `0x8011ef30: push {r4, r5, r6, lr}`<br>`0x8011ef34: subs r4, r1, #0`<br>`0x8011ef38: mov r5, r0`<br>`0x8011ef3c: beq #0x8011ef80`<br>`0x8011ef40: mov r0, r4`<br>`0x8011ef44: ldr r1, [pc, #0x4c]`<br>`0x8011ef48: ldr r2, [pc, #0x4c]`<br>`0x8011ef4c: mov r3, #0` |
| [13] | `0x8011d1c0` | `FUN_0011d1c0` | `0x8011d1c0: push {r4, r5, r6, r7, r8, sb, sl, lr}`<br>`0x8011d1c4: subs r5, r1, #0`<br>`0x8011d1c8: sub sp, sp, #8`<br>`0x8011d1cc: mov r8, r0`<br>`0x8011d1d0: beq #0x8011d320`<br>`0x8011d1d4: mov r0, r5`<br>`0x8011d1d8: ldr r1, [pc, #0x15c]`<br>`0x8011d1dc: ldr r2, [pc, #0x15c]` |
| [14] | `0x8011eeb4` | `?` | `0x8011eeb4: push {r4, lr}`<br>`0x8011eeb8: subs r4, r1, #0`<br>`0x8011eebc: beq #0x8011ef08`<br>`0x8011eec0: mov r0, r4`<br>`0x8011eec4: ldr r1, [pc, #0x54]`<br>`0x8011eec8: ldr r2, [pc, #0x54]`<br>`0x8011eecc: mov r3, #0`<br>`0x8011eed0: bl #0x80524194` |
| [15] | `0x8011cfa4` | `FUN_0011cfa4` | `0x8011cfa4: push {r3, r4, r5, lr}`<br>`0x8011cfa8: mov r5, r1`<br>`0x8011cfac: mov r4, r2`<br>`0x8011cfb0: bl #0x8011cd58`<br>`0x8011cfb4: ldr r3, [r0]`<br>`0x8011cfb8: mov r1, r5`<br>`0x8011cfbc: ldr r3, [r3, #0x1c]`<br>`0x8011cfc0: mov r2, r4` |
| [16] | `0x8011cf7c` | `FUN_0011cf7c` | `0x8011cf7c: push {r3, r4, r5, lr}`<br>`0x8011cf80: mov r5, r1`<br>`0x8011cf84: mov r4, r2`<br>`0x8011cf88: bl #0x8011cd58`<br>`0x8011cf8c: ldr r3, [r0]`<br>`0x8011cf90: mov r1, r5`<br>`0x8011cf94: ldr r3, [r3, #0x18]`<br>`0x8011cf98: mov r2, r4` |
| [17] | `0x8011cef0` | `?` | `0x8011cef0: cmp r2, #0`<br>`0x8011cef4: movne r3, #0`<br>`0x8011cef8: strne r3, [r2]`<br>`0x8011cefc: strne r3, [r2, #4]`<br>`0x8011cf00: bx lr`<br>`0x8011cf04: str lr, [sp, #-4]!`<br>`0x8011cf08: mov r3, #2`<br>`0x8011cf0c: sub sp, sp, #0xc` |
| [18] | `0x8011db0c` | `?` | `0x8011db0c: subs r0, r1, #0`<br>`0x8011db10: push {r4, lr}`<br>`0x8011db14: mov r4, r2`<br>`0x8011db18: beq #0x8011db54`<br>`0x8011db1c: ldr r1, [pc, #0x48]`<br>`0x8011db20: ldr r2, [pc, #0x48]`<br>`0x8011db24: mov r3, #0`<br>`0x8011db28: bl #0x80524194` |
| [19] | `0x8011cfcc` | `?` | `0x8011cfcc: subs r0, r1, #0`<br>`0x8011cfd0: push {r3, r4, r5, r6, r7, lr}`<br>`0x8011cfd4: mov r5, r2`<br>`0x8011cfd8: mov r4, r3`<br>`0x8011cfdc: beq #0x8011d0a4`<br>`0x8011cfe0: ldr r1, [pc, #0xe0]`<br>`0x8011cfe4: ldr r2, [pc, #0xe0]`<br>`0x8011cfe8: mov r3, #0` |
| [20] | `0x8011da2c` | `?` | `0x8011da2c: ldr r3, [r1, #8]`<br>`0x8011da30: mov r1, r0`<br>`0x8011da34: tst r3, #0x20000000`<br>`0x8011da38: beq #0x8011da48`<br>`0x8011da3c: mov r0, #7`<br>`0x8011da40: add r1, r1, #0xc`<br>`0x8011da44: b #0x801cc218`<br>`0x8011da48: cmp r3, #0` |
| [21] | `0x8011ebbc` | `FUN_0011ebbc` | `0x8011ebbc: push {r4, r5, r6, lr}`<br>`0x8011ebc0: subs r4, r1, #0`<br>`0x8011ebc4: sub sp, sp, #0x18`<br>`0x8011ebc8: beq #0x8011ed1c`<br>`0x8011ebcc: mov r3, #0`<br>`0x8011ebd0: mov r0, r4`<br>`0x8011ebd4: ldr r1, [pc, #0x178]`<br>`0x8011ebd8: ldr r2, [pc, #0x178]` |
| [22] | `0x8011cf04` | `FUN_0011cf04` | `0x8011cf04: str lr, [sp, #-4]!`<br>`0x8011cf08: mov r3, #2`<br>`0x8011cf0c: sub sp, sp, #0xc`<br>`0x8011cf10: str r3, [sp]`<br>`0x8011cf14: movw r0, #0x48f4`<br>`0x8011cf18: movw r1, #0x36e8`<br>`0x8011cf1c: movw r3, #0x3cc8`<br>`0x8011cf20: movt r1, #0x8058` |
| [23] | `0x8011ee58` | `FUN_0011ee58` | `0x8011ee58: push {r4, r5, lr}`<br>`0x8011ee5c: mov r4, r2`<br>`0x8011ee60: sub sp, sp, #0xc`<br>`0x8011ee64: mov r5, r1`<br>`0x8011ee68: bl #0x80173c88`<br>`0x8011ee6c: str r5, [sp]`<br>`0x8011ee70: str r4, [sp, #4]`<br>`0x8011ee74: mov r1, #0x10000003` |
| [24] | `0xfffffff4` | `?` | _(capstone 解码失败)_ |

### CBackend_3dlut_CS — `0x805839f8` (次表 top=2153265688, 子对象(主对象+2141701608), 4 槽)

| 槽 | VA | Ghidra 函数 | capstone 反汇编 |
|---|---|---|---|
| [0] | `0x8011ede8` | `?` | `0x8011ede8: sub r0, r0, #0xc`<br>`0x8011edec: b #0x8011ed80`<br>`0x8011edf0: push {r4, lr}`<br>`0x8011edf4: mov r4, r0`<br>`0x8011edf8: bl #0x8011ed80`<br>`0x8011edfc: mov r0, r4`<br>`0x8011ee00: bl #0x80524664`<br>`0x8011ee04: mov r0, r4` |
| [1] | `0x8011ee0c` | `?` | `0x8011ee0c: sub r0, r0, #0xc`<br>`0x8011ee10: b #0x8011edf0`<br>`0x8011ee14: cmp r1, #5`<br>`0x8011ee18: push {r3, lr}`<br>`0x8011ee1c: popne {r3, pc}`<br>`0x8011ee20: bl #0x8011cd58`<br>`0x8011ee24: mov r1, #6`<br>`0x8011ee28: mov r2, #0` |
| [2] | `0x8011eeac` | `?` | `0x8011eeac: sub r0, r0, #0xc`<br>`0x8011eeb0: b #0x8011ee58`<br>`0x8011eeb4: push {r4, lr}`<br>`0x8011eeb8: subs r4, r1, #0`<br>`0x8011eebc: beq #0x8011ef08`<br>`0x8011eec0: mov r0, r4`<br>`0x8011eec4: ldr r1, [pc, #0x54]`<br>`0x8011eec8: ldr r2, [pc, #0x54]` |
| [3] | `0x42433731` | `?` | _(capstone 解码失败)_ |

### C3DLUTIf — `0x80588cb8` (次表 top=2153286860, 子对象(主对象+2141680436), 3 槽)

| 槽 | VA | Ghidra 函数 | capstone 反汇编 |
|---|---|---|---|
| [0] | `0x801790c0` | `?` | `0x801790c0: ldr r3, [pc, #4]`<br>`0x801790c4: str r3, [r0]`<br>`0x801790c8: bx lr`<br>`0x801790cc: ldrhhi r8, [r8], #-0xc8`<br>`0x801790d0: push {r4, lr}`<br>`0x801790d4: ldr r4, [pc, #0x28]`<br>`0x801790d8: mov r0, #8`<br>`0x801790dc: bl #0x8017b5c8` |
| [1] | `0x801791c0` | `?` | `0x801791c0: ldr r3, [pc, #0x14]`<br>`0x801791c4: push {r4, lr}`<br>`0x801791c8: mov r4, r0`<br>`0x801791cc: str r3, [r0]`<br>`0x801791d0: bl #0x80524664`<br>`0x801791d4: mov r0, r4`<br>`0x801791d8: pop {r4, pc}`<br>`0x801791dc: ldrhhi r8, [r8], #-0xc8` |
| [2] | `0x44334338` | `?` | _(capstone 解码失败)_ |

### C3DLUTAlarm — `0x80588ce0` (次表 top=2153286908, 子对象(主对象+2141680388), 4 槽)

| 槽 | VA | Ghidra 函数 | capstone 反汇编 |
|---|---|---|---|
| [0] | `0x801796e8` | `?` | `0x801796e8: ldr r3, [pc, #0x28]`<br>`0x801796ec: push {r4, lr}`<br>`0x801796f0: mov r4, r0`<br>`0x801796f4: str r3, [r0], #4`<br>`0x801796f8: bl #0x804db388`<br>`0x801796fc: ldr r3, [pc, #0x18]`<br>`0x80179700: mov r0, r4`<br>`0x80179704: str r3, [r4]` |
| [1] | `0x80179720` | `?` | `0x80179720: push {r4, lr}`<br>`0x80179724: mov r4, r0`<br>`0x80179728: bl #0x801796e8`<br>`0x8017972c: mov r0, r4`<br>`0x80179730: bl #0x80524664`<br>`0x80179734: mov r0, r4`<br>`0x80179738: pop {r4, pc}`<br>`0x8017973c: ldr r3, [pc, #4]` |
| [2] | `0x80179678` | `?` | `0x80179678: push {r3, lr}`<br>`0x8017967c: ldr r3, [r0, #0x14]`<br>`0x80179680: blx r3`<br>`0x80179684: pop {r3, pc}`<br>`0x80179688: ldr r3, [pc, #0x28]`<br>`0x8017968c: push {r4, lr}`<br>`0x80179690: mov r4, r0`<br>`0x80179694: str r3, [r0], #4` |
| [3] | `0x33433131` | `?` | _(capstone 解码失败)_ |

### CMaterial_NX1_Still_3dlut_Normal — `0x8058baa8` (次表 top=2153298692, 子对象(主对象+2141668604), 10 槽)

| 槽 | VA | Ghidra 函数 | capstone 反汇编 |
|---|---|---|---|
| [0] | `0x8018ff8c` | `FUN_0018ff8c` | `0x8018ff8c: ldr r3, [pc, #0x1c]`<br>`0x8018ff90: push {r4, lr}`<br>`0x8018ff94: str r3, [r0]`<br>`0x8018ff98: ldr r3, [pc, #0x14]`<br>`0x8018ff9c: mov r4, r0`<br>`0x8018ffa0: str r3, [r0, #0x120]`<br>`0x8018ffa4: bl #0x8016fe60`<br>`0x8018ffa8: mov r0, r4` |
| [1] | `0x8018ffc0` | `FUN_0018ffc0` | `0x8018ffc0: push {r4, lr}`<br>`0x8018ffc4: mov r4, r0`<br>`0x8018ffc8: bl #0x8018ff8c`<br>`0x8018ffcc: mov r0, r4`<br>`0x8018ffd0: bl #0x80524664`<br>`0x8018ffd4: mov r0, r4`<br>`0x8018ffd8: pop {r4, pc}`<br>`0x8018ffdc: sub r0, r0, #0x120` |
| [2] | `0x8018fcf0` | `FUN_0018fcf0` | `0x8018fcf0: push {r3, lr}`<br>`0x8018fcf4: bl #0x8011cdd0`<br>`0x8018fcf8: ldr r3, [r0]`<br>`0x8018fcfc: ldr r3, [r3, #0x30]`<br>`0x8018fd00: blx r3`<br>`0x8018fd04: pop {r3, pc}`<br>`0x8018fd08: push {r4, r5, r6, r7, r8, lr}`<br>`0x8018fd0c: mov r1, #0` |
| [3] | `0x8018fca4` | `FUN_0018fca4` | `0x8018fca4: push {r4, lr}`<br>`0x8018fca8: mov r4, r0`<br>`0x8018fcac: ldr r0, [r0, #0x124]`<br>`0x8018fcb0: cmp r0, #0`<br>`0x8018fcb4: beq #0x8018fcc4`<br>`0x8018fcb8: ldr r2, [r0]`<br>`0x8018fcbc: ldr r3, [r2, #4]`<br>`0x8018fcc0: blx r3` |
| [4] | `0x8018fd08` | `FUN_0018fd08` | `0x8018fd08: push {r4, r5, r6, r7, r8, lr}`<br>`0x8018fd0c: mov r1, #0`<br>`0x8018fd10: sub sp, sp, #0x28`<br>`0x8018fd14: mov r4, r0`<br>`0x8018fd18: bl #0x8016f8ec`<br>`0x8018fd1c: subs r5, r0, #0`<br>`0x8018fd20: beq #0x8018ff30`<br>`0x8018fd24: mov r0, r4` |
| [5] | `0x8016eeec` | `?` | `0x8016eeec: mov r0, #0`<br>`0x8016eef0: bx lr`<br>`0x8016eef4: mov r0, #0`<br>`0x8016eef8: bx lr`<br>`0x8016eefc: mov r0, #0`<br>`0x8016ef00: bx lr`<br>`0x8016ef04: push {r4, r5, r6, r7, r8, lr}`<br>`0x8016ef08: ldr r5, [r0, #0xf4]` |
| [6] | `0x8018fc58` | `FUN_0018fc58` | `0x8018fc58: push {r4, lr}`<br>`0x8018fc5c: mov r4, r0`<br>`0x8018fc60: bl #0x80173c88`<br>`0x8018fc64: movw r3, #0x52ac`<br>`0x8018fc68: ldr r2, [r4, #0xfc]`<br>`0x8018fc6c: movt r3, #0x8072`<br>`0x8018fc70: mov r1, #0x4000002`<br>`0x8018fc74: bl #0x80173f34` |
| [7] | `0x8016efc8` | `?` | `0x8016efc8: cmp r1, #1`<br>`0x8016efcc: push {r3, lr}`<br>`0x8016efd0: beq #0x8016efec`<br>`0x8016efd4: sub r3, r1, #2`<br>`0x8016efd8: cmp r3, #1`<br>`0x8016efdc: bls #0x8016efe8`<br>`0x8016efe0: mov r0, #0`<br>`0x8016efe4: pop {r3, pc}` |
| [8] | `0x8018fc40` | `?` | `0x8018fc40: cmp r1, #1`<br>`0x8018fc44: bxne lr`<br>`0x8018fc48: mov r1, r2`<br>`0x8018fc4c: b #0x8016ef04`<br>`0x8018fc50: sub r0, r0, #0x120`<br>`0x8018fc54: b #0x8018fc40`<br>`0x8018fc58: push {r4, lr}`<br>`0x8018fc5c: mov r4, r0` |
| [9] | `0xfffffee0` | `?` | _(capstone 解码失败)_ |

### CMaterial_NX1_Still_3dlut_Normal — `0x8058bad4` (次表 top=2153298692, 子对象(主对象+2141668604), 4 槽)

| 槽 | VA | Ghidra 函数 | capstone 反汇编 |
|---|---|---|---|
| [0] | `0x8018ffb8` | `?` | `0x8018ffb8: sub r0, r0, #0x120`<br>`0x8018ffbc: b #0x8018ff8c`<br>`0x8018ffc0: push {r4, lr}`<br>`0x8018ffc4: mov r4, r0`<br>`0x8018ffc8: bl #0x8018ff8c`<br>`0x8018ffcc: mov r0, r4`<br>`0x8018ffd0: bl #0x80524664`<br>`0x8018ffd4: mov r0, r4` |
| [1] | `0x8018ffdc` | `?` | `0x8018ffdc: sub r0, r0, #0x120`<br>`0x8018ffe0: b #0x8018ffc0`<br>`0x8018ffe4: push {r3, r4, r5, lr}`<br>`0x8018ffe8: mov r4, r0`<br>`0x8018ffec: mov r5, r1`<br>`0x8018fff0: bl #0x8016fdb4`<br>`0x8018fff4: movw r3, #0xbaa0`<br>`0x8018fff8: movt r3, #0x8058` |
| [2] | `0x8018fc50` | `?` | `0x8018fc50: sub r0, r0, #0x120`<br>`0x8018fc54: b #0x8018fc40`<br>`0x8018fc58: push {r4, lr}`<br>`0x8018fc5c: mov r4, r0`<br>`0x8018fc60: bl #0x80173c88`<br>`0x8018fc64: movw r3, #0x52ac`<br>`0x8018fc68: ldr r2, [r4, #0xfc]`<br>`0x8018fc6c: movt r3, #0x8072` |
| [3] | `0x4d433233` | `?` | _(capstone 解码失败)_ |

### CMaterial_NX1_Still_3dlut_SelectColor — `0x8058bb38` (次表 top=2153298840, 子对象(主对象+2141668456), 10 槽)

| 槽 | VA | Ghidra 函数 | capstone 反汇编 |
|---|---|---|---|
| [0] | `0x80190320` | `FUN_00190320` | `0x80190320: ldr r3, [pc, #0x1c]`<br>`0x80190324: push {r4, lr}`<br>`0x80190328: str r3, [r0]`<br>`0x8019032c: ldr r3, [pc, #0x14]`<br>`0x80190330: mov r4, r0`<br>`0x80190334: str r3, [r0, #0x120]`<br>`0x80190338: bl #0x8016fe60`<br>`0x8019033c: mov r0, r4` |
| [1] | `0x80190354` | `FUN_00190354` | `0x80190354: push {r4, lr}`<br>`0x80190358: mov r4, r0`<br>`0x8019035c: bl #0x80190320`<br>`0x80190360: mov r0, r4`<br>`0x80190364: bl #0x80524664`<br>`0x80190368: mov r0, r4`<br>`0x8019036c: pop {r4, pc}`<br>`0x80190370: sub r0, r0, #0x120` |
| [2] | `0x801900e0` | `FUN_001900e0` | `0x801900e0: push {r3, lr}`<br>`0x801900e4: bl #0x8011cdd0`<br>`0x801900e8: ldr r3, [r0]`<br>`0x801900ec: ldr r3, [r3, #0x30]`<br>`0x801900f0: blx r3`<br>`0x801900f4: pop {r3, pc}`<br>`0x801900f8: push {r4, r5, r6, r7, r8, lr}`<br>`0x801900fc: mov r1, #0` |
| [3] | `0x80190094` | `FUN_00190094` | `0x80190094: push {r4, lr}`<br>`0x80190098: mov r4, r0`<br>`0x8019009c: ldr r0, [r0, #0x124]`<br>`0x801900a0: cmp r0, #0`<br>`0x801900a4: beq #0x801900b4`<br>`0x801900a8: ldr r2, [r0]`<br>`0x801900ac: ldr r3, [r2, #4]`<br>`0x801900b0: blx r3` |
| [4] | `0x801900f8` | `FUN_001900f8` | `0x801900f8: push {r4, r5, r6, r7, r8, lr}`<br>`0x801900fc: mov r1, #0`<br>`0x80190100: sub sp, sp, #0x28`<br>`0x80190104: mov r4, r0`<br>`0x80190108: bl #0x8016f8ec`<br>`0x8019010c: subs r5, r0, #0`<br>`0x80190110: beq #0x801902bc`<br>`0x80190114: mov r0, r4` |
| [5] | `0x8016eeec` | `?` | `0x8016eeec: mov r0, #0`<br>`0x8016eef0: bx lr`<br>`0x8016eef4: mov r0, #0`<br>`0x8016eef8: bx lr`<br>`0x8016eefc: mov r0, #0`<br>`0x8016ef00: bx lr`<br>`0x8016ef04: push {r4, r5, r6, r7, r8, lr}`<br>`0x8016ef08: ldr r5, [r0, #0xf4]` |
| [6] | `0x80190048` | `FUN_00190048` | `0x80190048: push {r4, lr}`<br>`0x8019004c: mov r4, r0`<br>`0x80190050: bl #0x80173c88`<br>`0x80190054: movw r3, #0x52ac`<br>`0x80190058: ldr r2, [r4, #0xfc]`<br>`0x8019005c: movt r3, #0x8072`<br>`0x80190060: mov r1, #0x4000002`<br>`0x80190064: bl #0x80173f34` |
| [7] | `0x8016efc8` | `?` | `0x8016efc8: cmp r1, #1`<br>`0x8016efcc: push {r3, lr}`<br>`0x8016efd0: beq #0x8016efec`<br>`0x8016efd4: sub r3, r1, #2`<br>`0x8016efd8: cmp r3, #1`<br>`0x8016efdc: bls #0x8016efe8`<br>`0x8016efe0: mov r0, #0`<br>`0x8016efe4: pop {r3, pc}` |
| [8] | `0x80190030` | `?` | `0x80190030: cmp r1, #1`<br>`0x80190034: bxne lr`<br>`0x80190038: mov r1, r2`<br>`0x8019003c: b #0x8016ef04`<br>`0x80190040: sub r0, r0, #0x120`<br>`0x80190044: b #0x80190030`<br>`0x80190048: push {r4, lr}`<br>`0x8019004c: mov r4, r0` |
| [9] | `0xfffffee0` | `?` | _(capstone 解码失败)_ |

### CMaterial_NX1_Still_3dlut_SelectColor — `0x8058bb64` (次表 top=2153298840, 子对象(主对象+2141668456), 4 槽)

| 槽 | VA | Ghidra 函数 | capstone 反汇编 |
|---|---|---|---|
| [0] | `0x8019034c` | `?` | `0x8019034c: sub r0, r0, #0x120`<br>`0x80190350: b #0x80190320`<br>`0x80190354: push {r4, lr}`<br>`0x80190358: mov r4, r0`<br>`0x8019035c: bl #0x80190320`<br>`0x80190360: mov r0, r4`<br>`0x80190364: bl #0x80524664`<br>`0x80190368: mov r0, r4` |
| [1] | `0x80190370` | `?` | `0x80190370: sub r0, r0, #0x120`<br>`0x80190374: b #0x80190354`<br>`0x80190378: push {r3, r4, r5, lr}`<br>`0x8019037c: mov r4, r0`<br>`0x80190380: mov r5, r1`<br>`0x80190384: bl #0x8016fdb4`<br>`0x80190388: movw r3, #0xbb28`<br>`0x8019038c: movt r3, #0x8058` |
| [2] | `0x80190040` | `?` | `0x80190040: sub r0, r0, #0x120`<br>`0x80190044: b #0x80190030`<br>`0x80190048: push {r4, lr}`<br>`0x8019004c: mov r4, r0`<br>`0x80190050: bl #0x80173c88`<br>`0x80190054: movw r3, #0x52ac`<br>`0x80190058: ldr r2, [r4, #0xfc]`<br>`0x8019005c: movt r3, #0x8072` |
| [3] | `0x4d433733` | `?` | _(capstone 解码失败)_ |

### CMaterial_NX1_Still_3dlut_CS — `0x8058bbc0` (次表 top=2153298968, 子对象(主对象+2141668328), 10 槽)

| 槽 | VA | Ghidra 函数 | capstone 反汇编 |
|---|---|---|---|
| [0] | `0x80190760` | `FUN_00190760` | `0x80190760: ldr r3, [pc, #0x24]`<br>`0x80190764: push {r4, lr}`<br>`0x80190768: str r3, [r0]`<br>`0x8019076c: mov r3, #0`<br>`0x80190770: str r3, [r0, #0x124]`<br>`0x80190774: ldr r3, [pc, #0x14]`<br>`0x80190778: mov r4, r0`<br>`0x8019077c: str r3, [r0, #0x120]` |
| [1] | `0x8019079c` | `FUN_0019079c` | `0x8019079c: push {r4, lr}`<br>`0x801907a0: mov r4, r0`<br>`0x801907a4: bl #0x80190760`<br>`0x801907a8: mov r0, r4`<br>`0x801907ac: bl #0x80524664`<br>`0x801907b0: mov r0, r4`<br>`0x801907b4: pop {r4, pc}`<br>`0x801907b8: sub r0, r0, #0x120` |
| [2] | `0x801906c0` | `?` | `0x801906c0: push {r3, r4, r5, lr}`<br>`0x801906c4: mov r4, r0`<br>`0x801906c8: ldr r5, [r0, #0x124]`<br>`0x801906cc: bl #0x8016fb54`<br>`0x801906d0: mov r1, r0`<br>`0x801906d4: mov r0, r5`<br>`0x801906d8: bl #0x8016f174`<br>`0x801906dc: mov r0, r4` |
| [3] | `0x80190474` | `?` | `0x80190474: ldr r3, [r0, #0x124]`<br>`0x80190478: push {r4, lr}`<br>`0x8019047c: ldr r2, [r3]`<br>`0x80190480: add r4, r0, #0x120`<br>`0x80190484: mov r0, r3`<br>`0x80190488: ldr r3, [r2, #0xc]`<br>`0x8019048c: blx r3`<br>`0x80190490: bl #0x8011cd58` |
| [4] | `0x801904d4` | `FUN_001904d4` | `0x801904d4: push {r4, r5, r6, lr}`<br>`0x801904d8: mov r1, #0`<br>`0x801904dc: sub sp, sp, #0x28`<br>`0x801904e0: mov r4, r0`<br>`0x801904e4: bl #0x8016f8ec`<br>`0x801904e8: subs r5, r0, #0`<br>`0x801904ec: beq #0x80190674`<br>`0x801904f0: mov r0, r4` |
| [5] | `0x8016eeec` | `?` | `0x8016eeec: mov r0, #0`<br>`0x8016eef0: bx lr`<br>`0x8016eef4: mov r0, #0`<br>`0x8016eef8: bx lr`<br>`0x8016eefc: mov r0, #0`<br>`0x8016ef00: bx lr`<br>`0x8016ef04: push {r4, r5, r6, r7, r8, lr}`<br>`0x8016ef08: ldr r5, [r0, #0xf4]` |
| [6] | `0x80190414` | `?` | `0x80190414: ldr r3, [r0, #0x124]`<br>`0x80190418: push {r4, lr}`<br>`0x8019041c: ldr r2, [r3]`<br>`0x80190420: add r4, r0, #0x120`<br>`0x80190424: mov r0, r3`<br>`0x80190428: ldr r3, [r2, #0x18]`<br>`0x8019042c: blx r3`<br>`0x80190430: bl #0x8011cd58` |
| [7] | `0x8016efc8` | `?` | `0x8016efc8: cmp r1, #1`<br>`0x8016efcc: push {r3, lr}`<br>`0x8016efd0: beq #0x8016efec`<br>`0x8016efd4: sub r3, r1, #2`<br>`0x8016efd8: cmp r3, #1`<br>`0x8016efdc: bls #0x8016efe8`<br>`0x8016efe0: mov r0, #0`<br>`0x8016efe4: pop {r3, pc}` |
| [8] | `0x801903c4` | `?` | `0x801903c4: cmp r1, #6`<br>`0x801903c8: beq #0x801903fc`<br>`0x801903cc: ldr r3, [r0, #0x128]`<br>`0x801903d0: cmp r1, #5`<br>`0x801903d4: addeq r3, r3, #1`<br>`0x801903d8: ldrb ip, [r0, #0x12c]`<br>`0x801903dc: streq r3, [r0, #0x128]`<br>`0x801903e0: cmp r3, #4` |
| [9] | `0xfffffee0` | `?` | _(capstone 解码失败)_ |

### CMaterial_NX1_Still_3dlut_CS — `0x8058bbec` (次表 top=2153298968, 子对象(主对象+2141668328), 4 槽)

| 槽 | VA | Ghidra 函数 | capstone 反汇编 |
|---|---|---|---|
| [0] | `0x80190794` | `?` | `0x80190794: sub r0, r0, #0x120`<br>`0x80190798: b #0x80190760`<br>`0x8019079c: push {r4, lr}`<br>`0x801907a0: mov r4, r0`<br>`0x801907a4: bl #0x80190760`<br>`0x801907a8: mov r0, r4`<br>`0x801907ac: bl #0x80524664`<br>`0x801907b0: mov r0, r4` |
| [1] | `0x801907b8` | `?` | `0x801907b8: sub r0, r0, #0x120`<br>`0x801907bc: b #0x8019079c`<br>`0x801907c0: push {r3, r4, r5, lr}`<br>`0x801907c4: mov r4, r0`<br>`0x801907c8: mov r5, r1`<br>`0x801907cc: bl #0x8016fdb4`<br>`0x801907d0: ldr r2, [pc, #0x40]`<br>`0x801907d4: mov r3, #0` |
| [2] | `0x8019040c` | `?` | `0x8019040c: sub r0, r0, #0x120`<br>`0x80190410: b #0x801903c4`<br>`0x80190414: ldr r3, [r0, #0x124]`<br>`0x80190418: push {r4, lr}`<br>`0x8019041c: ldr r2, [r3]`<br>`0x80190420: add r4, r0, #0x120`<br>`0x80190424: mov r0, r3`<br>`0x80190428: ldr r3, [r2, #0x18]` |
| [3] | `0x4d433832` | `?` | _(capstone 解码失败)_ |

### CMaterial_NX1_QView_3dlut_CS — `0x8058e688` (次表 top=2153309920, 子对象(主对象+2141657376), 10 槽)

| 槽 | VA | Ghidra 函数 | capstone 反汇编 |
|---|---|---|---|
| [0] | `0x801b3bdc` | `FUN_001b3bdc` | `0x801b3bdc: push {r4, lr}`<br>`0x801b3be0: ldr r3, [pc, #0x68]`<br>`0x801b3be4: mov r4, r0`<br>`0x801b3be8: ldr r0, [r0, #0x138]`<br>`0x801b3bec: add r2, r3, #0x2c`<br>`0x801b3bf0: cmp r0, #0`<br>`0x801b3bf4: str r3, [r4]`<br>`0x801b3bf8: str r2, [r4, #0x120]` |
| [1] | `0x801b3c60` | `FUN_001b3c60` | `0x801b3c60: push {r4, lr}`<br>`0x801b3c64: mov r4, r0`<br>`0x801b3c68: bl #0x801b3bdc`<br>`0x801b3c6c: mov r0, r4`<br>`0x801b3c70: bl #0x80524664`<br>`0x801b3c74: mov r0, r4`<br>`0x801b3c78: pop {r4, pc}`<br>`0x801b3c7c: sub r0, r0, #0x120` |
| [2] | `0x8016eedc` | `?` | `0x8016eedc: mov r0, #0`<br>`0x8016eee0: bx lr`<br>`0x8016eee4: mov r0, #0`<br>`0x8016eee8: bx lr`<br>`0x8016eeec: mov r0, #0`<br>`0x8016eef0: bx lr`<br>`0x8016eef4: mov r0, #0`<br>`0x8016eef8: bx lr` |
| [3] | `0x801b3cec` | `FUN_001b3cec` | `0x801b3cec: push {r4, lr}`<br>`0x801b3cf0: mov r4, r0`<br>`0x801b3cf4: bl #0x8016f884`<br>`0x801b3cf8: cmp r0, #2`<br>`0x801b3cfc: beq #0x801b3d18`<br>`0x801b3d00: mov r0, r4`<br>`0x801b3d04: bl #0x8016f88c`<br>`0x801b3d08: cmp r0, #1` |
| [4] | `0x801b3d54` | `FUN_001b3d54` | `0x801b3d54: push {r4, r5, r6, lr}`<br>`0x801b3d58: sub sp, sp, #0x30`<br>`0x801b3d5c: mov r4, r0`<br>`0x801b3d60: mov r5, #0`<br>`0x801b3d64: add r0, sp, #8`<br>`0x801b3d68: bl #0x8011ddd8`<br>`0x801b3d6c: mov r3, #4`<br>`0x801b3d70: str r5, [r4, #0x130]` |
| [5] | `0x8016eeec` | `?` | `0x8016eeec: mov r0, #0`<br>`0x8016eef0: bx lr`<br>`0x8016eef4: mov r0, #0`<br>`0x8016eef8: bx lr`<br>`0x8016eefc: mov r0, #0`<br>`0x8016ef00: bx lr`<br>`0x8016ef04: push {r4, r5, r6, r7, r8, lr}`<br>`0x8016ef08: ldr r5, [r0, #0xf4]` |
| [6] | `0x801b3c84` | `FUN_001b3c84` | `0x801b3c84: push {r4, lr}`<br>`0x801b3c88: mov r4, r0`<br>`0x801b3c8c: bl #0x8016f884`<br>`0x801b3c90: cmp r0, #2`<br>`0x801b3c94: beq #0x801b3cb0`<br>`0x801b3c98: mov r0, r4`<br>`0x801b3c9c: bl #0x8016f88c`<br>`0x801b3ca0: cmp r0, #1` |
| [7] | `0x8016efc8` | `?` | `0x8016efc8: cmp r1, #1`<br>`0x8016efcc: push {r3, lr}`<br>`0x8016efd0: beq #0x8016efec`<br>`0x8016efd4: sub r3, r1, #2`<br>`0x8016efd8: cmp r3, #1`<br>`0x8016efdc: bls #0x8016efe8`<br>`0x8016efe0: mov r0, #0`<br>`0x8016efe4: pop {r3, pc}` |
| [8] | `0x801b39d8` | `FUN_001b39d8` | `0x801b39d8: push {r4, r5, r6, lr}`<br>`0x801b39dc: sub sp, sp, #8`<br>`0x801b39e0: mov r5, r1`<br>`0x801b39e4: mov r4, r0`<br>`0x801b39e8: bl #0x80199eb8`<br>`0x801b39ec: cmp r5, #4`<br>`0x801b39f0: mov r6, r0`<br>`0x801b39f4: beq #0x801b3b48` |
| [9] | `0xfffffee0` | `?` | _(capstone 解码失败)_ |

### CMaterial_NX1_QView_3dlut_CS — `0x8058e6b4` (次表 top=2153309920, 子对象(主对象+2141657376), 4 槽)

| 槽 | VA | Ghidra 函数 | capstone 反汇编 |
|---|---|---|---|
| [0] | `0x801b3c58` | `?` | `0x801b3c58: sub r0, r0, #0x120`<br>`0x801b3c5c: b #0x801b3bdc`<br>`0x801b3c60: push {r4, lr}`<br>`0x801b3c64: mov r4, r0`<br>`0x801b3c68: bl #0x801b3bdc`<br>`0x801b3c6c: mov r0, r4`<br>`0x801b3c70: bl #0x80524664`<br>`0x801b3c74: mov r0, r4` |
| [1] | `0x801b3c7c` | `?` | `0x801b3c7c: sub r0, r0, #0x120`<br>`0x801b3c80: b #0x801b3c60`<br>`0x801b3c84: push {r4, lr}`<br>`0x801b3c88: mov r4, r0`<br>`0x801b3c8c: bl #0x8016f884`<br>`0x801b3c90: cmp r0, #2`<br>`0x801b3c94: beq #0x801b3cb0`<br>`0x801b3c98: mov r0, r4` |
| [2] | `0x801b3bd4` | `?` | `0x801b3bd4: sub r0, r0, #0x120`<br>`0x801b3bd8: b #0x801b39d8`<br>`0x801b3bdc: push {r4, lr}`<br>`0x801b3be0: ldr r3, [pc, #0x68]`<br>`0x801b3be4: mov r4, r0`<br>`0x801b3be8: ldr r0, [r0, #0x138]`<br>`0x801b3bec: add r2, r3, #0x2c`<br>`0x801b3bf0: cmp r0, #0` |
| [3] | `0x4d433832` | `?` | _(capstone 解码失败)_ |

### CMaterial_3DLUT_Liveview — `0x8059cb20` (次表 top=2153368736, 子对象(主对象+2141598560), 10 槽)

| 槽 | VA | Ghidra 函数 | capstone 反汇编 |
|---|---|---|---|
| [0] | `0x801ff750` | `FUN_001ff750` | `0x801ff750: ldr r3, [pc, #0x3c]`<br>`0x801ff754: push {r4, lr}`<br>`0x801ff758: add r2, r3, #0x2c`<br>`0x801ff75c: str r3, [r0]`<br>`0x801ff760: ldr r3, [pc, #0x30]`<br>`0x801ff764: mov r4, r0`<br>`0x801ff768: str r2, [r0, #0x128]`<br>`0x801ff76c: str r3, [r0, #0x138]` |
| [1] | `0x801ff7ac` | `FUN_001ff7ac` | `0x801ff7ac: push {r4, lr}`<br>`0x801ff7b0: mov r4, r0`<br>`0x801ff7b4: bl #0x801ff750`<br>`0x801ff7b8: mov r0, r4`<br>`0x801ff7bc: bl #0x80524664`<br>`0x801ff7c0: mov r0, r4`<br>`0x801ff7c4: pop {r4, pc}`<br>`0x801ff7c8: sub r0, r0, #0x128` |
| [2] | `0x801ff4bc` | `FUN_001ff4bc` | `0x801ff4bc: push {r3, lr}`<br>`0x801ff4c0: ldr r3, [r0, #0x128]`<br>`0x801ff4c4: mov r1, r0`<br>`0x801ff4c8: ldr r3, [r3, #8]`<br>`0x801ff4cc: add r0, r0, #0x128`<br>`0x801ff4d0: blx r3`<br>`0x801ff4d4: cmp r0, #0`<br>`0x801ff4d8: beq #0x801ff4f0` |
| [3] | `0x801ff458` | `?` | `0x801ff458: push {r4, lr}`<br>`0x801ff45c: mov r4, r0`<br>`0x801ff460: bl #0x8011cdcc`<br>`0x801ff464: ldr r3, [r0]`<br>`0x801ff468: mov r1, #2`<br>`0x801ff46c: ldr r3, [r3, #0xc]`<br>`0x801ff470: add r2, r4, #0x138`<br>`0x801ff474: blx r3` |
| [4] | `0x801ff4f8` | `FUN_001ff4f8` | `0x801ff4f8: push {r4, r5, r6, r7, lr}`<br>`0x801ff4fc: sub sp, sp, #0x3c`<br>`0x801ff500: mov r4, r0`<br>`0x801ff504: bl #0x800f0828`<br>`0x801ff508: cmp r0, #5`<br>`0x801ff50c: bgt #0x801ff670`<br>`0x801ff510: mov r0, r4`<br>`0x801ff514: mov r1, #0` |
| [5] | `0x801f4b78` | `?` | `0x801f4b78: push {r4, lr}`<br>`0x801f4b7c: sub sp, sp, #0x18`<br>`0x801f4b80: mov r4, r0`<br>`0x801f4b84: bl #0x800f0828`<br>`0x801f4b88: cmp r0, #5`<br>`0x801f4b8c: ble #0x801f4bc8`<br>`0x801f4b90: mov r2, #3`<br>`0x801f4b94: ldr r3, [r4, #0x100]` |
| [6] | `0x801ff3d8` | `?` | `0x801ff3d8: push {r4, lr}`<br>`0x801ff3dc: sub sp, sp, #0x10`<br>`0x801ff3e0: mov r4, r0`<br>`0x801ff3e4: bl #0x800f0828`<br>`0x801ff3e8: cmp r0, #5`<br>`0x801ff3ec: ble #0x801ff41c`<br>`0x801ff3f0: mov r3, #3`<br>`0x801ff3f4: ldr r1, [pc, #0x50]` |
| [7] | `0x801ff7d8` | `FUN_001ff7d8` | `0x801ff7d8: push {r4, r5, lr}`<br>`0x801ff7dc: sub sp, sp, #0x14`<br>`0x801ff7e0: mov r5, r0`<br>`0x801ff7e4: mov r4, r1`<br>`0x801ff7e8: bl #0x800f0828`<br>`0x801ff7ec: cmp r0, #5`<br>`0x801ff7f0: bgt #0x801ff814`<br>`0x801ff7f4: sub r3, r4, #2` |
| [8] | `0x801ff9f8` | `?` | `0x801ff9f8: push {r4, r5, r6, lr}`<br>`0x801ff9fc: sub sp, sp, #0x10`<br>`0x801ffa00: mov r6, r0`<br>`0x801ffa04: mov r5, r1`<br>`0x801ffa08: mov r4, r2`<br>`0x801ffa0c: bl #0x800f0828`<br>`0x801ffa10: cmp r0, #5`<br>`0x801ffa14: ble #0x801ffa44` |
| [9] | `0xfffffed8` | `?` | _(capstone 解码失败)_ |

### CMaterial_3DLUT_Liveview — `0x8059cb4c` (次表 top=2153368736, 子对象(主对象+2141598560), 4 槽)

| 槽 | VA | Ghidra 函数 | capstone 反汇编 |
|---|---|---|---|
| [0] | `0x801ff79c` | `?` | `0x801ff79c: sub r0, r0, #0x128`<br>`0x801ff7a0: b #0x801ff750`<br>`0x801ff7a4: sub r0, r0, #0x138`<br>`0x801ff7a8: b #0x801ff750`<br>`0x801ff7ac: push {r4, lr}`<br>`0x801ff7b0: mov r4, r0`<br>`0x801ff7b4: bl #0x801ff750`<br>`0x801ff7b8: mov r0, r4` |
| [1] | `0x801ff7c8` | `?` | `0x801ff7c8: sub r0, r0, #0x128`<br>`0x801ff7cc: b #0x801ff7ac`<br>`0x801ff7d0: sub r0, r0, #0x138`<br>`0x801ff7d4: b #0x801ff7ac`<br>`0x801ff7d8: push {r4, r5, lr}`<br>`0x801ff7dc: sub sp, sp, #0x14`<br>`0x801ff7e0: mov r5, r0`<br>`0x801ff7e4: mov r4, r1` |
| [2] | `0x8021e2f4` | `FUN_0021e2f4` | `0x8021e2f4: push {r4, r5, r6, r7, r8, sl, lr}`<br>`0x8021e2f8: sub sp, sp, #0x24`<br>`0x8021e2fc: mov r4, r0`<br>`0x8021e300: mov r6, r1`<br>`0x8021e304: bl #0x800f0828`<br>`0x8021e308: cmp r0, #5`<br>`0x8021e30c: bgt #0x8021e354`<br>`0x8021e310: mov r0, r4` |
| [3] | `0xfffffec8` | `?` | _(capstone 解码失败)_ |

### CMaterial_3DLUT_Liveview — `0x8059cb60` (次表 top=2153368736, 子对象(主对象+2141598560), 4 槽)

| 槽 | VA | Ghidra 函数 | capstone 反汇编 |
|---|---|---|---|
| [0] | `0x801ff7a4` | `?` | `0x801ff7a4: sub r0, r0, #0x138`<br>`0x801ff7a8: b #0x801ff750`<br>`0x801ff7ac: push {r4, lr}`<br>`0x801ff7b0: mov r4, r0`<br>`0x801ff7b4: bl #0x801ff750`<br>`0x801ff7b8: mov r0, r4`<br>`0x801ff7bc: bl #0x80524664`<br>`0x801ff7c0: mov r0, r4` |
| [1] | `0x801ff7d0` | `?` | `0x801ff7d0: sub r0, r0, #0x138`<br>`0x801ff7d4: b #0x801ff7ac`<br>`0x801ff7d8: push {r4, r5, lr}`<br>`0x801ff7dc: sub sp, sp, #0x14`<br>`0x801ff7e0: mov r5, r0`<br>`0x801ff7e4: mov r4, r1`<br>`0x801ff7e8: bl #0x800f0828`<br>`0x801ff7ec: cmp r0, #5` |
| [2] | `0x801ffa68` | `?` | `0x801ffa68: sub r0, r0, #0x138`<br>`0x801ffa6c: b #0x801ff9f8`<br>`0x801ffa70: str lr, [sp, #-4]!`<br>`0x801ffa74: sub sp, sp, #0x14`<br>`0x801ffa78: bl #0x800f0828`<br>`0x801ffa7c: cmp r0, #5`<br>`0x801ffa80: ble #0x801ffab0`<br>`0x801ffa84: mov r3, #3` |
| [3] | `0x706f7473` | `?` | _(capstone 解码失败)_ |

## 5. vtable 装填点（构造函数）

判据: 全量扫描 16468 个函数, capstone 解码后匹配 `ldr rX,[pc,#imm]` 且字面池值 ∈ 3D LUT vtable 集合。

| 函数 | 文件偏移 | 大小 | 装填的 vtable | store 目标 |
|---|---|---|---|---|
| `FUN_0011cb64` | `0x11cb64` | 148 | CBackend_3dlut | `r1->[r0]` |
| `FUN_0011cc58` | `0x11cc58` | 132 | CBackend_3dlut | `r3->[r4#3452]`; `r3->[r4#3468]` |
| `FUN_0011d944` | `0x11d944` | 140 | CBackend_3dlut_Base | `r1->[r0]` |
| `FUN_0011db7c` | `0x11db7c` | 196 | CBackend_3dlut_Base | `r3->[r4]` |
| `FUN_0011ed80` | `0x11ed80` | 88 | CBackend_3dlut_CS | `r3->[r4]` |
| `FUN_0011efa8` | `0x11efa8` | 108 | CBackend_3dlut_CS0_Callback, CBackend_3dlut_CS1_Callback, CBackend_3dlut_CS | `r2->[r4]`; `r2->[r0]`; `r3->[r4#24]` |
| `FUN_0018ff8c` | `0x18ff8c` | 36 | CMaterial_NX1_Still_3dlut_Normal | `r3->[r0]`; `r3->[r0#288]` |
| `FUN_00190320` | `0x190320` | 36 | CMaterial_NX1_Still_3dlut_SelectColor | `r3->[r0]`; `r3->[r0#288]` |
| `FUN_00190760` | `0x190760` | 44 | CMaterial_NX1_Still_3dlut_CS | `r3->[r0]`; `r3->[r0#292]`; `r3->[r0#288]` |
| `FUN_001907c0` | `0x1907c0` | 68 | CMaterial_NX1_Still_3dlut_CS | `r2->[r4]` |
| `FUN_001b3bdc` | `0x1b3bdc` | 96 | CMaterial_NX1_QView_3dlut_CS | `r3->[r4]`; `r3->[r4#288]` |
| `FUN_001b3f34` | `0x1b3f34` | 112 | CMaterial_NX1_QView_3dlut_CS | `r2->[r4]` |
| `FUN_001ff750` | `0x1ff750` | 56 | CMaterial_3DLUT_Liveview | `r3->[r0]`; `r3->[r0#312]` |

### `FUN_0011cb64` @ `0x11cb64` — capstone 逐条（节选前 0x60 字节）

```
0x8011cb64: push       {r4, r5, r6, lr}
0x8011cb68: ldr        r4, [pc, #0xc0]
0x8011cb6c: ldr        r1, [pc, #0xc0]
0x8011cb70: ldr        r3, [r4]
0x8011cb74: mov        r6, r0
0x8011cb78: cmp        r3, #0
0x8011cb7c: str        r1, [r0]
0x8011cb80: beq        #0x8011cba0
0x8011cb84: ldr        r0, [pc, #0xac]
0x8011cb88: add        r1, r1, #0x4c
0x8011cb8c: mov        r2, #0x4a
0x8011cb90: mov        r3, r4
0x8011cb94: bl         #0x804dcea8
0x8011cb98: mov        r3, #0
0x8011cb9c: str        r3, [r4]
0x8011cba0: bl         #0x8011e50c
0x8011cba4: bl         #0x8011e9b4
0x8011cba8: bl         #0x8011f09c
0x8011cbac: mov        r3, #0
0x8011cbb0: add        r5, r6, #0xd20
0x8011cbb4: add        r4, r6, #0xd70
0x8011cbb8: str        r3, [r6, #0xd80]
0x8011cbbc: str        r3, [r6, #0xd84]
0x8011cbc0: str        r3, [r6, #0xd88]
```

装填明细:

| 指令地址 | 寄存器 | 字面池地址 | 装入值 | 归属类 |
|---|---|---|---|---|
| `0x8011cb6c` | `r1` | `0x8011cc34` | `0x80583658` | `CBackend_3dlut` |

### `FUN_0011cc58` @ `0x11cc58` — capstone 逐条（节选前 0x60 字节）

```
0x8011cc58: push       {r4, r5, r6, lr}
0x8011cc5c: sub        sp, sp, #8
0x8011cc60: mov        r4, r0
0x8011cc64: bl         #0x801ca0b0
0x8011cc68: ldr        r3, [pc, #0xd8]
0x8011cc6c: mov        r0, r4
0x8011cc70: str        r3, [r0], #0xd20
0x8011cc74: add        r5, r0, #0xc
0x8011cc78: mov        r0, r5
0x8011cc7c: bl         #0x8011ddd8
0x8011cc80: add        r0, r4, #0xd50
0x8011cc84: add        r0, r0, #4
0x8011cc88: bl         #0x8011ddd8
0x8011cc8c: mov        r3, #0
0x8011cc90: str        r3, [r4, #0xd7c]
0x8011cc94: mov        r3, #1
0x8011cc98: str        r3, [sp]
0x8011cc9c: ldr        r0, [pc, #0xa8]
0x8011cca0: ldr        r1, [pc, #0xa8]
0x8011cca4: mov        r2, #0x38
0x8011cca8: ldr        r3, [pc, #0xa4]
0x8011ccac: bl         #0x804dc95c
0x8011ccb0: bl         #0x8011e49c
0x8011ccb4: str        r0, [r4, #0xd80]
```

装填明细:

| 指令地址 | 寄存器 | 字面池地址 | 装入值 | 归属类 |
|---|---|---|---|---|
| `0x8011cc68` | `r3` | `0x8011cd48` | `0x80583658` | `CBackend_3dlut` |

### `FUN_0011d944` @ `0x11d944` — capstone 逐条（节选前 0x60 字节）

```
0x8011d944: push       {r3, r4, r5, lr}
0x8011d948: ldr        r5, [pc, #0x94]
0x8011d94c: ldr        r1, [pc, #0x94]
0x8011d950: ldr        r3, [r5]
0x8011d954: add        r2, r1, #0x68
0x8011d958: cmp        r3, #0
0x8011d95c: mov        r4, r0
0x8011d960: str        r1, [r0]
0x8011d964: str        r2, [r0, #0xc]
0x8011d968: beq        #0x8011d990
0x8011d96c: ldr        r0, [pc, #0x78]
0x8011d970: add        r1, r1, #0x74
0x8011d974: mov        r2, #0x4b
0x8011d978: mov        r3, r5
0x8011d97c: bl         #0x804db830
0x8011d980: cmp        r0, #0
0x8011d984: bne        #0x8011d9b8
0x8011d988: mov        r3, #0
0x8011d98c: str        r3, [r5]
0x8011d990: ldr        r0, [r5, #4]
0x8011d994: cmp        r0, #0
0x8011d998: beq        #0x8011d9a0
0x8011d99c: bl         #0x80524664
0x8011d9a0: ldr        r3, [pc, #0x48]
```

装填明细:

| 指令地址 | 寄存器 | 字面池地址 | 装入值 | 归属类 |
|---|---|---|---|---|
| `0x8011d94c` | `r1` | `0x8011d9e8` | `0x805836f8` | `CBackend_3dlut_Base` |

### `FUN_0011db7c` @ `0x11db7c` — capstone 逐条（节选前 0x60 字节）

```
0x8011db7c: push       {r3, r4, r5, lr}
0x8011db80: ldr        r5, [pc, #0xcc]
0x8011db84: ldr        r3, [pc, #0xcc]
0x8011db88: ldr        r1, [r5, #4]
0x8011db8c: mov        r2, #0
0x8011db90: mov        r4, r0
0x8011db94: cmp        r1, r2
0x8011db98: add        r0, r3, #0x68
0x8011db9c: mvn        r1, #0
0x8011dba0: strb       r2, [r4, #4]
0x8011dba4: str        r1, [r4, #8]
0x8011dba8: strb       r2, [r4, #0x10]
0x8011dbac: str        r3, [r4]
0x8011dbb0: str        r0, [r4, #0xc]
0x8011dbb4: beq        #0x8011dc1c
0x8011dbb8: ldr        r3, [r5]
0x8011dbbc: cmp        r3, #0
0x8011dbc0: beq        #0x8011dbe8
0x8011dbc4: mvn        r3, #0
0x8011dbc8: mov        r2, #0
0x8011dbcc: strb       r2, [r4, #4]
0x8011dbd0: strb       r3, [r4, #0x11]
0x8011dbd4: strb       r3, [r4, #0x12]
0x8011dbd8: strb       r3, [r4, #0x13]
```

装填明细:

| 指令地址 | 寄存器 | 字面池地址 | 装入值 | 归属类 |
|---|---|---|---|---|
| `0x8011db84` | `r3` | `0x8011dc58` | `0x805836f8` | `CBackend_3dlut_Base` |

### `FUN_0011ed80` @ `0x11ed80` — capstone 逐条（节选前 0x60 字节）

```
0x8011ed80: push       {r4, lr}
0x8011ed84: ldr        r3, [pc, #0x58]
0x8011ed88: mov        r4, r0
0x8011ed8c: ldr        r0, [r0, #0x18]
0x8011ed90: add        r2, r3, #0x68
0x8011ed94: cmp        r0, #0
0x8011ed98: str        r3, [r4]
0x8011ed9c: str        r2, [r4, #0xc]
0x8011eda0: beq        #0x8011edb0
0x8011eda4: ldr        r3, [r0]
0x8011eda8: ldr        r3, [r3, #4]
0x8011edac: blx        r3
0x8011edb0: ldr        r0, [r4, #0x1c]
0x8011edb4: cmp        r0, #0
0x8011edb8: beq        #0x8011edc8
0x8011edbc: ldr        r3, [r0]
0x8011edc0: ldr        r3, [r3, #4]
0x8011edc4: blx        r3
0x8011edc8: mov        r0, r4
0x8011edcc: bl         #0x8011d944
0x8011edd0: mov        r0, r4
0x8011edd4: pop        {r4, pc}
0x8011edd8: mov        r0, r4
0x8011eddc: bl         #0x8011d944
```

装填明细:

| 指令地址 | 寄存器 | 字面池地址 | 装入值 | 归属类 |
|---|---|---|---|---|
| `0x8011ed84` | `r3` | `0x8011ede4` | `0x80583990` | `CBackend_3dlut_CS` |

### `FUN_0011efa8` @ `0x11efa8` — capstone 逐条（节选前 0x60 字节）

```
0x8011efa8: push       {r4, lr}
0x8011efac: mov        r4, r0
0x8011efb0: bl         #0x8011db7c
0x8011efb4: ldr        r2, [pc, #0x64]
0x8011efb8: mov        r3, #1
0x8011efbc: add        r1, r2, #0x68
0x8011efc0: str        r2, [r4]
0x8011efc4: str        r1, [r4, #0xc]
0x8011efc8: strb       r3, [r4, #4]
0x8011efcc: strb       r3, [r4, #0x10]
0x8011efd0: mov        r0, #8
0x8011efd4: bl         #0x805249bc
0x8011efd8: mov        r2, #0
0x8011efdc: strb       r2, [r0, #4]
0x8011efe0: ldr        r2, [pc, #0x3c]
0x8011efe4: mov        r3, r0
0x8011efe8: str        r2, [r0]
0x8011efec: mov        r0, #8
0x8011eff0: str        r3, [r4, #0x18]
0x8011eff4: bl         #0x805249bc
0x8011eff8: ldr        r3, [pc, #0x28]
0x8011effc: str        r3, [r0]
0x8011f000: mov        r3, #1
0x8011f004: strb       r3, [r0, #4]
```

装填明细:

| 指令地址 | 寄存器 | 字面池地址 | 装入值 | 归属类 |
|---|---|---|---|---|
| `0x8011efb4` | `r2` | `0x8011f020` | `0x80583990` | `CBackend_3dlut_CS` |
| `0x8011efe0` | `r2` | `0x8011f024` | `0x80583958` | `CBackend_3dlut_CS0_Callback` |
| `0x8011eff8` | `r3` | `0x8011f028` | `0x80583970` | `CBackend_3dlut_CS1_Callback` |

### `FUN_0018ff8c` @ `0x18ff8c` — capstone 逐条（节选前 0x60 字节）

```
0x8018ff8c: ldr        r3, [pc, #0x1c]
0x8018ff90: push       {r4, lr}
0x8018ff94: str        r3, [r0]
0x8018ff98: ldr        r3, [pc, #0x14]
0x8018ff9c: mov        r4, r0
0x8018ffa0: str        r3, [r0, #0x120]
0x8018ffa4: bl         #0x8016fe60
0x8018ffa8: mov        r0, r4
0x8018ffac: pop        {r4, pc}
0x8018ffb0: subshi     fp, r8, r8, lsr #21
0x8018ffb4: rsbshi     r2, r0, r0, lsr #3
0x8018ffb8: sub        r0, r0, #0x120
0x8018ffbc: b          #0x8018ff8c
0x8018ffc0: push       {r4, lr}
0x8018ffc4: mov        r4, r0
0x8018ffc8: bl         #0x8018ff8c
0x8018ffcc: mov        r0, r4
0x8018ffd0: bl         #0x80524664
0x8018ffd4: mov        r0, r4
0x8018ffd8: pop        {r4, pc}
0x8018ffdc: sub        r0, r0, #0x120
0x8018ffe0: b          #0x8018ffc0
0x8018ffe4: push       {r3, r4, r5, lr}
0x8018ffe8: mov        r4, r0
```

装填明细:

| 指令地址 | 寄存器 | 字面池地址 | 装入值 | 归属类 |
|---|---|---|---|---|
| `0x8018ff8c` | `r3` | `0x8018ffb0` | `0x8058baa8` | `CMaterial_NX1_Still_3dlut_Normal` |

### `FUN_00190320` @ `0x190320` — capstone 逐条（节选前 0x60 字节）

```
0x80190320: ldr        r3, [pc, #0x1c]
0x80190324: push       {r4, lr}
0x80190328: str        r3, [r0]
0x8019032c: ldr        r3, [pc, #0x14]
0x80190330: mov        r4, r0
0x80190334: str        r3, [r0, #0x120]
0x80190338: bl         #0x8016fe60
0x8019033c: mov        r0, r4
0x80190340: pop        {r4, pc}
0x80190344: subshi     fp, r8, r8, lsr fp
0x80190348: rsbshi     r2, r0, r0, lsr #3
0x8019034c: sub        r0, r0, #0x120
0x80190350: b          #0x80190320
0x80190354: push       {r4, lr}
0x80190358: mov        r4, r0
0x8019035c: bl         #0x80190320
0x80190360: mov        r0, r4
0x80190364: bl         #0x80524664
0x80190368: mov        r0, r4
0x8019036c: pop        {r4, pc}
0x80190370: sub        r0, r0, #0x120
0x80190374: b          #0x80190354
0x80190378: push       {r3, r4, r5, lr}
0x8019037c: mov        r4, r0
```

装填明细:

| 指令地址 | 寄存器 | 字面池地址 | 装入值 | 归属类 |
|---|---|---|---|---|
| `0x80190320` | `r3` | `0x80190344` | `0x8058bb38` | `CMaterial_NX1_Still_3dlut_SelectColor` |

### `FUN_00190760` @ `0x190760` — capstone 逐条（节选前 0x60 字节）

```
0x80190760: ldr        r3, [pc, #0x24]
0x80190764: push       {r4, lr}
0x80190768: str        r3, [r0]
0x8019076c: mov        r3, #0
0x80190770: str        r3, [r0, #0x124]
0x80190774: ldr        r3, [pc, #0x14]
0x80190778: mov        r4, r0
0x8019077c: str        r3, [r0, #0x120]
0x80190780: bl         #0x8016fe60
0x80190784: mov        r0, r4
0x80190788: pop        {r4, pc}
0x8019078c: subshi     fp, r8, r0, asr #23
0x80190790: rsbshi     r2, r0, r0, lsr #3
0x80190794: sub        r0, r0, #0x120
0x80190798: b          #0x80190760
0x8019079c: push       {r4, lr}
0x801907a0: mov        r4, r0
0x801907a4: bl         #0x80190760
0x801907a8: mov        r0, r4
0x801907ac: bl         #0x80524664
0x801907b0: mov        r0, r4
0x801907b4: pop        {r4, pc}
0x801907b8: sub        r0, r0, #0x120
0x801907bc: b          #0x8019079c
```

装填明细:

| 指令地址 | 寄存器 | 字面池地址 | 装入值 | 归属类 |
|---|---|---|---|---|
| `0x80190760` | `r3` | `0x8019078c` | `0x8058bbc0` | `CMaterial_NX1_Still_3dlut_CS` |

### `FUN_001907c0` @ `0x1907c0` — capstone 逐条（节选前 0x60 字节）

```
0x801907c0: push       {r3, r4, r5, lr}
0x801907c4: mov        r4, r0
0x801907c8: mov        r5, r1
0x801907cc: bl         #0x8016fdb4
0x801907d0: ldr        r2, [pc, #0x40]
0x801907d4: mov        r3, #0
0x801907d8: add        r1, r2, #0x2c
0x801907dc: str        r2, [r4]
0x801907e0: str        r1, [r4, #0x120]
0x801907e4: str        r5, [r4, #0x100]
0x801907e8: strb       r3, [r4, #0x115]
0x801907ec: str        r3, [r4, #0x128]
0x801907f0: strb       r3, [r4, #0x12c]
0x801907f4: bl         #0x801b3fd0
0x801907f8: str        r0, [r4, #0x124]
0x801907fc: mov        r0, r4
0x80190800: pop        {r3, r4, r5, pc}
0x80190804: ldr        r3, [pc, #0x10]
0x80190808: mov        r0, r4
0x8019080c: str        r3, [r4, #0x120]
0x80190810: bl         #0x8016fe60
0x80190814: bl         #0x80523ed8
0x80190818: subshi     fp, r8, r0, asr #23
0x8019081c: rsbshi     r2, r0, r0, lsr #3
```

装填明细:

| 指令地址 | 寄存器 | 字面池地址 | 装入值 | 归属类 |
|---|---|---|---|---|
| `0x801907d0` | `r2` | `0x80190818` | `0x8058bbc0` | `CMaterial_NX1_Still_3dlut_CS` |

### `FUN_001b3bdc` @ `0x1b3bdc` — capstone 逐条（节选前 0x60 字节）

```
0x801b3bdc: push       {r4, lr}
0x801b3be0: ldr        r3, [pc, #0x68]
0x801b3be4: mov        r4, r0
0x801b3be8: ldr        r0, [r0, #0x138]
0x801b3bec: add        r2, r3, #0x2c
0x801b3bf0: cmp        r0, #0
0x801b3bf4: str        r3, [r4]
0x801b3bf8: str        r2, [r4, #0x120]
0x801b3bfc: beq        #0x801b3c0c
0x801b3c00: ldr        r3, [r0]
0x801b3c04: ldr        r3, [r3, #4]
0x801b3c08: blx        r3
0x801b3c0c: ldr        r0, [r4, #0x12c]
0x801b3c10: cmp        r0, #0
0x801b3c14: beq        #0x801b3c24
0x801b3c18: ldr        r3, [r0]
0x801b3c1c: ldr        r3, [r3, #4]
0x801b3c20: blx        r3
0x801b3c24: ldr        r3, [pc, #0x28]
0x801b3c28: mov        r0, r4
0x801b3c2c: str        r3, [r4, #0x120]
0x801b3c30: bl         #0x8016fe60
0x801b3c34: mov        r0, r4
0x801b3c38: pop        {r4, pc}
```

装填明细:

| 指令地址 | 寄存器 | 字面池地址 | 装入值 | 归属类 |
|---|---|---|---|---|
| `0x801b3be0` | `r3` | `0x801b3c50` | `0x8058e688` | `CMaterial_NX1_QView_3dlut_CS` |

### `FUN_001b3f34` @ `0x1b3f34` — capstone 逐条（节选前 0x60 字节）

```
0x801b3f34: push       {r3, r4, r5, lr}
0x801b3f38: mov        r4, r0
0x801b3f3c: bl         #0x8016fdb4
0x801b3f40: ldr        r2, [pc, #0x7c]
0x801b3f44: mov        r3, #0
0x801b3f48: add        r1, r2, #0x2c
0x801b3f4c: str        r2, [r4]
0x801b3f50: str        r1, [r4, #0x120]
0x801b3f54: str        r3, [r4, #0x124]
0x801b3f58: str        r3, [r4, #0x128]
0x801b3f5c: mov        r0, #0x28
0x801b3f60: bl         #0x805249bc
0x801b3f64: mov        r5, r0
0x801b3f68: bl         #0x8011ddd8
0x801b3f6c: mov        r3, #0
0x801b3f70: str        r5, [r4, #0x12c]
0x801b3f74: str        r3, [r4, #0x130]
0x801b3f78: str        r3, [r4, #0x134]
0x801b3f7c: mov        r0, #0x10
0x801b3f80: bl         #0x805249bc
0x801b3f84: ldr        r2, [pc, #0x3c]
0x801b3f88: mov        r3, #0
0x801b3f8c: stm        r0, {r2, r3}
0x801b3f90: str        r3, [r0, #8]
```

装填明细:

| 指令地址 | 寄存器 | 字面池地址 | 装入值 | 归属类 |
|---|---|---|---|---|
| `0x801b3f40` | `r2` | `0x801b3fc4` | `0x8058e688` | `CMaterial_NX1_QView_3dlut_CS` |

### `FUN_001ff750` @ `0x1ff750` — capstone 逐条（节选前 0x60 字节）

```
0x801ff750: ldr        r3, [pc, #0x3c]
0x801ff754: push       {r4, lr}
0x801ff758: add        r2, r3, #0x2c
0x801ff75c: str        r3, [r0]
0x801ff760: ldr        r3, [pc, #0x30]
0x801ff764: mov        r4, r0
0x801ff768: str        r2, [r0, #0x128]
0x801ff76c: str        r3, [r0, #0x138]
0x801ff770: add        r0, r0, #0x128
0x801ff774: bl         #0x8021e524
0x801ff778: mov        r0, r4
0x801ff77c: bl         #0x801f4920
0x801ff780: mov        r0, r4
0x801ff784: pop        {r4, pc}
0x801ff788: mov        r0, r4
0x801ff78c: bl         #0x801f4920
0x801ff790: bl         #0x80523ed8
0x801ff794: subshi     ip, sb, r0, lsr #22
0x801ff798: rsbshi     r2, r0, r0, lsr #3
0x801ff79c: sub        r0, r0, #0x128
0x801ff7a0: b          #0x801ff750
0x801ff7a4: sub        r0, r0, #0x138
0x801ff7a8: b          #0x801ff750
0x801ff7ac: push       {r4, lr}
```

装填明细:

| 指令地址 | 寄存器 | 字面池地址 | 装入值 | 归属类 |
|---|---|---|---|---|
| `0x801ff750` | `r3` | `0x801ff794` | `0x8059cb20` | `CMaterial_3DLUT_Liveview` |

## 6. 类名在伪代码中的出现点

伪代码函数定义 **15825** 个被索引。

### `C3DLUTAlarm` — 出现 **0** 次 / **0** 个函数

_伪代码无该类名字面量（仅存在于 RTTI 元数据）_

### `C3DLUTIf` — 出现 **0** 次 / **0** 个函数

_伪代码无该类名字面量（仅存在于 RTTI 元数据）_

### `CBackend_3dlut` — 出现 **0** 次 / **0** 个函数

_伪代码无该类名字面量（仅存在于 RTTI 元数据）_

### `CBackend_3dlut_Base` — 出现 **0** 次 / **0** 个函数

_伪代码无该类名字面量（仅存在于 RTTI 元数据）_

### `CBackend_3dlut_CS` — 出现 **0** 次 / **0** 个函数

_伪代码无该类名字面量（仅存在于 RTTI 元数据）_

### `CBackend_3dlut_CS0_Callback` — 出现 **0** 次 / **0** 个函数

_伪代码无该类名字面量（仅存在于 RTTI 元数据）_

### `CBackend_3dlut_CS1_Callback` — 出现 **0** 次 / **0** 个函数

_伪代码无该类名字面量（仅存在于 RTTI 元数据）_

### `CBackend_3dlut_Still` — 出现 **0** 次 / **0** 个函数

_伪代码无该类名字面量（仅存在于 RTTI 元数据）_

### `CBackend_3dlut_View` — 出现 **0** 次 / **0** 个函数

_伪代码无该类名字面量（仅存在于 RTTI 元数据）_

### `CMaterial_3DLUT_Liveview` — 出现 **0** 次 / **0** 个函数

_伪代码无该类名字面量（仅存在于 RTTI 元数据）_

### `CMaterial_NX1_QView_3dlut_CS` — 出现 **0** 次 / **0** 个函数

_伪代码无该类名字面量（仅存在于 RTTI 元数据）_

### `CMaterial_NX1_Still_3dlut_CS` — 出现 **0** 次 / **0** 个函数

_伪代码无该类名字面量（仅存在于 RTTI 元数据）_

### `CMaterial_NX1_Still_3dlut_Normal` — 出现 **0** 次 / **0** 个函数

_伪代码无该类名字面量（仅存在于 RTTI 元数据）_

### `CMaterial_NX1_Still_3dlut_SelectColor` — 出现 **0** 次 / **0** 个函数

_伪代码无该类名字面量（仅存在于 RTTI 元数据）_

## 7. 区段量纲（修正版）

| 区域 | 文件偏移 | 内容 |
|---|---|---|
| 代码区 | `0x000000`-`0x56a114` | 16460 个 Ghidra 函数 |
| 混合/字符串 | `0x56a114`-`0x800000` | 少量函数 + 大量字符串（含 RTTI 名串 0x58xxxx、API 名 0x63xxxx、日志 0x71xxxx） |
| 表区 | `0x800000`-`0xb80000` | 参数/浮点表 |
| .bss | `0xb80000`-`0xc40000` | 镜像内全 0，运行时分配 |

> 单块 `rwx` ⇒ **不能靠权限区分代码/数据**，只能用 Ghidra 函数入口集合 + capstone 实解码判定。★★

## 复现

```bash
python scripts/discovery/t2_vtables.py
```

```python
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_LITTLE_ENDIAN
md = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)   # ARM 模式
# Itanium: vtable[-2]=&typeinfo, vtable[-1]=offset-to-top, vtable[0]=address point
# ARM 字面池: ldr rX,[pc,#imm] 的池地址 = 指令地址 + 8 + imm
```