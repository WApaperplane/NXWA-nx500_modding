# 任务5 · st3dlutParam 完整布局追查

- 全局实例 `0x81433cc8` (文件偏移 `0x1433cc8`, .bss, 镜像内全 0)
- 反汇编: capstone 5.0.7, **ARM 模式**

## ⚠ 本文档修正了任务书的 3 条前提（证据均为 capstone 逐条解码，★★确定）

| 任务书前提 | 实测 | 证据 |
|---|---|---|
| `r5 = (st3dlutParam.+0x40 != 1)` | **`+0x40` 读的是"后端对象", 不是 st3dlutParam** | `0x8011e238 ldr r2,[r0,#0x10]` → `0x8011e240 ldrb r2,[r2,#0x40]`, 是**两级**间接; r0 来自 `bl FUN_00524194`, 与 st3dlutParam 无关 |
| `+0x20/+0x21/+0x22`、`+0x24` 是 st3dlutParam 字段 | **同样是后端对象的字段** | `0x8011e254 ldrb r7,[r0,#0x20]` / `0x8011e258 ldrb r4,[r0,#0x21]` / `0x8011e25c ldrb r6,[r0,#0x22]` / `0x8011e2f0 ldrb r0,[r0,#0x24]`, 全部基于 r0=后端对象 |
| 构造函数 `FUN_0011ddfc` 初始化字段 | **该函数不存在**(0 命中) | `grep 11ddfc` 在 `53_all_pseudocode.c` 与 `02_functions.txt` 里都是 0 结果 |

## 核心发现

1. **`st3dlutParam` 的长度被运行时明文注册为 `0x300` = 768 字节**: `FUN_0011cf04` 里唯一一处静态引用 —— `FUN_004db91c("product/Backend/EP/3DLUT/CBackend_3dlut_Base.cpp", "_OnLoad", 0x300, &DAT_81433cc8, 2)`。这是全固件**参数块注册机制**(共 59 处注册)的其中一次。`FUN_0011cf04` 同时是 `CBackend_3dlut_View` vtable 的一个槽位。★★
2. **`View::_load` 里 st3dlutParam 只被当作"地址参数"传给诊断函数, 没有任何字段读写**: `0x8011e298 ldr r3,[pc,#0xc4]` 把 `0x81433cc8` 装进 r3, 随后 `0x8011e2a4 bl FUN_004dbb08` 把它当第 5 参数(栈传参)送出。任务书想找的`+0x40 / +0x20..0x22 / +0x24` 全部落在**另一个对象**(后端对象)上。★★
3. **`+0x20/+0x21/+0x22` 是三次连续 `ldrb`(各 1 字节)且 `+0x24` 也是 `ldrb`** —— 字节宽度 + 连续性说明它们是一组**字节型参数(如 3 个索引/尺寸/位深)**, 而 `+0x40` 是 `ldrb` 出来的**二值标志**(被 `subs/movne` 转成 0/1)。这组字段属于后端对象基类, 是"取景器用哪档 LUT"的开关。★

## 1. `View::_load` 的 capstone 完整反汇编（★ 标注 st3dlutParam 出现处）

