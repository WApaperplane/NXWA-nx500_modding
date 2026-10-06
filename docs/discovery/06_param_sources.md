# 任务6 · LoadLut 四参来源穷尽追查（byte A/B/C/D + 通道 ID）

- 固件：`D:/download/NX-KS2-88/raw8/p7/p7_full.bin`（12.8 MB），ARM **模式**（非 Thumb）
- 全部指令级结论均由 **capstone 5.0.7** 产出，脚本见 `tools/`
- 地址约定：Ghidra 地址 == 文件偏移；VA = 0x80000000 + 文件偏移

---

## 核心发现 3 条

### 发现 1 —— `FUN_00524194` 不是"查表"，是 `dynamic_cast`；`r0` 就是 `st3dlutParam` 本体 ★★

任务书称其为"查表得到的一个结构指针"。capstone 证明它是 **ARM EABI `__dynamic_cast`**：

```
0x8052419c: ldr  r0, [r0]        ; 取 vptr
0x805241a0: ldr  lr, [r0, #-8]   ; offset-to-top
0x805241a4: ldr  r0, [r0, #-4]   ; ★ type_info 指针 (Itanium ABI 标准负偏移)
0x805241fc: ldr  ip, [r6, #0x1c] ; vtable slot7 = __do_upcast
0x80524204: bx   ip
```

两个实参被 capstone + hexdump 证实是 **`std::type_info` 静态对象**（`{vptr, name}`）：

| 实参 | 地址 | name 指针 | mangled name | 语义 |
|---|---|---|---|---|
| `r1` (src_type) | `0x80711f28` | `0x80711f3c` | **`9stEpParam`** | 源类型 |
| `r2` (dst_type) | `0x807148d8` | `0x807148e4` | **`12st3dlutParam`** | 目标类型 |

故 `bl 0x80524194` ≡ `dynamic_cast<st3dlutParam*>(stEpParam*)`。
**返回值 `r0` 就是 `st3dlutParam` 对象的指针**（转换成功时），不是全局表、不是单例、不是配置块。

继承链（type_info `base@+8`，★★ capstone 解出指针后回读）：

```
0x807148d8  12st3dlutParam   base@+8 -> 0x80711f28 (9stEpParam)   __si_class_type_info
0x80711f30  13stResizeParam  base@+8 -> 0x80711f28 (9stEpParam)
```

**因此 task5 文档"这四个字节与 st3dlutParam 无关"的结论是错的 —— 它们就是 `st3dlutParam` 的字段。** ★★

全固件共 **263** 处 `bl 0x80524194`，其中 `9stEpParam -> 12st3dlutParam` **14 处**，全部在 `0x8011xxxx`（3DLUT 模块）。

### 发现 2 —— 四字节的写入点已穷尽：只有构造函数与拷贝赋值，且都先清零 ★★

`st3dlutParam` 布局（由 `FUN_0011ddd8` 构造函数的 `str/strb` 序列直接给出，★★）：

| 偏移 | 类型 | 初值 | 含义 |
|---|---|---|---|
| `+0x00` | 4 (ptr) | `0x80714990`（自身 vtable） | vptr |
| `+0x10` | 4 (ptr) | `0` | ★ **间接指针**，byte A 需二次解引用 |
| `+0x14` | 4 | `0` | |
| `+0x18` | 4 | `-1` | |
| `+0x1c` | 4 | `-1` | |
| `+0x20` | 1 | `0` | **byte B** |
| `+0x21` | 1 | `0` | **byte C** |
| `+0x22` | 1 | `0` | **byte D** |
| `+0x23` | 1 | `0` | |
| `+0x24` | 1 | `0` | `+0x24` 路径开关 |

**全部写入点（★★ 穷尽，见 §2.2）**：

| # | 函数 | VA | 动作 | 条件 |
|---|---|---|---|---|
| W1 | `FUN_0011ddd8` | `0x8011ddd8` | 构造：5 字节全置 0 | 无条件 |
| W2 | `FUN_0011de24` | `0x8011de24` | 拷贝赋值：`+0x10..+0x24` 逐字段复制 | `param_1 != 0` |

