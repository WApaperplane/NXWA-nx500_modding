# SMA 动态分配实测结论（2026-10-06 19:00）

> 起因：卡死事故后，寻找"不用硬编码物理地址"的替代方案
> 结论前置：★★ **动态分配路线判定为不可用**，但拿到一个有用的副产品。

---

## 0. 结论

| 项 | 结论 |
|---|---|
| ★★★ `SMA_ALLOC` | ❌ **不可用**，12 种参数组合全部 EFAULT |
| 根因 | `dmesg: d4_cma_alloc failed. Device is null or invalid argument` |
| ⇒ 解读 | ★★★ **不是内存不足，是驱动层不给用户态分配** |
| ★★ `SMA_VIRT_TO_PHYS` | ✅ **可用，但只认自己 mmap 的映射** |
| ⇒ 副产品 | ★★ 现在能**直接核对物理地址**，不必再靠"写完回读"间接判断 |

---

## 1. 官方接口（头文件是权威，不猜）

来源：`.uploads/nx1_open/rootfs_dev/standard-armv7l/usr/include/media/drime5/sma/d5_sma_ioctl.h`

```c
#define SMA_MAGIC 's'

SMA_GET_REGION_SIZE       _IOR('s', 1, unsigned int)
SMA_VIRT_TO_PHYS_IOWR('s', 2, unsigned int)   ★ libudd5 用的就是这个
SMA_SET_CACHE             _IOWR('s', 3, int)
SMA_GET_REGION_START_ADDR _IOR('s', 4, unsigned int)
SMA_ALLOC                 _IOWR('s', 5, struct SMA_Buffer_Info)  ★ 本次目标
SMA_FREE                  _IO('s', 6, unsigned int)   /* 虚拟地址 */
SMA_FREE_PHYS             _IO('s', 7, unsigned int)
SMA_GET_ALLOCATED_SIZE    _IOR('s', 8, unsigned int)
SMA_CACHE_FLUSH           _IOWR('s', 9, struct SMA_Buffer_Info)
SMA_CONTROL_PREBUFFER     _IO('s', 10, unsigned int)

struct SMA_Buffer_Info { unsigned int addr; unsigned int size; };
```

### ★★ 交叉验证（重要）
自己按 `_IOWR('s',2,4)` 算出 **`0xc0047302`**，与 libudd5 反汇编里
`d5_ep_sma_virt_to_phys` 用的号**完全一致**
⇒ ★★ **证明我的 ioctl 编码方式正确**，所有号可信。

---

## 2. 实测结果

### 2.1 查询类接口全部可用
| ioctl | 返回 | 说明 |
|---|---|---|
| `SMA_GET_REGION_START_ADDR` | `0x94000000` | ★ **正是我硬编码的那个地址** |
| `SMA_GET_REGION_SIZE` | `0x09000000` | 144 MB |
| `SMA_GET_ALLOCATED_SIZE` | `0x12000000` | 288 MB（= 两个 CMA 区合计）|

### 2.2 ★★★ `SMA_ALLOC` 全部失败
扫描的参数组合（**每次成功都立即 FREE，零硬件风险**）：
```
size=1B / 1page / 0x1000 / 0x2000 / 0x4000 / 64K / 1MB / 4MB   → 全EFAULT
size=0（自动）                                              → EFAULT
addr 作 hint = region 首 / 中 / 尾                        → 全 EFAULT
```
**内核日志给出原因**：
```
d4_cma_alloc failed. Device is null or invalid argument
```
⇒ ★★★ **不是"内存不足"，是"Device is null"** ⇒ 驱动内部拿不到它要的 device 句柄
⇒ ★ **三星这个 SMA 驱动是给内核内部（p7/driver）用的，不打算开放给用户态**

### 2.3 ★★ 副产品：`VIRT_TO_PHYS` 可用，但有条件
| 内存来源 | 虚拟地址 | `VIRT_TO_PHYS` 返回 |
|---|---|---|
| `malloc` 堆 | `0x00066008` | ★★ `0x00000000`（不支持）|
| `mmap` 匿名 | `0xb6faf000` | ★★ `0x00000000`（不支持）|
| ★★ `mmap /dev/d5_sma` @ `0x99000000` | `0xb6faf000` | ★★★ **`0x99000000` 精确等于预期** |