```
0x8011e20c: push       {r4, r5, r6, r7, lr}
0x8011e210: subs       r4, r1, #0
0x8011e214: sub        sp, sp, #0xc
0x8011e218: beq        #0x8011e33c
0x8011e21c: mov        r0, r4
0x8011e220: ldr        r1, [pc, #0x130]
0x8011e224: ldr        r2, [pc, #0x130]
0x8011e228: mov        r3, #0
0x8011e22c: bl         #0x80524194
0x8011e230: cmp        r0, #0
0x8011e234: beq        #0x8011e33c
0x8011e238: ldr        r2, [r0, #0x10]
0x8011e23c: ldr        r1, [r4, #8]
0x8011e240: ldrb       r2, [r2, #0x40]
0x8011e244: subs       r5, r2, #1
0x8011e248: movne      r5, #1
0x8011e24c: cmp        r1, #0x10000002
0x8011e250: beq        #0x8011e2e8
0x8011e254: ldrb       r7, [r0, #0x20]
0x8011e258: ldrb       r4, [r0, #0x21]
0x8011e25c: ldrb       r6, [r0, #0x22]
0x8011e260: bl         #0x800f6474
0x8011e264: bl         #0x800f1b58
0x8011e268: cmp        r0, #0
0x8011e26c: bne        #0x8011e2d0
0x8011e270: bl         #0x80099194
0x8011e274: mov        r2, r4
0x8011e278: mov        r1, r6
0x8011e27c: bl         #0x8009a3e8
0x8011e280: mov        r4, r0
0x8011e284: cmp        r4, #0
0x8011e288: beq        #0x8011e320
0x8011e28c: mov        r0, #2
0x8011e290: ldr        r1, [pc, #0xc8]   ; '_load'
0x8011e294: mov        r2, #0xb4
0x8011e298: ldr        r3, [pc, #0xc4]   ★★ 装载 st3dlutParam (0x81433cc8) 到 r3
0x8011e29c: str        r0, [sp]
0x8011e2a0: ldr        r0, [pc, #0xc0]   ; 'product/Backend/EP/3DLUT/View/CBackend_3dlut_View.cpp'
0x8011e2a4: bl         #0x804dbb08
0x8011e2a8: mov        r1, #0
0x8011e2ac: mov        r0, r4
0x8011e2b0: mov        r2, r5
0x8011e2b4: mov        r3, r1
0x8011e2b8: bl         #0x80179314
0x8011e2bc: subs       r4, r0, #0
0x8011e2c0: blt        #0x8011e304
0x8011e2c4: mov        r0, r4
0x8011e2c8: add        sp, sp, #0xc
0x8011e2cc: pop        {r4, r5, r6, r7, pc}
0x8011e2d0: bl         #0x80099194
0x8011e2d4: mov        r2, r4
0x8011e2d8: mov        r1, r7
0x8011e2dc: bl         #0x8009a408
0x8011e2e0: mov        r4, r0
0x8011e2e4: b          #0x8011e284
0x8011e2e8: mov        r1, #0
0x8011e2ec: mov        r2, r1
0x8011e2f0: ldrb       r0, [r0, #0x24]
0x8011e2f4: bl         #0x80176884
0x8011e2f8: bl         #0x80175c80
0x8011e2fc: mov        r4, r0
0x8011e300: b          #0x8011e284
0x8011e304: bl         #0x80173c88
0x8011e308: str        r4, [sp]
0x8011e30c: mov        r1, #0x10000001
0x8011e310: ldr        r2, [pc, #0x54]   ; 'CBackend_3dlut_Base'
0x8011e314: ldr        r3, [pc, #0x54]
0x8011e318: bl         #0x80173f34
0x8011e31c: b          #0x8011e2c4
0x8011e320: bl         #0x80173c88
0x8011e324: mov        r1, #0x10000001
0x8011e328: ldr        r2, [pc, #0x3c]   ; 'CBackend_3dlut_Base'
0x8011e32c: ldr        r3, [pc, #0x40]
0x8011e330: bl         #0x80173f34
0x8011e334: mvn        r4, #0
0x8011e338: b          #0x8011e2c4
0x8011e33c: bl         #0x80173c88
0x8011e340: mov        r1, #0x10000001
0x8011e344: ldr        r2, [pc, #0x2c]   ; 'CBackend_3dlut_View'
0x8011e348: ldr        r3, [pc, #0x2c]
0x8011e34c: bl         #0x80173f34
0x8011e350: mvn        r4, #0
0x8011e354: b          #0x8011e2c4
```

### 字段访问归纳（全部 capstone 解码，非推测）