两处都是**先清零再按需覆盖**，故字节的运行期值**来自运行期消息/参数下发，而非固件内的静态赋值**。

### 发现 3 —— View / Still / CS 三条LoadLut 路径参数**不同**：闸门值与选表函数都不同 ★★

三个 `_load` 都调用同一个 `FUN_00179314`，但前置条件与选表函数不同：

| | View `_load`<br>`0x8011e20c` | Still `_load`<br>`0x8011e678` | CS `_load`<br>`0x8011ebbc` |
|---|---|---|---|
| 闸门比较 | `cmp r1, #0x10000002` | `cmp r0, #0x20000002` | `cmp r0, #0x20000002` |
| 读 byte B(`+0x20`) | ✅ | ❌ **不读** | ❌ **不读** |
| 读 byte C(`+0x21`) | ✅ | ✅ | ✅ |
| 读 byte D(`+0x22`) | ✅ | ✅ | ✅ |
| 静态选表 | `0x8009a3e8` | `0x8009a3c8` | `0x8009a3c8` |
| 动态选表 | `0x8009a408` | 无 | 无 |
| LoadLut 第3参 | `r5 = (byteA != 1)` | 同左 | 同左 |

**View 多一条"动态选表"分支**，且 View 是唯一读 `byte B` 的调用方。★★

---

## 1. 任务1：`FUN_00524194` 的语义

### 1.1 函数边界与反汇编（全文296 字节，★★ capstone）

`02_functions.txt` 记录 `00524194  296  FUN_00524194`。Ghidra 伪代码：

```c
int FUN_00524194(int *param_1, undefined4 param_2, int *param_3, int param_4) {
  piVar1 = *(int **)(*param_1 + -4);          // ← type_info = *(vptr - 4)
  ...
  (**(code **)(*piVar1 + 0x1c))               // ← __do_upcast (slot 7)
      (piVar1, param_4, 6, param_3,
       (int)param_1 + *(int *)(*param_1 + -8), // ← offset-to-top = *(vptr - 8)
       param_2, param_1, &local_24);
  if (local_24 != 0) { ... cv-qualifier 检查 (&6 / &5) ... 
    if (param_4 >= 0) { if (param_1 == (int *)(local_24 + param_4)) return local_24; } }
  return 0;
}
```

这段代码与 ARM EABI `__dynamic_cast` 的定义逐行对应，其中 `&6` / `&5` 是 cv-qualifier 掩码（const/volatile/restrict）。★

### 1.2 `__do_upcast` 的实证

`r2` 指向的 type_info（`0x807148d8`）的 vtable = `0x80759908`，其 **slot7 = `0x80523d00`**。capstone 反汇编 `0x80523d00`：

```
0x80523d28: bl   #0x80525e6c        ; ← __type_info 比较
0x80523d38: str  r5, [r4]           ; 写回结果指针
0x80523d3c: strb sl, [r4, #4]
0x80523d50: moveq r8, #6            ; ← cv 掩码 6
```

而 `0x80525e6c`（★ capstone）：

```
0x80525e6c: cmp   r1, r0            ; ★ 直接比较 type_info 指针
0x80525e74: beq   #0x80525eb0       ; 相等 -> 匹配
0x80525e78: ldr   r0, [r0, #4]      ; 否则比 name 字符串
0x80525e80: cmp   r3, #0x2a         ; 0x2a = '*'
```

→ 标准 `__class_type_info::operator==`。**判定成立。★★**

### 1.3 "数据区在哪"的回答

任务书问返回值的"数据区VA 范围"。**该问法不适用** —— 返回值是对象指针，不查表。
真实情况：

- 全局实例：**`0x81433cc8`**，长度 **0x300 = 768 字节**（由 `FUN_004db91c(src, "_OnLoad", 0x300, &DAT_81433cc8, 2)` 注册，★★）
- 对象 vtable：**`0x80714990`**（`FUN_0011ddd8` 的 `str r1,[r4]` 写入，`r1` 由字面池 `0x8011de20 -> 0x80714990` 装入，★★）
- 该 vtable 右侧紧邻字符串 `"st3dlutParam"`（`0x80714998`），与 type_info 名字互相印证。★★

