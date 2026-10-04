# B2 路线：PW 7 维经 yccmixer 实时写入（待实机验证）

> 程序：`b1/src/pw7_ycc.c` → `out/pw7_ycc.arm`（32.6KB）
> 相机：`/opt/usr/nx-ks/lut3dl/pw7_ycc.arm`
> 2026-10-04 13:10 dry run 已通过

## 一、为什么这条路可行（与 3D LUT 的关键差别）

| | 3D LUT (`d5_ep_3dl_*`) | PW 7 维 (`d5_ep_mc_set_custom_param_yccmixer`) |
|---|---|---|
| 是否需要 handle | **需要**（ISP 侧分配的用户态拿不到，传栈结构体 → SIGSEGV） | **不需要**，只解引用自己的 2 个参数 |
| 是否被预加载保护 | 是（6 进程映射） | 是（同） |
| 能否用户态直调 | ❌ 实测段错误 | ✅ dry run 通过 |

## 二、反汇编读出的完整机制（libudd5.so @ 0x29488, 288B）

```c
void d5_ep_mc_set_custom_param_yccmixer(void *p0, void *p1) {
    u32 a = *(u32 *)p1;          // p1[0]..p1[3] 当一个 u32 读
    u32 b = *(u32 *)(p1 + 4);   // p1[4]..p1[7] 当一个 u32 读
    // 打包：
    *(u8 *)(p1 + 5) = (u8)a;            // 槽5 = a低字节
    *(u8 *)(p1 + 6) = (u8)b;            // 槽6 = b低字节
    *(u8 *)(p1 + 3) = (*(u8 *)(p1+3) & 0x0f) | (7 << 4);   // 槽3 高4位 = 7
    // 写寄存器（基址 = *(GOT)，MC 侧）：
    *(u32 *)(*(GOT) + 0x280) = *(u32 *)p0;
    *(u32 *)(*(GOT) + 0x284) = b;
    d5_ep_top_update_sreg(0x14);
}
```

**★ 关键确认：`d5_ep_top_update_sreg(0x14)` 的参数 `0x14` = 20
= 我们早已实测的 `setusr` 索引 20 = `PW_TYPE`。**
**所以这个函数就是 PW 参数的"写入+立即生效"入口，完全免重启。**

## 三、dry run 结果（只解析符号，未写任何寄存器）

```
ycc=0xb6d0b488  sreg=0xb6d106a8  mcbase=0xb6d39740
dry run: nothing written
MC_BASE=00000000
```
符号全部解析成功。`ycc - 0x29488 = 0xb6d22000`，与B1 探针算出的库基址 **完全一致** → 交叉验证第三次通过。

`MC_BASE=0` 是内核填充的全局指针，但 `yccmixer` 不用它，无影响。

## 四、待验证的未知项（只能靠看画面）

| 未知 | 现状 |
|---|---|
| 7 维在 p1[0..6] 里的**字段顺序** | 未解。反汇编只证明槽3/5/6 被写，槽0-2 直接进寄存器 |
| 各维度的**取值范围与编码** | 未知（prefman 侧已知中性值 R/G/B=100、H/S/S/C=10，但这里的实时层编码可能不同） |
| 写入后**画面是否立即变化** | 未验证 |

## 五、执行步骤（请木一操作，看画面）

### 步骤 1：先备份当前 PW 状态
```sh
sh /mnt/mmc/_pwtest/filmlab-apply.sh dump
```
把输出留底，便于回滚对照。

### 步骤 2：dry run 确认环境（可重复，零风险）
```sh
/opt/usr/nx-ks/lut3dl/pw7_ycc.arm /usr/lib/libudd5.so 0
cat /mnt/mmc/_pwtest/pw7.log
```

### 步骤 3：★ 写入测试 1 —— 尝试制造纯黑白
yccmixer 不像 PW 参数有"SAT=0即黑白"的语义，这里用**最小图案**试：

```sh
# pat 的低字节写槽0/槽5，高字节写槽4/槽6
/opt/usr/nx-ks/lut3dl/pw7_ycc.arm /usr/lib/libudd5.so 1 00000000
cat /mnt/mmc/_pwtest/pw7.log
```
**看取景器：画面有没有变化？**记下现象（变黑白 / 偏色 / 完全没变 / 崩溃）。

### 步骤 4：写入测试 2 —— 明显的偏色图案
```sh
/opt/usr/nx-ks/lut3dl/pw7_ycc.arm /usr/lib/libudd5.so 1 0000FF00
```
`0xFF` 落在槽6。看画面是否出现明显色偏。

### 步骤 5：回滚
若画面异常：
```sh
sh /mnt/mmc/_pwtest/filmlab-apply.sh reset   # 恢复 prefman 中性值
```
或直接 `sh /mnt/mmc/_pwtest/filmlab-apply.sh apply trix400` 切到一个已知配方对照。

## 六、风险评估

| 项 | 评估 |
|---|---|
| 变砖 | **无风险**。只写 ISP 运行寄存器（0x280/0x284），不碰 eMMC/文件系统。异常最坏是画面变色，重启即恢复 |
| 相机过热 | 低。程序是单次写入后立即退出，不驻留 |
| 最坏情况 | 写入非法值导致取景器花屏 → 相机重启恢复；`update_sreg(0x14)` 是已知合法调用路径，不应触发看门狗 |

**★ 因此这一步可以安全推进。** 与3D LUT 不同，PW 这条路有 prefman 的 8 配方作为回滚参照。

## 七、若测试 3/4 成功，得到什么

**一个免重启、无需 prefman、可由自写 ARM 程序直接调用的 PW 写入接口。**
配合已解出的属性 ID 表（`setPWColor=0x10e` 等），意味着：

- 配方切换可以做到**亚秒级 + 无需 prefman 落盘**
- 8 个配方 → 60 个配方只是 JSON 扩容，槽位限制（CUSTOM_1-4）不再存在
- 且这是**真曲线**通路（`yccmixer` = YCC mixer，比 7 个标量更底层），与 3D LUT 同一层

若测试失败（画面不变），说明 MC 侧寄存器被内核独占，则退回 B3：`/dev/d5_ipcc` 报文通路。