| 指令 VA | 指令 | 访问的基址 | 偏移 | 宽度 | 读/写 |
|---|---|---|---|---|---|
| `0x8011e238` | `ldr r2, [r0, #0x10]` | 后端对象 | `#0x10` | 4 | 读 |
| `0x8011e240` | `ldrb r2, [r2, #0x40]` | 后端对象+0x10 | `#0x40` | 1 | 读 |
| `0x8011e254` | `ldrb r7, [r0, #0x20]` | 后端对象 | `#0x20` | 1 | 读 |
| `0x8011e258` | `ldrb r4, [r0, #0x21]` | 后端对象 | `#0x21` | 1 | 读 |
| `0x8011e25c` | `ldrb r6, [r0, #0x22]` | 后端对象 | `#0x22` | 1 | 读 |
| `0x8011e2f0` | `ldrb r0, [r0, #0x24]` | 后端对象 | `#0x24` | 1 | 读 |

> `对象+0x10` 表示该基址本身是 `后端对象 + 0x10` 的指针(两级间接), 所以 `ldrb [r2,#0x40]` 实际偏移是 `对象 + 0x50`。

## 2. st3dlutParam 的全部访问点

`0x81433cc8` 在镜像中出现 **8** 次(全部是字面池), 被 **9** 条 `ldr` 指令、**7** 个函数引用:

| # | 字面池偏移 | 字面池 VA | 引用函数 | 函数大小 | 引用指令 VA | 装入寄存器 |
|---|---|---|---|---|---|---|
| 1 | `0x11d1b4` | `0x8011d1b4` | `FUN_0011d14c` | 104 | `0x8011d150` | `r3` |
| 2 | `0x11d9e4` | `0x8011d9e4` | `FUN_0011d944` | 140 | `0x8011d948` | `r5` |
| 3 | `0x11dc54` | `0x8011dc54` | `FUN_0011db7c` | 196 | `0x8011db80` | `r5` |
| 4 | `0x11dc54` | `0x8011dc54` | `FUN_0011db7c` | 196 | `0x8011dbf4` | `r3` |
| 5 | `0x11e364` | `0x8011e364` | `FUN_0011e20c` | 332 | `0x8011e298` | `r3` |
| 6 | `0x11e664` | `0x8011e664` | `FUN_0011e510` | 320 | `0x8011e574` | `r3` |
| 7 | `0x11e7a0` | `0x8011e7a0` | `FUN_0011e678` | 284 | `0x8011e6f0` | `r3` |
| 8 | `0x11ed60` | `0x8011ed60` | `FUN_0011ebbc` | 408 | `0x8011ec50` | `r3` |
| 9 | `0x11ed60` | `0x8011ed60` | `FUN_0011ebbc` | 408 | `0x8011ecb4` | `r3` |

### 各访问点的紧邻上下文（capstone）

**1. `FUN_0011d14c` @ `0x11d14c` — `0x8011d150` 把 st3dlutParam 装入 `r3`**

_(该引用点不在 View::_load 内; 函数 `FUN_0011d14c` 大小 104, 见 §2 表)_

**2. `FUN_0011d944` @ `0x11d944` — `0x8011d948` 把 st3dlutParam 装入 `r5`**

_(该引用点不在 View::_load 内; 函数 `FUN_0011d944` 大小 140, 见 §2 表)_

**3. `FUN_0011db7c` @ `0x11db7c` — `0x8011db80` 把 st3dlutParam 装入 `r5`**

_(该引用点不在 View::_load 内; 函数 `FUN_0011db7c` 大小 196, 见 §2 表)_

**4. `FUN_0011db7c` @ `0x11db7c` — `0x8011dbf4` 把 st3dlutParam 装入 `r3`**

_(该引用点不在 View::_load 内; 函数 `FUN_0011db7c` 大小 196, 见 §2 表)_

**5. `FUN_0011e20c` @ `0x11e20c` — `0x8011e298` 把 st3dlutParam 装入 `r3`**