`0x81433cc8` 全镜像共 **10** 处 `ldr` 装入（字面池扫描，见 §3），**全部是只读/传参，无一是指向 `+0x20/+0x21/+0x22/+0x40` 的写**。★★

---

## 2. 任务2：四字节写入点穷尽

### 2.1 读取点（capstone，`View::_load`）

```
0x8011e238: ldr  r2, [r0, #0x10]      ; ★ 两级间接: 先取 +0x10 指针
0x8011e240: ldrb r2, [r2, #0x40]      ; ★ byte A
0x8011e254: ldrb r7, [r0, #0x20]      ; ★ byte B
0x8011e258: ldrb r4, [r0, #0x21]      ; ★ byte C
0x8011e25c: ldrb r6, [r0, #0x22]      ; ★ byte D
0x8011e2f0: ldrb r0, [r0, #0x24]      ;   +0x24
```

注意 byte A 是**唯二需要二次解引用**的字段：`+0x10` 是指针，`+0x40` 挂在被指对象上。
故 `st3dlutParam.+0x40` 不存在 —— **任务书表格里的 `[[查表结果]+0x40]` 实际是 `[st3dlutParam.+0x10] → +0x40`，偏移是 `对象+0x50`（若基址为+0x10）**。★★

### 2.2 穷尽方法与结果

三重交叉验证：

1. **全镜像 ARM 编码扫描**（`tools/t6e_strb.py`，54111 条 `str/strb`）→ 偏移命中 `0x20/0x21/0x22/0x40` 者 1303 条，其中 3DLUT 模块内仅两处**连续三字节**写入
2. **字面池引用扫描**（`tools/litref.py`）→ `0x81433cc8` 共 10 处，无写
3. **vtable/RTTI 反查**（`tools/vtf.py` + hexdump）→ 确认写入者属`st3dlutParam`

结论：**`+0x20/+0x21/+0x22` 的写入者全固件只有 2 个函数**。

#### W1 构造函数`FUN_0011ddd8 @ 0x8011ddd8`（★★）

```
0x8011dde0: bl   #0x801ca19c          ; 基类构造
0x8011dde4: ldr  r1, [pc, #0x34]      ; pool@0x8011de20 -> 0x80714990 (自身 vtable)
0x8011dde8: mov  r3, #0
0x8011ddec: mvn  r2, #0
0x8011ddf0: str  r1, [r4]             ; +0x00 = vptr
0x8011ddf4: str  r3, [r4, #0x10]      ; +0x10 = NULL   ← byte A 的间接指针清零
0x8011ddf8: str  r3, [r4, #0x14]
0x8011ddfc: str  r2, [r4, #0x18]      ; = 0xFFFFFFFF
0x8011de00: str  r2, [r4, #0x1c]
0x8011de04: strb r3, [r4, #0x20]      ; ★ byte B = 0
0x8011de08: strb r3, [r4, #0x21]      ; ★ byte C = 0
0x8011de0c: strb r3, [r4, #0x22]      ; ★ byte D = 0
0x8011de10: strb r3, [r4, #0x23]
0x8011de14: strb r3, [r4, #0x24]
```

**无条件**执行。8 个调用点：`0x8011cc7c`/`0x8011cc88`（`FUN_0011cc58`，在一个对象的 `+0xd20` 处建**两个**实例）、`0x8018fdb8`、`0x801901a8`、`0x80190520`、`0x801b3d68`、`0x801b3f68`、`0x801ff588`。

#### W2 拷贝赋值 `FUN_0011de24 @ 0x8011de24`（★★）