⇒ ★★ **驱动只认"自己 mmap 出来的映射"**
⇒ ★ 这**正是 libudd5 的做法**（`load_lut` 用的是自己 mmap 的缓冲区）
⇒ ⇒★ **我们可以在写入前核对物理地址，而不是事后靠回读间接判断**

---

## 3. 对 `lutload.arm` 的改进

`import` 现在**写入前先核对物理地址**：

```c
unsigned int real = verify_phys(fds, lp);
printf("  VIRT_TO_PHYS => 0x%08x  (期望 0x%08lx) %s\n", real, phys,
       real == phys ? "★ 匹配" : "★ 不匹配");
if (real != phys) {
    printf("⇒★★ 物理地址对不上，硬件 DMA 会读到错误数据。\n");
    rc = 3; goto out;      /* ★ 直接中止，不写硬件 */
}
```

⇒ ★★ **这是本次唯一实质改进**：把"地址对不对"从"事后观察"变成"事前拦截"。

---

## 4. ★★★ 三条使用纪律（铁律 61 的具体落实）

```
1. import 前必须用 VIRT_TO_PHYS 核对地址，不靠猜
2. ★ 导入完成立即释放映射，不让硬件长期引用这块内存
3. 出现异常先重启，不要在不确定状态下反复试
```

**第 2 条的必要性**：
卡死的直接原因是硬件 DMA 长期引用我写入的内存，
而那块内存同时被 ISP 需要 ⇒ 冲突 ⇒ `alloc_contig_range failed`。
⇒ **"用完即还"把冲突窗口缩到最小。**

---

## 5. ★★ 动态分配路线：判定为不可行

| 方案 | 状态 |
|---|---|
| ★★★ `SMA_ALLOC` 动态分配 | ❌ 驱动不支持用户态 |
| ★ 选一个"实时确认空闲"的固定地址 | ⚠️ 可行但**仍在与 ISP 抢**，需遵守纪律 2 |
| ★★ **让 p7 自己灌表**（半按对焦），我们只改内容源 | ★★★ **最稳方向** |

⇒ ★★★ **第三条路才是正解**：
　p7 在 AF 流程里会 `FUN_0009a3e8 → SetAddress → rw_Start(1)` 走一遍完整流程。
　⇒ 若能让 p7 读到**我们的数据**（而不是它自己的缓冲），就完全不碰 `0x94000000`。
　⇒ 这需要在 `0x81xxxxxx` 那个缓冲里放我们的表 —— 而 Linux 侧够不着它。
　⇒ ⇒★ **这条路最终还是要改 p7**（但只是改一个数据指针，风险极低）。

---

## 6. 新增工具

| 文件 | 用途 | 结论 |
|---|---|---|
| `test_server/sysarch/smaalloc.c` → `smaalloc.arm` | SMA 区域信息 + ALLOC 探测 | 记录事实（ALLOC 失败）|
| `test_server/sysarch/smascan.c` → `smascan.arm` | ALLOC 参数扫描（12 组合）| ★ **证伪动态分配** |
| `test_server/sysarch/v2p.c` → `v2p.arm` | ★★ `VIRT_TO_PHYS` 三路验证 | ★ **决定性** |
| `test_server/sysarch/lutload.c` → `lutload.arm` | ★★ 新增物理地址核对 | ★ **唯一实质改进** |

---

## 7. ★ 安全记录

- 三个新工具**都不写任何硬件寄存器**（只有 `lutload.arm import` 会）
- `smascan` 每次分配成功都立即 FREE
- ★★ **p7 前 12MB md5 = `7c0b5b31b11cbaa63bc1d1ad5c9f4f26`，与备份完全一致**
- 备份 11/11 完好，全程未写任何分区
- 相机当前：出厂指针 + 正常画面