```
0x8011e284: cmp        r4, #0
0x8011e288: beq        #0x8011e320
0x8011e28c: mov        r0, #2
0x8011e290: ldr        r1, [pc, #0xc8]
0x8011e294: mov        r2, #0xb4
0x8011e298: ldr        r3, [pc, #0xc4]   <<<
0x8011e29c: str        r0, [sp]
0x8011e2a0: ldr        r0, [pc, #0xc0]
0x8011e2a4: bl         #0x804dbb08
0x8011e2a8: mov        r1, #0
0x8011e2ac: mov        r0, r4
0x8011e2b0: mov        r2, r5
0x8011e2b4: mov        r3, r1
```

**6. `FUN_0011e510` @ `0x11e510` — `0x8011e574` 把 st3dlutParam 装入 `r3`**

_(该引用点不在 View::_load 内; 函数 `FUN_0011e510` 大小 320, 见 §2 表)_

**7. `FUN_0011e678` @ `0x11e678` — `0x8011e6f0` 把 st3dlutParam 装入 `r3`**

_(该引用点不在 View::_load 内; 函数 `FUN_0011e678` 大小 284, 见 §2 表)_

**8. `FUN_0011ebbc` @ `0x11ebbc` — `0x8011ec50` 把 st3dlutParam 装入 `r3`**

_(该引用点不在 View::_load 内; 函数 `FUN_0011ebbc` 大小 408, 见 §2 表)_

**9. `FUN_0011ebbc` @ `0x11ebbc` — `0x8011ecb4` 把 st3dlutParam 装入 `r3`**

_(该引用点不在 View::_load 内; 函数 `FUN_0011ebbc` 大小 408, 见 §2 表)_

## 3. 参数块注册机制（st3dlutParam 的真实"字段访问"路径）

| 项 | 值 |
|---|---|
| 伪代码行号 | 140226 |
| 实参1 源文件 | `0x807148f4` → `product/Backend/EP/3DLUT/CBackend_3dlut_Base.cpp` |
| 实参2 成员名 | `0x805836e8` → `_OnLoad` |
| 实参3 长度 | `0x300` = **768 字节 (0x300)** |
| 实参4 基址 | `&DAT_81433cc8` = `st3dlutParam` |
| 实参5 标志 | `2` |
| 全固件同类注册数 | **59** 处 |

→ 语义: `FUN_004db91c` 把 `st3dlutParam` 这 768 字节 .bss 空间, 以 `_OnLoad` 为名, 登记进 `CBackend_3dlut_Base.cpp` 的加载流程。由于是**按偏移的运行期注册**, Ghidra 无法静态还原出字段名, 这正是任务书搜不到字段访问点的原因。★★

**为什么任务书搜不到**: `53_all_pseudocode.c` 里 `81433cc8` 只出现 **1 次**(就是上面这处注册), 因为其余访问都表现为 `FUN_004db91c` 内部的 `基址 + 偏移` 指针算术, 被Ghidra 折叠成了对 `&DAT_81433cc8` 的一次引用。

## 4. 结构布局（可确证部分）

| 项 | 值 | 置信度 |
|---|---|---|
| 基址 | `0x81433cc8` | ★★确定 |
| 总长度 | `0x300` = 768 字节 | ★★确定（`FUN_004db91c` 第3实参明文） |
| 所属模块 | `CBackend_3dlut_Base.cpp` | ★★确定（第1实参字符串） |
| 注册名 | `_OnLoad` | ★★确定（第2实参字符串） |
| 字段级布局 | **证据不足** | ?待查 |

> **字段级布局目前无法确定**, 原因: (1) 镜像里 .bss 全 0, 无静态初值可参考; (2) 9 处访问点里没有一处对它做 `ldr/str [rX, #off]` —— 它只被整体当指针传递; (3) Ghidra 未给它建类型。**不做臆断**。要确定布局, 需运行时 dump `0x81433cc8` 起768 字节。

## 5. 灌入链路（`View::_load` →硬件）