```
0x8011de28: subs r5, r1, #0
0x8011de34: beq  #0x8011de90         ; if (src == NULL) 跳过
0x8011de3c: ldr  sl, [r5, #0x10]      ; 源 +0x10
0x8011de4c: ldrb ip, [r5, #0x20]      ; 源 byte B
0x8011de50: ldrb r0, [r5, #0x21]      ; 源 byte C
0x8011de54: ldrb r1, [r5, #0x22]      ; 源 byte D
0x8011de58: ldrb r2, [r5, #0x23]
0x8011de5c: ldrb r3, [r5, #0x24]
0x8011de60: str  sl, [r4, #0x10]
0x8011de70: strb ip, [r4, #0x20]      ; ★ 写 byte B
0x8011de74: strb r0, [r4, #0x21]      ; ★ 写 byte C
0x8011de78: strb r1, [r4, #0x22]      ; ★ 写 byte D
0x8011de7c: strb r2, [r4, #0x23]
0x8011de80: strb r3, [r4, #0x24]
```

2 个调用点：`0x8011c88c`（`FUN_0011c860` 内，按 `ubfx r3,r2,#0x1d,#1` 索引数组元素）与 `0x801b3eb0`。

### 2.3 `+0x10` 指针（byte A 的来源）

`FUN_0011ddd8`/`FUN_0011de24` 都写`+0x10`。3DLUT 模块内 `str [rX,#0x10]` 共 14 处，其余属于**后端对象**（`FUN_0011e460` / `FUN_0011e90c` 等，基址不同），非 `st3dlutParam`。

byte A 本身的最终取值 (`[+0x10]→+0x40`) 落在被指对象上，**该被指对象的 `+0x40` 写入点证据不足（?待查）**：需要先确定 `+0x10` 指向什么类型。`FUN_0011ddd8` 把它清零、`FUN_0011de24` 从源复制，但**复制源本身的值来自运行期**。静态无法再推进。★

### 2.4 参数块的运行期装载机制

`FUN_0011db7c @ 0x8011db7c` 是 3DLUT 的加载器（★★）：

```
0x8011db80: ldr  r5, [pc, #0xcc]      ; pool@0x8011dc54 -> 0x81433cc8 (st3dlutParam)
0x8011db88: ldr  r1, [r5, #4]         ; [param+4] == NULL ?
0x8011dc28: str  r0, [r5, #4]
0x8011dc2c: strb r3, [r0]             ; 分配 4 字节并清零
0x8011dc30: strb r3, [r0, #1]
0x8011dc34: strb r3, [r0, #2]
0x8011dc38: strb r3, [r0, #3]
...
0x8011dbe8: ldr  r0, [pc, #0x6c]      ; 'product/Backend/EP/3DLUT/CBackend_3dlut_Base.cpp'
0x8011dbec: ldr  r1, [pc, #0x6c]      ; 'CBackend_3dlut_Base'
0x8011dbf0: mov  r2, #0x33
0x8011dbf4: ldr  r3, [pc, #0x58]      ; &st3dlutParam
0x8011dbf8: bl   #0x804db734          ; ★ 注册
```

`FUN_004db91c`（77 处调用）与 `FUN_004db830`（33 处）是**运行期参数块注册机制**：把 768 字节 `.bss` 空间登记到加载流程，由框架在收到配置时填充。**这就是"固件内找不到字段写"的原因** —— 字段值来自配置下发，不在代码里。★★

---

## 3. 任务3：View 与 Still 的 LoadLut 参数对比

### 3.1 vtable 对齐（修正）

任务书称 Still vtable = `0x805838b8`。capstone 交叉核对后：

| 类 | vtable | `_load` 所在槽 |
|---|---|---|
| `CBackend_3dlut_View` | **`0x8058380c`** | slot20 (`+0x50`) |
| `CBackend_3dlut_Still` | **`0x805838b8`** | slot21 (`+0x54`) |

两个 vtable 的 slot2..slot7 完全相同（继承自 `CBackend_3dlut_Base`），slot8 起分叉。★★

### 3.2 `0x11e7ec` 不是 `_run`，是 deleting destructor ★★

任务书称 `_run @0x11e7ec`（11 条）。capstone 全文（实际 8 条有效）：

```
0x8011e7ec: push       {r4, lr}
0x8011e7f0: mov        r4, r0
0x8011e7f4: bl         #0x8011e7b8      ; → 构造函数体
0x8011e7f8: mov        r0, r4
0x8011e7fc: bl         #0x80524664      ; ★ operator delete
0x8011e800: mov        r0, r4
0x8011e804: pop        {r4, pc}
0x8011e808: sub        r0, r0, #0xc    ; 调整 this (基类子对象 -0xc)
0x8011e80c: b          #0x8011e7ec
```

`bl operator delete` + `this -= 0xc` + 尾跳回自身，是标准 **deleting destructor**（伪 + `-0xc` 偏移的双继承调整）。
`0x11e7b8` 同样是构造/析构对（`str r2,[r0]` 写 vtable `0x805838b8`，再 `bl 0x8011d944`）。

**真正承载 LUT 灌入的是 Still 的 `_load @ 0x8011e678`。**

### 3.3 三条路径逐条 capstone 对比

#### View `_load @ 0x8011e20c`

```
0x8011e23c: ldr  r1, [r4, #8]
0x8011e240: ldrb r2, [r2, #0x40]      ; byte A
0x8011e244: subs r5, r2, #1
0x8011e248: movne r5, #1              ; ★ r5 = (byteA != 1)
0x8011e24c: cmp  r1, #0x10000002      ; ★★ 闸门 A
0x8011e250: beq  #0x8011e2e8
0x8011e254: ldrb r7, [r0, #0x20]      ; ★ byte B
0x8011e258: ldrb r4, [r0, #0x21]      ; ★ byte C
0x8011e25c: ldrb r6, [r0, #0x22]      ; ★ byte D
0x8011e260: bl   #0x800f6474
0x8011e264: bl   #0x800f1b58
0x8011e268: cmp  r0, #0
0x8011e26c: bne  #0x8011e2d0          ; ★ 有"动态选表"分支
0x8011e270: bl   #0x80099194
0x8011e274: mov  r2, r4               ; arg2 = byte C
0x8011e278: mov  r1, r6               ; arg1 = byte D
0x8011e27c: bl   #0x8009a3e8          ; ★ 静态选表(仅 byte C/D)
...
0x8011e2d0: bl   #0x80099194
0x8011e2d4: mov  r2, r4               ; arg2 = byte C
0x8011e2d8: mov  r1, r7               ; arg1 = byte B
0x8011e2dc: bl   #0x8009a408          ; ★ 动态选表(用 byte B)
...
0x8011e2b0: mov  r2, r5
0x8011e2b8: bl   #0x80179314          ; LoadLut(addr, 0, r5, 0)
```

#### Still `_load @ 0x8011e678`

```
0x8011e6a4: ldr  r1, [r3, #0x10]
0x8011e6ac: ldrb r2, [r1, #0x40]      ; byte A
0x8011e6b0: subs r5, r2, #1
0x8011e6b4: movne r5, #1              ; ★ r5 = (byteA != 1) —— 与 View 一致
0x8011e6b8: cmp  r0, #0x20000002      ; ★★ 闸门 B (与 View 不同!)
0x8011e6bc: beq  #0x8011e728
0x8011e6c0: ldrb r4, [r3, #0x21]      ; ★ 只读 byte C
0x8011e6c4: ldrb r6, [r3, #0x22]      ; ★ 只读 byte D (无+0x20!)
0x8011e6c8: bl   #0x80099194
0x8011e6cc: mov  r2, r4
0x8011e6d0: mov  r1, r6
0x8011e6d4: bl   #0x8009a3c8          ; ★ 不同选表函数
...
0x8011e728: ldr  r2, [r3, #0x14]      ; ★ Still 额外传 +0x14
0x8011e72c: ldrb r0, [r3, #0x24]
0x8011e730: bl   #0x80176884
0x8011e710: bl   #0x80179314          ; LoadLut(addr, 0, r5, 0)
```

#### CS `_load @ 0x8011ebbc`（第三个变体，任务书未提）

```
0x8011ebe8: ldrb r2, [r3, #0x23]      ; ★ CS 额外先读 +0x23 做前置判断
0x8011ec08: ldr  r1, [r3, #0x10]
0x8011ec0c: ldrb r2, [r1, #0x40]
0x8011ec18: cmp  r0, #0x20000002
0x8011ec20: ldrb r4, [r3, #0x21]
0x8011ec24: ldrb r6, [r3, #0x22]
0x8011ec34: bl   #0x8009a3c8          ; 与 Still 同
0x8011ec70: bl   #0x80179314
```