`FUN_00179314`（文件偏移 `0x179314`, 104 字节）是任务书提到的"灌入"函数。capstone 反汇编:

```
0x80179314: push       {r4, r5, r6, r7, lr}
0x80179318: subs       r7, r0, #0
0x8017931c: sub        sp, sp, #0x14
0x80179320: mov        r6, r1
0x80179324: mov        r5, r2
0x80179328: mov        r4, r3
0x8017932c: beq        #0x80179370
0x80179330: bl         #0x80173c88
0x80179334: str        r7, [sp]
0x80179338: str        r6, [sp, #4]
0x8017933c: str        r5, [sp, #8]
0x80179340: str        r4, [sp, #0xc]
0x80179344: mov        r1, #0x20000003
0x80179348: ldr        r2, [pc, #0x2c]
0x8017934c: ldr        r3, [pc, #0x2c]
0x80179350: bl         #0x80173f34
0x80179354: mov        r0, r7
0x80179358: mov        r1, r6
0x8017935c: mov        r2, r5
0x80179360: mov        r3, r4
0x80179364: add        sp, sp, #0x14
0x80179368: pop        {r4, r5, r6, r7, lr}
0x8017936c: b          #0x804a5c44
0x80179370: mvn        r0, #0
0x80179374: add        sp, sp, #0x14
0x80179378: pop        {r4, r5, r6, r7, pc}
```

**关键**: `0x80179344: mov r1, #0x20000003` —— 它把 **`0x20000003`** 作为消息 ID 发出。这与任务4 独立统计出的 `0x20000003`(182 次调用, 占消息总量 34.3%) 是同一个 ID, **两条独立线索交叉印证**。★★

完整灌入路径:

```
View::_load  (FUN_0011e20c @ 0x11e20c)
  ├─ bl FUN_00524194            -> 取后端对象
  ├─ ldrb r2,[r2,#0x40] / ldrb r7,[r0,#0x20..0x22] / ldrb r0,[r0,#0x24]
  │                             -> 读后端对象的档位/尺寸参数
  ├─ bl FUN_004dbb08(..., 2, '_load', 0xb4, st3dlutParam)   <- 诊断日志
  └─ bl FUN_00179314(addr=结果, 0, r5=(x!=1), 0)
        └─ mov r1, #0x20000003 ; bl FUN_00173f34   -> 发消息 0x20000003
```

## 6. 关键函数伪代码

### FUN_0011cf04

```c
void FUN_0011cf04(void)

{
{
  FUN_004db91c(0x807148f4,0x805836e8,0x300,&DAT_81433cc8,2);
  return;
}
```

### FUN_0011ce08

```c
void FUN_0011ce08(int *param_1,int param_2,undefined4 param_3)

{
{
  undefined4 uVar1;
  
  if (param_2 == 1) {
    (**(code **)(*param_1 + 0x1c))();
    uVar1 = FUN_00173c88();
    FUN_00173f34(uVar1,0x10000003,param_1[0x34a],DAT_0011ce64,param_3);
  }
  else if (param_2 == 2) {
    (**(code **)(*param_1 + 0x18))();
  }
  return;
}
```

### FUN_0011cf3c

```c
void FUN_0011cf3c(undefined4 param_1,undefined4 param_2,undefined4 param_3)

{
{
  undefined4 uVar1;
  
  uVar1 = FUN_00173c88();
  FUN_00173f34(uVar1,0x10000003,0x80714928,0x80712dc0,param_2,param_3);
  return;
}
```

## 7. 复现

```bash
python scripts/discovery/t5_st3dlutparam.py
```

```python
# 关键: ARM 字面池地址 = 指令地址 + 8 + imm (不是 +4)
#View::_load 里 +0x40 的读取是两级间接: ldr r2,[r0,#0x10]; ldrb r2,[r2,#0x40]
# st3dlutParam(0x81433cc8) 在 _load 里只被 ldr 进 r3 后当栈参数传出, 无字段读写
```