### 3.4 四个 LoadLut 参数：是否不同？

`FUN_00179314(r0=addr, r1, r2, r3)` 的实参：

| 参数 | View | Still | CS |
|---|---|---|---|
| arg0 (r0) | 选表返回值 | 选表返回值 | 选表返回值 |
| arg1 (r1) | `0` | `0` | `0` |
| arg2 (r2) | `r5 = (byteA != 1)` | `r5 = (byteA != 1)` | `r5 = (byteA != 1)` |
| arg3 (r3) | `0` | `0` | `0` |

**直接传给 LoadLut 的 4 个参数：三条路径形式完全一致**（`arg1`/`arg3` 恒为 0，`arg2` 恒为 `(byteA != 1)` 的0/1）。★★

**但"喂给 LoadLut 的东西"不同**，差异体现在 arg0的来源：

| 差异点 | View | Still/CS |
|---|---|---|
| byte B (`+0x20`) | 参与（动态选表 `0x8009a408` 的 arg1） | **完全不读** |
| 触发闸门 | `0x10000002` | `0x20000002` |
| 静态选表函数 | `0x8009a3e8` | `0x8009a3c8` |
| 是否有动态分支 | 有（`0x800f1b58` 返回值决定） | 无 |
| `+0x24` 路径 | `FUN_00176884(0,0)` | `FUN_00176884(+0x14, ...)` 传 `+0x14` |

选表函数三者最终都 `bl 0x802aebd8` 后尾跳到不同地址（`0x802b03f4` / `0x802b03d4` / `0x802b0414`），说明**是同一族函数的三个不同实例/变体**。★

---

## 4. 任务4：`0x1040000X` 通道 ID 的来源

### 4.1 重要修正：立即数是 `0x0104000X`，不是 `0x1040000X` ★★

任务书写 `0x10400001`。capstone 在 `0x80060310` 实测：

```
0x8006030c: mov  r3, #1
0x80060310: movt r3, #0x104
```

`movt` 把 `0x0104` 放到高 16 位，`mov` 提供低 16 位 → **合成值 = `0x01040001`**。
全固件以 `0x1040000X` 形式出现的证据：**0 处**。★★

### 4.2 `FUN_000602ac` 的分派结构（capstone 全文）

```
0x800602ac: push  {r4,r5,r6,lr}
0x800602b4: mov   r4, r1                ; r4 = 通道 ID (arg1)
0x800602bc: mov   r6, r0
0x800602c0: bl    #0x8005f75c
...
0x800602dc: movw  r2, #0x11e
0x800602f4: ldr   r0, [pc,#..] -> 'product/CaptureInterface/Publisher/CapturePublisher.cpp'
0x800602f8: ldr   r1, [pc,#..] -> 'Publish'
0x800602fc: mov   r2, #0x120
0x80060300: bl    #0x80045fb8
0x80060304: cmp   r0, #0
0x80060308: ble   #0x80060380
0x8006030c: mov   r3, #1
0x80060310: movt  r3, #0x104            ; ★ r3 = 0x01040001
0x80060314: cmp   r4, r3
0x80060318: beq   #0x80060388
0x8006031c: mov   r3, #2
0x80060320: movt  r3, #0x104            ; ★ 0x01040002
0x80060324: cmp   r4, r3
0x80060328: beq   #0x800603b8
0x8006032c: mov   r3, #6
0x80060330: movt  r3, #0x104            ; ★ 0x01040006
0x80060334: cmp   r4, r3
0x80060338: beq   #0x800603e0
0x8006033c: mov   r0, r4
0x80060340: bl    #0x800cbf14
0x80060344: ubfx  r3, r4, #0x10, #8     ; ★ 取bit16-23
0x80060348: cmp   r3, #7
0x8006034c: beq   #0x80060368           ; ==7 -> this+0x24
0x80060350: add   r0, r6, #4            ; 否则 this+4
...
```

**这是 CapturePublisher 的通道分派器**（`FUN_000602ac` 自身即`CapturePublisher.cpp` 的 `Publish`）。三条硬编码分支把 `0x01040001/2/6` 分别导向 `CAP_CTRL` 等处理，其余走 `ubfx` 取 **bit 16-23** 作为子通道号：等于 7 走 `this+0x24` 槽位，否则 `this+4`。★★

### 4.3 `0x0104000X` 家族全量清单

`mov+movt` 配对扫描（`tools/t6d_movt.py`，全镜像 14671 对中高 16 位 == `0x104`者 **120 个**）：

| ID | 处数 | 主要构造点 |
|---|---|---|
| `0x01040001` | 11 | `FUN_000602ac`、`FUN_0005f75c`、`FUN_000ccd08`、`FUN_0005aeac`… |
| `0x01040002` | 14 | `FUN_000602ac`、`FUN_0004b9f4`、`FUN_000ab4e0`… |
| `0x01040003` | 5 | `FUN_0005f75c`、`FUN_000ccd08` |
| `0x01040004` | 3 | `FUN_0005f75c`、`FUN_000ccd08` |
| `0x01040005` | 3 | 同上 |
| `0x01040006` | 7 | `FUN_000602ac`、`FUN_0005f75c`、`FUN_000ccd08` |
| `0x01040007` | 2 | `FUN_000ccd08` |
| `0x01040008` | 5 | `FUN_0005af18`、`FUN_0005f75c`、`FUN_000ccd08` |
| `0x01040009` | 7 | `FUN_000c938`、`FUN_00181f8c`… |
| `0x0104000a` | 7 | `FUN_0004b9f4`、`FUN_000c904`、`FUN_0005f75c` |
| `0x0104000b` | 4 | `FUN_000c660`、`FUN_0005f75c` |
| `0x0104000c` | 4 | `FUN_000c764`、`FUN_0005f75c` |
| `0x0104000d` | 5 | `FUN_0004b9f4`、`FUN_000bd5b8` |
| `0x0104000e` | 2 | `FUN_000bd5b8` |
| `0x0104000f` | 4 | `FUN_0005f75c`、`FUN_000a5cd8` |
| `0x01040010` | 4 | `FUN_000c730` 等 |
| `0x01040011` | 5 | `FUN_000c6fc`、`FUN_0005f75c` |
| `0x01040012` | 4 | `FUN_0005f75c` |
| `0x01040411` | 1 | `FUN_00024ddc`（异常） |
| `0x01048000`~`0x01048007` | 25 | `0x8020xxxx` 一带（另一子系统） |

**ID 是硬编码立即数，没有任何运行时计算/构造** —— 都是 `mov`+`movt` 字面量。★★

**结构解读（★推测）**：低 8 位为子功能号（`0x01`/`0x02`/`0x06`…），bit 16-23 为主通道号（`ubfx r3,r4,#0x10,#8` 取的就是它，`0x0104000X` 家族该字段 = `0x04`）。这解释了 `FUN_000602ac` 中"三个硬编码 + 一个 ubfx 兜底"的写法。⚠️ 高 16 位 = `0x0104` 而非 `0x0004`，故 bit24-31 为 `0x01`；该位域含义**证据不足（?待查）**。

---

## 5. 方法论：本次踩到的三个坑（与项目既有教训一致）

**全程 capstone 优先，但"用 capstone 生成掩码"本身也会错**。三处教训：

1. **LDR 立即数位域写错**。首版`(w & 0x00001000) == 0` 判断失败——`0xe59f305c` 实测是 `ldr r3,[pc,#0x5c]`，`W` 位(bit20)=1。改用 capstone 输出的编码反推后正确。
2. **寄存器编号取反**。`Rt` 是 bit15-12、`Rn` 是 bit19-16，首版写反导致所有结果显示 `r15`。用 capstone 复核 `ldr r3,[pc,#0x5c]` 后修正。
3. **扫描窗口 off-by-one 吃掉目标**。`CODE_HI = 0x600000` 而目标在 `0x60310`，恰好差 `0x310`，自检"看起来对但漏了已知点"。**教训：任何穷尽扫描必须先拿一个已知正例做自检**，否则"0 命中"和"漏扫"无法区分。

另有一处真实工具 bug：`litref.py` 首版因 `02_functions.txt` 列序解析错误（把 `size` 当 `name`）导致 `func_of()` 全部返回 `None`；修正后又发现传入了 VA 而非文件偏移。修正后 10 处引用全部定位到函数：

```
0x8011d150in FUN_0011d14c(size 104)     0x8011e574 in FUN_0011e510(size 320)
0x8011d948 in FUN_0011d944(size 140)     0x8011e6f0 in FUN_0011e678(size 284)
0x8011da8c in ?(Ghidra 未识别为函数)      0x8011ec50 in FUN_0011ebbc(size 408)
0x8011db80 in FUN_0011db7c(size 196)     0x8011ecb4 in FUN_0011ebbc(size 408)
0x8011dbf4 in FUN_0011db7c(size 196)     0x8011e298 in FUN_0011e20c(size 332)
```

（`0x8011da8c` 落在 `FUN_0011da08`(size 28) 之后的函数空洞里，capstone 可正常解码，判定为Ghidra 函数边界切分问题，非固件异常。★）

---

## 6. 可复现代码

```bash
PY="C:/Users/31623/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
cd D:/download/NX-KS2-88/docs/discovery/tools

# 任务1: dynamic_cast 语义
$PY -c "import sys;sys.path.insert(0,'.');from armcap import*;show(0x80524194,0x128)"
$PY -c "import sys;sys.path.insert(0,'.');from armcap import*;show(0x80523d00,0x60)"   # __do_upcast
$PY -c "import sys;sys.path.insert(0,'.');from armcap import*;show(0x80525e6c,0x30)"   # type_info 比较
$PY t6b_dyncast_args.py       # 263 处dynamic_cast 的 (src,dst) 统计

# 任务2: 写入点穷尽
$PY t6e_strb.py                        # 全镜像 str/strb 偏移扫描
$PY litref.py 0x81433cc8               # 全局块字面池引用(10 处, 全只读)
$PY -c "import sys;sys.path.insert(0,'.');from armcap import*;show(0x8011ddd8,0x50)"
$PY -c "import sys;sys.path.insert(0,'.');from armcap import*;show(0x8011de24,0x60)"

# 任务3: 三条 LoadLut 路径
$PY -c "import sys;sys.path.insert(0,'.');from armcap import*;show(0x8011e20c,0x150)"  # View
$PY -c "import sys;sys.path.insert(0,'.');from armcap import*;show(0x8011e678,0x11c)"  # Still
$PY -c "import sys;sys.path.insert(0,'.');from armcap import*;show(0x8011e7ec,0x34)"   # dtor 而非 _run
$PY -c "import sys;sys.path.insert(0,'.');from blscan import bl_sites;print(bl_sites(0x80179314))"

# 任务4: 通道 ID
$PY t6d_movt.py 0x104          # mov+movt 配对, 高16==0x104 的全部 120 处
$PY -c "import sys;sys.path.insert(0,'.');from armcap import*;show(0x800602ac,0x120)"
```

---

## 7. 遗留问题

| 问题 | 状态 |
|---|---|
| byte A 的被指对象（`[+0x10]` 指向的类型）及其 `+0x40` 写入点 | **?待查** —— 需运行期 dump 才能确定 |
| `+0x10` 初值为 NULL，运行期由谁赋成有效指针 | **?待查** —— 静态只见清零与拷贝 |
| `st3dlutParam` `+0x10..+0x1c` 四字的语义 | **?待查** —— 构造函数给`0,0,-1,-1`，像"4 个通道索引/句柄" |
| 通道 ID 高 16 位 `0x0104` 中bit24-31 = `0x01` 的含义 | **?待查** |
| `0x0104000X` 的生产者（谁 `mov` 低位发出这些 ID） | 部分 —— 已列出 120 个比较点，但"构造并发送"的一侧需从 `FUN_0005f75c` 等的调用者继续追 |